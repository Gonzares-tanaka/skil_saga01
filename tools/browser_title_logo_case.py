"""User logo in actual Web plus isolated real TITLE and localStorage input."""
import gc
import io
import json
import unittest
from rpg.dungeon_app import DungeonApp
from rpg.save import make_save_data,BrowserSaveBackend
import rpg.sound as _sound

_foundation_live_app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
_suite=unittest.defaultTestLoader.loadTestsFromModule(_skill_test_module)
_stream=io.StringIO()
_result=unittest.TextTestRunner(stream=_stream,verbosity=2).run(_suite)
assert _result.wasSuccessful(),_stream.getvalue()
_sound._audio=_foundation_live_app.audio
_foundation_live_app.audio.bank=None
_foundation_live_app.start_new_game(); _foundation_live_app.enter_camp()
_foundation_live_app.hub_intro_shown=True
_foundation_live_app.session.treasure.banked=17
_title_saved=make_save_data(_foundation_live_app)
_title_backend=BrowserSaveBackend()
assert not _title_backend.exists()  # This is a fresh temporary browser profile.

def _title_show_again():
    _foundation_live_app.state='title'; _foundation_live_app.overlay=None
    _foundation_live_app.opening_input_blocked=False
    _foundation_live_app.title_cursor=1
    _foundation_live_app.sync_scene_audio()

_title_show_again(); _foundation_live_app.title_cursor=0
json.dumps(dict(count=_result.testsRun,passed=_result.testsRun,
    cases=unittest.defaultTestLoader.getTestCaseNames(_skill_test_module.TitleLogoTests),
    total_skills=62,save_version=1))
