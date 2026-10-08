"""Fixed QUEST catalog, safe return transaction and completion-aware selection."""
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
from rpg.quests import QUEST_TYPES, QUEST_COMPLETION_IDS, QUEST_COMPLETION_TOTAL
from rpg.tiles import DUNGEON_RESOURCE


class QuestCompletionTests(unittest.TestCase):
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

    def completed_goal(self, kind='explore', level=1, flavor_id=None):
        self.e.accept(level, quest_type=kind)
        if flavor_id is not None:
            self.e.active['flavor_id'] = flavor_id
        self.e.surveyed = True
        return self.e.active

    def test_fixed_27_ids_and_all_36_have_distinct_thanks(self):
        texts, defaults = self.e.flavor_data['texts'], self.e.flavor_data['fallbacks']
        regular, fallback, thanks = set(), set(), []
        for kind in QUEST_TYPES:
            for level in ('1', '2', '3'):
                rows = texts[kind][level]
                self.assertEqual(len(rows), 3)
                regular.update(row['id'] for row in rows)
                fallback.add(defaults[kind][level]['id'])
                for row in rows + [defaults[kind][level]]:
                    self.assertTrue(2 <= len(row['complete_lines']) <= 3)
                    self.assertTrue(row['requester'])
                    thanks.append(tuple(row['complete_lines']))
            self.assertEqual({r['id'] for rows in texts[kind].values() for r in rows},
                             set(QUEST_COMPLETION_IDS[kind]))
        self.assertEqual((len(regular), len(fallback), QUEST_COMPLETION_TOTAL), (27, 9, 27))
        self.assertFalse(regular & fallback)
        self.assertEqual(len(set(thanks)), 36)

    def test_initial_records_and_json_friendly_structures(self):
        self.assertEqual(self.e.quest_clear_counts, dict.fromkeys(QUEST_TYPES, 0))
        self.assertEqual(self.e.completed_quest_ids, [])
        stats = self.e.quest_record()
        for kind in QUEST_TYPES:
            self.assertEqual(stats[kind], dict(clears=0, completed=0, total=9, percent=0))
        self.assertEqual(stats['total'], dict(completed=0, total=27, percent=0))
        self.assertEqual(json.loads(json.dumps(self.e.quest_clear_counts)), self.e.quest_clear_counts)

    def test_only_safe_return_can_finalize_and_double_finalization_is_harmless(self):
        q = self.completed_goal()
        self.assertFalse(self.e.finalize_quest_completion())
        self.assertEqual(self.s.treasure.banked, 0)
        self.assertFalse(self.e.completed_quest_ids)
        self.e.return_to_camp(True, defer_completion=True)
        self.assertIs(self.e.active, q)
        self.assertEqual(self.s.treasure.banked, 0)
        self.assertTrue(self.e.finalize_quest_completion())
        self.assertEqual(self.s.treasure.banked, q['reward'])
        self.assertEqual(self.e.quest_clear_counts, dict(explore=1, investigate=0, hunt=0))
        self.assertEqual(self.e.completed_quest_ids, [q['flavor_id']])
        for _ in range(3):
            self.assertFalse(self.e.finalize_quest_completion())
            self.assertFalse(self.e.return_to_camp(True))
        self.assertEqual(self.s.treasure.banked, q['reward'])
        self.assertEqual(self.e.quest_clear_counts['explore'], 1)

    def test_repeat_counts_again_but_does_not_duplicate_id(self):
        for count in (1, 2):
            self.completed_goal(flavor_id='explore_l1_01')
            self.e.return_to_camp(True)
            self.assertEqual(self.e.quest_clear_counts['explore'], count)
            self.assertEqual(self.e.completed_quest_ids, ['explore_l1_01'])
        self.assertEqual(self.e.quest_record()['explore']['completed'], 1)

    def test_defeat_resets_goal_without_payment_counts_or_completion(self):
        for kind in QUEST_TYPES:
            q = self.completed_goal(kind)
            self.assertTrue(self.e.return_to_camp(False))
            self.assertIs(self.e.active, q)
            self.assertFalse(q['completed'])
            self.assertFalse(self.e.completion_ready)
            self.assertFalse(self.e.finalize_quest_completion())
            self.assertEqual(self.e.quest_clear_counts, dict.fromkeys(QUEST_TYPES, 0))
            self.assertFalse(self.e.completed_quest_ids)
            self.assertEqual(self.s.treasure.banked, 0)
            self.e.active = None

    def test_each_pool_yields_three_new_ids_then_all_27_reach_100_percent(self):
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                seen = set()
                for _ in range(3):
                    q = self.completed_goal(kind, level)
                    self.assertNotIn(q['flavor_id'], seen)
                    seen.add(q['flavor_id'])
                    self.e.return_to_camp(True)
                self.assertEqual(seen, {row['id'] for row in self.e.flavor_data['texts'][kind][str(level)]})
            self.assertEqual(self.e.quest_record()[kind], dict(clears=9, completed=9, total=9, percent=100))
        self.assertEqual(self.e.quest_record()['total'], dict(completed=27, total=27, percent=100))

    def test_unseen_priority_and_normal_pool_after_every_id_completed(self):
        self.e.completed_quest_ids = ['investigate_l2_01']
        with patch.object(self.e.flavor_rng, 'choice', side_effect=lambda pool: pool[0]) as choice:
            self.e.choose_flavor('investigate', 2)
            self.assertEqual({row['id'] for row in choice.call_args.args[0]},
                             {'investigate_l2_02', 'investigate_l2_03'})
            self.e.completed_quest_ids += ['investigate_l2_02', 'investigate_l2_03']
            self.e.choose_flavor('investigate', 2)
            self.assertEqual({row['id'] for row in choice.call_args.args[0]},
                             {'investigate_l2_01', 'investigate_l2_02', 'investigate_l2_03'})

    def test_fallback_missing_and_wrong_pool_ids_never_count_as_unique(self):
        for kind in QUEST_TYPES:
            for value in (f'{kind}_l1_default', 'unknown', None, 'investigate_l3_01'):
                q = self.completed_goal(kind)
                q['flavor_id'] = value
                self.assertTrue(self.e.quest_flavor()['id'].endswith('_default'))
                self.assertTrue(self.e.quest_flavor()['complete_lines'])
                self.e.return_to_camp(True)
                self.assertFalse(self.e.completed_quest_ids)
            self.assertEqual(self.e.quest_clear_counts[kind], 4)
        self.assertEqual(self.e.quest_record()['total']['total'], 27)

    def test_record_roundtrip_ignores_unknown_ids_and_final_retry_preserves_history(self):
        self.completed_goal()
        self.e.return_to_camp(True)
        original = self.e.quest_record()
        saved = json.loads(json.dumps(dict(counts=self.e.quest_clear_counts, ids=self.e.completed_quest_ids)))
        self.e.quest_clear_counts, self.e.completed_quest_ids = saved['counts'], saved['ids']
        self.assertEqual(self.e.quest_record(), original)
        self.e.completed_quest_ids += [self.e.completed_quest_ids[0], 'hunt_l1_default', 'removed']
        self.assertEqual(self.e.quest_record(), original)
        self.e.completed_quest_ids = saved['ids'][:1]
        history = deepcopy((self.e.quest_clear_counts, self.e.completed_quest_ids))
        self.d.finale.has_amrita = True
        checkpoint = FinalBattleCheckpoint.capture(self.s, self.d, self.e)
        for _ in range(3):
            checkpoint.restore(self.s, self.d, self.e)
            self.assertEqual((self.e.quest_clear_counts, self.e.completed_quest_ids), history)


if __name__ == '__main__':
    unittest.main()
