"""Flavor selection is persistent, editable and independent of gameplay RNG."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import pyxel

from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.exploration import Exploration
from rpg.final_battle import FinalBattleCheckpoint
from rpg.map_resources import load_maps
from rpg.quests import QUEST_TYPES
from rpg.tiles import DUNGEON_RESOURCE


class QuestFlavorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        pyxel.load(str(DUNGEON_RESOURCE))
        self.s = Session(*load_content(), seed=73)
        self.d = Dungeon(load_maps(), self.s.enemy_data, load_dungeon_settings(),
                         self.s.rng, self.s.treasure, self.s.inventory)
        self.e = Exploration(self.s, self.d)
        self.d.defeated_bosses.update((4, 9))

    def test_all_nine_pools_have_three_short_flavors_and_are_selected_without_repeats(self):
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                pool = self.e.flavor_data['texts'][kind][str(level)]
                self.assertGreaterEqual(len(pool), 3)
                self.assertTrue(all(2 <= len(row['lines']) <= 3 for row in pool))
                expected, seen, previous = {row['id'] for row in pool}, set(), None
                for _ in range(30):
                    self.e.accept(level, quest_type=kind)
                    q = self.e.active
                    self.assertIn(q['flavor_id'], expected)
                    self.assertNotEqual(q['flavor_id'], previous)
                    self.assertNotIn('lines', q)
                    self.assertNotIn('requester', q)
                    self.assertEqual(self.e.quest_flavor()['id'], q['flavor_id'])
                    previous = q['flavor_id']
                    seen.add(previous)
                    self.e.surveyed = True
                    self.e.return_to_camp(True)
                self.assertEqual(seen, expected)

    def test_json_floor_changes_defeat_and_final_retry_preserve_the_same_flavor(self):
        self.e.accept(3, quest_type='investigate')
        original = deepcopy(self.e.quest_flavor())
        self.e.active = json.loads(json.dumps(self.e.active))
        for floor in (10, 11, 14, 0):
            self.d.floor = floor
            self.assertEqual(self.e.quest_flavor(), original)
        self.e.surveyed = True
        self.e.return_to_camp(False)
        self.assertEqual(self.e.quest_flavor(), original)
        self.d.finale.has_amrita = True
        checkpoint = FinalBattleCheckpoint.capture(self.s, self.d, self.e)
        for _ in range(3):
            self.e.active['flavor_id'] = 'deleted'
            checkpoint.restore(self.s, self.d, self.e)
            self.assertEqual(self.e.quest_flavor(), original)

    def test_unknown_removed_missing_and_wrong_pool_ids_use_matching_defaults(self):
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                self.e.active = None
                self.e.accept(level, quest_type=kind)
                default = self.e.flavor_data['fallbacks'][kind][str(level)]
                selected = self.e.active['flavor_id']
                pool = self.e.flavor_data['texts'][kind][str(level)]
                with patch.dict(self.e.flavor_data['texts'][kind], {str(level): [r for r in pool if r['id'] != selected]}):
                    self.assertEqual(self.e.quest_flavor(), default)
                for unknown in ('deleted', 'hunt_l3_99', None):
                    self.e.active['flavor_id'] = unknown
                    self.assertEqual(self.e.quest_flavor(), default)
                self.e.active.pop('flavor_id')
                self.assertEqual(self.e.quest_flavor(), default)
                other = next(k for k in QUEST_TYPES if k != kind)
                self.e.active['flavor_id'] = self.e.flavor_data['texts'][other][str(level)][0]['id']
                self.assertEqual(self.e.quest_flavor(), default)

    def test_empty_and_single_flavor_pools_can_still_accept(self):
        for pool in ([], self.e.flavor_data['texts']['explore']['1'][:1]):
            with patch.dict(self.e.flavor_data['texts']['explore'], {'1': pool}):
                for _ in range(3):
                    self.e.active = None
                    self.e.accept(1)
                    self.assertTrue(self.e.quest_flavor()['lines'])
                    self.assertEqual(self.e.active['flavor_id'],
                                     (pool[0] if pool else self.e.flavor_data['fallbacks']['explore']['1'])['id'])

    def test_flavor_selection_does_not_change_targets_enemy_or_gameplay_rng(self):
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                self.e.active = None
                before = self.s.rng.getstate()
                self.e.accept(level, quest_type=kind)
                actual, after = deepcopy(self.e.active), self.s.rng.getstate()
                self.e.active = None
                self.s.rng.setstate(before)
                with patch.object(self.e, 'choose_flavor', return_value=actual['flavor_id']):
                    self.e.accept(level, quest_type=kind)
                self.assertEqual(self.e.active, actual)
                self.assertEqual(self.s.rng.getstate(), after)

    def test_rejected_acceptance_does_not_reroll_flavor(self):
        self.e.accept(1)
        before = deepcopy(self.e.active)
        rng, last = self.e.flavor_rng.getstate(), self.e.last_flavor_id
        with self.assertRaises(ValueError):
            self.e.accept(2, quest_type='hunt')
        self.assertEqual(self.e.active, before)
        self.assertEqual(self.e.flavor_rng.getstate(), rng)
        self.assertEqual(self.e.last_flavor_id, last)

    def test_preview_is_not_active_and_accepts_exact_displayed_contract(self):
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                self.e.active = None
                rng, last = self.s.rng.getstate(), self.e.last_flavor_id
                offer = self.e.preview_quest(level, kind)
                original = deepcopy(offer)
                flavor = deepcopy(self.e.quest_flavor(offer))
                self.assertIsNone(self.e.active)
                self.assertFalse(self.e.visible_points())
                self.assertFalse(self.e.investigate())
                self.assertEqual(self.s.rng.getstate(), rng)
                self.assertEqual(self.e.last_flavor_id, last)
                expected_rng, flavor_rng = self.e.pending_quest_rng_state, self.e.flavor_rng.getstate()
                self.e.accept_preview()
                self.assertEqual(self.e.active, original)
                self.assertEqual(self.e.quest_flavor(), flavor)
                self.assertIsNone(self.e.pending_quest)
                self.assertIsNone(self.e.pending_quest_rng_state)
                self.assertEqual(self.s.rng.getstate(), expected_rng)
                self.assertEqual(self.e.flavor_rng.getstate(), flavor_rng)

    def test_decline_changes_no_progress_funds_or_gameplay_rng(self):
        self.s.treasure.banked, self.s.treasure.unbanked = 3, 7
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                rng, last = self.s.rng.getstate(), self.e.last_flavor_id
                self.e.preview_quest(level, kind)
                self.e.decline_preview()
                self.assertIsNone(self.e.active)
                self.assertIsNone(self.e.pending_quest)
                self.assertIsNone(self.e.pending_quest_rng_state)
                self.assertEqual(self.s.rng.getstate(), rng)
                self.assertEqual(self.e.last_flavor_id, last)
                self.assertFalse(self.e.completed)
                self.assertEqual((self.s.treasure.banked, self.s.treasure.unbanked), (3, 7))
        with self.assertRaises(ValueError):
            self.e.accept_preview()

    def test_preview_cannot_replace_active_quest_or_accept_twice(self):
        self.e.preview_quest(1, 'hunt')
        self.e.accept_preview()
        before = deepcopy(self.e.active)
        rng, flavor_rng = self.s.rng.getstate(), self.e.flavor_rng.getstate()
        for action in (lambda: self.e.preview_quest(1, 'explore'), self.e.accept_preview):
            with self.assertRaises(ValueError):
                action()
            self.assertEqual(self.e.active, before)
            self.assertEqual(self.s.rng.getstate(), rng)
            self.assertEqual(self.e.flavor_rng.getstate(), flavor_rng)


if __name__ == '__main__':
    unittest.main()
