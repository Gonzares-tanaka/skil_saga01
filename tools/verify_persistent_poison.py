"""Preservation and real Pyxel field UI checks for the poison lifetime change."""
from collections import deque
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
from rpg.models import Enemy
from rpg.statuses import apply_status
from rpg.text import text_width, FONT_HEIGHT


def main():
    backup=ROOT/'verification/backups/persistent_poison'
    baseline=json.loads((backup/'baseline.json').read_text(encoding='utf8'))
    allowed={'rpg/models.py','rpg/statuses.py','rpg/battle.py','rpg/app.py','rpg/dungeon_app.py'}
    protected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
               for name,digest in baseline.items() if name not in allowed}
    assert all(protected.values()),protected
    old=ModuleType('rpg._poison_baseline'); old.__package__='rpg'
    exec(compile((backup/'battle.py').read_text(encoding='utf8'),str(backup/'battle.py'),'exec'),old.__dict__)
    cases=[(ident,'berserker') for ident in json.loads((ROOT/'data/enemy_actions.json').read_text(encoding='utf8'))]
    cases.extend((None,r['id']) for r in load_content()[3] if r.get('boss'))
    compared=0
    for seed in range(15):
        for action,ident in cases:
            snapshots=[]
            for cls in (old.Battle,Battle):
                _,skills,party,rows=load_content()
                for c in party: c.hp=c.max_hp=1000
                enemy=Enemy.from_definition(next(r for r in rows if r['id']==ident),max_hp=10000)
                if action: enemy.actions=[dict(id=action,weight=1)]
                b=cls(party,[enemy],skills,rng=random.Random(seed),boss=action is None)
                b.queue=deque([('enemy',0)]); lines=b.step()
                snapshots.append((lines,[asdict(c) for c in party],asdict(enemy),b.rng.getstate(),b.outcome))
            assert snapshots[0]==snapshots[1],(action,ident,seed)
            compared+=1
    pyxel.init(160,120,headless=True)
    with patch.object(pyxel,'init'):
        app=DungeonApp(Session(*load_content(),seed=701),run=False,headless=True,start_at_title=False)
    app.enter_dungeon(); actor=app.session.party[0]
    apply_status(actor,'poison'); actor.statuses['poison']=2
    shots=[]; texts=[]; glyphs=[]; real_text=pyxel.text; real_blt=pyxel.blt
    def bounded(x,y,value,color,font=None):
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        texts.append(value); real_text(x,y,value,color,font)
    def bounded_blt(x,y,*args,**kwargs):
        if len(args)>=5 and args[:5]==(2,192,0,8,8):
            assert 0<=x<=152 and 0<=y<=112,(x,y)
            glyphs.append((x,y))
        real_blt(x,y,*args,**kwargs)
    def shot(name):
        app.draw(); path=ROOT/f'verification/screenshots/persistent_poison_{name}.png'
        path.parent.mkdir(parents=True,exist_ok=True); pyxel.screenshot(str(path),scale=4)
        shots.append(path.relative_to(ROOT).as_posix())
    with patch.object(pyxel,'text',side_effect=bounded),patch.object(pyxel,'blt',side_effect=bounded_blt):
        shot('explore')
        app.state='menu'; shot('menu')
        app.state='items'; app.item_kind_cursor=2; shot('items')
        app.state='item_target'; app.item_cursor=0; shot('target')
        app.overlay='info'; app.info_tab=app.info_character=0; shot('party_info')
        app.overlay=None; app.begin_encounter(); shot('next_battle')
        assert actor.statuses=={'poison':2}
    result=dict(protected_files=protected,unchanged_action_samples=compared,
                screenshots=shots,bounded_text_calls=len(texts),poison_icon_positions=glyphs,
                data_enemy_skills_maps_save_unchanged=True,physical_gkd_tested=False,
                physical_ios_tested=False)
    (ROOT/'verification/persistent_poison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(protected),'protected files;',compared,'action results/RNG;',len(shots),
          'screenshots;',len(texts),'bounded text calls')


if __name__=='__main__': main()
