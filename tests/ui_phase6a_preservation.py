"""Protect received game data and all logic outside the three UI changes."""
import ast
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT

METHODS = {
    'rpg/elevator.py': {'b15_elevator_point', 'at_b15_elevator'},
    'rpg/dungeon.py': {'Dungeon.can_enter'},
    'rpg/app.py': {'App.skill_details', 'App.draw'},
    'rpg/dungeon_app.py': {'DungeonApp.draw_explore', 'DungeonApp.draw'},
    'rpg/text.py': set(), 'rpg/battle.py': set(), 'rpg/items.py': set(),
}


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/ui_phase6a_before.json').read_text(encoding='utf8'))


@lru_cache(maxsize=1)
def protected_hashes():
    hashes=dict(baseline()['hashes'])
    received=ROOT/'tests/fixtures/b15_elevator_right_assets.json'
    if received.exists():
        hashes.update(json.loads(received.read_text(encoding='utf8'))['hashes'])
    return hashes


class Normalize(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        self.generic_visit(node)
        node.values = [n for n in node.values if not isinstance(n, ast.Constant) or n.value != '']
        return node

    def visit_Constant(self, node):
        if node.value in ('確定', '確定した'):
            node.value = ''
        if node.value == 'B15の入口近くからも拠点へ帰還できる。':
            node.value = 'デーモンがいた場所の右隣から拠点へ帰還できる。'
        return node


@lru_cache(maxsize=32)
def normalized(name, source):
    tree = Normalize().visit(ast.parse(source))
    tree.body = [n for n in tree.body if not (
        isinstance(n, ast.ClassDef) and n.name == 'DescriptionScroll' or
        isinstance(n, ast.FunctionDef) and n.name == 'b15_elevator_open' or
        isinstance(n, ast.Assign) and any(getattr(t, 'id', '') in (
            'B15_ELEVATOR_SPRITE', 'DESCRIPTION_HOLD_FRAMES', 'DESCRIPTION_STEP_FRAMES')
            for t in n.targets))]
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and n.name+'.'+m.name in METHODS[name]:
                    m.body = []
        elif isinstance(n, ast.FunctionDef) and n.name in METHODS[name]:
            n.body = []
        elif isinstance(n, ast.ImportFrom):
            n.names = [a for a in n.names if a.name not in (
                'DescriptionScroll', 'b15_elevator_open', 'B15_ELEVATOR_SPRITE')]
            if name == 'rpg/elevator.py':
                n.names = [a for a in n.names if a.name not in ('PASSABLE', 'TILE_DOOR')]
    return ast.dump(tree, include_attributes=False)


def assert_ui_preserved(case):
    if (ROOT/'tests/fixtures/ui_phase6b1_before.json').exists():
        from tests.ui_phase6b1_preservation import assert_preserved
        return assert_preserved(case)
    before = baseline()
    for name, digest in protected_hashes().items():
        if name in METHODS:
            case.assertEqual(normalized(name, (ROOT/name).read_text(encoding='utf8')),
                             normalized(name, before['sources'][name]), name)
        else:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    case.assertEqual(json.loads((ROOT/'data/skills.json').read_text(encoding='utf8')), before['skills'])
