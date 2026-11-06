"""Compare exact PASS03 move against PASS04 on authored ordinary floor cells."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random
import statistics
import sys
from textwrap import dedent
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rpg.dungeon as module
from rpg.dungeon import Dungeon,load_dungeon_settings
from rpg.content import load_content
from rpg.map_resources import load_maps
from tools.simulate_encounter03 import floor_pair


def main():
    import pyxel
    pyxel.init(160,120,headless=True)
    before = json.loads((ROOT/'tests/fixtures/alpha_encounter04_before.json').read_text(encoding='utf8'))
    namespace = {}
    exec(dedent(before['legacy_move']),vars(module),namespace)
    maps,settings,enemies = load_maps(),load_dungeon_settings(),load_content()[3]
    samples,trials = 10000,2000

    def measure(area,legacy):
        d = Dungeon(maps,enemies,deepcopy(settings),random.Random(44000+area))
        d.floor = (area-1)*5+3
        start,delta = floor_pair(d,d.floor)
        d.x,d.y = start
        if legacy:
            d.settings = deepcopy(before['settings'])
            d.move = MethodType(namespace['move'],d)
        def reset():
            if legacy: d.grace = 6
            else: d.reset_encounter()
        def walk():
            sign = 1 if (d.x,d.y)==start else -1
            return d.move(sign*delta[0],sign*delta[1])[0]=='battle'
        reset()
        n,intervals = 0,[]
        while len(intervals)<samples:
            n += 1
            if walk():
                intervals.append(n)
                n = 0
                reset()  # Include a real re-draw after every encounter.
        counts = []
        d.rng.seed(45000+area)
        for _ in range(trials):
            reset()
            count = 0
            for _ in range(100):
                if walk():
                    count += 1
                    reset()
            counts.append(count)
        return dict(samples=samples,seed=44000+area,mean=round(statistics.mean(intervals),4),
            minimum=min(intervals),maximum_observed=max(intervals),
            theoretical_maximum=None if legacy else settings['encounter_step_ranges'][area-1][1],
            theoretical_mean=6+1/before['settings']['encounter_rates'][area-1] if legacy else
                statistics.mean(settings['encounter_step_ranges'][area-1]),
            within_2_percent=sum(n<=2 for n in intervals)*100/samples,
            within_6_percent=sum(n<=6 for n in intervals)*100/samples,
            encounters_per_100_steps=round(statistics.mean(counts),4),trials_100_steps=trials,
            steady_state_per_100=round(100/statistics.mean(intervals),4),
            histogram=dict(sorted(Counter(intervals).items())),first_20=intervals[:20])
    rows = [dict(area=area,before=measure(area,True),after=measure(area,False)) for area in (1,2,3)]
    for row in rows:
        new = row['after']
        lo,hi = settings['encounter_step_ranges'][row['area']-1]
        assert (new['minimum'],new['maximum_observed'])==(lo,hi)
        assert abs(new['mean']-(lo+hi)/2)<.2
        assert new['within_6_percent']==0
        expected = samples/(hi-lo+1)
        assert all(abs(count-expected)<expected*.15 for count in new['histogram'].values())
        print('AREA',row['area'],'mean',row['before']['mean'],'->',new['mean'],
              'battles/100',row['before']['encounters_per_100_steps'],'->',new['encounters_per_100_steps'])
    result = dict(conditions='Actual authored ordinary floor pairs B4/B9/B14. Successful moves only; combat/loot RNG excluded. PASS03 exact archived move; new reset_encounter after every battle. Event-tile priority and B15 tested separately.',
        intervals_each_area_each_version=samples,normal_comparison=rows,physical_devices=False)
    (ROOT/'verification/alpha_encounter04_simulation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__': main()
