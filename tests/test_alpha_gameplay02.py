"""Boss gates, real pad routes, shared return settlement and durable inventory."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pyxel

from rpg.app import App
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp, TRAVEL_STATES
from rpg.elevator import (unlocked_destinations, arrival_point, b15_elevator_point,
                          at_b15_elevator, unlock_notice)
from rpg.hub import (HUB_FACILITIES, HUB_ICONS, HUB_POSITIONS, HUB_IMAGE_BANK,
                     HUB_PICTURE_SIZE, HUB_PICTURES)
from rpg.items import ITEMS, RETURN_FEATHER
from rpg.models import Action
from rpg.quests import spawn_candidates
from rpg.save import FileSaveBackend, SaveError, make_save_data, prepare_saved_game
from rpg.suspend import FileSuspendBackend, make_suspend_data, job_result
from rpg.text import font, text_width, FONT_HEIGHT
from rpg.tiles import (FLOOR_TILES, TILE_STAIRS_UP, TILE_ENTRANCE, TILE_CHEST,
                       TILE_RARE_CHEST, TILE_BOSS, TILE_WARNING)
from tests.gameplay_preservation import assert_gameplay_preserved


class Gameplay02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.backend = FileSuspendBackend(root/'suspend.json')
        with patch.object(pyxel, 'init'):
            self.a = DungeonApp(Session(*load_content(), seed=51), run=False, headless=True,
                start_at_title=False, save_backend=FileSaveBackend(root/'save.json'),
                suspend_backend=self.backend)
        self.tick()
        self.a.hub_intro_shown = True

    def tick(self, key=None):
        with patch.object(pyxel, 'btn', return_value=False), \
             patch.object(pyxel, 'btnp', new=lambda k, *args: k == key):
            self.a.update()
            self.a.draw()

    def unlock(self, deepest=True):
        d = self.a.dungeon
        d.defeated_bosses.update((4, 9))
        if deepest:
            d.finale.guardians_defeated = True
            d.floor = 14
            d.defeat_boss()

    def travel(self, floor):
        self.a.state = 'elevator'
        self.a.travel_elevator(floor)
        self.tick()  # Release transition input gate.

    def feather(self):
        self.a.enter_dungeon()
        self.a.state = 'items'
        self.a.item_kind_cursor = 3
        self.a.session.inventory.counts[RETURN_FEATHER] = 3

    def test_new_game_gates_and_unlocked_menu(self):
        a = self.a
        self.assertEqual(unlocked_destinations(a.dungeon), [])
        a.camp_cursor = 5
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'elevator')
        self.tick(pyxel.GAMEPAD1_BUTTON_A)  # Only Back is selectable.
        self.assertEqual(a.state, 'camp')
        for floor in (5, 10, 14):
            a.state = 'elevator'
            before = a.dungeon.floor, a.dungeon.x, a.dungeon.y
            with self.assertRaises(ValueError): a.travel_elevator(floor)
            self.assertEqual((a.dungeon.floor, a.dungeon.x, a.dungeon.y), before)
        for gate, expected in ((4, [5]), (9, [5, 10])):
            a.dungeon.defeated_bosses.add(gate)
            self.assertEqual([f for f, _ in unlocked_destinations(a.dungeon)], expected)
        a.dungeon.defeated_bosses.add(14)  # Incomplete demon story cannot unlock.
        self.assertNotIn(14, [f for f, _ in unlocked_destinations(a.dungeon)])
        a.dungeon.finale.demon_defeated = True
        self.assertIn(14, [f for f, _ in unlocked_destinations(a.dungeon)])

    def test_arrivals_are_safe_no_rng_rolls_and_expected_music(self):
        self.unlock()
        a = self.a
        for floor, music in ((5, 'bgm_area2'), (10, 'bgm_area3'), (14, 'bgm_area3')):
            with self.subTest(floor=floor):
                state = a.session.rng.getstate()
                battles = a.session.total_battles
                self.travel(floor)
                self.assertEqual(a.dungeon.floor, floor)
                self.assertEqual((a.dungeon.x, a.dungeon.y), arrival_point(a.dungeon, floor))
                self.assertTrue(a.dungeon.can_enter(floor, a.dungeon.x, a.dungeon.y))
                if floor != 14:
                    self.assertIn(a.dungeon.tile(floor, a.dungeon.x, a.dungeon.y), FLOOR_TILES | {TILE_STAIRS_UP})
                self.assertTrue(9 <= a.dungeon.encounter_remaining <= 22)
                self.assertNotEqual(a.session.rng.getstate(), state)
                self.assertEqual(a.session.total_battles, battles)
                self.assertEqual(a.audio.current_bgm, music)
                self.assertEqual(a.state, 'explore')

    def test_normal_dungeon_still_starts_b1_and_new_trip_clears_only_transient_map_state(self):
        self.unlock()
        self.travel(10)
        a = self.a
        a.dungeon.opened.add((10, 1, 1))
        a.dungeon.activated_switches.add(10)
        a.exploration.springs.add((10, 2, 2))
        a.enter_dungeon()
        self.assertEqual(a.dungeon.floor, 0)
        self.assertEqual((a.dungeon.x, a.dungeon.y), a.dungeon.find(0, TILE_ENTRANCE))
        self.assertFalse(a.dungeon.opened | a.dungeon.activated_switches | a.exploration.springs)
        self.assertEqual(a.dungeon.defeated_bosses, {4, 9, 14})

    def test_b15_return_area_is_distinct_from_quests_and_story(self):
        d = self.a.dungeon
        point = b15_elevator_point(d)
        self.assertEqual(point, (12, 0))
        x, y = point
        cells = {point}
        self.assertFalse(cells & set(spawn_candidates(d, 14)))
        self.assertEqual(d.boss_positions[14], (x-1, y))
        d.floor, d.x, d.y = 14, x, y
        self.assertFalse(at_b15_elevator(d))
        self.unlock()
        self.assertTrue(at_b15_elevator(d))
        self.assertTrue(d.can_enter(14, *point))
        for floor in (5, 10):
            d.floor = floor
            self.assertFalse(at_b15_elevator(d))

    def test_no_safe_landing_fails_before_trip_reset(self):
        self.unlock()
        a = self.a
        a.state = 'elevator'
        a.dungeon.opened.add((0, 2, 2))
        with patch.object(a.dungeon, 'can_enter', return_value=False):
            with self.assertRaises(ValueError): a.travel_elevator(5)
        self.assertIn((0, 2, 2), a.dungeon.opened)
        self.assertEqual(a.state, 'elevator')

    def test_b15_return_amrita_offer_later_revisit_and_no_boss_reappearance(self):
        self.unlock()
        self.travel(14)
        a, d = self.a, self.a.dungeon
        a.session.treasure.unbanked = 7
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'elevator_return')
        self.assertEqual(a.travel_choice, 1)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'return_result')
        self.assertEqual(a.session.treasure.unbanked, 0)
        self.assertEqual(a.session.treasure.banked, 7)
        self.assertEqual(a.audio.current_bgm, 'bgm_hub')
        self.tick()
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'amrita_offer')
        # Existing offer may have a paginated prompt; finish those pages.
        while a.final_question_page+1 < len(a.final_question_pages()):
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
        a.final_choice = 1
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'camp')
        self.assertTrue(d.finale.has_amrita)
        self.assertFalse(d.finale.final_event_started)
        self.travel(14)
        d.x, d.y = d.find(14, TILE_WARNING)
        self.assertEqual(d.interact()[0], '')
        d.x, d.y = d.find(14, TILE_BOSS)
        self.assertEqual(d.interact()[0], '')
        d.x, d.y = b15_elevator_point(d)
        a.state, a.travel_choice = 'elevator_return', 0
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick()
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'amrita_offer')

    def test_b15_return_cancel_keeps_expedition(self):
        self.unlock()
        self.travel(14)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(self.a.state, 'explore')
        self.assertEqual(self.a.dungeon.floor, 14)

    def test_feather_price_banked_only_count_limit_and_all_four_shop_rows(self):
        a = self.a
        a.state = 'shop'
        a.session.treasure.banked = 2
        a.session.treasure.unbanked = 99
        a.shop_cursor = 3
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 0)
        a.session.treasure.banked = 3
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 1)
        self.assertEqual(a.session.treasure.banked, 0)
        self.assertEqual(a.session.treasure.unbanked, 99)
        a.session.inventory.counts[RETURN_FEATHER] = 9
        a.session.treasure.banked = 10
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.session.treasure.banked, 10)
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 9)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.assertEqual(a.shop_cursor, 0)

    def test_feather_success_first_trip_no_battle_and_full_safe_return(self):
        self.feather()
        a, s = self.a, self.a.session
        self.assertIsNone(s.battle)
        s.treasure.banked, s.treasure.unbanked = 2, 7
        s.party[0].hp = 1
        s.party[0].statuses = {'poison': 3}
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'feather_return')
        self.assertEqual(a.travel_choice, 1)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'return_result')
        self.assertEqual(s.inventory.counts[RETURN_FEATHER], 2)
        self.assertEqual((s.treasure.banked, s.treasure.unbanked), (9, 0))
        self.assertEqual(s.party[0].hp, s.party[0].max_hp)
        self.assertFalse(s.party[0].statuses)
        self.assertEqual(a.audio.current_bgm, 'bgm_hub')

    def test_feather_cancel_no_choice_empty_invalid_and_return_failure_do_not_consume(self):
        self.feather()
        a = self.a
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)  # Default No.
        self.assertEqual(a.state, 'items')
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 3)
        self.tick()
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 3)
        self.tick()
        a.state, a.travel_choice = 'feather_return', 0
        with patch.object(a, 'enter_camp', side_effect=OSError('cannot return')):
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'feather_return')
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 3)
        a.session.inventory.counts[RETURN_FEATHER] = 0
        with self.assertRaises(ValueError): a.use_return_feather()

    def test_feather_refuses_every_unstable_state(self):
        self.feather()
        a = self.a
        for state in ('command', 'resolve', 'result', 'replace', 'boss_after', 'guardian_between',
                      'field_event', 'camp', 'amrita_offer', 'suspend_busy', 'battle_transition'):
            a.state = state
            with self.subTest(state=state), self.assertRaises(ValueError): a.use_return_feather()
        a.state = 'items'
        a.dungeon.finale.guardian_index = 1
        with self.assertRaises(ValueError): a.use_return_feather()
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 3)
        a.dungeon.finale.guardian_index = None
        a.overlay = 'info'
        with self.assertRaises(ValueError): a.use_return_feather()

    def test_feather_hidden_and_rejected_in_combat(self):
        a = self.a
        a.enter_dungeon()
        a.session.inventory.counts[RETURN_FEATHER] = 9
        a.begin_encounter()
        self.assertNotIn(RETURN_FEATHER, a.battle_items())
        with self.assertRaises(ValueError):
            a.battle.begin_round([Action(i, 'ITEM', 0, item_id=RETURN_FEATHER) for i in range(4)])
        before = a.session.inventory.counts[RETURN_FEATHER]
        self.assertFalse(a.session.inventory.use(RETURN_FEATHER, a.session.party[0])[0])
        self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], before)

    def test_feather_completed_quest_uses_existing_deferred_thanks_reward(self):
        self.feather()
        a = self.a
        a.exploration.accept(1, quest_type='explore')
        q = a.exploration.active
        q['progress'], q['completed'] = 1, True
        reward = q['reward']
        a.state = 'feather_return'
        a.use_return_feather()
        self.assertEqual(a.state, 'quest_thanks')
        self.assertEqual(a.session.treasure.banked, 0)
        pages = len(a.quest_thanks_pages())
        for _ in range(pages): self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'quest_reward')
        self.assertEqual(a.session.treasure.banked, reward)
        self.assertEqual(a.exploration.quest_clear_counts['explore'], 1)

    def test_old_v1_zeros_feather_and_unknown_shapes_still_rejected(self):
        self.unlock()
        a = self.a
        data = make_save_data(a)
        data['items'].pop(RETURN_FEATHER)
        data['banked_trz'] = 19
        restored = prepare_saved_game(a, data)
        self.assertEqual(restored[0].inventory.counts[RETURN_FEATHER], 0)
        self.assertEqual(restored[0].treasure.banked, 19)
        self.assertEqual([floor for floor, _ in unlocked_destinations(restored[1])], [5, 10, 14])
        self.assertNotIn(RETURN_FEATHER, data['items'])
        for change in ('unknown', 'missing', 'negative', 'too_many'):
            bad = deepcopy(data)
            if change == 'unknown': bad['items']['BAD'] = 1
            elif change == 'missing': bad['items'].pop('REMEDY')
            else: bad['items'][RETURN_FEATHER] = -1 if change == 'negative' else 10
            with self.subTest(change=change), self.assertRaises(SaveError): prepare_saved_game(a, bad)

    def test_new_normal_save_retains_feathers_and_derived_unlocks_without_notices(self):
        self.unlock()
        a = self.a
        a.session.inventory.counts[RETURN_FEATHER] = 5
        a.enter_camp()
        a.state, a.facility_index = 'facility', 0
        a.save_manager.save(a)
        data = a.save_manager.backend.read()
        self.assertEqual(data['save_version'], 1)
        self.assertEqual(data['items'][RETURN_FEATHER], 5)
        s, d, _, _ = prepare_saved_game(a, data)
        self.assertEqual(s.inventory.counts[RETURN_FEATHER], 5)
        self.assertEqual([f for f, _ in unlocked_destinations(d)], [5, 10, 14])

    def test_elevator_suspend_all_destinations_exact_once_and_old_suspend_compatible(self):
        self.unlock()
        a = self.a
        a.session.inventory.counts[RETURN_FEATHER] = 6
        for floor in (5, 10, 14):
            with self.subTest(floor=floor):
                self.travel(floor)
                before = json.loads(json.dumps(make_suspend_data(a)))
                job_result(a.suspend_manager.save(a))
                raw = job_result(self.backend.start('read'))
                prepared = a.suspend_manager.prepare(a, raw)
                job_result(self.backend.start('consume', raw))
                a.activate_suspended_game(prepared)
                self.assertEqual(json.loads(json.dumps(make_suspend_data(a))), before)
                self.assertEqual(a.session.inventory.counts[RETURN_FEATHER], 6)
                self.assertTrue(self.backend.start('consume', raw).error)
        # Pre-phase suspend shape: same version/maps/RNG, only absent feather.
        job_result(a.suspend_manager.save(a))
        old = json.loads(job_result(self.backend.start('read')))
        old['game']['items'].pop(RETURN_FEATHER)
        prepared = a.suspend_manager.prepare(a, json.dumps(old))
        self.assertEqual(prepared[0].inventory.counts[RETURN_FEATHER], 0)

    def test_notifications_first_victory_only_after_existing_story_and_not_on_travel(self):
        a, d = self.a, self.a.dungeon
        for floor in (4, 9, 14):
            if floor == 14: d.finale.guardians_defeated = True
            d.floor = floor
            original = deepcopy(d.finale.data['demon_after'] if floor == 14 else d.boss_data['after_message'])
            lines = d.defeat_boss()
            self.assertEqual(lines[:len(original)], original)
            self.assertEqual(lines[len(original):], unlock_notice(floor))
            self.assertEqual(d.defeat_boss(), original)
        self.assertTrue(d.finale.has_amrita)
        self.assertFalse(d.finale.final_event_started)
        self.travel(14)
        self.assertEqual(a.state, 'explore')

    def test_all_quest_levels_can_be_accepted_after_corresponding_gate(self):
        for level, gate in ((1, None), (2, 4), (3, 9)):
            if gate is not None: self.a.dungeon.defeated_bosses.add(gate)
            for kind in ('explore', 'investigate', 'hunt'):
                self.a.exploration.active = None
                self.a.exploration.accept(level, quest_type=kind)
                self.assertEqual(self.a.exploration.active['level'], level)
                self.assertEqual(self.a.exploration.active['type'], kind)

    def test_layout_bounds_six_icons_and_gamepad_horizontal_navigation(self):
        a = self.a
        self.assertEqual(HUB_FACILITIES[:5], ('GUILD','TRAINING','PUB','SHOP','DUNGEON'))
        self.assertEqual(HUB_POSITIONS[:5], tuple((5,16+i*19) for i in range(5)))
        self.assertEqual(HUB_ICONS[-1], (80,0))
        a.camp_cursor = 4
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
        self.assertEqual(a.camp_cursor, 5)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)
        self.assertEqual(a.camp_cursor, 4)
        calls = []
        real_text = pyxel.text
        def bounded(x, y, value, color, selected_font):
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x+text_width(value), 160, (x,y,value))
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(y+FONT_HEIGHT, 120, (x,y,value))
            real_text(x,y,value,color,selected_font)
        real_blt = pyxel.blt
        def blit(*args, **kwargs):
            calls.append(args)
            real_blt(*args, **kwargs)
        self.unlock()
        shots = ROOT/'verification/screenshots'
        shots.mkdir(parents=True, exist_ok=True)
        with patch.object(pyxel, 'text', side_effect=bounded), patch.object(pyxel, 'blt', side_effect=blit):
            for state in ('camp','elevator','shop','items','feather_return','elevator_return'):
                a.state, a.overlay = state, None
                a.camp_cursor = 5
                a.draw()
                pyxel.screenshot(str(shots/f'gameplay02_{state}.png'), scale=4)
                if state == 'camp':
                    icons = [c for c in calls if c[2] == HUB_IMAGE_BANK and c[5:7] == (16,16)]
                    self.assertEqual(len(icons), 6)
                    self.assertIn((92,92,2,80,0,16,16,0), icons)
                    calls.clear()

    def test_previous_phase_and_all_other_gameplay_and_sound_unchanged(self):
        assert_gameplay_preserved(self)
        self.assertEqual(len(self.a.session.skills), 62)

    def test_audio_failure_does_not_block_elevator_feather_or_b15_return(self):
        self.unlock()
        a = self.a
        a.audio.enabled = False
        a.audio.current_bgm = None
        self.travel(10)
        self.assertEqual(a.state, 'explore')
        a.session.inventory.counts[RETURN_FEATHER] = 1
        a.state = 'feather_return'
        a.use_return_feather()
        self.assertEqual(a.state, 'return_result')
        self.travel(14)
        a.state, a.travel_choice = 'elevator_return', 0
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'return_result')


if __name__ == '__main__':
    unittest.main()
