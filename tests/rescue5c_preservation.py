"""Protect the received 5B-2 tree; only rescue identity, notices and helpers vary."""
import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT

METHODS = {
    'rpg/models.py': set(),
    'rpg/content.py': {'load_content'},
    'rpg/save.py': {'prepare_saved_game'},
    'rpg/battle.py': {'Session.__init__','Session.next_battle','Session.resolve_replacement'},
    'rpg/app.py': {'App.update','App.draw','App.draw_replacement'},
    'rpg/dungeon_app.py': {'DungeonApp.update','DungeonApp.draw'},
    'rpg/skill_resources.py': {'ensure_attack'},
}
ADDED = {'App.update_rescue_notice','App.draw_rescue_notice'}


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/skill_rescue5c_before.json').read_text(encoding='utf8'))


def adopted_skill_rows(rows):
    """Preserve the user's finalized name/description edits, never rule data."""
    rows=deepcopy(rows)
    change=baseline().get('concurrent_changes',{}).get('data/skills.json',{})
    final={r['id']:r for r in change.get('received_rows',[])}
    for row in rows:
        for key in change.get('changed_fields',{}).get(row['id'],[]):
            assert key in ('name','description')
            row[key]=final[row['id']][key]
    if (ROOT/'tests/fixtures/ui_phase6b1_before.json').exists():
        from tests.ui_phase6b1_preservation import renamed_skill_rows
        rows = renamed_skill_rows(rows)
    return rows


@lru_cache(maxsize=32)
def normalized(name, source):
    tree=ast.parse(source)
    # Preserve all AST outside the explicitly authorized functions/additions.
    for n in tree.body:
        if isinstance(n,ast.ClassDef):
            n.body=[m for m in n.body if not isinstance(m,ast.FunctionDef) or n.name+'.'+m.name not in ADDED]
            for m in n.body:
                if isinstance(m,ast.FunctionDef) and n.name+'.'+m.name in METHODS[name]: m.body=[]
            if name=='rpg/models.py' and n.name=='Character':
                n.body=[m for m in n.body if not isinstance(m,ast.AnnAssign) or getattr(m.target,'id',None)!='party_id']
        elif isinstance(n,ast.FunctionDef) and n.name in METHODS[name]: n.body=[]
        elif isinstance(n,ast.ImportFrom):
            n.names=[x for x in n.names if x.name not in ('PARTY_IDS','FALLBACK_SKILLS','FALLBACK_SKILL')]
    tree.body=[n for n in tree.body if not isinstance(n,ast.Assign) or not any(
        getattr(t,'id',None) in ('PARTY_IDS','FALLBACK_SKILLS','RESCUE_SKILLS') for t in n.targets)]
    return ast.dump(tree,include_attributes=False)


def assert_preserved(case):
    if (ROOT/'tests/fixtures/ui_phase6a_before.json').exists():
        from tests.ui_phase6a_preservation import assert_ui_preserved
        return assert_ui_preserved(case)
    before=baseline()
    for name,digest in before['hashes'].items():
        digest=before.get('concurrent_changes',{}).get(name,{}).get('sha256',digest)
        if name in METHODS:
            case.assertEqual(normalized(name,(ROOT/name).read_text(encoding='utf8')),
                             normalized(name,before['sources'][name]),name)
        elif name=='README.md':
            original=before['sources'][name]
            expected=''.join(line for line in original.splitlines(True) if not line.startswith('**試作用の救済**'))
            case.assertEqual((ROOT/name).read_text(encoding='utf8'),expected)
        else:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
    case.assertEqual(json.loads((ROOT/'data/skills.json').read_text(encoding='utf8')),
                     adopted_skill_rows(before['skills']))
