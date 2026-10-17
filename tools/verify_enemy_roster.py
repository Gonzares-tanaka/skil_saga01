"""Actual encounters/actions, immutable assets, and measured Pyxel UI verification."""
from collections import Counter, deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.dungeon_app import DungeonApp
from rpg.map_resources import load_maps
from rpg.models import Enemy
from rpg.statuses import clear_statuses
from rpg.text import text_width, FONT_HEIGHT


def main():
    pyxel.init(160,120,headless=True)
    with patch.object(pyxel,'init'):
        app=DungeonApp(Session(*load_content(),seed=723),run=False,headless=True,start_at_title=False)
    s,d=app.session,app.dungeon
    baseline=json.loads((ROOT/'tests/fixtures/enemy_roster_before.json').read_text(encoding='utf8'))
    allowed={'data/enemies.json','data/enemy_actions.json','data/dungeon.json',
             'rpg/models.py','rpg/statuses.py','rpg/battle.py','rpg/app.py','rpg/dungeon_app.py'}
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
            for name,digest in baseline['hashes'].items() if name not in allowed}
    assert all(hashes.values()),hashes
    floors=[]
    for floor in range(14):
        d.floor=floor; counts=Counter()
        profile=d.settings['floors'][floor if floor not in (4,9) else floor-1]
        for _ in range(3000): counts.update(e.id for e in d.make_enemies())
        assert set(counts)==set(profile['enemy_ids'])
        total=sum(counts.values()); weight_total=sum(profile['weights'])
        for ident,weight in zip(profile['enemy_ids'],profile['weights']):
            assert abs(counts[ident]/total-weight/weight_total)<.025,(floor,ident)
        floors.append(dict(floor=floor+1,encounters=3000,counts=dict(counts),
                           expected=dict(zip(profile['enemy_ids'],profile['weights']))))
    actions=[]
    newids=[r['id'] for r in s.enemy_data if r['id'] not in {r['id'] for r in baseline['enemies']}]
    for ident in newids:
        enemy=Enemy.from_definition(d.enemies[ident])
        b=Battle(s.party,[enemy],s.skills,rng=random.Random(614),inventory=s.inventory)
        picked,successes=Counter(),Counter()
        for _ in range(10000):
            for unit in b.party+b.enemies:
                unit.hp=unit.max_hp=10000; clear_statuses(unit); unit.effects.clear()
            b.outcome=None; b.turn_plan=None; b.queue=deque([('enemy',0)])
            b.step(); action=b.enemy_action_visual['action_id']; picked[action]+=1
            if any(c.statuses for c in b.party): successes[action]+=1
        for row in enemy.actions:
            action,weight=row['id'],row['weight']
            assert abs(picked[action]/10000-weight/100)<.02,(ident,action)
            definition=b.enemy_actions[action]
            if definition.status_id:
                assert abs(successes[action]/picked[action]-definition.status_chance/100)<.07
                assert abs(successes[action]/10000-weight/100*definition.status_chance/100)<.02
            else: assert not successes[action]
        actions.append(dict(enemy_id=ident,turns=10000,action_counts=dict(picked),
                            status_successes=dict(successes)))
    app.begin_encounter()
    calls=[]; screenshots=[]; real_text=pyxel.text
    def bounded(x,y,value,color,font=None):
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        calls.append(value); real_text(x,y,value,color,font)
    def shot(name):
        app.draw(); path=ROOT/f'verification/screenshots/roster_{name}.png'
        path.parent.mkdir(parents=True,exist_ok=True); pyxel.screenshot(str(path),scale=4)
        screenshots.append(path.relative_to(ROOT).as_posix())
    app.begin_input()
    with patch.object(pyxel,'text',side_effect=bounded):
        for chunk in (newids[:4],newids[4:]):
            app.battle.enemies=[Enemy.from_definition(d.enemies[i]) for i in chunk]
            shot('_'.join(chunk))
        for ident,action in (('poison_snake','poison_bite'),('ghost','confusion_touch'),
                             ('mummy','paralyze_grab'),('dark_wisp','sleep_spell')):
            b=app.battle; enemy=Enemy.from_definition(d.enemies[ident],max_hp=10000)
            enemy.actions=[dict(id=action,weight=1)]; b.enemies=[enemy]
            for c in b.party:
                c.hp=c.max_hp=1000; clear_statuses(c); c.effects.clear()
            b.outcome=None; b.turn_plan=None; b.queue=deque([('enemy',0)])
            app.state='resolve'; app.delay=0; app.pending.clear(); app.battle_visual().reset()
            app.confirm=app.confirm_held=lambda:False
            with patch.object(b.rng,'random',return_value=0),patch.object(b.rng,'choice',return_value=b.party[0]):
                app.apply_visual_action()
            seen=set()
            for tick in range(120):
                if not app.battle_visual().active: break
                phase=app.battle_visual().phase; seen.add(phase)
                if phase=='status_effect' and app.battle_visual().frame==2: shot(action)
                app.update()
            else: raise AssertionError('Status visual stalled')
            assert 'status_effect' in seen
    result=dict(regular_enemies=18,all_enemy_ids=25,protected_files=hashes,
                encounter_simulations=floors,enemy_action_simulations=actions,
                bounded_text_calls=len(calls),screenshots=screenshots,
                natural_balance_test=False,physical_gkd_tested=False)
    (ROOT/'verification/enemy_roster.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(hashes),'unchanged files;',14*3000,'encounters;',len(newids)*10000,
          'actual enemy turns;',len(screenshots),'screenshots;',len(calls),'bounded text calls')


if __name__=='__main__': main()
