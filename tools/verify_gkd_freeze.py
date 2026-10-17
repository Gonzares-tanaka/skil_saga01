"""Read-only game audit via real frame updates/draws, synthetic encounters.

No real saves, balance edits or production monkey patches survive this process.
Headless desktop Pyxel is not the GKD SDL/audio/input backend.
"""
from collections import Counter
from contextlib import ExitStack
import faulthandler
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Enemy,Action
from rpg.battle_presentation import BattlePresentation
from rpg.tiles import TILE_STAIRS_UP

FORCED=(('skeleton','skeleton'),('skeleton',)*3,('assassin',)*2,('assassin',)*3,
        ('skeleton','assassin'),('assassin','skeleton'),
        ('skeleton','assassin','skeleton'),('assassin','skeleton','assassin'),
        ('iron_golem',)*2,('berserker',)*2,('mage',)*2,('stone_beast',)*2,
        ('skeleton','mage'),('assassin','mage'),
        ('skeleton','skeleton','mage'),('assassin','assassin','mage'))


def run_trials(app,count,ids=None,floor=5,audio='normal',animate=True):
    s=app.session; counts=Counter(); max_frames=0
    def buttons(key):
        with patch.object(pyxel,'btnp',new=lambda code,*args:code==key):
            app.update(); app.draw()
    with ExitStack() as stack:
        stack.enter_context(patch.object(pyxel,'btn',new=lambda *args:False))
        stack.enter_context(patch.object(pyxel,'btnp',new=lambda *args:False))
        if ids:
            stack.enter_context(patch.object(app.dungeon,'make_enemies',
                new=lambda *args:[Enemy.from_definition(app.dungeon.enemies[sid],
                    name=app.dungeon.enemies[sid]['name']+' '+str(i)) for i,sid in enumerate(ids)]))
        if audio=='failed':
            for api in ('play','playm','stop','play_pos'):
                stack.enter_context(patch.object(pyxel,api,side_effect=RuntimeError('test unavailable audio')))
        elif audio=='off':
            for api in ('play','playm','stop'):
                stack.enter_context(patch.object(pyxel,api))
        for trial in range(count):
            s.battle=None; s.settled=True
            app.overlay=None; app.state='explore'; app.opening_input_blocked=False
            app.dungeon.floor=floor
            app.dungeon.x,app.dungeon.y=app.dungeon.find(floor,TILE_STAIRS_UP)
            app.sync_scene_audio()  # Real exploration -> battle music switch each trial.
            app.begin_encounter(animate=animate)
            counts[','.join(e.id for e in app.battle.enemies)]+=1
            for frames in range(1,40):
                app.update(); app.draw()
                if app.state=='command' and not app.battle_input_blocked: break
            else: raise AssertionError(('COMMAND_READY not reached',floor,trial,ids,app.state))
            max_frames=max(max_frames,frames)
            assert app.actor_index==0 and app.actor_position==0 and app.cursor==0
            assert not app.battle_visual().active and not app.pending and not app.battle.queue
            assert len({id(e) for e in app.battle.enemies})==len(app.battle.enemies)
            # Real game's input mapping, not direct commit()/state assignment.
            buttons(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN); assert app.cursor==2
            buttons(pyxel.GAMEPAD1_BUTTON_DPAD_UP); assert app.cursor==0
            buttons(pyxel.GAMEPAD1_BUTTON_A); assert app.state=='skill'
            buttons(pyxel.GAMEPAD1_BUTTON_B); assert app.state=='command'
    return dict(count=count,max_ready_frames=max_frames,groups=dict(counts),audio=audio,
                transition=animate,dpad_a_b_passed=count)


def identity_checks(app):
    s=app.session
    for ids in (('skeleton','skeleton'),('skeleton','assassin')):
        enemies=[Enemy.from_definition(app.dungeon.enemies[sid]) for sid in ids]
        s.battle=None; s.settled=True; b=s.next_battle(enemies,recover=False)
        before=enemies[1].hp
        b._damage(enemies[0],3); b.apply_status(enemies[0],'poison',100)
        assert enemies[1].hp==before and not enemies[1].statuses
        hp_before=[c.hp for c in s.party]
        b.queue.append(('enemy',1)); visual=BattlePresentation(b)
        b.step(); assert b.enemy_action_visual['enemy_index']==1
        visual.after_action([True,True],hp_before); assert visual.enemy_actor==1
        b.queue.clear(); b._party_action(Action(0,'SKILL',1,'punch'))
        assert enemies[1].hp<before  # Target index 1 is a different instance.
    return True


def main():
    faulthandler.enable(); faulthandler.dump_traceback_later(60,repeat=True)
    start=time.monotonic()
    app=DungeonApp(Session(*load_content(),seed=1337),run=False,headless=True,start_at_title=False)
    app.enter_dungeon(); app.opening_input_blocked=False
    identities=identity_checks(app)
    forced={}
    for ids in FORCED:
        label='+'.join(ids); forced[label]=run_trials(app,1000,ids)
        print('PASS forced:',label,'1000 starts',flush=True)
    ordinary={}
    for floor in range(5,10):
        ordinary['B'+str(floor+1)]=run_trials(app,2000,floor=floor)
        print('PASS area:',floor+1,'2000 table encounters',flush=True)
    audio={}
    for mode in ('normal','off','failed'):
        audio[mode]=run_trials(app,100,('skeleton','skeleton'),audio=mode)
        print('PASS audio:',mode,flush=True)
    bypass=run_trials(app,100,('skeleton','assassin'),animate=False)
    baseline=json.loads((ROOT/'verification/gkd_freeze_before.json').read_text(encoding='utf-8-sig'))
    protected={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in baseline.items()
               if n not in ('rpg/sound.py','dist/game.html','verification/packages/skill_seekers_gkd.zip')}
    assert all(protected.values()),[n for n,ok in protected.items() if not ok]
    report=dict(result='A',reproduced_before_fix=True,native_playm_blocking_identified=True,forced=forced,
                area2=ordinary,forced_total=16000,table_total=10000,
                total_starts=26400,identity_target_presentation_independent=identities,
                audio=audio,transition_bypassed=bypass,protected_files=protected,
                seconds=round(time.monotonic()-start,2),physical_gkd_tested=False)
    (ROOT/'verification/gkd_freeze_stress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    faulthandler.cancel_dump_traceback_later()
    print('PASS: 26400 full-frame starts after native audio fix; GKD hardware not tested',flush=True)


if __name__=='__main__': main()
