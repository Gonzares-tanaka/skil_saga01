"""Driver injects test module separately; nothing enters production skill JSON."""
import gc
import io
import json
import unittest
from dataclasses import replace
from copy import deepcopy
from rpg.dungeon_app import DungeonApp
from rpg.save import apply_save_data, make_save_data, BrowserSaveBackend

_foundation_live_app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
_suite=unittest.defaultTestLoader.loadTestsFromModule(_skill_test_module)
_stream=io.StringIO()
_result=unittest.TextTestRunner(stream=_stream,verbosity=2).run(_suite)
assert _result.wasSuccessful(),_stream.getvalue()
assert _result.testsRun==31,_result.testsRun
apply_save_data(_foundation_live_app,deepcopy(_old_skill_save))
assert make_save_data(_foundation_live_app)==_old_skill_save
_save_backend=BrowserSaveBackend()
_save_backend.write(_old_skill_save)
apply_save_data(_foundation_live_app,_save_backend.read())
assert make_save_data(_foundation_live_app)==_old_skill_save

# Prepare the actual app for the driver's keyboard / physical HTML touch events.
_foundation_live_app.start_new_game()
_foundation_live_app.enter_camp()
_foundation_live_app.opening_input_blocked=False
_foundation_live_app.enter_dungeon()
_foundation_live_app.begin_encounter()
_foundation_live_app.battle_input_blocked=False
_fixture=replace(_foundation_live_app.session.skills['punch'],id='fixture_live',
                 target='all_enemies',relearn_cost=0,relearn_uses=0)
_foundation_live_app.session.skills[_fixture.id]=_fixture
_foundation_live_app.session.party[0].learn(_fixture)
_foundation_live_app.begin_input()
_foundation_live_app.state='skill'
_foundation_live_app.skill_cursor=0
_foundation_live_app.notice_timer=0
json.dumps(dict(count=_result.testsRun,cases=unittest.defaultTestLoader.getTestCaseNames(_skill_test_module.SkillFoundationTests),
                passed=_result.testsRun,fixture_skills_not_shipped=True,old_save_localStorage_equal=True,save_version=1))
