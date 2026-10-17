"""Run opening and strict audio-scope tests inside the actual Web runtime."""
import gc
import io
import json
import unittest
from rpg.dungeon_app import DungeonApp
import rpg.sound as _sound

_foundation_live_app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
_suite=unittest.defaultTestLoader.loadTestsFromModule(_skill_test_module)
_stream=io.StringIO()
_result=unittest.TextTestRunner(stream=_stream,verbosity=2).run(_suite)
assert _result.wasSuccessful(),_stream.getvalue()
_sound._audio=_foundation_live_app.audio
_foundation_live_app.audio.bank=None
_foundation_live_app.start_new_game(); _foundation_live_app.enter_camp()
_foundation_live_app.opening_input_blocked=False
_foundation_live_app.enter_dungeon(); _foundation_live_app.begin_encounter()
_foundation_live_app.battle_input_blocked=False
_foundation_live_app.session.party[0].learn(_foundation_live_app.session.skills['sweep'])
_foundation_live_app.begin_input(); _foundation_live_app.state='skill'
_foundation_live_app.skill_cursor=0; _foundation_live_app.notice_timer=0
json.dumps(dict(count=_result.testsRun,passed=_result.testsRun,
    cases=unittest.defaultTestLoader.getTestCaseNames(_skill_test_module.AudioPass03Tests),
    total_skills=62,save_version=1))
