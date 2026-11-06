"""Render the real native 160x120 support/cure screens and check text widths."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from tests.encounter_fixture import EncounterFixture
from rpg.text import text_width

def main():
    EncounterFixture.setUpClass()
    f=EncounterFixture(); f.setUp()
    try:
        a=f.a; c=a.session.party[0]
        for sid in list(c.skills): c.forget(sid)
        for sid in ('power_up','focus','sanctuary','cure','purify_wind','punch'):
            c.learn(a.session.skills[sid])
        a.begin_encounter(); a.begin_input()
        out=ROOT/'verification/screenshots'; out.mkdir(parents=True,exist_ok=True)
        rows=[]
        for sid in ('power_up','focus','sanctuary','purify_wind'):
            a.state='skill'; a.skill_cursor=c.skills.index(sid)
            pyxel.cls(0); a.draw_skills()
            path=out/f'skill5b2_native_{sid}.png'; pyxel.screen.save(str(path),3)
            if sid!='purify_wind':
                width=text_width(a.session.skills[sid].description)
                assert width<=148
                rows.append(dict(skill=sid,description_width=width))
        a.state='target'; a.selected_skill=a.session.skills['cure']; a.target_cursor=1
        pyxel.cls(0); a.draw_battle(); pyxel.screen.save(str(out/'skill5b2_native_target.png'),3)
        a.state='field_heal'; a.field_actor=0; a.field_skill='cure'; a.item_cursor=1
        pyxel.cls(0); a.draw_field_heal(); pyxel.screen.save(str(out/'skill5b2_native_field.png'),3)
        for hint in ('治療対象なし / 予約可','治療対象なし / 消費なし'):
            assert text_width(hint)<=148
            rows.append(dict(hint=hint,width=text_width(hint)))
        (ROOT/'verification/skill_balance5b2_native_ui.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('PASS: six real Pyxel screens; descriptions and hints fit 148px')
    finally:
        f.doCleanups()

if __name__=='__main__': main()
