"""Actual Pyodide audio scenes/events, original visual traces and real input."""
import gc
import io
import json
import unittest
from copy import deepcopy
from rpg.dungeon_app import DungeonApp
from rpg.save import make_save_data, apply_save_data, BrowserSaveBackend
import rpg.sound as _sound

_foundation_live_app = next(o for o in gc.get_objects() if isinstance(o, DungeonApp))
_suite = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromTestCase(_skill_test_module.AudioManagerTests),
    unittest.defaultTestLoader.loadTestsFromTestCase(_skill_test_module.AudioSceneTests),
    _skill_test_module.AudioPreservationTests('test_all_twenty_rare_eight_legend_traces_exactly_match_before'),
])
_stream = io.StringIO()
_result = unittest.TextTestRunner(stream=_stream, verbosity=2).run(_suite)
assert _result.wasSuccessful(), _stream.getvalue()
_status_cases = json.loads(run_cases())
apply_save_data(_foundation_live_app, deepcopy(_old_skill_save))
assert make_save_data(_foundation_live_app) == _old_skill_save
_backend = BrowserSaveBackend(); _backend.write(_old_skill_save)
apply_save_data(_foundation_live_app, _backend.read())
assert make_save_data(_foundation_live_app) == _old_skill_save
for _method in ('confirm', 'confirm_held', 'cancel', 'direction'):
    _foundation_live_app.__dict__.pop(_method, None)
_sound._audio = _foundation_live_app.audio
_foundation_live_app.audio.bank = None
_foundation_live_app.start_new_game(); _foundation_live_app.enter_camp()
_foundation_live_app.opening_input_blocked = False
_foundation_live_app.enter_dungeon(); _foundation_live_app.begin_encounter()
_foundation_live_app.battle_input_blocked = False
_foundation_live_app.session.party[0].learn(_foundation_live_app.session.skills['ragnarok'])
_foundation_live_app.session.discovered_skills.add('ragnarok')
_foundation_live_app.begin_input(); _foundation_live_app.state = 'skill'
_foundation_live_app.skill_cursor = 0; _foundation_live_app.notice_timer = 0
json.dumps(dict(count=_result.testsRun + _status_cases['count'] + 2,
                audio_tests=_result.testsRun, audio_passed=_result.testsRun,
                bgm_scenes=8, exploration_se=6, status_cases=_status_cases['count'],
                old_save_roundtrips=2, rare_traces=20, legend_traces=8,
                native_asset_audits_excluded=True, save_version=1))
