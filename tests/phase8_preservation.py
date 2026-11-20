"""Protect the beta tester's received tree, allowing only the requested Phase 8 edits."""
import ast
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT

METHODS={
 'rpg/app.py':{'__init__','handle_quit_input','commit','update','update_amrita_effect','draw_info','draw_skills','draw_battle','draw_replacement','mastered_label'},
 'rpg/dungeon_app.py':{'update','update_final_event','activate_suspended_game','draw_camp_resources'},
 'rpg/models.py':{'forget'},'rpg/growth.py':{'growth_bonus'},'rpg/content.py':{'load_content'},
 'rpg/exploration.py':{'make_quest'},'rpg/quests.py':{'load_quest_settings'},
 'rpg/battle.py':{'__init__','step','hp_stage_feedback'},
 'rpg/postgame.py':{'load_postgame_data'},'rpg/postgame_ui.py':{'begin_dragon_battle','restore_final_victory'},
}


@lru_cache(maxsize=1)
def baseline():return json.loads((ROOT/'tests/fixtures/phase8_before.json').read_text(encoding='utf8'))


def stable(source,allowed):
    # Phase 9B changes only this save-candidate call, not other ending logic.
    source=source.replace('restore_final_victory(self.final_checkpoint,s,d,e)',
                          'self.final_checkpoint.restore(s,d,e)')
    tree=ast.parse(source)
    def keep(nodes):return [n for n in nodes if not isinstance(n,ast.FunctionDef) or n.name not in allowed]
    tree.body=keep(tree.body)
    for node in tree.body:
        if isinstance(node,ast.ClassDef):node.body=keep(node.body)
    tree.body=[n for n in tree.body if not isinstance(n,ast.ImportFrom)]
    return ast.dump(tree,include_attributes=False)


def assert_preserved(case):
    before=baseline()
    replacements={'skills.json':{'独義理':'毒霧','敵の走行':'敵の装甲','帰還にする':'帰還する'},
                  'enemies.json':{'欲っする':'欲する'},'pub_messages.json':{'SKILL SEAKERS':'SKILL SEEKERS'},
                  'finale.json':{'イビルナイトが倒れた。':'デーモンガードが倒れた。',
                                 'キュクロープスが崩れ落ちた。':'レッドドラゴンが崩れ落ちた。'}}
    for name,old in before['data'].items():
        current=json.loads((ROOT/'data'/name).read_text(encoding='utf8'))
        expected=deepcopy(old)
        if name in replacements:
            raw=json.dumps(expected,ensure_ascii=False)
            for a,b in replacements[name].items():raw=raw.replace(a,b)
            expected=json.loads(raw)
        for field in {'settings.json':('character_int_growth',),'quests.json':('target_floors',),
                      'postgame.json':('hp_stage_messages',)}.get(name,()):
            current.pop(field,None);expected.pop(field,None)
        case.assertEqual(current,expected,name)
    for name,digest in before['hashes'].items():
        if name.startswith('data/') or name=='README.md':continue
        if 'save' in name.split('/'):continue # Never read or copy a user's save into a test fixture.
        if name in METHODS:
            case.assertEqual(stable((ROOT/name).read_text(encoding='utf8'),METHODS[name]),
                             stable(before['sources'][name],METHODS[name]),name)
        else:
            payload=(ROOT/name).read_bytes()
            if name=='main.py':
                # Author-approved metadata only; the executable source is protected.
                payload=payload.replace(
                    b'# license: Copyright (c) 2026 GONZARES TANAKA. All rights reserved.',
                    b'# license: TBD')
            case.assertEqual(hashlib.sha256(payload).hexdigest(),digest,name)
