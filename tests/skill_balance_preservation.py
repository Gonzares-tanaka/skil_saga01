"""Narrow 5B-1 authorization, relative to the received 5A working tree."""
import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT
from tests.skill_balance5b2_preservation import adjusted_rows, assert_preserved as assert_5b2_preserved


CHANGES = {
    'double_slash': {'str_scale': 1.15},
    'triple_slash': {'str_scale': 1.0},
    'rapid_edge': {'str_scale': .35, 'agi_scale': .65},
    'seven_slash': {'agi_scale': .15, 'description': 'STR0.55+AGI0.15で七連撃。'},
    'full_heal': {'description': 'INTの10倍を回復。初期2回。'},
}

# Only the damage numeral differs in these otherwise identical visual traces.
NUMERIC_TRACES = {
    'triple_slash': '451c5a98bef91b42f7f80c2416793fc8d6f02958e39dd9ad6a91f1b2adfddffd',
    'rapid_edge': '9455a27a92f2ac866a1f9131610009912f560029401d00578db5ab67e6f7f3f8',
    'seven_slash': '06c2d1acd216363ec7cce976db469e4bee5f9e7b6bacd5ca7426b8a9917166ff',
}


def adjusted_skill_rows(rows):
    """Update only authorized fields in historical visual-parity fixtures.

    Old fixture files remain untouched. Visual/rule parity uses current damage;
    old/new balance comparisons are separately tested against the 5A snapshot.
    """
    rows = deepcopy(rows)
    for row in rows:
        row.update(CHANGES.get(row['id'], {}))
    return adjusted_rows(rows)


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/skill_balance5b1_before.json').read_text(encoding='utf8'))


def method_source(source, cls, method):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return ast.get_source_segment(source, next(n for n in node.body
        if isinstance(n, ast.FunctionDef) and n.name == method))


def assert_skill_balance_preserved(case):
    # 5B-2 received additional user changes after the historical 5B-1 snapshot.
    # Protect the complete received tree against the newer exact snapshot.
    if (ROOT/'tests/fixtures/skill_balance5b2_before.json').exists():
        assert_5b2_preserved(case)
        return
    before = baseline()
    editable = {'rpg/models.py': ('Skill', 'power'), 'rpg/app.py': ('App', 'draw_replacement')}
    for name, digest in before['hashes'].items():
        if name in editable or name == 'data/skills.json':
            continue
        case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    for name, (cls, method) in editable.items():
        source = (ROOT/name).read_text(encoding='utf8')
        old = before['sources'][name]
        restored = source.replace(method_source(source, cls, method), method_source(old, cls, method), 1)
        case.assertEqual(restored, old, name)
    case.assertEqual(json.loads((ROOT/'data/skills.json').read_text(encoding='utf8')),
                     adjusted_skill_rows(before['skills']))
