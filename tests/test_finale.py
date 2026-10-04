"""Phase 6A: gauntlet resources, story flags and the editable final-area events."""
from collections import deque
from copy import deepcopy
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pyxel

from rpg.battle import Session
from rpg.app import FANFARE_MAX_WAIT_SECONDS
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.dungeon_app import DungeonApp
from rpg.exploration import Exploration
from rpg.finale import FinaleProgress, load_finale_data
from rpg.map_resources import load_maps
from rpg.models import Action
from rpg.tiles import (LORE_TILES, TILE_BOSS, TILE_GUARDIAN, TILE_HEAL_POINT,
                       TILE_QUEST, TILE_WARNING)


class FinaleProgressTests(unittest.TestCase):
    def test_only_three_victories_unlock_guardians_and_amrita(self):
        progress = FinaleProgress()
        with self.assertRaises(ValueError):
            progress.guardian_victory()
        with self.assertRaises(ValueError):
            progress.claim_amrita()
        progress.start_guardians()
        with self.assertRaises(ValueError):
            progress.start_guardians()
        for index in (1, 2):
            self.assertFalse(progress.guardian_victory())
            self.assertEqual(progress.guardian_index, index)
            self.assertFalse(progress.guardians_defeated)
            with self.assertRaises(ValueError):
                progress.claim_amrita()
        self.assertTrue(progress.guardian_victory())
        self.assertIsNone(progress.guardian_index)
        self.assertTrue(progress.guardians_defeated)
        self.assertFalse(progress.has_amrita)
        progress.claim_amrita()
        self.assertTrue(progress.has_amrita and progress.demon_defeated)
        with self.assertRaises(ValueError):
            progress.start_guardians()
        with self.assertRaises(ValueError):
            progress.guardian_victory()

    def test_failed_attempt_restarts_at_first_guardian_completed_flags_persist(self):
        progress = FinaleProgress()
        progress.start_guardians()
        progress.guardian_victory()
        progress.abort_guardians()
        self.assertIsNone(progress.guardian_index)
        self.assertFalse(progress.guardians_defeated)
        progress.start_guardians()
        self.assertEqual(progress.guardian_index, 0)
        for _ in range(3):
            progress.guardian_victory()
        progress.claim_amrita()
        progress.abort_guardians()
        self.assertTrue(progress.guardians_defeated)
        self.assertTrue(progress.demon_defeated and progress.has_amrita)

    def test_lore_text_is_data_driven_and_repeated_read_is_safe(self):
        progress = FinaleProgress()
        ident, row = next(iter(progress.data['lore'].items()))
        self.assertEqual(progress.lore_at(row['floor'] - 1, tuple(row['tile'])), ident)
        self.assertIsNone(progress.lore_at(0, tuple(row['tile'])))
        self.assertEqual(progress.read(ident), row['lines'])
        self.assertEqual(progress.read(ident), row['lines'])
        self.assertEqual(progress.read_lore, {ident})
        self.assertFalse(progress.has_amrita or progress.demon_defeated)

    def test_invalid_editable_story_data_is_rejected(self):
        original = load_finale_data()
        invalid = []
        data = deepcopy(original)
        data['guardian_ids'][1] = data['guardian_ids'][0]
        invalid.append(data)
        data = deepcopy(original)
        data['guardian_warning'] = ['']
        invalid.append(data)
        data = deepcopy(original)
        data['guardian_between'] = [['one page']]
        invalid.append(data)
        data = deepcopy(original)
        next(iter(data['lore'].values()))['floor'] = 10
        invalid.append(data)
        data = deepcopy(original)
        rows = list(data['lore'].values())
        rows[1]['tile'] = rows[0]['tile']
        invalid.append(data)
        for data in invalid:
            with self.subTest(data=data), patch('pathlib.Path.read_text', return_value=json.dumps(data)):
                with self.assertRaisesRegex(ValueError, 'finale.json'):
                    load_finale_data()


class FinaleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        self.session = Session(*load_content(), seed=62)
        self.dungeon = Dungeon(load_maps(), self.session.enemy_data,
                               load_dungeon_settings(), self.session.rng,
                               self.session.treasure, self.session.inventory)
        self.dungeon.debug_floor(14)
        self.dungeon.settings['encounter_chance'] = 0
        self.session.settings['spark_chance'] = 0
        for rates in self.session.settings['growth_rates'].values():
            rates.update(HP=0, STR=0, AGI=0, INT=0)
        # Exercise the real UI methods without reinitializing Pyxel in each test.
        app = self.app = DungeonApp.__new__(DungeonApp)
        app.session, app.dungeon = self.session, self.dungeon
        app.exploration = Exploration(self.session, self.dungeon)
        app.initial_content = deepcopy((self.session.settings, self.session.skills,
                                        self.session.party, self.session.enemy_data))
        app.initial_rng_state = self.session.rng.getstate()
        app.initial_debug = False
        app.keyboard = SimpleNamespace(update=lambda: None)
        app.overlay = None
        app.state = 'explore'
        app.battle = None
        app.battle_is_boss = False
        app.battle_kind = None
        app.battle_position = None
        app.next_guardian_index = None
        app.opening_input_blocked = app.battle_input_blocked = False
        app.fanfare_started_at = app.fanfare_start_frame = None
        app.fanfare_timed_out = False
        app.debug_return_state = None
        app.debug_return_overlay = 'debug_skills'
        app.debug_events = []
        app.pending = deque()
        app.message_page = app.result_page = 0
        app.notice_timer = app.shake_timer = 0
        app.notice = app.explore_message = ''
        app.info_tab = app.info_character = app.scroll = 0
        app.item_cursor = app.menu_cursor = 0
        app.return_lines = []

    def press(self, confirm=False, cancel=False):
        app = self.app
        with patch.object(app, 'confirm', return_value=confirm), \
             patch.object(app, 'cancel', return_value=cancel), \
             patch.object(app, 'pressed', return_value=False), \
             patch.object(app, 'direction', return_value=0):
            app.update()

    def finish_guardian(self):
        """Win through legal skill use, then consume the ordinary result screen."""
        actor = self.session.party[0]
        if 'fire' not in actor.skills:
            actor.learn(self.session.skills['fire'])
        actor.intellect = actor.agility = 999
        battle = self.app.battle
        actions = [Action(0, 'SKILL', 0, 'fire')] + [
            Action(i, 'GUARD') for i, member in enumerate(self.session.party)
            if i and member.alive
        ]
        battle.begin_round(actions)
        while battle.queue:
            battle.step()
        self.assertEqual(battle.outcome, 'VICTORY')
        self.session.settle()
        self.app.state = 'result'
        self.app.finish_results()

    def complete_guardian_flags(self):
        self.dungeon.finale.start_guardians()
        for _ in range(3):
            self.dungeon.finale.guardian_victory()

    def test_gate_blocks_without_moving_or_consuming_safe_steps(self):
        d = self.dungeon
        gate = d.find(14, TILE_GUARDIAN)
        self.assertFalse(d.can_enter(14, *gate))
        neighbor = next((gate[0] + dx, gate[1] + dy)
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                        if d.can_enter(14, gate[0] + dx, gate[1] + dy))
        d.x, d.y = neighbor
        before = d.x, d.y, d.steps, d.grace, d.rng.getstate()
        self.assertEqual(d.move(gate[0] - d.x, gate[1] - d.y)[0], 'guardian')
        self.assertEqual((d.x, d.y, d.steps, d.grace, d.rng.getstate()), before)
        self.complete_guardian_flags()
        self.assertTrue(d.can_enter(14, *gate))

    def test_demon_cannot_start_or_clear_before_guardians(self):
        d = self.dungeon
        d.x, d.y = d.find(14, TILE_BOSS)
        self.assertEqual(d.interact()[0], 'guardian')
        with self.assertRaises(ValueError):
            d.defeat_boss()
        self.assertFalse(d.cleared or d.finale.has_amrita)
        self.complete_guardian_flags()
        self.assertEqual(d.interact()[0], 'boss')
        self.assertEqual(d.defeat_boss(), d.finale.data['demon_after'])
        self.assertTrue(d.cleared and d.finale.has_amrita and d.finale.demon_defeated)

    def test_warning_can_cancel_before_any_battle_or_resource_cost(self):
        app, d = self.app, self.dungeon
        d.x, d.y = d.find(14, TILE_WARNING)
        before = [member.hp for member in self.session.party]
        app.handle_event(*d.interact())
        self.assertEqual(app.state, 'guardian_warning')
        self.press(cancel=True)
        self.assertEqual(app.state, 'explore')
        self.assertIsNone(d.finale.guardian_index)
        self.assertIsNone(app.battle)
        self.assertEqual([member.hp for member in self.session.party], before)

    def test_three_independent_fights_preserve_wounds_ko_uses_and_items(self):
        app, session, d = self.app, self.session, self.dungeon
        actor = session.party[0]
        actor.learn(session.skills['fire'])
        actor.hp = 7
        session.party[1].hp = 0
        session.inventory.counts['POTION'] = 3
        before_hp = [member.hp for member in session.party]
        before_items = dict(session.inventory.counts)
        fire_uses = actor.skill_uses['fire']
        d.finale.start_guardians()
        app.begin_encounter(boss=True, guardian_index=0)
        for index in range(3):
            self.assertTrue(app.battle.boss)
            self.assertIn('CANNOT', app.battle.attempt_run()[0])
            self.finish_guardian()
            self.assertEqual([member.hp for member in session.party], before_hp)
            self.assertEqual(session.inventory.counts, before_items)
            self.assertEqual(actor.skill_uses['fire'], fire_uses - index - 1)
            self.assertEqual(session.wins, index + 1)
            self.assertFalse(d.cleared or d.finale.has_amrita)
            self.assertEqual(app.state, 'guardian_after' if index == 2 else 'guardian_between')
            self.press(confirm=True)
        self.assertEqual(app.state, 'explore')
        self.assertTrue(d.finale.guardians_defeated)
        self.assertIsNone(d.finale.guardian_index)

    def test_silent_guardians_and_demon_reach_results_and_exploration(self):
        app, session, d = self.app, self.session, self.dungeon
        actor = session.party[0]
        actor.learn(session.skills['fire'])
        actor.intellect = actor.agility = 999

        def silent_win():
            actions = [Action(0, 'SKILL', 0, 'fire')] + [Action(i, 'GUARD') for i in range(1, 4)]
            app.battle.begin_round(actions)
            app.state, app.delay = 'resolve', 0
            for _ in range(80):
                self.press(confirm=True)
                if app.state == 'result':
                    break
            self.assertEqual(app.state, 'result')
            self.assertEqual(app.battle.outcome, 'VICTORY')
            self.assertTrue(session.settled)
            self.assertFalse(app.waiting_for_fanfare())
            app.finish_results()

        with patch.object(pyxel, 'play', side_effect=RuntimeError('AudioContext interrupted')), \
             patch.object(pyxel, 'playm', side_effect=RuntimeError('AudioContext interrupted')), \
             patch.object(pyxel, 'play_pos', side_effect=RuntimeError('AudioContext interrupted')), \
             patch.object(pyxel, 'stop', side_effect=RuntimeError('AudioContext interrupted')):
            d.finale.start_guardians()
            app.begin_encounter(boss=True, guardian_index=0)
            for index in range(3):
                silent_win()
                self.assertEqual(app.state, 'guardian_after' if index == 2 else 'guardian_between')
                self.press(confirm=True)
            self.assertEqual(app.state, 'explore')
            d.x, d.y = d.find(14, TILE_BOSS)
            app.begin_encounter(boss=True)
            silent_win()
            self.assertEqual(app.state, 'boss_after')
            self.assertTrue(d.finale.has_amrita)
            for _ in range(10):
                if app.state == 'explore':
                    break
                self.press(confirm=True)
            self.assertEqual(app.state, 'explore')
            self.assertEqual(session.wins, 4)

    def test_active_return_is_rejected_before_spending_a_charge_or_banking_treasure(self):
        app, session, d = self.app, self.session, self.dungeon
        actor = session.party[0]
        actor.learn(session.skills['return'])
        session.treasure.unbanked = 5
        uses = actor.skill_uses['return']
        d.finale.start_guardians()
        app.state, app.item_cursor = 'field_return', 0
        with patch.object(app, 'confirm', return_value=True), \
             patch.object(app, 'cancel', return_value=False), \
             patch.object(app, 'direction', return_value=0):
            app.update_camp_resources()
        self.assertEqual(actor.skill_uses['return'], uses)
        self.assertEqual((session.treasure.unbanked, session.treasure.banked), (5, 0))
        self.assertNotIn(app.state, ('camp', 'return_result'))
        self.assertEqual(d.finale.guardian_index, 0)

    def test_pending_replacement_blocks_next_guardian_until_decided(self):
        app, session, d = self.app, self.session, self.dungeon
        d.finale.start_guardians()
        app.begin_encounter(boss=True, guardian_index=0)
        app.battle.outcome = 'VICTORY'
        session.settings['spark_chance'] = 1
        actor = session.party[0]
        for skill in session.skills.values():
            if len(actor.skills) == session.settings['skill_slots']:
                break
            if skill.id not in actor.skills:
                actor.learn(skill)
        session.settle()
        app.state = 'result'
        self.assertTrue(session.pending_replacements)
        app.finish_results()
        self.assertEqual(app.state, 'result')
        self.assertEqual(d.finale.guardian_index, 0)
        with self.assertRaises(ValueError):
            session.next_battle(d.make_enemies(guardian_index=1), recover=False, boss=True)
        for index in list(session.pending_replacements):
            session.resolve_replacement(index)
        app.finish_results()
        self.assertEqual(app.state, 'guardian_between')
        self.assertEqual(d.finale.guardian_index, 1)
        self.assertEqual(session.completed, 1)

    def test_stuck_victory_audio_times_out_before_the_next_guardian(self):
        app, session, d = self.app, self.session, self.dungeon
        d.finale.start_guardians()
        app.begin_encounter(boss=True, guardian_index=0)
        app.battle.outcome = 'VICTORY'
        session.settle()
        app.state = 'result'
        app.fanfare_started_at = time.monotonic() - FANFARE_MAX_WAIT_SECONDS - 1
        app.fanfare_start_frame = pyxel.frame_count
        with patch('rpg.app.music_is_playing', return_value=True), \
             patch.object(pyxel, 'stop', side_effect=RuntimeError('AudioContext interrupted')):
            app.finish_results()
        self.assertTrue(app.fanfare_timed_out)
        self.assertEqual(app.state, 'guardian_between')
        self.assertEqual(d.finale.guardian_index, 1)

    def test_defeat_and_draw_abort_incomplete_gauntlet_without_granting_clear(self):
        for outcome in ('DEFEAT', 'DRAW'):
            with self.subTest(outcome=outcome):
                self.setUp()
                app, d, session = self.app, self.dungeon, self.session
                d.finale.start_guardians()
                d.finale.guardian_victory()
                app.begin_encounter(boss=True, guardian_index=1)
                if outcome == 'DEFEAT':
                    for actor in session.party:
                        actor.hp = 0
                app.battle.outcome = outcome
                session.settle()
                app.state = 'result'
                app.finish_results()
                self.assertIsNone(d.finale.guardian_index)
                self.assertFalse(d.finale.guardians_defeated or d.cleared)
                d.finale.start_guardians()
                self.assertEqual(d.finale.guardian_index, 0)
                if outcome == 'DEFEAT':
                    self.assertEqual(app.state, 'camp')
                    self.assertTrue(all(actor.hp == actor.max_hp for actor in session.party))

    def test_spring_is_once_per_expedition_and_never_recovers_uses_items_or_ko(self):
        app, d, session = self.app, self.dungeon, self.session
        self.complete_guardian_flags()
        d.x, d.y = d.find(14, TILE_HEAL_POINT)
        actor = session.party[0]
        actor.hp = 1
        session.party[1].hp = 0
        actor.skill_uses[actor.skills[0]] -= 4
        uses, items = dict(actor.skill_uses), dict(session.inventory.counts)
        app.handle_event(*d.interact())
        self.assertEqual(actor.hp, actor.max_hp)
        self.assertEqual(session.party[1].hp, 0)
        self.assertEqual((actor.skill_uses, session.inventory.counts), (uses, items))
        actor.hp = 2
        app.handle_event(*d.interact())
        self.assertEqual(actor.hp, 2)
        self.assertEqual(len(app.exploration.springs), 1)

    def test_amrita_is_outside_inventory_and_survives_return_death_and_new_expedition(self):
        app, d, session = self.app, self.dungeon, self.session
        self.complete_guardian_flags()
        for item in session.inventory.counts:
            session.inventory.counts[item] = 9
        items = dict(session.inventory.counts)
        session.treasure.unbanked = 7
        d.defeat_boss()
        self.assertEqual(session.inventory.counts, items)
        self.assertNotIn('アムリタ', session.inventory.counts)
        self.assertEqual(session.treasure.unbanked, 7)
        app.enter_camp(returned=True)
        self.assertTrue(d.finale.has_amrita)
        session.treasure.unbanked = 3
        session.treasure.lose()
        app.enter_camp(defeated=True)
        self.assertTrue(d.finale.has_amrita and d.finale.demon_defeated)
        d.enter(allow_cleared=True)
        self.assertTrue(d.finale.guardians_defeated and d.finale.has_amrita)
        self.assertEqual(session.inventory.counts, items)

    def test_new_game_resets_all_story_flags_and_lore(self):
        app, d = self.app, self.dungeon
        self.complete_guardian_flags()
        d.defeat_boss()
        d.finale.read_lore.add(next(iter(d.finale.data['lore'])))
        app.start_new_game()
        progress = app.dungeon.finale
        self.assertFalse(progress.guardians_defeated or progress.demon_defeated or progress.has_amrita)
        self.assertIsNone(progress.guardian_index)
        self.assertEqual(progress.read_lore, set())
        self.assertEqual(app.dungeon.defeated_bosses, set())
        self.assertEqual(app.state, 'title_fade')

    def test_guardian_enemy_variants_and_invalid_index(self):
        d = self.dungeon
        armor, speed, mind = [d.make_enemies(guardian_index=i)[0] for i in range(3)]
        self.assertEqual(len({armor.name, speed.name, mind.name}), 3)
        self.assertGreater(armor.defense, speed.defense)
        self.assertGreater(speed.agility, armor.agility)
        self.assertGreater(mind.magic_chance, armor.magic_chance)
        with self.assertRaises(ValueError):
            d.make_enemies(guardian_index=3)
        d.floor = 10
        with self.assertRaises(ValueError):
            d.make_enemies(guardian_index=0)

    def test_lore_tiles_and_level_three_quest_candidates_do_not_overlap_events(self):
        d = self.dungeon
        all_lore = [(floor, tile, point) for floor in range(10, 14) for tile in LORE_TILES
                    for point in d.positions(floor, tile)]
        self.assertGreaterEqual(len(all_lore), 5)
        self.assertLessEqual(len(all_lore), 7)
        for floor, tile, point in all_lore:
            d.floor, d.x, d.y = floor, *point
            event, ident = d.interact()
            self.assertEqual(event, 'lore')
            self.assertIsNotNone(ident)
            self.assertEqual(d.finale.data['lore'][ident]['floor'], floor + 1)
        d.defeated_bosses.add(9)
        floors = set()
        for seed in range(30):
            self.session.rng.seed(seed)
            exploration = Exploration(self.session, d)
            exploration.accept(3)
            floor, x, y = exploration.target
            floors.add(floor)
            self.assertIn(floor, range(10, 15))
            self.assertEqual(d.tile(floor, x, y), TILE_QUEST)
            self.assertIn((x, y), d.reachable(floor))
        self.assertEqual(floors, set(range(10, 15)))


if __name__ == '__main__':
    unittest.main()
