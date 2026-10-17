"""Every target floor, real file round trips, gate safety and failure guards."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pyxel

from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.exploration import Exploration
from rpg.map_resources import load_maps
from rpg.quests import QUEST_TYPES, quest_spawn_report, spawn_candidates
from rpg.save import FileSaveBackend, SaveManager, make_save_data
from rpg.tiles import FLOOR_TILES, TILE_QUEST


class QuestSpawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True
        cls.maps = load_maps()
        cls.content = load_content()

    def make_app(self):
        s = Session(*deepcopy(self.content), seed=81)
        d = Dungeon(self.maps, s.enemy_data, load_dungeon_settings(), s.rng, s.treasure, s.inventory)
        d.defeated_bosses.update((4, 9))
        return SimpleNamespace(session=s, dungeon=d, exploration=Exploration(s, d),
                               initial_content=self.content, hub_intro_shown=True,
                               can_save_game=lambda: True)

    def accept_at(self, app, kind, floor):
        e, s = app.exploration, app.session
        with patch.object(s.rng, 'choice', return_value=floor):
            e.accept(floor // 5 + 1, quest_type=kind)
        self.assertEqual(e.active['target_floor'], floor + 1)

    def assert_symbols(self, app, floor, progress=0):
        d, e = app.dungeon, app.exploration
        d.debug_floor(floor)
        q = e.active
        count = (2 if floor < 5 else 3) if q['type'] == 'investigate' else 1
        self.assertEqual(q['required_count'], count)
        self.assertEqual(q['progress'], progress)
        self.assertEqual(len(e.visible_points()), count - progress)
        self.assertEqual(len({tuple(p) for p in q['points']}), count)
        valid = spawn_candidates(d, floor)
        for p in q['points']:
            self.assertIn(tuple(p), valid)
            self.assertIn(d.tile(floor, *p), FLOOR_TILES | {TILE_QUEST})
        d.debug_floor((floor + 1) % 15)
        self.assertEqual(e.visible_points(), [])
        d.debug_floor(floor)

    def test_all_fifteen_floors_have_enough_safe_candidates(self):
        d = self.make_app().dungeon
        for f in range(15):
            with self.subTest(floor=f+1):
                row = quest_spawn_report(d, f)
                self.assertGreaterEqual(row['valid_count'], 2 if f < 5 else 3)
                self.assertEqual(row['valid_count'], len(set(row['valid_points'])))
        row = quest_spawn_report(d, 14)
        self.assertEqual((row['marker_count'], row['extra_count'], row['valid_count']), (3, 4, 5))
        self.assertEqual({tuple(r['point']) for r in row['rejected']}, {(4, 10), (20, 12)})
        self.assertTrue(all(y >= 27 for x, y in row['valid_points']))
        before = row['valid_points']
        d.finale.guardians_defeated = True
        self.assertEqual(spawn_candidates(d, 14), before)

    def test_every_type_on_every_floor_without_save(self):
        app = self.make_app()
        for kind in QUEST_TYPES:
            for floor in range(15):
                with self.subTest(kind=kind, floor=floor+1):
                    app.exploration.active = None
                    self.accept_at(app, kind, floor)
                    self.assert_symbols(app, floor)

    def test_every_type_on_every_floor_after_file_save_fresh_game_load(self):
        app = self.make_app()
        with tempfile.TemporaryDirectory() as td:
            manager = SaveManager(FileSaveBackend(Path(td)/'save.json'))
            for kind in QUEST_TYPES:
                for floor in range(15):
                    with self.subTest(kind=kind, floor=floor+1):
                        app.exploration.active = None
                        self.accept_at(app, kind, floor)
                        before = make_save_data(app)
                        manager.save(app)
                        self.assertEqual(make_save_data(app), before)  # SAVE itself cannot hide symbols.
                        self.assertNotIn('points', before['active_quest'])
                        fresh = self.make_app()
                        manager.load(fresh)
                        self.assertEqual(make_save_data(fresh), before)
                        self.assert_symbols(fresh, floor)

    def test_partial_investigation_loads_remaining_points_without_double_count(self):
        app = self.make_app()
        with tempfile.TemporaryDirectory() as td:
            manager = SaveManager(FileSaveBackend(Path(td)/'save.json'))
            for floor in range(15):
                with self.subTest(floor=floor+1):
                    app.exploration.active = None
                    self.accept_at(app, 'investigate', floor)
                    q = app.exploration.active
                    app.dungeon.debug_floor(floor)
                    app.dungeon.x, app.dungeon.y = q['points'][0]
                    app.exploration.investigate()
                    manager.save(app)
                    fresh = self.make_app()
                    manager.load(fresh)
                    self.assert_symbols(fresh, floor, progress=1)
                    e, d = fresh.exploration, fresh.dungeon
                    d.x, d.y = e.active['investigated_points'][0]
                    self.assertEqual(e.investigate(), [])
                    for point in list(e.visible_points()):
                        d.x, d.y = point
                        e.investigate()
                        self.assertEqual(e.investigate(), [])
                    self.assertTrue(e.surveyed)
                    reward, flavor = e.active['reward'], e.active['flavor_id']
                    bank = fresh.session.treasure.banked
                    self.assertEqual(e.return_to_camp(True, defer_completion=True), [])
                    self.assertTrue(e.quest_flavor()['complete_lines'])
                    self.assertTrue(e.finalize_quest_completion())
                    self.assertEqual(fresh.session.treasure.banked, bank + reward)
                    self.assertEqual(e.completed_quest_ids, [flavor])
                    self.assertEqual(e.quest_clear_counts['investigate'], 1)
                    self.assertEqual(e.finalize_quest_completion(), [])

    def test_invalid_supplemental_points_are_filtered_and_duplicate_points_deduplicated(self):
        d = self.make_app().dungeon
        d.settings['floors'][14]['quest_spawn_points'] += [[2,27], [-1,0], [1000,1000], [3,28], [19,16]]
        row = quest_spawn_report(d,14)
        self.assertEqual(row['valid_count'], 5)
        self.assertIn('outside_map', {r['reason'] for r in row['rejected']})
        self.assertIn('not_empty_floor', {r['reason'] for r in row['rejected']})

    def test_insufficient_candidates_are_logged_and_never_accepted(self):
        app = self.make_app()
        with patch('rpg.exploration.spawn_candidates', return_value=[]), \
             self.assertLogs('rpg.quests', level='WARNING') as logs:
            with self.assertRaises(ValueError):
                app.exploration.accept(3, quest_type='investigate')
        self.assertIsNone(app.exploration.active)
        self.assertEqual(len(logs.output), 5)
        self.assertTrue(all('required_count=3 valid_candidate_count=0' in line for line in logs.output))
        self.assertTrue(any('target_floor=B15F' in line for line in logs.output))

    def test_invalid_preview_is_not_moved_to_another_floor_or_accepted(self):
        app = self.make_app()
        with patch.object(app.session.rng, 'choice', return_value=13):
            # Preview uses its own copied RNG; use the direct generator fixture.
            q = app.exploration.make_quest(3, quest_type='investigate')
        e = app.exploration
        e.pending_quest, e.pending_quest_rng_state = q, app.session.rng.getstate()
        before, rng = deepcopy(q), app.session.rng.getstate()
        with patch('rpg.exploration.spawn_candidates', return_value=[]), \
             self.assertLogs('rpg.quests', level='WARNING'):
            with self.assertRaises(ValueError):
                e.accept_preview()
        self.assertIsNone(e.active)
        self.assertEqual(e.pending_quest, before)
        self.assertEqual(app.session.rng.getstate(), rng)


if __name__ == '__main__':
    unittest.main()
