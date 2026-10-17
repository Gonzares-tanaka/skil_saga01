"""Disclosed deterministic before/after balance fixtures; never reads player saves."""
from collections import Counter, deque
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import random
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rpg.battle import Battle,Session
from rpg.content import load_content
from rpg.dungeon import load_dungeon_settings
from rpg.enemy_actions import load_enemy_actions,choose_enemy_action,action_categories
from rpg.models import Action,Enemy
from tools.enemy_balance_metrics import normal_metrics,weighted_damage,STATS,BASIC,COMMON
from tools.verify_skill_foundation import legacy_case


def party_fixture(content,area,loadout):
    party=deepcopy(content[2])
    ids=(BASIC if loadout=='basic' else COMMON)
    for i,c in enumerate(party):
        for key,value in STATS[area].items(): setattr(c,key,value)
        c.hp=c.max_hp; c.skills.clear(); c.skill_uses.clear(); c.mastered_copies.clear()
        c.learn(content[1][ids[i%3]])
        if loadout=='common' and i==2: c.learn(content[1]['first_aid'])
    return party


def fight(content,rows,floor,seed,loadout):
    profile=load_dungeon_settings()['floors'][floor]
    if 'enemy_ids' not in profile: profile=load_dungeon_settings()['floors'][floor-1]
    rng=random.Random(seed)
    ids=rng.choices(profile['enemy_ids'],profile['weights'],k=rng.randint(*profile['count']))
    enemies=[Enemy.from_definition(rows[sid],max_hp=round(rows[sid]['max_hp']*profile['hp_scale']),
        strength=round(rows[sid]['str']*profile['power_scale']),
        intellect=round(rows[sid]['int']*profile['power_scale'])) for sid in ids]
    b=Battle(party_fixture(content,floor//5+1,loadout),enemies,content[1],rng=random.Random(seed))
    count=enemy_count=0
    received=0; lose_hp=b._lose_hp
    def observed_damage(target,amount):
        nonlocal received
        dealt=lose_hp(target,amount)
        if any(target is c for c in b.party): received+=dealt
        return dealt
    b._lose_hp=observed_damage
    while not b.outcome:
        b.begin_round(b.auto_actions())
        while b.queue:
            side,action=b.queue[0]
            unit=b.party[action.actor] if side=='party' else b.enemies[action]
            if unit.alive:
                count+=side=='party'; enemy_count+=side=='enemy'
            b.step()
    return dict(actions=count,enemy_actions=enemy_count,rounds=b.round,outcome=b.outcome,received=received)


def action_sample(row,defs,ratio=1,n=10000):
    enemy=Enemy.from_definition(row); enemy.hp=round(enemy.max_hp*ratio)
    rng=random.Random(317); recent=[]; counts=Counter(); pairs=Counter()
    for _ in range(n):
        history=[]
        for i in range(enemy.ai.get('actions_per_round',1)):
            ident=choose_enemy_action(enemy,defs,rng,history,recent)
            if ident is None:
                ident='magic' if rng.random()<enemy.magic_chance else 'attack'
            history.append(ident); recent=(recent+[ident])[-3:]; counts[ident]+=1
        if len(history)==2:
            assert history[0]!=history[1]
            tags=[action_categories(defs[k]) for k in history]
            for tag in ('control','major_aoe'): assert sum(tag in t for t in tags)<=1
            pairs[' + '.join(history)]+=1
        # Buffs persist two subsequent rounds, matching the existing duration3.
        enemy.effects={k:(factor,t-1) for k,(factor,t) in enemy.effects.items() if t>1}
        if 'power_up' in history: enemy.effects['power_up']=(defs['power_up'].power,2)
    return dict(rounds=n,actions=sum(counts.values()),counts=dict(counts),
        percentages={k:round(v/sum(counts.values())*100,2) for k,v in counts.items()},
        aoe_percent=round(sum(v for k,v in counts.items() if 'major_aoe' in action_categories(defs[k]))/sum(counts.values())*100,2),
        pairs=dict(pairs))


def boss_fights(content,row,area,loadout,n=100):
    results=[]
    for seed in range(n):
        party=party_fixture(content,area,loadout)
        if area==1:
            # A prepared B5 party: still only BASIC/COMMON, no rare prerequisite.
            for c in party:
                c.hp=c.max_hp=100; c.strength=16; c.agility=18; c.intellect=18
        b=Battle(party,[Enemy.from_definition(row)],content[1],boss=True,rng=random.Random(seed))
        while not b.outcome:
            b.begin_round(b.auto_actions())
            while b.queue: b.step()
        results.append(dict(outcome=b.outcome,rounds=b.round))
    return dict(wins=sum(r['outcome']=='VICTORY' for r in results),total=n,
                mean_rounds=round(statistics.mean(r['rounds'] for r in results),3))


def main():
    content=load_content(); defs=load_enemy_actions(); settings=load_dungeon_settings()
    before=json.loads((ROOT/'tests/fixtures/enemy_balance_before.json').read_text(encoding='utf8'))
    old={r['id']:r for r in before['enemies']}; new={r['id']:r for r in content[3]}
    normal=[sid for sid,r in new.items() if not r.get('boss')]
    atk_old=normal_metrics(before['enemies'],settings,content[1],content[2])
    atk_new=normal_metrics(content[3],settings,content[1],content[2])
    stats=[]
    for sid in normal:
        a,b=old[sid],new[sid]
        d0,d1=weighted_damage(a,defs),weighted_damage(b,defs)
        stats.append(dict(id=sid,name=b['name'],before=a,after=b,
            hp_increase_percent=round((b['max_hp']/a['max_hp']-1)*100,2),
            expected_per_target_damage_before=round(d0,3),expected_per_target_damage_after=round(d1,3),
            expected_damage_increase_percent=round((d1/d0-1)*100,2),
            atk_before=atk_old[sid],atk_after=atk_new[sid]))
    areas={}; tempo={}
    for area in (1,2,3):
        ids=set()
        for floor in range((area-1)*5,min(area*5,14)):
            profile=settings['floors'][floor]
            if 'enemy_ids' not in profile: profile=settings['floors'][floor-1]
            ids.update(profile['enemy_ids'])
        items=[r for r in stats if r['id'] in ids]
        areas[area]=dict(enemy_ids=sorted(ids),
            mean_hp_percent=round(statistics.mean(r['hp_increase_percent'] for r in items),2),
            mean_damage_percent=round(statistics.mean(r['expected_damage_increase_percent'] for r in items),2))
        tempo[area]={}
        for loadout in ('basic','common'):
            trials=[(floor,1000+floor*100+seed) for floor in range((area-1)*5,min(area*5,14)) for seed in range(60)]
            pair=[]
            for rows in (old,new): pair.append([fight(content,rows,floor,seed,loadout) for floor,seed in trials])
            result={}
            for label,values in zip(('before','after'),pair):
                result[label]=dict(mean_party_actions=round(statistics.mean(v['actions'] for v in values),3),
                    mean_enemy_actions=round(statistics.mean(v['enemy_actions'] for v in values),3),
                    mean_rounds=round(statistics.mean(v['rounds'] for v in values),3),
                    mean_received=round(statistics.mean(v['received'] for v in values),3),
                    received_per_enemy_action=round(sum(v['received'] for v in values)/sum(v['enemy_actions'] for v in values),3),
                    wins=sum(v['outcome']=='VICTORY' for v in values),total=len(values))
            tempo[area][loadout]=result
    print('PASS: normal table simulations',sum(v['basic']['after']['total'] for v in tempo.values())*4,flush=True)
    bosses={sid:dict(before=old[sid],after=row,sample=action_sample(row,defs)) for sid,row in new.items() if row.get('boss')}
    lord='lord_of_elysion'
    bosses[lord]['old_sample']=action_sample(old[lord],defs)
    bosses[lord]['phases']={str(ratio):action_sample(new[lord],defs,ratio) for ratio in (1,.5,.25)}
    b5={loadout:boss_fights(content,new['guardian'],1,loadout) for loadout in ('basic','common')}
    assert b5['common']['wins']==b5['common']['total'],b5
    assert b5['basic']['wins']>=90,b5  # BASIC-only auto-play is deliberately less reliable.
    # Committed traces permit reruns from a fresh checkout without private backups.
    legacy=json.loads((ROOT/'tests/fixtures/enemy_balance_skill_traces.json').read_text(encoding='utf8'))['traces']
    comparisons=0
    for sid in content[1]:
        for seed in (9,817):
            for mode in ('plain','buff','debuff','last_use'):
                for mastered in (False,True):
                    value=legacy_case(Battle,content,sid,seed,mode,mastered)
                    digest=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
                    assert legacy[f'{sid}|{seed}|{mode}|{int(mastered)}']==digest,(sid,seed,mode,mastered)
                    comparisons+=1
    report=dict(party_stat_fixtures=STATS,basic_skills=BASIC,common_skills=COMMON,
        normal=stats,areas=areas,tempo=tempo,bosses=bosses,b5_no_rare=b5,
        player_skill_exact_comparisons=comparisons,physical_gkd_tested=False,
        limitations=['Prepared fixtures, not a natural-growth run or real saves.',
          'ATK excludes +/-10% RNG and guard; actual tempo includes all actions/status/AI.',
          'Per-area averages count each enemy appearing in that area once; not encounter-weighted.',
          'B5 no-rare fixture: HP100 STR16 AGI18 INT18; B5 comparison does not imply starting-party victory.'])
    path=ROOT/'verification/enemy_balance.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',comparisons,'exact player skill traces; B5 no-rare',b5,flush=True)


if __name__=='__main__': main()
