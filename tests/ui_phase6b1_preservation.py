"""Narrow UI authorization over the exact received working tree."""
import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from rpg.content import ROOT

NAMES = {'return': 'リターン', 'revive': 'リバイブ'}
UI_METHODS = {
    'rpg/dungeon_app.py': {'update', 'draw', 'draw_camp', 'draw_facility', 'draw_archive',
                         'draw_menu', 'draw_items', 'draw_shop', 'draw_pub',
                         'draw_camp_resources', 'draw_field_ui', 'draw_help',
                         'feedback_options', 'draw_treasure_debug', 'draw_travel'},
}


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT / 'tests/fixtures/ui_phase6b1_before.json').read_text(encoding='utf8'))


def renamed_skill_rows(rows):
    rows = deepcopy(rows)
    for row in rows:
        if row['id'] in NAMES:
            row['name'] = NAMES[row['id']]
    return rows


def normalized(name, source):
    # Only localized lift notices vary outside the explicitly tested UI methods.
    source = source.replace('エレベーター', 'エレベータ').replace('城下町のパブへ', '城下町のPUBへ')
    source = source.replace('"SPARK / 操作"', '"ヘルプ / 操作"')
    source = source.replace('self.tell("RETURNは探索メニューから使用")',
                            'self.tell(skill.name + "は探索メニューから使用")')
    source = source.replace('raise ValueError("生存者の使用可能なRETURNが必要です。")',
                            '''raise ValueError(f"生存者の使用可能な{self.skills['return'].name}が必要です。")''')
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            node.body = [m for m in node.body if not (
                isinstance(m, ast.FunctionDef) and name == 'rpg/dungeon_app.py'
                and m.name == 'draw_field_quest')]
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and method.name in UI_METHODS.get(name, set()):
                    method.body = []
        elif isinstance(node, ast.ImportFrom):
            node.names = [a for a in node.names if a.name not in ('HUB_FACILITY_LABELS', 'HUB_MENU_LABELS')]
    tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign)
        and any(getattr(t, 'id', '') in ('HUB_FACILITY_LABELS', 'HUB_MENU_LABELS', 'EXPLORATION_MENU')
                for t in node.targets))]
    return ast.dump(tree, include_attributes=False)


def assert_preserved(case):
    if (ROOT/'tests/fixtures/quest_reaccept_before.json').exists():
        from tests.quest_reaccept_preservation import assert_preserved as assert_reaccept_preserved
        return assert_reaccept_preserved(case)
    before = baseline()
    for name, digest in before['hashes'].items():
        # Real player files are protected by the final source-tree hash check;
        # isolated test runs deliberately do not copy them into their game.
        if 'save' in Path(name).parts:
            continue
        if name in ('README.md', 'dist/index.html', 'data/skills.json'):
            continue
        if name in before['sources']:
            case.assertEqual(normalized(name, (ROOT / name).read_text(encoding='utf8')),
                             normalized(name, before['sources'][name]), name)
        else:
            case.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)
    case.assertEqual(json.loads((ROOT / 'data/skills.json').read_text(encoding='utf8')),
                     renamed_skill_rows(before['skills']))
