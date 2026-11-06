"""Fixed-seed simulations with disclosed hypothetical parties, real battle rules."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rpg.battle import Battle,Session
from rpg.content import load_content
from rpg.models import Action
from rpg.postgame import load_postgame_data,dragon_enemy
from rpg.enemy_actions import load_enemy_actions,EnemyAction


def simulate(seed,kind,hp,stat):
    s=Session(*load_content(),seed=seed);data=load_postgame_data()
    loadouts={
        'physical':('power_strike','double_slash','triple_slash','armor_break','first_aid','counter'),
        'speed':('quick_hit','quick_stab','wind_blade','wild_edge','slow','first_aid'),
        'magic':('fire','ice','thunder','drain','heal','focus'),
    }
    for i,c in enumerate(s.party):
        for sid in list(c.skills):c.forget(sid)
        c.max_hp=c.hp=hp;c.strength=c.agility=c.intellect=stat
        skills=list(loadouts[kind])
        if i==2:skills=['fire','heal','mending_wind','weaken','focus_field','first_aid']
        if i==3:skills=['power_strike','battle_cry','armor_break','revive','first_aid','guard_up']
        for sid in skills:c.learn(s.skills[sid])
    definitions=load_enemy_actions();definitions.update({k:EnemyAction(**v) for k,v in data['actions'].items()})
    b=Battle(s.party,[dragon_enemy(data)],s.skills,max_rounds=data['max_rounds'],rng=s.rng,
             inventory=s.inventory,boss=True,enemy_actions=definitions)
    counts=Counter()
    while not b.outcome:
        actions=b.auto_actions()
        for index,action in enumerate(actions):
            c=s.party[action.actor]
            if b.round<2 and action.actor==3:
                sid='battle_cry' if b.round==0 else 'armor_break'
                if sid in c.skills and c.skill_uses.get(sid,0):actions[index]=Action(action.actor,'SKILL',0,sid)
            if c.hp<c.max_hp*.12 and action.kind=='SKILL' and s.skills[action.skill_id].effect not in ('heal','drain'):
                actions[index]=Action(action.actor,'GUARD')
        for action in actions:counts[action.skill_id or action.kind]+=1
        b.begin_round(actions)
        for _ in range(200):
            if not b.queue or b.outcome:break
            b.step()
        else:raise AssertionError('unbounded battle queue')
    return dict(seed=seed,outcome=b.outcome,turns=b.round,enemy_hp=b.enemies[0].hp,
                surviving=sum(c.alive for c in s.party),actions=dict(counts))


def main():
    results=[]
    for kind,hp,stat in (('physical',250,35),('physical',650,80),('speed',650,80),('magic',650,80)):
        trials=[simulate(seed,kind,hp,stat) for seed in range(10)]
        results.append(dict(kind=kind,hypothetical_hp=hp,hypothetical_all_stats=stat,
            victories=sum(t['outcome']=='VICTORY' for t in trials),trials=trials))
    assert all(r['victories']>0 for r in results[1:])
    output=dict(enemy_definition_unchanged=True,party_values_are_assumptions_not_measured_players=True,
                no_legend_required=True,sleep_not_used=True,cases=results)
    (ROOT/'verification/phase7_dragon_simulation.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for row in results:
        wins=[t['turns'] for t in row['trials'] if t['outcome']=='VICTORY']
        print(row['kind'],row['hypothetical_hp'],row['hypothetical_all_stats'],'wins',row['victories'],'/10','turns',wins)


if __name__=='__main__':main()
