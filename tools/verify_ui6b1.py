"""Real Pyxel before/after pixels and a pre-change SAVE/suspend compatibility fixture."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prefix',default='ui6b1_after')
    parser.add_argument('--legacy-output',type=Path)
    args=parser.parse_args()
    args.output=args.output.resolve()
    if args.legacy_output:
        args.legacy_output=args.legacy_output.resolve()
    sys.path.insert(0,str(args.source_root.resolve()))
    import pyxel
    from tests.encounter_fixture import EncounterFixture
    from rpg.save import make_save_data
    from rpg.suspend import make_suspend_data
    from rpg.quests import spawn_candidates
    from rpg.text import font,text_width
    EncounterFixture.setUpClass()
    fixture=EncounterFixture();fixture.setUp()
    a,d=fixture.a,fixture.d
    args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    try:
        fixture.unlock();s=a.session;s.treasure.banked=37
        c=s.party[0]
        for sid in list(c.skills):c.forget(sid)
        s.discovered_skills.update(('return','revive','punch','fire'))
        s.mastered_skills.add('revive')
        for sid in ('return','revive','punch'):c.learn(s.skills[sid])
        c.skill_uses['return'],c.skill_uses['revive']=2,1
        e=a.exploration;e.accept(3,quest_type='investigate')
        q=e.active_quest;q['target_floor']=14
        q['points']=[list(p) for p in spawn_candidates(d,13)[:3]]
        q['progress']=1;q['investigated_points']=[q['points'][0]]
        d.floor=13;d.x,d.y=q['points'][1]
        a.state,a.overlay='explore',None
        if args.legacy_output:
            args.legacy_output.mkdir(parents=True,exist_ok=True)
            for name,data in (('ui_phase6b1_legacy_save.json',make_save_data(a)),
                              ('ui_phase6b1_legacy_suspend.json',make_suspend_data(a))):
                target=args.legacy_output/name
                if target.exists():raise FileExistsError(target)
                target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        actual=pyxel.text
        def bounded(x,y,value,color,selected_font=None):
            width=selected_font.text_width(value) if selected_font else len(value)*4
            assert 0<=x and x+width<=160,(x,y,value,width)
            assert 0<=y and y+8<=120,(x,y,value)
            if selected_font is None:actual(x,y,value,color)
            else:actual(x,y,value,color,selected_font)
        def shot(name):
            with patch.object(pyxel,'text',side_effect=bounded):a.draw()
            path=args.output/(args.prefix+'_'+name+'.png')
            pyxel.screen.save(str(path),4)
            results.append(path.name)
        a.state,a.camp_cursor='camp',5;shot('hub')
        for index,label in ((2,'pub'),(1,'training')):
            a.state,a.facility_index,a.facility_cursor='facility',index,0;shot(label)
        a.state='items'
        for index,label in enumerate(('potion','ash','remedy','feather')):
            a.item_kind_cursor=index;shot(label)
        a.state,a.overlay,a.menu_cursor='menu',None,6 if hasattr(a,'draw_field_quest') else 0
        shot('menu')
        if hasattr(a,'draw_field_quest'):
            a.overlay='field_quest';shot('quest_partial')
            q.update(progress=3,completed=True);shot('quest_return')
            q.update(progress=1,completed=False)
        for sid in ('return','revive'):
            a.state,a.overlay,a.info_tab,a.info_character,a.scroll='menu','info',1,0,c.skills.index(sid)
            shot(sid)
        a.state,a.overlay,a.relearn_skill='relearn_confirm',None,'punch'
        a.session.mastered_skills.add('punch');shot('preview_mastered')
        a.show_field_event(['酒場の噂:',a.rumors['gameplay'][0]],return_state='pub');shot('rumor')
        report=dict(source_root=str(args.source_root),screenshots=results,
                    all_rendered_text_inside_160x120=True,physical_hardware_tested=False)
        (args.output.parent/(args.prefix+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('PASS:',args.prefix,len(results),'real Pyxel screens, measured glyph bounds')
    finally:fixture.doCleanups()


if __name__=='__main__':main()
