"""Native real-frame balance regression; injected audio faults, no live saves."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.final_presentation import AMRITA_EFFECT_FRAMES
from rpg.models import Action
from rpg.text import text_width,FONT_HEIGHT
from tools.verify_gkd_freeze import run_trials


def main():
    app=DungeonApp(Session(*load_content(),seed=163),run=False,headless=True,start_at_title=False)
    app.enter_dungeon(); app.opening_input_blocked=False
    starts={}; rounds={}; text_count=0
    original=pyxel.text
    def bounded(x,y,value,color,font):
        nonlocal text_count
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        text_count+=1; original(x,y,value,color,font)
    with patch.object(pyxel,'playm',side_effect=AssertionError('native playm forbidden')), \
         patch.object(pyxel,'btn',return_value=False),patch.object(pyxel,'btnp',return_value=False), \
         patch.object(pyxel,'text',side_effect=bounded):
        starts['normal']=run_trials(app,1000,floor=8)
        print('PASS: 1000 normal real-frame starts / D-PAD A B',flush=True)
        for label,floor,guardian in (('B5',4,None),('B10',9,None),('KNIGHT',14,0),
                ('CYCLOPS',14,1),('DRAGON',14,2),('DEMON',14,None),('LORD',None,None)):
            max_frames=0
            for i in range(100):
                app.session.battle=None; app.session.settled=True
                app.audio.play_bgm('bgm_hub'); app.overlay=None
                if floor is None:
                    app.dungeon.finale.has_amrita=app.dungeon.finale.final_event_started=True
                    app.begin_final_battle()
                else:
                    app.dungeon.debug_floor(floor); app.begin_encounter(boss=True,guardian_index=guardian)
                for frame in range(40):
                    app.update(); app.draw()
                    if app.state=='command' and not app.battle_input_blocked: break
                else: raise AssertionError((label,'COMMAND READY'))
                assert app.audio.current_bgm=='bgm_boss' and app.audio.bgm_started
                max_frames=max(max_frames,frame+1)
            starts[label]=dict(count=100,max_ready_frames=max_frames)
            print('PASS:',label,'100 native starts',flush=True)
        for mode in ('normal','failed','disabled'):
            rounds[mode]={}
            with ExitStack() as stack:
                if mode=='failed':
                    for api in ('play','playm','stop','play_pos'):
                        stack.enter_context(patch.object(pyxel,api,side_effect=RuntimeError('unavailable')))
                app.audio.enabled=mode!='disabled'
                for label,guardian in (('KNIGHT',0),('CYCLOPS',1),('DRAGON',2),('DEMON',None)):
                    app.session.battle=None; app.session.settled=True
                    for c in app.session.party: c.hp=c.max_hp=999
                    app.dungeon.debug_floor(14); app.begin_encounter(boss=True,guardian_index=guardian)
                    app.battle_input_blocked=False
                    app.battle.begin_round([Action(i,'GUARD') for i in range(4)])
                    app.state='resolve'; app.pending.clear(); app.delay=0; app.message_timer=0
                    for frame in range(1000):
                        app.pending.clear(); app.delay=0; app.message_timer=0
                        app.update(); app.draw()
                        if app.state=='command': break
                    else: raise AssertionError((mode,label,app.state,app.battle_visual().phase))
                    expected=2 if label=='DEMON' else 1
                    assert len(app.battle.enemy_round_actions[0])==expected
                    rounds[mode][label]=dict(frames=frame+1,actions=list(app.battle.enemy_round_actions[0]))
                app.session.battle=None; app.session.settled=True
                app.dungeon.finale.has_amrita=app.dungeon.finale.final_event_started=True
                app.begin_final_battle()
                app.battle._party_action(Action(0,'ITEM',item_id='AMRITA')); app.start_amrita_effect()
                seen=[]
                for frame in range(AMRITA_EFFECT_FRAMES+5):
                    app.update(); app.draw(); seen.append(app.audio.current_bgm)
                    if app.state!='amrita_effect': break
                assert app.state=='resolve' and not app.battle.elysion_barrier_active
                assert 'bgm_boss' in seen and 'bgm_final' in seen
                rounds[mode]['AMRITA']=dict(frames=frame+1,finished=True,bgm_boss_then_final=True)
    report=dict(starts=starts,total_starts=1700,real_frame_rounds=rounds,bounded_text_calls=text_count,
                native_playm_unused=True,physical_gkd_tested=False,physical_ios_tested=False)
    (ROOT/'verification/enemy_balance_runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS: 1700 native starts, all boss real-frame actions, failed/disabled audio,',text_count,'bounded text draws')


if __name__=='__main__': main()
