"""Reproducible, disclosed stat fixtures for before/after enemy comparisons."""
from collections import defaultdict
from copy import deepcopy
import math

STATS={1:dict(strength=10,agility=12,intellect=12,max_hp=70),
       2:dict(strength=22,agility=24,intellect=24,max_hp=120),
       3:dict(strength=34,agility=36,intellect=36,max_hp=180)}
BASIC=('punch','quick_hit','spark')
COMMON=('power_strike','quick_stab','fire')


def normal_metrics(rows,settings,skills,party):
    enemies={r['id']:r for r in rows}; observations=defaultdict(list)
    for floor,profile in enumerate(settings['floors']):
        if floor==14: continue
        if 'enemy_ids' not in profile: profile=settings['floors'][floor-1]
        area=floor//5+1
        for sid in profile['enemy_ids']:
            row=enemies[sid]; hp=round(row['max_hp']*profile['hp_scale'])
            actor=deepcopy(party[0])
            for key,value in STATS[area].items(): setattr(actor,key,value)
            results={}
            for skill_id in BASIC+COMMON:
                skill=skills[skill_id]
                defense=row.get('magic_defense',0) if skill.skill_type=='magic' else row.get('defense',0)
                damage=max(1,round(skill.power(actor)-defense))
                results[skill_id]=dict(damage=damage,actions=math.ceil(hp/damage))
            # Preserve the existing armored-enemy role: compare their standard
            # magic options separately; physical mismatch remains in full table.
            standard=('spark',) if sid in ('iron_golem','stone_beast') else BASIC
            observations[sid].append(dict(floor=floor+1,area=area,hp=hp,skills=results,
                standard_atk=sum(results[k]['actions'] for k in standard)/len(standard)))
    return {sid:dict(samples=values,standard_atk=sum(v['standard_atk'] for v in values)/len(values))
            for sid,values in observations.items()}


def weighted_damage(row,actions):
    """Expected raw damage per action/target; weights and status chance unchanged."""
    entries=row.get('actions') or [dict(id='attack',weight=(1-row['magic_chance'])*100),
                                  dict(id='magic',weight=row['magic_chance']*100)]
    total=sum(r['weight'] for r in entries)
    damage=0
    for entry in entries:
        action=actions[entry['id']]
        if action.type.startswith(('physical','magic')):
            stat=row['int'] if action.type.startswith('magic') else row['str']
            damage+=entry['weight']/total*stat*action.power*action.hits
    return damage
