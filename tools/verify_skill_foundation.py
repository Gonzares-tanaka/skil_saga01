"""Compare all legacy skills to pre-foundation Battle and verify real PC UI/save."""
from collections import deque, Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import sys
from types import ModuleType
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Action, Enemy
from rpg.save import make_save_data, apply_save_data, SAVE_VERSION
from rpg.text import text_width, FONT_HEIGHT


def snapshot(b, messages):
    def unit(c):
        fields=('hp','max_hp','strength','agility','intellect','effects','statuses','guarding','berserk')
        result={k:deepcopy(getattr(c,k)) for k in fields}
        if hasattr(c,'skills'):
            for k in ('skills','skill_uses','cooldowns','used_skills','category_uses','growth_points','mastered_copies'):
                value=deepcopy(getattr(c,k)); result[k]=sorted(value) if isinstance(value,set) else value
            result['counter']=c.counter.id if c.counter else None
        return result
    return dict(messages=messages,party=[unit(c) for c in b.party],enemies=[unit(e) for e in b.enemies],
                discovered=sorted(b.discovered_skills),mastered=sorted(b.mastered_skills),
                resource_events=b.resource_events,sound=b.sound_cue,outcome=b.outcome,
                queue=[(side,asdict(action) if side=='party' else action) for side,action in b.queue],
                rng=repr(b.rng.getstate()))


def legacy_case(cls, content, sid, seed, mode, mastered):
    settings,skills,party,rows=deepcopy(content)
    enemy=Enemy('TEST',500,16,8,14,(0,0),defense=7,magic_defense=11)
    for c in party: c.max_hp=200; c.hp=75
    actor=party[0]; actor.strength=19; actor.agility=17; actor.intellect=23
    if sid not in actor.skills: actor.learn(skills[sid])
    known=set(actor.skills); marks={sid} if mastered else set()
    actor.mastered_skills=marks
    if mastered:
        actor.forget(sid); actor.learn(skills[sid])
    target=1 if skills[sid].target=='ally' else 0
    if skills[sid].effect=='revive': party[1].hp=0
    if mode=='buff': actor.effects={'power_up':(1.4,3),'focus':(1.5,3)}; actor.berserk=3; enemy.guarding=True
    if mode=='debuff': actor.effects={'weaken':(.8,3)}; enemy.effects={'armor_break':(.7,3),'guard_up':(.7,3)}
    if mode=='last_use': actor.skill_uses[sid]=1
    b=cls(party,[enemy],skills,rng=random.Random(seed),discovered_skills=known,mastered_skills=marks)
    b.round=1; b.queue=deque([('party',Action(0,'SKILL',target,sid)),('party',Action(1,'GUARD'))])
    lines=[]
    while b.queue: lines.extend(b.step())
    return snapshot(b,lines)


def main():
    backup=ROOT/'verification/backups/skill_foundation'
    old=ModuleType('rpg._skill_foundation_before'); old.__package__='rpg'
    exec(compile((backup/'battle.py').read_text(encoding='utf8'),str(backup/'battle.py'),'exec'),old.__dict__)
    current=load_content()
    legacy_ids={row['id'] for row in json.loads((ROOT/'tests/fixtures/player_skills_31.json').read_text(encoding='utf8'))}
    content=(current[0],{sid:skill for sid,skill in current[1].items() if sid in legacy_ids},current[2],current[3])
    comparisons=0
    for sid in content[1]:
        for seed in (1,9,817):
            for mode in ('plain','buff','debuff','last_use'):
                for mastered in (False,True):
                    before=legacy_case(old.Battle,content,sid,seed,mode,mastered)
                    after=legacy_case(Battle,content,sid,seed,mode,mastered)
                    assert before==after,(sid,seed,mode,mastered)
                    comparisons+=1
    # Legacy field results/RESTORE conditions and seeded sparks remain identical.
    old_session=old.Session(*deepcopy(content),seed=19)
    new_session=Session(*deepcopy(content),seed=19)
    field_cases=0
    for sid in ('first_aid','heal','renew','full_heal'):
        for situation in ('injured','full','dead','last'):
            a=old.Session(*deepcopy(content),seed=19); b=Session(*deepcopy(content),seed=19)
            for s in (a,b):
                s.party[0].learn(s.skills[sid]); s.party[1].hp=0 if situation=='dead' else s.party[1].max_hp if situation=='full' else 1
                if situation=='last': s.party[0].skill_uses[sid]=1
            assert a.field_heal(0,sid,1)==b.field_heal(0,sid,1),(sid,situation)
            assert asdict(a.party[0])==asdict(b.party[0]) and asdict(a.party[1])==asdict(b.party[1])
            field_cases+=1
    old_model=ModuleType('rpg._skill_model_before'); old_model.__package__='rpg'
    sys.modules[old_model.__name__]=old_model
    exec(compile((backup/'models.py').read_text(encoding='utf8'),str(backup/'models.py'),'exec'),old_model.__dict__)
    raw=json.loads((ROOT/'tests/fixtures/player_skills_31.json').read_text(encoding='utf8'))
    for row in raw:
        before=old_model.Skill(**row); after=content[1][row['id']]
        assert (before.can_relearn,before.relearn_cost,before.relearn_uses)==(after.can_relearn,after.relearn_cost,after.relearn_uses)
        assert before.formula()==after.formula() and before.mastery_label==after.mastery_label
        for actor in content[2]:
            assert before.power(actor)==after.power(actor),(row['id'],actor.name)
    assert len([s for s in content[1].values() if s.can_relearn])==15
    for _ in range(20):
        for s in (old_session,new_session):
            s.next_battle([Enemy('TEST',1,1,1,1,(0,0))]).outcome='VICTORY'; s.settle()
            for i in list(s.pending_replacements): s.resolve_replacement(i,None)
        assert old_session.results==new_session.results
        assert [asdict(c) for c in old_session.party]==[asdict(c) for c in new_session.party]
        assert old_session.rng.getstate()==new_session.rng.getstate()
    allowed={'rpg/models.py','rpg/content.py','rpg/battle.py','rpg/statuses.py',
             'rpg/app.py','rpg/dungeon_app.py','rpg/labels.py','rpg/battle_presentation.py','data/skills.json','rpg/sound.py'}
    assert json.loads((ROOT/'data/skills.json').read_text(encoding='utf8'))[:31]==raw
    hashes=json.loads((backup/'hashes.json').read_text(encoding='utf8'))
    protected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
               for name,digest in hashes.items() if name not in allowed}
    assert all(protected.values()),[n for n,ok in protected.items() if not ok]
    pyxel.init(160,120,headless=True)
    with patch.object(pyxel,'init'):
        app=DungeonApp(Session(*deepcopy(content),seed=77),run=False,headless=True,start_at_title=False)
    fixture=json.loads((ROOT/'tests/fixtures/skill_foundation_save_v1.json').read_text(encoding='utf8'))
    apply_save_data(app,deepcopy(fixture)); assert make_save_data(app)==fixture
    assert SAVE_VERSION==1 and app.session.party[0].skill_uses['fire']==7
    calls=0; original=pyxel.text
    def bounded(x,y,value,color,font):
        nonlocal calls
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        calls+=1; original(x,y,value,color,font)
    with patch.object(pyxel,'text',side_effect=bounded):
        for page in (0,1):
            app.state='archive'; app.archive_page=page; app.archive_cursor=0; app.draw()
    report=dict(legacy_battle_comparisons=comparisons,legacy_field_comparisons=field_cases,
                seeded_victories_equal=20,restore_exact=15,roster_total=len(content[1]),
                rarities=dict(Counter(s.rarity for s in content[1].values())),
                protected_files=protected,old_save_equal=True,save_version=SAVE_VERSION,
                bounded_text_calls=calls,physical_ios_tested=False,physical_gkd_tested=False)
    (ROOT/'verification/skill_foundation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',comparisons,'legacy battles,',field_cases,'field cases, 20 seeded victories, 15 restores, old SAVE,',len(protected),'protected files')


if __name__=='__main__': main()
