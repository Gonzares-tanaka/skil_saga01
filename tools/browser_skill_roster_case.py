"""Run the official roster tests inside the real isolated Web runtime."""
import gc
import io
import json
import unittest
from copy import deepcopy
from rpg.dungeon_app import DungeonApp
from rpg.save import apply_save_data, make_save_data, BrowserSaveBackend

_foundation_live_app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
_suite=unittest.defaultTestLoader.loadTestsFromModule(_skill_test_module)
_stream=io.StringIO()
_result=unittest.TextTestRunner(stream=_stream,verbosity=2).run(_suite)
assert _result.wasSuccessful(),_stream.getvalue()
apply_save_data(_foundation_live_app,deepcopy(_old_skill_save))
assert make_save_data(_foundation_live_app)==_old_skill_save
_save_backend=BrowserSaveBackend()
_save_backend.write(_old_skill_save)
apply_save_data(_foundation_live_app,_save_backend.read())
assert make_save_data(_foundation_live_app)==_old_skill_save

# Round-trip a new attack copy, exact Uses and mastery, via localStorage.
_s=_foundation_live_app.session
_s.mastered_skills.add('sweep'); _s.discovered_skills.add('sweep')
_s.party[0].learn(_s.skills['sweep']); _s.party[0].skill_uses['sweep']=5
_new_save=make_save_data(_foundation_live_app)
_save_backend.write(_new_save)
apply_save_data(_foundation_live_app,_save_backend.read())
assert make_save_data(_foundation_live_app)==_new_save

# Prepare for real D-pad/A/B pointer events in the outer browser driver.
_foundation_live_app.start_new_game(); _foundation_live_app.enter_camp()
_foundation_live_app.opening_input_blocked=False
_foundation_live_app.enter_dungeon(); _foundation_live_app.begin_encounter()
_foundation_live_app.battle_input_blocked=False
_foundation_live_app.session.party[0].learn(_foundation_live_app.session.skills['sweep'])
_foundation_live_app.begin_input(); _foundation_live_app.state='skill'
_foundation_live_app.skill_cursor=0; _foundation_live_app.notice_timer=0
json.dumps(dict(count=_result.testsRun,passed=_result.testsRun,
                cases=unittest.defaultTestLoader.getTestCaseNames(_skill_test_module.SkillRosterTests),
                old_save_localStorage_equal=True,new_save_localStorage_equal=True,
                total_skills=62,save_version=1))
