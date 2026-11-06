"""Actual Pyxel state flow and model combat, with an isolated completion SAVE."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def prepare_party(s):
    loadouts=[['power_strike','double_slash','triple_slash','armor_break','first_aid','counter'],
              ['quick_hit','quick_stab','wind_blade','wild_edge','slow','first_aid'],
              ['fire','heal','mending_wind','weaken','focus_field','first_aid'],
              ['power_strike','battle_cry','armor_break','revive','first_aid','guard_up']]
    for c,ids in zip(s.party,loadouts):
        for sid in list(c.skills):c.forget(sid)
        c.hp=c.max_hp=650;c.strength=c.agility=c.intellect=80
        for sid in ids:c.learn(s.skills[sid]);s.discovered_skills.add(sid)
    s.settings['spark_chance']=0


def fight(a):
    from rpg.models import Action
    b=a.battle
    for _ in range(b.max_rounds):
        if b.outcome:break
        actions=b.auto_actions()
        for i,act in enumerate(actions):
            if b.round<2 and act.actor==3:
                sid='battle_cry' if b.round==0 else 'armor_break'
                c=b.party[3]
                if sid in c.skills and c.skill_uses.get(sid,0):actions[i]=Action(3,'SKILL',0,sid)
        b.begin_round(actions)
        for _ in range(200):
            if not b.queue or b.outcome:break
            b.step()
    assert b.outcome=='VICTORY',(b.outcome,b.round,b.enemies[0].hp)
    a.session.settle()
    for i in list(a.session.pending_replacements):a.session.resolve_replacement(i,None)
    with patch.object(a,'waiting_for_fanfare',return_value=False):a.finish_results()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--window',action='store_true')
    args=parser.parse_args()
    import pyxel
    from tests.test_phase7 import Phase7Tests,A,B
    from rpg.postgame import dragon_location
    from tests.phase7_preservation import assert_preserved
    from rpg.text import text_width
    if args.window:pyxel.init(160,120,headless=False);pyxel._tests_initialized=True
    Phase7Tests.setUpClass();t=Phase7Tests();t.setUp();a=t.a
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True)
    stages=[];rendered=[];actual=pyxel.text
    def bounded(x,y,value,color,font=None):
        width=font.text_width(value) if font else len(value)*4
        assert 0<=x and x+width<=160 and 0<=y and y+8<=120,(x,y,value,width)
        return actual(x,y,value,color,font) if font else actual(x,y,value,color)
    def shot(name):
        with patch.object(pyxel,'text',side_effect=bounded):a.draw()
        path=shots/f'phase7_{name}.png';pyxel.screen.save(str(path),4)
        if args.window:pyxel.flip()
        rendered.append(path.relative_to(ROOT).as_posix())
        stages.append(dict(stage=name,state=a.state,completion=a.dungeon.completion.snapshot()))
    try:
        prepare_party(a.session);t.final_ready();shot('final_battle')
        before=[(c.strength,dict(c.skill_uses)) for c in a.session.party]
        fight(a);assert a.state=='ending';shot('ending')
        saved=a.save_manager.backend.read();assert saved['completion']['main_game_cleared']
        for _ in a.final_ending_pages():t.tick(A)
        assert a.state=='credits'
        a.postgame_frame=360;shot('credits_title')
        a.postgame_frame=(120+4*a.credits_data['line_height']-45)*a.credits_data['scroll_frames_per_pixel'];shot('credits_scenario')
        a.postgame_frame=(120+23*a.credits_data['line_height']-45)*a.credits_data['scroll_frames_per_pixel'];shot('credits_font')
        a.postgame_frame=(120+len(a.credits_data['lines'])*a.credits_data['line_height'])*a.credits_data['scroll_frames_per_pixel']
        t.tick();assert a.state=='ending_end';shot('end')
        for _ in range(a.credits_data['end_frames']):t.tick()
        shot('extra_title');t.advance();shot('extra_story');t.advance()
        assert a.state=='title'
        a.continue_game();t.tick();shot('continue_hub')
        assert [(c.strength,dict(c.skill_uses)) for c in a.session.party]==before
        floor,point=dragon_location(a.dungeon);a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point;a.state='explore'
        shot('dragon_symbol');t.tick(A);shot('dragon_warning');t.tick();t.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP);t.tick(A)
        assert a.battle_kind=='dragon';t.tick();shot('dragon_battle');fight(a)
        shot('dragon_victory');t.advance();shot('dragon_title');t.advance();shot('dragon_record');t.advance();t.advance()
        assert a.state=='camp';a.continue_game();t.tick()
        assert a.dungeon.completion.ancient_dragon_victories==1
        a.state='completion_record';shot('guild_record')
        assert_preserved(t)
        report=dict(success=True,native_visible_window=args.window,screen_size=[160,120],
            party_hp=650,party_all_stats=80,party_values_are_test_assumptions=True,
            combat_used_real_rules=True,animation_wait_skipped=True,travel_coordinate_fixture=True,
            completion=saved['completion'],dragon_record=a.dungeon.completion.snapshot(),
            player_save_used=False,all_text_bounds_checked=True,stages=stages,screenshots=rendered)
        (ROOT/'verification/phase7_native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('PASS:',len(rendered),'screens; real final/dragon victory, automatic SAVE, CONTINUE and records')
    finally:t.doCleanups()


if __name__=='__main__':main()
