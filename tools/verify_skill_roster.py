"""Before/after legacy comparison and bounds checks for the 62-skill build."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_skill_foundation import legacy_case
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.save import apply_save_data, make_save_data, SAVE_VERSION
from rpg.text import text_width, FONT_HEIGHT
import pyxel


def main():
    backup=ROOT/'verification/backups/skill_roster/battle.py'
    old=ModuleType('rpg._before_roster'); old.__package__='rpg'
    exec(compile(backup.read_text(encoding='utf8'),str(backup),'exec'),old.__dict__)
    original=json.loads((ROOT/'tests/fixtures/player_skills_31.json').read_text(encoding='utf8'))
    raw=json.loads((ROOT/'data/skills.json').read_text(encoding='utf8'))
    assert raw[:31]==original and len(raw)==62
    content=load_content(); comparisons=0
    for row in original:
        for seed in (1,9,817):
            for mode in ('plain','buff','debuff','last_use'):
                for mastery in (False,True):
                    assert legacy_case(old.Battle,content,row['id'],seed,mode,mastery)==legacy_case(Battle,content,row['id'],seed,mode,mastery),(row['id'],seed,mode,mastery)
                    comparisons+=1
    field_cases=0
    for sid in ('first_aid','heal','renew','full_heal'):
        for situation in ('injured','full','dead','last'):
            a=old.Session(*deepcopy(content),seed=19); b=Session(*deepcopy(content),seed=19)
            for s in (a,b):
                s.party[0].learn(s.skills[sid]); s.party[1].hp=0 if situation=='dead' else s.party[1].max_hp if situation=='full' else 1
                if situation=='last': s.party[0].skill_uses[sid]=1
            assert a.field_heal(0,sid,1)==b.field_heal(0,sid,1)
            assert asdict(a.party[0])==asdict(b.party[0]) and asdict(a.party[1])==asdict(b.party[1])
            field_cases+=1
    protected=json.loads((ROOT/'tests/fixtures/player_skill_roster_protected.json').read_text(encoding='utf-8-sig'))
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
               for name,digest in protected.items() if name!='rpg/sound.py')
    pyxel.init(160,120,headless=True)
    with patch.object(pyxel,'init'):
        app=DungeonApp(Session(*deepcopy(content),seed=77),run=False,headless=True,start_at_title=False)
    saved=json.loads((ROOT/'tests/fixtures/skill_foundation_save_v1.json').read_text(encoding='utf8'))
    apply_save_data(app,deepcopy(saved)); assert make_save_data(app)==saved and SAVE_VERSION==1
    app.session.discovered_skills.update(app.session.skills)
    calls=0; original_text=pyxel.text
    def bounded(x,y,value,color,font):
        nonlocal calls
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        calls+=1; original_text(x,y,value,color,font)
    with patch.object(pyxel,'text',side_effect=bounded):
        app.state='archive'; app.archive_page=0; app.draw()
        app.archive_page=1
        for i in range(62): app.archive_cursor=i; app.draw()
        app.enter_dungeon(); app.begin_encounter(); app.begin_input()
        actor=app.session.party[0]
        for sid,skill in app.session.skills.items():
            for known in list(actor.skills): actor.forget(known)
            actor.learn(skill); app.skill_cursor=0; app.state='skill'; app.draw()
            app.selected_skill=skill; app.target_cursor=0
            if skill.target in ('enemy','ally') and app.targets():
                app.state='target'; app.draw()
    report=dict(total=62,rarities=dict(Counter(s.rarity for s in content[1].values())),
                restore_count=sum(s.can_relearn for s in content[1].values()),
                legacy_rows_identical=31,legacy_battle_comparisons=comparisons,
                legacy_field_comparisons=field_cases,protected_file_count=len(protected),
                old_save_exact=True,save_version=SAVE_VERSION,bounded_text_calls=calls,
                physical_ios_tested=False,physical_gkd_tested=False)
    (ROOT/'verification/skill_roster.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',comparisons,'legacy actions,',field_cases,'legacy field cases,',len(protected),'protected files;',calls,'bounded text calls')


if __name__=='__main__': main()
