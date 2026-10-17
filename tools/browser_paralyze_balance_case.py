"""Append new balance tests to the existing actual-Pyodide status cases."""
import io
import sys
import types
import unittest
from rpg.content import ROOT

previous = json.loads(run_cases())
module = types.ModuleType('_paralyze_balance_tests')
sys.modules[module.__name__] = module
exec((ROOT / 'tests/test_paralyze_balance.py').read_text(encoding='utf8'), module.__dict__)
suite = unittest.defaultTestLoader.loadTestsFromModule(module)
output = io.StringIO()
result = unittest.TextTestRunner(stream=output).run(suite)
assert result.wasSuccessful(), output.getvalue()
rates = {side: module.sample_turns(side) for side in ('party', 'enemy')}
json.dumps(dict(cases=previous['cases'], count=previous['count'] + result.testsRun,
                balance_tests=result.testsRun, balance_passed=result.testsRun,
                samples=rates, audio_unavailable=True, save_version=1))
