"""Final-event gates, barrier actions and repeated checkpoint restoration."""
from collections import deque
from copy import deepcopy
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pyxel
from rpg.app import FANFARE_MAX_WAIT_SECONDS
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.dungeon_app import DungeonApp
from rpg.exploration import Exploration
from rpg.final_battle import (AMRITA_ITEM_ID, FinalBattleCheckpoint,
                             load_final_battle_data, make_final_enemy)
from rpg.map_resources import load_maps
from rpg.models import Action


class FinalBattleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        self.s = Session(*load_content(), seed=81)
        self.s.settings['spark_chance'] = 0
        for rates in self.s.settings['growth_rates'].values():
            rates.update(HP=0, STR=0, AGI=0, INT=0)
        for actor in self.s.party:
            actor.hp = actor.max_hp = 180
            actor.strength = actor.intellect = 40
            actor.agility = 50
        self.d = Dungeon(load_maps(), self.s.enemy_data, load_dungeon_settings(), self.s.rng,
                         self.s.treasure, self.s.inventory)
        self.e = Exploration(self.s, self.d)
        self.a = a = DungeonApp.__new__(DungeonApp)
        a.session, a.dungeon, a.exploration = self.s, self.d, self.e
        a.initial_content = deepcopy((self.s.settings, self.s.skills, self.s.party, self.s.enemy_data))
        a.initial_rng_state, a.initial_debug = self.s.rng.getstate(), False
        a.keyboard = SimpleNamespace(update=lambda: None)
        a.state, a.overlay, a.battle = 'camp', None, None
        a.battle_kind, a.battle_is_boss = 'normal', False
        a.battle_position, a.next_guardian_index = None, None
        a.battle_input_blocked = a.opening_input_blocked = False
        a.final_battle_data = load_final_battle_data()
        a.final_checkpoint = None
        a.final_choice = a.final_story_page = a.ending_page = 0
        a.camp_offer_pending = False
        a.return_lines = []
        a.notice, a.notice_timer, a.shake_timer = '', 0, 0
        a.fanfare_started_at = a.fanfare_start_frame = None
        a.fanfare_timed_out = False
        a.camp_cursor = a.facility_index = a.facility_cursor = a.shop_cursor = 0
        a.pub_cursor = a.archive_cursor = a.archive_page = a.floor_cursor = 0
        a.facility_back = 'camp'
        a.debug_return_state, a.debug_return_overlay = None, 'debug_skills'
        a.debug_events = []
        a.actions, a.pending = [], deque()

    def press(self, key=None):
        with patch.object(pyxel, 'btnp', side_effect=lambda code, *args: code == key), \
             patch.object(pyxel, 'btn', return_value=False):
            self.a.update()

    def grant(self):
        self.d.finale.guardians_defeated = True
        self.d.finale.claim_amrita()
        self.d.defeated_bosses.update((4, 9, 14))

    def launch(self):
        self.grant()
        self.a.start_final_story()
        self.a.begin_final_battle()
        self.press()  # Release the story/retry A before any battle commands.
        boss = self.a.battle.enemies[0]
        boss.strength = boss.intellect = 1
        boss.agility = 1
        return self.a.battle

    def round(self, actions):
        battle, lines = self.a.battle, []
        battle.begin_round(actions)
        while battle.queue:
            lines.extend(battle.step())
        return lines

    def actions(self, first):
        return [first] + [Action(i, 'GUARD') for i, actor in enumerate(self.s.party)
                          if i != first.actor and actor.alive]

    def fail(self, outcome='DEFEAT'):
        if outcome == 'DEFEAT':
            for actor in self.s.party:
                actor.hp = 0
        self.a.battle.outcome = outcome
        self.a.battle.queue.clear()
        self.s.settle()
        self.a.state = 'result'
        self.a.finish_results()

    def resources(self):
        return deepcopy({
            'party': [vars(actor) for actor in self.s.party],
            'items': self.s.inventory.counts, 'treasure': vars(self.s.treasure),
            'discovered': self.s.discovered_skills, 'mastered': self.s.mastered_skills,
            'counts': (self.s.completed, self.s.wins, self.s.losses, self.s.draws),
            'flags': self.d.finale.snapshot(), 'quest': (self.e.active, self.e.target,
                      self.e.surveyed, self.e.completed, self.e.springs)})

    def test_external_arrival_prompts_only_after_return_summary(self):
        self.grant()
        self.s.treasure.unbanked = 7
        self.a.enter_camp(returned=True)
        self.assertEqual(self.a.state, 'return_result')
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'amrita_offer')
        self.assertEqual(self.s.treasure.banked, 7)
        self.assertTrue(self.d.finale.has_amrita)

    def test_later_allows_facilities_without_reprompt_but_next_trip_prompts(self):
        self.grant()
        self.a.enter_camp(returned=True)
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'camp')
        for facility in (1, 2, 3):
            self.a.camp_cursor = facility
            self.press(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(self.a.state, 'facility')
            if facility == 2:
                self.a.facility_cursor = 1
            self.press(pyxel.GAMEPAD1_BUTTON_A)
            self.assertIn(self.a.state, ('archive', 'pub', 'shop'))
            self.press(pyxel.GAMEPAD1_BUTTON_B)
            self.press(pyxel.GAMEPAD1_BUTTON_B)
            self.assertEqual(self.a.state, 'camp')
        self.a.enter_dungeon()
        self.a.handle_event('base', '')
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'amrita_offer')
        self.assertTrue(self.d.finale.can_offer_amrita)

    def test_no_key_or_started_event_never_prompts_again(self):
        self.a.enter_camp(returned=True)
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'camp')
        self.grant()
        self.d.finale.start_final_event()
        self.a.enter_camp(returned=True)
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'camp')

    def test_yes_keeps_key_and_story_leads_to_checkpoint_and_battle(self):
        self.grant()
        self.a.show_amrita_offer()
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'final_story')
        self.assertTrue(self.d.finale.has_amrita and self.d.finale.final_event_started)
        for _ in self.a.final_story_pages():
            self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'command')
        self.assertIsInstance(self.a.final_checkpoint, FinalBattleCheckpoint)
        self.assertTrue(self.a.battle.elysion_barrier_active)
        self.assertEqual(self.a.battle.enemies[0].name, 'ロードオブエリシオン')
        self.press(pyxel.GAMEPAD1_BUTTON_A)  # Held/fresh input cannot pass release gate yet.
        self.assertFalse(self.a.actions)

    def test_barrier_blocks_physical_magic_legends_and_drain_with_one_hint(self):
        b = self.launch()
        actor = self.s.party[0]
        hp, hints = b.enemies[0].hp, []
        for sid in ('power_strike', 'fire', 'seven_slash', 'meteor', 'drain'):
            with self.subTest(skill=sid):
                actor.skills, actor.skill_uses = [sid], {sid: 5}
                actor.cooldowns.clear()
                lines = self.round(self.actions(Action(0, 'SKILL', 0, sid)))
                self.assertEqual(b.enemies[0].hp, hp)
                self.assertTrue(any('-0' in line for line in lines))
                hints.extend(line for line in lines if line in b.final_data['barrier_hint'])
        self.assertEqual(hints, b.final_data['barrier_hint'])

    def test_counter_cannot_bypass_barrier(self):
        b = self.launch()
        hp = b.enemies[0].hp
        self.assertEqual(b._damage(b.enemies[0], 999999, magic=False, power_bonus=1.2), 0)
        self.assertEqual(b.enemies[0].hp, hp)

    def test_amrita_uses_one_action_without_charges_or_item_consumption_then_damage_passes(self):
        b = self.launch()
        uses, items = deepcopy([c.skill_uses for c in self.s.party]), dict(self.s.inventory.counts)
        lines = self.round(self.actions(Action(0, 'ITEM', item_id=AMRITA_ITEM_ID)))
        self.assertFalse(b.elysion_barrier_active)
        self.assertTrue(self.d.finale.has_amrita)
        self.assertEqual([c.skill_uses for c in self.s.party], uses)
        self.assertEqual(self.s.inventory.counts, items)
        self.assertTrue(all(line in lines for line in b.final_data['amrita_release']))
        self.assertEqual(b.round, 1)
        actor = self.s.party[0]
        skill = next(sid for sid in actor.skills if self.s.skills[sid].effect == 'damage')
        hp = b.enemies[0].hp
        self.round(self.actions(Action(0, 'SKILL', 0, skill)))
        self.assertLess(b.enemies[0].hp, hp)
        with self.assertRaises(ValueError):
            b.begin_round(self.actions(Action(0, 'ITEM', item_id=AMRITA_ITEM_ID)))

    def test_ordinary_battles_reject_amrita_and_keep_normal_damage_and_loss_rules(self):
        self.grant()
        self.s.treasure.unbanked = 6
        b = self.s.next_battle(recover=False)
        self.assertFalse(b.can_use_amrita or b.elysion_barrier_active)
        with self.assertRaises(ValueError):
            b.begin_round([Action(i, 'ITEM', item_id=AMRITA_ITEM_ID) if i == 0 else Action(i, 'GUARD') for i in range(4)])
        self.assertGreater(b._damage(b.enemies[0], 50), 0)
        b.outcome = 'DEFEAT'
        self.s.settle()
        self.assertEqual(self.s.treasure.unbanked, 0)
        self.assertTrue(self.d.finale.has_amrita)

    def test_cannot_queue_key_twice_or_use_skill_and_item_with_same_actor(self):
        b = self.launch()
        with self.assertRaises(ValueError):
            b.begin_round([Action(i, 'ITEM', item_id=AMRITA_ITEM_ID) if i < 2 else Action(i, 'GUARD') for i in range(4)])
        with self.assertRaises(ValueError):
            b.begin_round([Action(0, 'ITEM', item_id=AMRITA_ITEM_ID),
                           Action(0, 'SKILL', 0, self.s.party[0].skills[0]), Action(2, 'GUARD'), Action(3, 'GUARD')])

    def test_real_use_exhaustion_and_mastery_are_rolled_back_on_retry(self):
        self.grant()
        actor = self.s.party[0]
        sid = 'power_strike'
        if sid not in actor.skills:
            actor.learn(self.s.skills[sid])
        actor.skill_uses[sid] = 1
        self.a.start_final_story()
        self.a.begin_final_battle()
        self.press()
        b = self.a.battle
        b.enemies[0].strength = b.enemies[0].intellect = b.enemies[0].agility = 1
        expected = self.resources()
        self.round(self.actions(Action(0, 'SKILL', 0, sid)))
        self.assertNotIn(sid, actor.skills)
        self.assertIn(sid, self.s.mastered_skills)
        self.fail()
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.resources(), expected)
        self.assertTrue(self.a.battle.elysion_barrier_active)

    def test_repeated_loss_after_amrita_restores_items_treasure_stats_skills_flags_and_references(self):
        self.s.inventory.counts = {item: 9 for item in self.s.inventory.counts}
        self.s.treasure.banked, self.s.treasure.unbanked = 55, 4
        self.e.completed.add(2)
        self.launch()
        expected = self.resources()
        checkpoint = self.a.final_checkpoint
        for _ in range(4):
            self.round(self.actions(Action(0, 'ITEM', item_id=AMRITA_ITEM_ID)))
            self.assertFalse(self.a.battle.elysion_barrier_active)
            for _ in range(7):
                self.s.party[1].hp = 1
                self.assertTrue(self.s.inventory.use('POTION', self.s.party[1])[0])
            self.s.party[2].hp = 0
            self.assertTrue(self.s.inventory.use('PHOENIX ASH', self.s.party[2])[0])
            self.s.party[0].strength += 10
            self.s.treasure.banked -= 10
            self.d.finale.read_lore.add('B11_01')
            self.e.completed.add(3)
            self.fail()
            self.assertEqual(self.a.state, 'final_retry')
            self.assertEqual(self.s.treasure.unbanked, 4)
            self.assertTrue(self.d.finale.has_amrita)
            self.press(pyxel.GAMEPAD1_BUTTON_A)
            self.assertIs(self.a.final_checkpoint, checkpoint)
            self.assertEqual(self.resources(), expected)
            self.assertTrue(self.a.battle.elysion_barrier_active)
            self.assertIs(self.d.inventory, self.s.inventory)
            self.assertIs(self.d.treasure, self.s.treasure)
            self.assertIs(self.e.session, self.s)
            self.assertTrue(all(c.mastered_skills is self.s.mastered_skills for c in self.s.party))
            self.a.battle.enemies[0].strength = self.a.battle.enemies[0].intellect = self.a.battle.enemies[0].agility = 1
            self.press()

    def test_draw_uses_same_safe_retry_and_no_returns_title(self):
        self.launch()
        self.fail('DRAW')
        self.assertEqual(self.a.state, 'final_retry')
        self.press(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(self.a.state, 'title')
        self.assertTrue(self.d.finale.has_amrita)

    def test_victory_spends_amrita_only_at_victory_and_reaches_ending(self):
        b = self.launch()
        self.round(self.actions(Action(0, 'ITEM', item_id=AMRITA_ITEM_ID)))
        self.assertFalse(self.d.finale.amrita_power_spent)
        b.enemies[0].hp = 1
        sid = next(sid for sid in self.s.party[0].skills if self.s.skills[sid].effect == 'damage')
        self.round(self.actions(Action(0, 'SKILL', 0, sid)))
        self.assertEqual(b.outcome, 'VICTORY')
        self.s.settle()
        self.a.finish_results()
        self.assertEqual(self.a.state, 'ending')
        self.assertTrue(self.d.finale.lord_of_elysion_defeated and self.d.finale.amrita_power_spent)
        self.assertFalse(self.d.finale.has_amrita)
        self.assertIsNone(self.a.final_checkpoint)

    def test_edited_long_story_automatically_pages_and_new_game_resets_checkpoint_flags(self):
        self.a.final_battle_data['story_pages'] = [['文章' * 25] * 12]
        self.assertGreater(len(self.a.final_story_pages()), 1)
        self.assertTrue(all(len(page) <= 8 for page in self.a.final_story_pages()))
        self.launch()
        self.a.start_new_game()
        self.assertIsNone(self.a.final_checkpoint)
        self.assertFalse(self.a.dungeon.finale.final_event_started or self.a.dungeon.finale.has_amrita)
        self.assertFalse(self.a.dungeon.finale.lord_of_elysion_defeated or self.a.dungeon.finale.amrita_power_spent)

    def test_debug_gates_and_amrita_reservation_in_item_ui(self):
        self.assertFalse(self.a.debug_final_stage('battle'))
        self.s.debug = True
        self.assertTrue(self.a.debug_final_stage('battle'))
        self.assertIn(AMRITA_ITEM_ID, self.a.battle_items())
        self.a.actions.append(Action(0, 'ITEM', item_id=AMRITA_ITEM_ID))
        self.assertNotIn(AMRITA_ITEM_ID, self.a.battle_items())
        self.assertNotIn(AMRITA_ITEM_ID, self.s.inventory.counts)

    def test_stuck_audio_timeout_allows_final_victory(self):
        self.launch()
        self.a.battle.outcome = 'VICTORY'
        self.s.settle()
        self.a.fanfare_started_at = time.monotonic() - FANFARE_MAX_WAIT_SECONDS - 1
        self.a.fanfare_start_frame = pyxel.frame_count
        with patch('rpg.app.music_is_playing', return_value=True), \
             patch.object(pyxel, 'stop', side_effect=RuntimeError('interrupted')):
            self.a.finish_results()
        self.assertEqual(self.a.state, 'ending')

    def test_authored_b15_extended_stairs_are_visible_without_changing_other_floor_bounds(self):
        self.assertEqual(self.d.map_bounds(0), (24, 24))
        self.assertEqual(self.d.map_bounds(13), (24, 24))
        self.assertEqual(self.d.map_bounds(14), (24, 32))
        self.assertEqual(self.d.find(14, (2, 0)), (3, 28))

    def test_long_edited_question_is_read_before_acceptance(self):
        self.grant()
        self.a.final_battle_data['offer_question'] = ['文章' * 25] * 7
        self.a.show_amrita_offer()
        pages = self.a.final_question_pages()
        self.assertGreater(len(pages), 1)
        for index in range(len(pages) - 1):
            self.press(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(self.a.state, 'amrita_offer')
            self.assertFalse(self.d.finale.final_event_started)
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'final_story')


if __name__ == '__main__':
    unittest.main()
