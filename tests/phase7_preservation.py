"""Preserve received data/resources and non-extension code during Phase 7."""
import ast
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from rpg.content import ROOT

METHODS={
 'rpg/dungeon.py':{'__init__'},
 'rpg/app.py':{'draw_battle'},
 'rpg/save.py':{'make_save_data','prepare_saved_game','read_completion'},
 'rpg/quests.py':{'quest_spawn_report'},
 'rpg/dungeon_app.py':{'__init__','start_new_game','update_suspend_io','finish_results','sync_scene_audio',
     'update','draw','draw_explore','update_camp_resources','draw_camp_resources','quest_or_field_event',
     'update_final_event','draw_final_event'},
 'rpg/sound.py':set(),
}


@lru_cache(maxsize=1)
def baseline():return json.loads((ROOT/'tests/fixtures/phase7_before.json').read_text(encoding='utf8'))


def stable_tree(name,source):
    tree=ast.parse(source)
    for node in tree.body:
        if isinstance(node,ast.ClassDef):
            node.bases=[b for b in node.bases if getattr(b,'id','')!='PostgameMixin']
            node.body=[m for m in node.body if not isinstance(m,ast.FunctionDef) or m.name not in METHODS[name]]
    tree.body=[n for n in tree.body if not (
        isinstance(n,ast.ImportFrom) and n.module in ('postgame','postgame_ui') or
        isinstance(n,ast.FunctionDef) and n.name in METHODS[name] or
        name=='rpg/sound.py' and isinstance(n,ast.Assign) and any(
            getattr(t,'id','') in ('BGM_IDS','BATTLE_BGM','RESOURCE_BANKS') for t in n.targets))]
    return ast.dump(tree,include_attributes=False)


def assert_preserved(case):
    before=baseline()
    for name,digest in before['hashes'].items():
        if 'save' in Path(name).parts:continue
        if name in METHODS:
            case.assertEqual(stable_tree(name,(ROOT/name).read_text(encoding='utf8')),
                stable_tree(name,before['sources'][name]),name)
        elif name=='README.md':
            case.assertTrue((ROOT/name).read_text(encoding='utf8').startswith(before['readme']))
        else:case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
    # All existing music/SE routes stay identical; additions are explicit.
    def routes(source):
        tree=ast.parse(source);result={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and getattr(node.targets[0],'id','') in ('BGM_IDS','BATTLE_BGM','RESOURCE_BANKS'):
                result[node.targets[0].id]={ast.literal_eval(k):ast.dump(v) for k,v in zip(node.value.keys,node.value.values)}
        return result
    old=routes(before['sources']['rpg/sound.py']);new=routes((ROOT/'rpg/sound.py').read_text(encoding='utf8'))
    for key,mapping in old.items():
        for ident,value in mapping.items():case.assertEqual(new[key][ident],value,(key,ident))
