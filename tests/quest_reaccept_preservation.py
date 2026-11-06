"""Permit only the unsettled-battle guard over the received production tree."""
import ast
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from rpg.content import ROOT


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/quest_reaccept_before.json').read_text(encoding='utf8'))


def assert_preserved(case):
    if (ROOT/'tests/fixtures/ui_phase6b2_before.json').exists():
        from tests.ui_phase6b2_preservation import assert_preserved as assert_ui_preserved
        return assert_ui_preserved(case)
    before=baseline()
    for name,digest in before['hashes'].items():
        if 'save' in Path(name).parts:continue # Checked in the source tree, never copied for tests.
        if name=='rpg/dungeon_app.py':
            old=before['dungeon_app']
            expected=old.replace("self.battle.outcome == 'VICTORY' and q and not q['completed']",
                "self.battle.outcome == 'VICTORY' and not self.session.settled and q and not q['completed']")
            case.assertNotEqual(old,expected)
            case.assertEqual(ast.dump(ast.parse((ROOT/name).read_text(encoding='utf8'))),
                             ast.dump(ast.parse(expected)),name)
        else:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
