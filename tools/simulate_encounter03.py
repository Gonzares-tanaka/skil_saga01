"""Seeded before/after measurements using actual authored, reachable floor pairs.

No resource mutation. Excludes combat/loot RNG and event stops; each tested move
is one successful cell traversal. The legacy move function is the exact source
captured before edits, not a hand-reimplemented probability model.
"""
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import statistics
import sys
from textwrap import dedent
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rpg.dungeon as module
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.content import load_content
from rpg.map_resources import load_maps
from rpg.tiles import FLOOR_TILES


def floor_pair(dungeon, floor):
    for x,y in sorted(dungeon.reachable(floor)):
        if dungeon.tile(floor,x,y) in FLOOR_TILES:
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                if dungeon.tile(floor,x+dx,y+dy) in FLOOR_TILES:
                    return (x,y),(dx,dy)
    raise ValueError('No reachable floor pair')


def main():
    import pyxel
    pyxel.init(160,120,headless=True)
    before = json.loads((ROOT/'tests/fixtures/alpha_encounter03_before.json').read_text(encoding='utf8'))
    namespace = {}
    exec(dedent(before['legacy_move']), vars(module), namespace)
    legacy_move = namespace['move']
    settings = load_dungeon_settings()
    maps = load_maps()
    enemy_data = load_content()[3]
    rows = []
    samples, trials = 10000, 2000
    def measure(area, legacy=False, debug=False, boss_exit=False):
        d = Dungeon(maps, enemy_data, deepcopy(settings), random.Random(31000+area))
        floor = (area-1)*5+3  # B4/B9/B14, all random-encounter eligible.
        start, delta = floor_pair(d, floor)
        d.floor = floor
        d.x,d.y = start
        if legacy:
            d.settings = deepcopy(before['settings'])
            d.move = MethodType(legacy_move, d)
        grace = (0 if boss_exit else before['settings']['safe_steps']) if legacy else settings['post_battle_safe_steps']
        d.grace = grace
        steps, intervals = 0, []
        def walk():
            # Bounce on two actual adjacent floor cells; no walls/menu frames.
            sign = 1 if (d.x,d.y)==start else -1
            return d.move(delta[0]*sign,delta[1]*sign,debug=debug)[0]
        while len(intervals)<samples:
            steps += 1
            if walk()=='battle':
                intervals.append(steps)
                steps,d.grace = 0,grace
        ordered = sorted(intervals)
        mean = statistics.mean(intervals)
        d.rng.seed(41000+area)
        counts = []
        for _ in range(trials):
            d.grace = grace
            n = 0
            for step in range(100):
                if walk()=='battle':
                    n += 1
                    d.grace = grace
            counts.append(n)
        return dict(area=area, floor=floor+1, legacy=legacy, debug=debug,
            post_boss_exit=boss_exit, seed=31000+area, samples=samples,
            safe_steps=grace, rate=(before['settings']['debug_encounter_chance'] if debug else before['settings']['encounter_chance'])
                if legacy else settings['debug_encounter_chance'] if debug else settings['encounter_rates'][area-1],
            mean=round(mean,4), median=statistics.median(intervals), minimum=min(intervals),
            p90=ordered[math.ceil(.9*samples)-1], within_2_percent=sum(x<=2 for x in intervals)*100/samples,
            within_6_percent=sum(x<=6 for x in intervals)*100/samples,
            encounters_per_100_steps=round(statistics.mean(counts),4), trials_100_steps=trials,
            steady_state_per_100_steps=round(100/mean,4), first_intervals=intervals[:20],
            distinct_intervals=len(set(intervals)), histogram=dict(sorted(Counter(intervals).items())))
    for area in (1,2,3):
        old,new = measure(area,True),measure(area)
        rows.append(dict(area=area,before=old,after=new,
            density_change_percent=round((new['encounters_per_100_steps']/old['encounters_per_100_steps']-1)*100,3)))
    contexts = [dict(kind='post_boss_no_old_reset',before=measure(1,True,boss_exit=True),after=measure(1,boss_exit=True)),
                dict(kind='debug_bypassed_old_grace',before=measure(1,True,debug=True),after=measure(1,debug=True))]
    result = dict(conditions='Actual reachable ordinary floor pairs B4/B9/B14; only successful grid moves; combat/loot RNG excluded; reset grace at simulated battle exit.',
        normal_comparison=rows, short_gap_contexts=contexts, physical_device_playtest=False)
    output = ROOT/'verification/alpha_encounter03_simulation.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for row in rows:
        print('AREA',row['area'],'mean',row['before']['mean'],'->',row['after']['mean'],
              'battles/100',row['before']['encounters_per_100_steps'],'->',row['after']['encounters_per_100_steps'],
              'change',row['density_change_percent'],'%')
    for row in contexts:
        print(row['kind'],'within2%',row['before']['within_2_percent'],'->',row['after']['within_2_percent'])


if __name__=='__main__': main()
