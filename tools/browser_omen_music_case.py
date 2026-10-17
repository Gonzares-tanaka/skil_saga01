"""Offering tests in the real Web runtime; no player save access."""
import gc
import io
import json
import unittest
from rpg.dungeon_app import DungeonApp
import rpg.sound as _sound

_foundation_live_app = next(o for o in gc.get_objects() if isinstance(o, DungeonApp))
_suite = unittest.defaultTestLoader.loadTestsFromModule(_skill_test_module)
_stream = io.StringIO()
_result = unittest.TextTestRunner(stream=_stream, verbosity=2).run(_suite)
assert _result.wasSuccessful(), _stream.getvalue()
_sound._audio = _foundation_live_app.audio
_foundation_live_app.audio.bank = None
_foundation_live_app.start_new_game()
_foundation_live_app.enter_camp()
_foundation_live_app.dungeon.finale.guardians_defeated = True
_foundation_live_app.dungeon.finale.claim_amrita()
_foundation_live_app.show_amrita_offer()
_foundation_live_app.opening_input_blocked = False
json.dumps(dict(count=_result.testsRun, passed=_result.testsRun,
    total_skills=62, save_version=1))
