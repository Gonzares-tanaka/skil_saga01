"""Native pixel screenshots of the received/new lift and description endpoints."""
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from tests.encounter_fixture import EncounterFixture
from tests.ui_phase6a_preservation import baseline, assert_ui_preserved
from rpg.elevator import b15_elevator_point, B15_ELEVATOR_SPRITE
from rpg.text import text_width, font, DESCRIPTION_HOLD_FRAMES, DESCRIPTION_STEP_FRAMES
from rpg.tiles import TILE_BOSS_CLEAR


def main():
    import unittest
    assert_ui_preserved(unittest.TestCase())
    EncounterFixture.setUpClass()
    f = EncounterFixture(); f.setUp()
    try:
        a, d = f.a, f.d
        f.unlock()
        d.floor = 14
        a.state, a.overlay = 'explore', None
        out = ROOT/'verification/screenshots'
        out.mkdir(parents=True, exist_ok=True)
        shots = []
        def save(name, image=None):
            path = out/f'ui_phase6a_{name}.png'
            (image or pyxel.screen).save(str(path), 4 if image is None else 3)
            shots.append(path.relative_to(ROOT).as_posix())

        old_lift = {'__name__': 'rpg.before_elevator', '__package__': 'rpg'}
        exec(compile(baseline()['sources']['rpg/elevator.py'], 'before/elevator.py','exec'),old_lift)
        old_ui = {'__name__': 'rpg.before_dungeon_app', '__package__': 'rpg'}
        exec(compile(baseline()['sources']['rpg/dungeon_app.py'],'before/dungeon_app.py','exec'),old_ui)
        old_ui['b15_elevator_point'] = old_lift['b15_elevator_point']
        old_point = old_lift['b15_elevator_point'](d)
        d.x, d.y = 5, 30
        pyxel.cls(0); old_ui['DungeonApp'].draw_explore(a)
        save('elevator_before')
        new_point = b15_elevator_point(d)
        d.x, d.y = 11, 2
        pyxel.cls(0); a.draw_explore()
        save('elevator_after')
        for old, point in ((True, old_point), (False, new_point)):
            width, height = d.map_bounds(14)
            image = pyxel.Image(width*8,height*8+8)
            image.cls(0)
            image.text(1,0,'BEFORE' if old else 'AFTER',3,font())
            image.bltm(0,8,d.maps[14],0,0,width*8,height*8)
            x,y=d.boss_positions[14]
            image.blt(x*8,y*8+8,1,TILE_BOSS_CLEAR[0]*8,TILE_BOSS_CLEAR[1]*8,8,8)
            x,y=point
            if old:
                image.blt(x*8,y*8+8,2,80,0,16,16,0)
            else:
                u,v=d.floor_appearance(14,*point)
                image.blt(x*8,y*8+8,1,u*8,v*8,8,8)
                image.blt(x*8,y*8+8,*B15_ELEVATOR_SPRITE,0)
            save('map_before' if old else 'map_after',image)

        c=a.session.party[0]
        for sid in list(c.skills): c.forget(sid)
        for sid in ('power_up','full_heal','punch'): c.learn(a.session.skills[sid])
        a.begin_encounter(); a.begin_input()
        descriptions=[]
        for mode in ('battle','status','catalog'):
            for sid in ('power_up','full_heal'):
                a.state='skill' if mode=='battle' else 'command'
                a.overlay=None if mode=='battle' else 'info' if mode=='status' else 'catalog'
                a.skill_cursor=a.scroll=c.skills.index(sid)
                a.info_tab,a.info_character=1,0
                a.catalog_cursor=list(a.session.skills).index(sid)
                value=a.session.skills[sid].description
                overflow=max(0,text_width(value)-148)
                end=DESCRIPTION_HOLD_FRAMES+overflow*DESCRIPTION_STEP_FRAMES
                for frame in range(end+1):
                    with patch.object(pyxel,'frame_count',frame): a.draw()
                    if frame==0: save(f'{mode}_{sid}_start')
                assert a.description_scroll.offset==overflow
                save(f'{mode}_{sid}_end')
                descriptions.append(dict(screen=mode,id=sid,width=text_width(value),
                    viewport=148,end_offset=a.description_scroll.offset,
                    data_sha256=hashlib.sha256(value.encode('utf8')).hexdigest()))
        a.state,a.overlay='camp',None
        a.session.treasure.banked=15
        for state in ('camp','shop','pub','relearn_character'):
            a.state=state; a.draw(); save(f'trz_{state}')
        result=dict(old_lift=old_point,new_lift=new_point,demon=d.boss_positions[14],
            sprite=B15_ELEVATOR_SPRITE,descriptions=descriptions,
            skill_widths=[dict(id=s.id,width=text_width(s.description),scrolls=text_width(s.description)>148)
                          for s in a.session.skills.values()],screenshots=shots,
            actual_hardware_tested=False,assets_unmodified=True)
        (ROOT/'verification/ui_phase6a_native.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        assert_ui_preserved(unittest.TestCase())
        print('PASS: received/new lift, map overview, 3 description screens/start+end, base labels;',len(shots),'screenshots')
    finally:
        f.doCleanups()


if __name__=='__main__': main()
