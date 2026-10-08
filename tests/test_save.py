"""JSON round trips, validation before mutation and atomic file failure."""
from copy import deepcopy
import json
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
from rpg.save import (FileSaveBackend, BrowserSaveBackend, BROWSER_SAVE_KEY,
                      SaveManager, SaveError, NoSaveError, default_backend,
                      make_save_data, apply_save_data)


class MemoryStorage:
    def __init__(self):
        self.values = {}

    def getItem(self, key):
        return self.values.get(key)

    def setItem(self, key, value):
        self.values[key] = value


class SaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        content = load_content()
        s = Session(*deepcopy(content), seed=13)
        d = Dungeon(load_maps(), s.enemy_data, load_dungeon_settings(), s.rng, s.treasure, s.inventory)
        self.app = SimpleNamespace(session=s, dungeon=d, exploration=Exploration(s, d),
                                   initial_content=content, hub_intro_shown=True, can_save_game=lambda: True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = FileSaveBackend(Path(self.temp.name) / 'save/save.json')
        self.manager = SaveManager(self.backend)

    def fixture(self):
        s, d, e = self.app.session, self.app.dungeon, self.app.exploration
        s.treasure.banked, s.total_battles = 17, 123
        s.inventory.counts.update({'POTION': 2, 'PHOENIX ASH': 7, 'REMEDY': 9})
        s.mastered_skills.add('fire')
        s.discovered_skills.update(('fire', 'return'))
        c = s.party[0]
        for sid in ('fire', 'return'):
            if sid not in c.skills:
                c.learn(s.skills[sid])
        c.skill_uses['fire'] = min(17, s.skills['fire'].max_uses)
        c.skill_uses['return'] = 2
        c.max_hp += 40
        c.hp = c.max_hp
        c.strength += 7
        c.agility += 6
        c.intellect += 10
        c.history.append('日本語の成長記録')
        e.quest_clear_counts.update(explore=5, investigate=3, hunt=2)
        e.completed_quest_ids = ['explore_l1_01', 'investigate_l2_01', 'hunt_l3_02']
        e.completed.update((1, 2))
        d.defeated_bosses.update((4, 9))
        d.finale.read_lore.add('B11_01')

    def test_full_json_roundtrip_and_no_initial_money_added(self):
        self.fixture()
        # Normally camp heals everyone. The codec itself preserves exact HP,
        # including a sparse/empty loadout without introducing another heal.
        last = self.app.session.party[-1]
        last.skills.clear()
        last.skill_uses.clear()
        last.mastered_copies.clear()
        last.hp -= 1
        original = make_save_data(self.app)
        self.manager.save(self.app)
        self.assertIn('日本語', self.backend.path.read_text(encoding='utf-8'))
        for _ in range(3):
            self.app.session.treasure.banked = 0
            self.manager.load(self.app)
            self.assertEqual(make_save_data(self.app), original)
            self.assertEqual(self.app.session.treasure.banked, 17)
            self.assertEqual(self.app.session.treasure.unbanked, 0)
            self.assertIs(self.app.session.party[0].mastered_skills, self.app.session.mastered_skills)
            self.assertIn('fire', self.app.session.party[0].mastered_copies)
        self.app.session.treasure.banked += 5
        self.app.session.total_battles += 1
        self.manager.save(self.app)
        self.manager.load(self.app)
        self.assertEqual((self.app.session.treasure.banked, self.app.session.total_battles), (22, 124))

    def test_every_quest_band_preserves_contract_and_rebuilds_safe_points(self):
        self.app.dungeon.defeated_bosses.update((4, 9))
        for kind in ('explore', 'investigate', 'hunt'):
            for level in (1, 2, 3):
                e = self.app.exploration
                e.active = None
                e.accept(level, quest_type=kind)
                if kind == 'investigate':
                    e.active['progress'] = 1
                    e.active['investigated_points'] = [e.active['points'][0]]
                flavor = deepcopy(e.quest_flavor())
                data = make_save_data(self.app)
                self.assertNotIn('points', data['active_quest'])
                apply_save_data(self.app, data)
                self.assertEqual(make_save_data(self.app), data)
                self.assertEqual(self.app.exploration.quest_flavor(), flavor)
                q = self.app.exploration.active
                self.assertEqual(len(q['investigated_points']), q['progress'])
                self.assertEqual(len(q['points']), q['required_count'])

    def test_story_before_amrita_after_amrita_and_after_ending(self):
        self.fixture()
        for stage in ('before', 'amrita', 'ending'):
            d = self.app.dungeon
            if stage == 'amrita':
                d.finale.guardians_defeated = True
                d.finale.claim_amrita()
                d.defeated_bosses.add(14)
            elif stage == 'ending':
                d.finale.start_final_event()
                d.finale.final_victory()
            snapshot = d.finale.snapshot()
            data = make_save_data(self.app)
            if stage == 'amrita':
                invalid = deepcopy(data)
                invalid['story']['final_event_started'] = True
                with self.assertRaises(SaveError):
                    apply_save_data(self.app, invalid)
            apply_save_data(self.app, data)
            self.assertEqual(self.app.dungeon.finale.snapshot(), snapshot)
            self.assertNotIn('AMRITA', self.app.session.inventory.counts)

    def test_invalid_data_is_rejected_without_changing_current_game(self):
        original = make_save_data(self.app)
        invalid = []
        for key in original:
            bad = deepcopy(original); bad.pop(key); invalid.append(bad)
        for key, value in (('save_version', 999), ('save_version', True), ('total_battles', True),
                           ('banked_trz', -1), ('party', {}), ('items', {'POTION': 10}),
                           ('completed_quest_ids', ['explore_l1_default']), ('story', [])):
            bad = deepcopy(original); bad[key] = value; invalid.append(bad)
        bad = deepcopy(original); bad['party'][0]['skills'][0]['uses'] = '17'; invalid.append(bad)
        for bad in invalid:
            with self.assertRaises(SaveError):
                apply_save_data(self.app, bad)
            self.assertEqual(make_save_data(self.app), original)

    def test_missing_corrupt_and_atomic_write_failure_preserve_file(self):
        with self.assertRaises(NoSaveError):
            self.manager.load(self.app)
        self.backend.path.parent.mkdir()
        for text in ('{broken', '[]', '{"save_version":999}'):
            self.backend.path.write_text(text, encoding='utf-8')
            with self.assertRaises(SaveError):
                self.manager.load(self.app)
            self.assertEqual(self.backend.path.read_text(encoding='utf-8'), text)
        self.manager.save(self.app)
        before = self.backend.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=PermissionError('test write failure')):
            with self.assertRaises(SaveError):
                self.manager.save(self.app)
        self.assertEqual(self.backend.path.read_bytes(), before)
        self.assertFalse(self.backend.path.with_suffix('.tmp').exists())

    def test_no_transients_and_missing_flavor_uses_existing_fallback(self):
        self.app.exploration.accept(1, quest_type='investigate')
        self.app.exploration.active['flavor_id'] = 'removed_old_flavor'
        c = self.app.session.party[0]
        c.effects['power_up'] = (1.5, 3)
        c.guarding, c.berserk = True, 3
        self.app.session.treasure.unbanked = 6
        data = make_save_data(self.app)
        encoded = json.dumps(data)
        for key in ('points', 'investigated_points', 'guardian_index', 'effects', 'guarding', 'checkpoint', 'unbanked', 'cooldowns'):
            self.assertNotIn('"' + key + '"', encoded)
        apply_save_data(self.app, data)
        self.assertEqual(self.app.session.treasure.unbanked, 0)
        self.assertEqual(self.app.session.party[0].effects, {})
        self.assertTrue(self.app.exploration.quest_flavor()['id'].endswith('_default'))

    def test_save_guard_and_browser_backend_have_no_file_fallback(self):
        self.app.can_save_game = lambda: False
        with self.assertRaises(SaveError):
            self.manager.save(self.app)
        self.assertFalse(self.backend.path.exists())
        with patch('rpg.save.sys.platform', 'emscripten'):
            self.assertIsInstance(default_backend(), BrowserSaveBackend)
        with patch('rpg.save.sys.platform', 'win32'), patch.dict('sys.modules', {'js': None}):
            self.assertIsInstance(default_backend(), FileSaveBackend)
            self.assertEqual(default_backend().read.__func__, FileSaveBackend.read)
        with patch.object(FileSaveBackend, 'write', side_effect=AssertionError('file fallback')):
            with self.assertRaises(SaveError):
                BrowserSaveBackend().write(make_save_data(self.app))

    def test_browser_uses_same_complete_json_and_overwrites_only_its_key(self):
        self.fixture()
        self.app.exploration.accept(2, quest_type='investigate')
        self.app.exploration.active['progress'] = 1
        storage = MemoryStorage()
        storage.values['another_game'] = 'untouched'
        backend = BrowserSaveBackend(storage)
        manager = SaveManager(backend)
        self.assertFalse(backend.exists())
        expected = make_save_data(self.app)
        manager.save(self.app)
        self.assertTrue(backend.exists())
        self.assertEqual(json.loads(storage.values[BROWSER_SAVE_KEY]), expected)
        self.assertIn('日本語', storage.values[BROWSER_SAVE_KEY])
        self.app.session.treasure.banked = 0
        manager.load(self.app)
        self.assertEqual(make_save_data(self.app), expected)
        self.app.session.treasure.banked += 5
        self.app.session.total_battles += 1
        manager.save(self.app)
        manager.load(self.app)
        self.assertEqual((self.app.session.treasure.banked, self.app.session.total_battles), (22, 124))
        self.assertEqual(set(storage.values), {BROWSER_SAVE_KEY, 'another_game'})
        self.assertEqual(storage.values['another_game'], 'untouched')

    def test_browser_invalid_data_is_not_deleted_or_partially_applied(self):
        storage = MemoryStorage()
        manager = SaveManager(BrowserSaveBackend(storage))
        original = make_save_data(self.app)
        with self.assertRaises(NoSaveError):
            manager.load(self.app)
        # Pyodide 314's null sentinel is not None and is not a string.
        with patch.object(storage, 'getItem', return_value=object()):
            with self.assertRaises(NoSaveError):
                manager.load(self.app)
        for raw in ('', '{broken', '[]', '{"save_version":999}', '{"save_version":1}'):
            storage.values[BROWSER_SAVE_KEY] = raw
            with self.assertRaises(SaveError):
                manager.load(self.app)
            self.assertEqual(storage.values[BROWSER_SAVE_KEY], raw)
            self.assertEqual(make_save_data(self.app), original)

    def test_browser_denied_read_write_and_storage_getter_do_not_touch_file_or_game(self):
        storage = MemoryStorage()
        manager = SaveManager(BrowserSaveBackend(storage))
        manager.save(self.app)
        original = make_save_data(self.app)
        raw = storage.values[BROWSER_SAVE_KEY]
        with patch.object(storage, 'setItem', side_effect=RuntimeError('QuotaExceededError')):
            with self.assertRaises(SaveError):
                manager.save(self.app)
        with patch.object(storage, 'getItem', side_effect=RuntimeError('SecurityError')):
            with self.assertRaises(SaveError):
                manager.load(self.app)
        class DeniedWindow:
            @property
            def localStorage(self):
                raise RuntimeError('SecurityError')
        with patch.dict('sys.modules', {'js': SimpleNamespace(window=DeniedWindow())}):
            backend = BrowserSaveBackend()  # Construction must not access storage.
            for action in (backend.read, backend.exists, lambda: backend.write(original)):
                with self.assertRaises(SaveError):
                    action()
        self.assertEqual(storage.values[BROWSER_SAVE_KEY], raw)
        self.assertEqual(make_save_data(self.app), original)
        self.assertFalse(self.backend.path.exists())


if __name__ == '__main__':
    unittest.main()
