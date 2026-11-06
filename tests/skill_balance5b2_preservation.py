"""Exact received-tree protection, with narrowly authorized 5B-2 changes."""
import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT

CHANGES = {
    'power_up': dict(duration=4, description='味方STR1.4倍。4ターン。'),
    'focus': dict(duration=4, description='味方INT1.5倍。4ターン。'),
    'sanctuary': dict(duration=3, description='味方全体の被害45%減。3ターン。'),
    'slow': dict(description='敵1体の行動順を遅くする。'),
    'slow_field': dict(description='敵全体の行動順を遅くする。'),
}
METHODS = {'rpg/app.py': ('App', ('draw_battle', 'skill_details')),
           'rpg/dungeon_app.py': ('DungeonApp', ('draw_field_heal',))}

@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/skill_balance5b2_before.json').read_text(encoding='utf8'))

def adjusted_rows(rows):
    rows = deepcopy(rows)
    for row in rows:
        row.update(CHANGES.get(row['id'], {}))
    if (ROOT/'tests/fixtures/skill_rescue5c_before.json').exists():
        from tests.rescue5c_preservation import adopted_skill_rows
        return adopted_skill_rows(rows)
    return rows

def pre_5b2_source(name, source):
    if name not in METHODS:
        return source
    cls, names = METHODS[name]
    old = baseline()['sources'][name]
    def methods(value):
        node = next(n for n in ast.parse(value).body if isinstance(n, ast.ClassDef) and n.name == cls)
        return {n.name: ast.get_source_segment(value, n) for n in node.body if isinstance(n, ast.FunctionDef)}
    current, previous = methods(source), methods(old)
    for method in names:
        source = source.replace(current[method], previous[method], 1)
    if name == 'rpg/app.py':
        source = source.replace('    ' + current['cure_target_hint'] + '\n\n', '', 1)
    return source

def assert_preserved(case):
    if (ROOT/'tests/fixtures/skill_rescue5c_before.json').exists():
        from tests.rescue5c_preservation import assert_preserved as assert_rescue_preserved
        assert_rescue_preserved(case)
        return
    before = baseline()
    for name, digest in before['hashes'].items():
        digest = before.get('concurrent_changes', {}).get(name, {}).get('sha256', digest)
        if name == 'data/skills.json':
            continue
        if name in METHODS:
            case.assertEqual(pre_5b2_source(name, (ROOT/name).read_text(encoding='utf8')), before['sources'][name], name)
        else:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    case.assertEqual(json.loads((ROOT/'data/skills.json').read_text(encoding='utf8')), adjusted_rows(before['skills']))
    for name, change in before.get('concurrent_changes', {}).items():
        allowed = set(change['changed_fields'])
        strip = lambda rows: [{k:v for k,v in row.items() if k not in allowed} for row in rows]
        case.assertEqual(strip(json.loads((ROOT/name).read_text(encoding='utf8'))), strip(change['original_rows']), name)
