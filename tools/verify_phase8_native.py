"""Render actual 160x120 screens with the bundled font and bounded text checks."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    import pyxel
    from tests.encounter_fixture import EncounterFixture
    from rpg.postgame import dragon_location
    from rpg.text import wrap_lines
    EncounterFixture.setUpClass();t=EncounterFixture();t.setUp();a=t.a
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True);rows=[]
    actual=pyxel.text;star_labels=[]
    def bounded(x,y,value,color,font=None):
        width=font.text_width(value) if font else len(value)*4
        assert 0<=x and x+width<=160 and 0<=y and y+8<=120,(x,y,value,width)
        if '★' in value:star_labels.append(value)
        return actual(x,y,value,color,font) if font else actual(x,y,value,color)
    def shot(name):
        star_labels.clear()
        with patch.object(pyxel,'text',side_effect=bounded):a.draw()
        if name in ('replacement','replacement_confirm','info_1','relearn_list','relearn_confirm','battle_skills','battle_target'):
            assert any('パンチ★' in value for value in star_labels),(name,star_labels)
        path=shots/f'phase8_pc_{name}.png';pyxel.screen.save(str(path),4)
        rows.append(dict(screen=name,path=path.relative_to(ROOT).as_posix(),bounded=True,star_labels=list(star_labels)))
    try:
        c=a.session.party[0]
        for sid in ('power_strike','fire','heal','return','cure'):c.learn(a.session.skills[sid])
        c.pending_skill='meteor';a.session.mastered_skills.update(('punch','fire','meteor'))
        a.state='replace';a.replacement_choice=0;a.replacement_confirm=False;shot('replacement')
        a.replacement_confirm=True;shot('replacement_confirm')
        c.pending_skill=None;a.replacement_confirm=False;a.state='explore';a.overlay='info'
        for tab in range(3):a.info_tab=tab;a.scroll=0;shot('info_'+str(tab))
        a.overlay=None;a.info_character=0;a.relearn_cursor=0
        a.session.discovered_skills.update(c.skills)
        a.state='relearn_list';shot('relearn_list')
        a.relearn_skill='punch';a.state='relearn_confirm';shot('relearn_confirm')
        a.overlay=None;a.dungeon.completion.main_game_cleared=True
        floor,point=dragon_location(a.dungeon);a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point
        a.begin_dragon_battle();b=a.battle;e=b.enemies[0]
        a.state='skill';a.skill_cursor=0;shot('battle_skills')
        a.selected_skill=a.session.skills['punch'];a.state='target';a.target_cursor=0;shot('battle_target')
        for percent in (74,49,24):
            e.hp=e.max_hp*percent//100;lines=b.hp_stage_feedback()
            a.state='resolve';a.log=wrap_lines(lines);shot('dragon_'+str(percent))
        (ROOT/'verification/phase8_native.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('PASS:',len(rows),'actual Pyxel screens; bundled font; all text bounded')
    finally:t.doCleanups()


if __name__=='__main__':main()
