"""Phase 6D: repeatable single contracts, safe markers, progress and checkpoint."""
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
from rpg.quests import QUEST_TYPES, spawn_candidates
from rpg.tiles import DUNGEON_RESOURCE, TILE_QUEST


class QuestTests(unittest.TestCase):
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

    def at(self, point):
        self.d.floor = self.e.active_quest['target_floor'] - 1
        self.d.x, self.d.y = point

    def complete(self):
        q = self.e.active_quest
        if q['type'] == 'hunt':
            self.at(q['points'][0])
            self.assertFalse(self.e.investigate())
            for c in self.s.party:
                c.hp = c.max_hp = 300
                c.strength = c.intellect = 100
                c.agility = 60
            battle = self.s.next_battle(self.e.make_hunt_enemy(), recover=False)
            for _ in range(60):
                if battle.outcome:
                    break
                battle.begin_round(battle.auto_actions())
                while battle.queue:
                    battle.step()
            self.assertEqual(battle.outcome, 'VICTORY')
            self.s.settle()
            self.e.hunt_victory()
        else:
            for index, point in enumerate(q['points']):
                self.at(point)
                self.assertTrue(self.e.investigate())
                self.assertEqual(q['progress'], index + 1)
                self.assertFalse(self.e.investigate())
                self.assertEqual(q['progress'], index + 1)
        self.assertTrue(self.e.surveyed)

    def test_all_nine_patterns_floor_bands_counts_and_json(self):
        self.d.defeated_bosses.update((4, 9))
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                seen = set()
                for _ in range(40):
                    self.e.active = None
                    self.e.accept(level, quest_type=kind)
                    q = self.e.active_quest
                    self.assertEqual(json.loads(json.dumps(q)), q)
                    self.assertIs(self.e.active, q)
                    self.assertEqual((q['type'], q['level']), (kind, level))
                    self.assertIn(q['target_floor'], range((level-1)*5+1, level*5+1))
                    count = (2 if level == 1 else 3) if kind == 'investigate' else 1
                    self.assertEqual(q['required_count'], count)
                    self.assertEqual(len({tuple(p) for p in q['points']}), count)
                    for p in q['points']:
                        self.assertEqual(self.d.tile(q['target_floor']-1, *p), TILE_QUEST)
                        self.assertIn(tuple(p), spawn_candidates(self.d, q['target_floor']-1))
                    seen.add(q['target_floor'])
                eligible = {f+1 for f in range((level-1)*5, level*5)
                            if len(spawn_candidates(self.d, f)) >= count}
                self.assertEqual(seen, eligible)

    def test_selected_quests_respect_boss_unlocks(self):
        for gates, levels in (((),(1,)), ((4,),(1,2)), ((4,9),(1,2,3))):
            self.d.defeated_bosses = set(gates)
            expected = {(kind, level) for kind in QUEST_TYPES for level in levels}
            self.assertEqual(set(self.e.available()), expected)
            for kind in QUEST_TYPES:
                for level in (1, 2, 3):
                    self.e.active = None
                    rng = self.s.rng.getstate()
                    if level in levels:
                        self.e.accept(level, quest_type=kind)
                        self.assertEqual((self.e.active['type'], self.e.active['level']), (kind, level))
                    else:
                        with self.assertRaises(ValueError):
                            self.e.accept(level, quest_type=kind)
                        self.assertIsNone(self.e.active)
                        self.assertEqual(self.s.rng.getstate(), rng)

    def test_active_contract_rejection_does_not_reroll_or_change_rng(self):
        self.e.accept(1, quest_type='investigate')
        self.at(self.e.active['points'][0])
        self.e.investigate()
        before = deepcopy(self.e.active)
        rng = self.s.rng.getstate()
        for kind in QUEST_TYPES:
            with self.assertRaisesRegex(ValueError, 'すでに依頼'):
                self.e.accept(1, quest_type=kind)
            self.assertEqual(self.e.active, before)
            self.assertEqual(self.s.rng.getstate(), rng)

    def test_every_pattern_reward_only_on_safe_return_once_and_repeatable(self):
        self.d.defeated_bosses.update((4,9))
        for kind in QUEST_TYPES:
            for level in (1,2,3):
                self.e.accept(level, quest_type=kind)
                self.assertFalse(self.e.return_to_camp(True))
                before = self.s.treasure.banked
                reward = self.e.active['reward']
                self.complete()
                self.assertEqual(self.s.treasure.banked, before)
                lines = self.e.return_to_camp(True)
                self.assertIn('TRZ', lines[0])
                self.assertEqual(self.s.treasure.banked, before + reward)
                self.assertIsNone(self.e.active_quest)
                self.assertFalse(self.e.return_to_camp(True))
                self.assertEqual(self.s.treasure.banked, before + reward)

    def test_death_loses_partial_and_completed_progress_but_keeps_contract(self):
        self.d.defeated_bosses.update((4,9))
        for kind in QUEST_TYPES:
            for level in (1,2,3):
                self.e.active = None
                self.e.accept(level, quest_type=kind)
                self.complete()
                q = self.e.active
                points = deepcopy(q['points'])
                before = self.s.treasure.banked
                self.assertTrue(self.e.return_to_camp(False))
                self.assertIs(self.e.active, q)
                self.assertEqual(q['points'], points)
                self.assertEqual(q['progress'], 0)
                self.assertFalse(q['completed'])
                self.assertEqual(q['investigated_points'], [])
                self.assertEqual(self.s.treasure.banked, before)
                self.assertFalse(self.e.return_to_camp(True))
        self.e.active = None
        self.e.accept(3, quest_type='investigate')
        self.at(self.e.active['points'][0])
        self.e.investigate()
        self.assertFalse(self.e.surveyed)
        self.assertTrue(self.e.return_to_camp(False))
        self.assertEqual(self.e.active['progress'], 0)

    def test_partial_investigation_survives_unchanged_final_checkpoint(self):
        self.d.defeated_bosses.update((4,9))
        self.e.accept(3, quest_type='investigate')
        self.at(self.e.active['points'][0])
        self.e.investigate()
        saved = deepcopy(self.e.active_quest)
        self.d.finale.has_amrita = True
        checkpoint = FinalBattleCheckpoint.capture(self.s,self.d,self.e)
        for _ in range(3):
            self.e.surveyed = True
            self.e.active = None
            checkpoint.restore(self.s,self.d,self.e)
            self.assertEqual(self.e.active_quest, saved)
            self.assertEqual(self.e.active['progress'], 1)
            self.assertFalse(self.e.surveyed)

    def test_boss_floors_hunt_reuses_normal_enemy_without_changing_data(self):
        self.d.defeated_bosses.update((4,9))
        originals = deepcopy(self.d.enemies)
        for level in (1,2,3):
            self.e.active = None
            with patch.object(self.s.rng,'choice',side_effect=lambda values:values[-1]):
                self.e.accept(level, quest_type='hunt')
            q = self.e.active
            self.assertEqual(q['target_floor'], level*5)
            self.at(q['points'][0])
            enemy = self.e.make_hunt_enemy()[0]
            row = self.d.enemies[enemy.id]
            self.assertFalse(row.get('boss'))
            profile = self.d.settings['floors'][q['hunt_source_floor']-1]
            self.assertGreater(enemy.max_hp, round(row['max_hp']*profile['hp_scale']))
            self.assertEqual(self.d.enemies, originals)
            self.assertFalse(self.d.finale.demon_defeated)

    def test_b15_spawn_never_crosses_guardian_or_warning(self):
        candidates = spawn_candidates(self.d,14)
        self.assertTrue(candidates)
        self.d.finale.guardians_defeated = True
        self.assertEqual(spawn_candidates(self.d,14), candidates)
        self.assertLess(len(candidates), 3)  # Human map stays unchanged.


if __name__ == '__main__':
    unittest.main()
