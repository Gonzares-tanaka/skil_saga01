"""Paired growth trials and authored-map quest routes; never reads player saves."""
from collections import deque
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from random import Random
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from tests.encounter_fixture import EncounterFixture
    from rpg.growth import grow_and_spark, growth_bonus
    from rpg.content import load_content
    from rpg.quests import spawn_candidates
    from rpg.tiles import PASSABLE, PIT_TILES, TILE_DOOR, TILE_SWITCH, TILE_GUARDIAN, TILE_ENTRANCE, TILE_STAIRS_UP, TILE_STAIRS_DOWN
    EncounterFixture.setUpClass();fixture=EncounterFixture();fixture.setUp()
    try:
        a=fixture.a;s=a.session;d=a.dungeon
        old=deepcopy(s.settings);old.pop('character_int_growth');old['spark_chance']=0
        new=deepcopy(s.settings);new['spark_chance']=0
        growth=[]
        for sid in ('fire','quick_hit'):
            skill=s.skills[sid]
            def prepare(c):
                c.growth_points={k:v*3 for k,v in skill.growth.items()}
                c.category_uses={skill.skill_type:3}
            probabilities={}
            for c in s.party:
                c=deepcopy(c);prepare(c)
                probabilities[c.party_id]=[round(old['growth_rates'][c.growth_type]['INT']+growth_bonus(c,'INT',config),6)
                                           for config in (old,new)]
            rows={n:{'before':[],'after':[]} for n in (50,100,200)}
            unchanged=True
            for seed in range(200):
                parties=[deepcopy(s.party),deepcopy(s.party)]
                streams=[[Random(80000+seed*4+i) for i in range(4)] for _ in (old,new)]
                for n in range(1,201):
                    for variant,config in enumerate((old,new)):
                        for i,c in enumerate(parties[variant]):
                            prepare(c);grow_and_spark(c,s.skills,config,streams[variant][i],n)
                    for i in range(4):
                        c,b=parties[0][i],parties[1][i]
                        unchanged &= (c.max_hp,c.strength,c.agility)==(b.max_hp,b.strength,b.agility)
                        if i!=1 or sid=='quick_hit':unchanged &= c.intellect==b.intellect
                    if n in rows:
                        for label,party in zip(('before','after'),parties):rows[n][label].append([c.intellect for c in party])
            means={n:{label:[round(statistics.mean(row[i] for row in samples),3) for i in range(4)]
                      for label,samples in states.items()} for n,states in rows.items()}
            assert unchanged
            growth.append(dict(skill=sid,uses_per_victory=3,trials=200,seed_base=80000,
                               int_probability=probabilities,mean_int=means,unrelated_growth_identical=True))

        # Exact shortest floor paths include collecting the reachable switch before
        # crossing its door. Stairs are endpoints, never shortcuts through a floor.
        @lru_cache(maxsize=None)
        def route(floor,start,points,end):
            bits={p:1<<i for i,p in enumerate(points)};full=(1<<len(points))-1
            queue=deque([(start[0],start[1],False,bits.get(start,0),0)]);seen=set()
            allowed=PASSABLE-PIT_TILES-{TILE_GUARDIAN}
            while queue:
                x,y,opened,mask,n=queue.popleft();state=x,y,opened,mask
                if state in seen:continue
                seen.add(state)
                if mask==full and (end is None or (x,y)==end):return n
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    p=x+dx,y+dy;t=d.tile(floor,*p)
                    if t in (TILE_ENTRANCE,TILE_STAIRS_UP,TILE_STAIRS_DOWN) and p not in (start,end):continue
                    if t in allowed or t==TILE_DOOR and opened:
                        queue.append((*p,opened or t==TILE_SWITCH,mask|bits.get(p,0),n+1))
            raise AssertionError(('unreachable',floor,start,points,end))
        results=[];d.defeated_bosses.update((4,9))
        for level in (1,2,3):
            base=(level-1)*5;travel=0;prefix={}
            for floor in range(base,base+5):
                prefix[floor]=travel
                if floor<base+4:
                    entry=d.find(floor,TILE_ENTRANCE if floor==0 else TILE_STAIRS_UP)
                    travel+=route(floor,entry,(),d.find(floor,TILE_STAIRS_DOWN))
            for kind in ('explore','investigate','hunt'):
                for version in ('before','after'):
                    e=a.exploration
                    e.quest_data=deepcopy(json.loads((ROOT/'data/quests.json').read_text(encoding='utf8')))
                    if version=='before':e.quest_data.pop('target_floors')
                    paths=[];floors=set();enemies=[]
                    for seed in range(100):
                        q=e.make_quest(level,quest_type=kind,rng=Random(88000+level*100+seed))
                        floor=q['target_floor']-1;floors.add(floor+1)
                        entry=d.find(floor,TILE_ENTRANCE if floor==0 else TILE_STAIRS_UP)
                        paths.append(prefix[floor]+route(floor,entry,tuple(map(tuple,q['points'])),None))
                        if kind=='hunt':
                            e.active=q;d.floor=floor;d.x,d.y=q['points'][0]
                            enemy=e.make_hunt_enemy()[0];enemies.append((enemy.max_hp,enemy.strength,enemy.defense))
                            e.active=None
                    step_range=d.settings['encounter_step_ranges'][level-1]
                    # Renewal approximation only, not measured battles: events can
                    # defer a zero countdown, and quest fights reseed it.
                    results.append(dict(level=level,kind=kind,version=version,floors=sorted(floors),
                        samples=100,mean_outbound_steps=round(statistics.mean(paths),2),
                        min_steps=min(paths),max_steps=max(paths),
                        expected_random_battles_upper_approx=round(statistics.mean(paths)/statistics.mean(step_range),2),
                        encounter_step_range=step_range,mandatory_quest_battles=int(kind=='hunt'),
                        points=q['required_count'],reward=q['reward'],
                        hunt_stats_range={k:[min(v[i] for v in enemies),max(v[i] for v in enemies)]
                                          for i,k in enumerate(('HP','STR','DEF'))} if enemies else None))
        report=dict(growth=growth,quests=results,
                    assumptions=['Three casts per victory; no sparking, same seed per character before/after.',
                        'Growth trials impose actions and victories; not observed natural play or Uses sustainability.',
                        'Quest routes start at B1 entrance / unlocked B6 or B11 lift, shortest known route, no looting.',
                        'Distance ends at objective; return feather/RETURN travel cost is zero; walking return is extra.',
                        'Random battle estimates divide walking steps by countdown mean; event tiles/B15 make these approximate.',
                        'Mandatory hunt is one stronger enemy; other quests have no mandatory battle.'])
        (ROOT/'verification/phase8_balance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:fixture.doCleanups()


if __name__=='__main__':main()
