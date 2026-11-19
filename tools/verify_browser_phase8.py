"""Release Web smoke using actual keyboard/touch; isolated browser storage only."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from verify_browser_save import QuietHandler


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--playwright-path',type=Path,required=True)
    p.add_argument('--disable-audio',action='store_true');args=p.parse_args()
    sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    label='unavailable' if args.disable_audio else 'running';results=[]
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='phase8-browser-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
            for mobile in (False,True):
                mode='touch' if mobile else 'desktop';print('START',label,mode,flush=True)
                options=dict(channel='msedge',headless=True,ignore_https_errors=True,args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:options.update(pw.devices['Pixel 7']);options.pop('default_browser_type',None)
                context=pw.chromium.launch_persistent_context(str(Path(temp)/mode),**options)
                context.add_init_script('''window.phase8Contexts=[];const Native=window.AudioContext;
                if(Native)window.AudioContext=new Proxy(Native,{construct(t,a,n){
                  const c=Reflect.construct(t,a,n);phase8Contexts.push(c);return c;}});''')
                page=context.pages[0];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded')
                page.locator('#play').click();frame=page.frame_locator('#game')
                frame.locator('#pyxel-prompt').wait_for(timeout=120000);frame.locator('#canvas').click();game=page.frames[-1]
                game.wait_for_function('''()=>{try{return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`)}catch(_){return false}}''',timeout=120000)
                def py(code):return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)',code)
                def check(code):game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)',arg=code,timeout=25000)
                py('import json\na=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))')
                check('a.state=="title" and a.suspend_job is None')
                assert not py('__import__("rpg.runtime",fromlist=["DEVELOPMENT_BUILD"]).DEVELOPMENT_BUILD')
                assert not py('a.debug_allowed')
                if args.disable_audio:
                    states=game.evaluate('''async()=>{await Promise.all(phase8Contexts.map(async c=>{
                      await c.suspend();c.resume=()=>Promise.reject(new Error('intentional failure'))}));
                      document.dispatchEvent(new Event('visibilitychange'));
                      for(const e of ['blur','focus','pageshow'])window.dispatchEvent(new Event(e));
                      return phase8Contexts.map(c=>c.state)}''')
                    assert states and all(s=='suspended' for s in states)
                cdp=context.new_cdp_session(page) if mobile else None
                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box=game.locator(f'[data-gb="{button}"]').bounding_box();assert box
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)]))
                        page.wait_for_timeout(90);cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key=dict(a='z',b='x',up='ArrowUp',down='ArrowDown',left='ArrowLeft',right='ArrowRight')[button]
                        page.keyboard.down(key);page.wait_for_timeout(90);page.keyboard.up(key)
                    page.wait_for_timeout(150)
                def key(k):page.keyboard.press(k);page.wait_for_timeout(180)
                def shot(name):page.screenshot(path=str(shots/f'phase8_web_{label}_{mode}_{name}.png'))
                press('a');check('a.state=="intro" and not a.opening_input_blocked')
                for _ in range(py('len(a.intro_pages)')):press('a')
                check('a.state=="hub_intro" and not a.opening_input_blocked');press('a');check('a.state=="camp"')
                for k in ('q','F9','a'):key(k)
                assert py('a.state=="camp" and not a.session.debug')
                py('a.enter_dungeon()');press('b');check('a.state=="menu"')
                py("a.menu_cursor=0");press('a');check('a.overlay=="info" and a.info_tab==0')
                press('down');assert py('a.info_character==1')
                press('right');check('a.info_tab==1');shot('skills')
                press('right');check('a.info_tab==2');press('a');assert py('a.info_tab==2')
                shot('history');press('left');check('a.info_tab==1');press('b');check('a.overlay is None')
                py('''
c=a.session.party[0]
for sid in ('power_strike','fire','heal','return','cure'):c.learn(a.session.skills[sid])
c.pending_skill='meteor';a.session.mastered_skills.update(('punch','fire','meteor'))
a.state='replace';a.replacement_choice=0;a.replacement_confirm=False
''')
                assert py("a.mastered_label(a.session.skills['meteor']).endswith('★')")
                for k in ('d','Tab','h'):key(k)
                assert py('a.state=="replace" and a.overlay is None');shot('replacement')
                press('a');check('a.replacement_confirm');shot('replacement_confirm');press('b')
                py('''
c.pending_skill=None;c.forget('punch');a.session.discovered_skills.add('punch')
a.info_character=0;a.overlay=None;a.state='relearn_list'
a.relearn_cursor=next(i for i,s in enumerate(a.session.relearn_candidates()) if s.id=='punch')
''')
                shot('relearn_list');press('a');check('a.state=="relearn_confirm"');shot('relearn_confirm')
                press('a');check('a.state=="relearn_list" and "punch" in c.skills')
                assert py("c.power_multiplier(a.session.skills['punch'])==1.2")
                py("a.state='menu';a.overlay='info';a.info_character=0;a.info_tab=1;a.scroll=c.skills.index('punch')")
                shot('relearned_status');press('b')
                # Inject progress only to reach the postgame presentation without
                # claiming a full natural playthrough or changing enemy stats.
                py('''
c.pending_skill=None;a.overlay=None
from rpg.postgame import dragon_location
a.dungeon.completion.main_game_cleared=True
f,p=dragon_location(a.dungeon);a.dungeon.floor=f;a.dungeon.x,a.dungeon.y=p
a.begin_dragon_battle();e=a.battle.enemies[0];dragon_max=e.max_hp
''')
                check('a.state=="command" and not a.battle_input_blocked')
                press('a');check('a.state=="skill"');shot('battle_skills')
                py("a.skill_cursor=c.skills.index('punch')")
                press('a');check('a.state=="target"');shot('battle_target')
                press('b');press('b')
                py('''
e.hp=int(e.max_hp*.74);stage=a.battle.hp_stage_feedback()
a.log=__import__('rpg.text',fromlist=['wrap_lines']).wrap_lines(stage)
a.state='resolve';a.delay=99999  # Fixture pause; actual resolve entry initializes delay.
''')
                assert py('len(stage)==1 and not a.battle.hp_stage_feedback() and dragon_max==9999')
                shot('dragon_stage')
                # Audio-independent normal battle progress, actual model then
                # actual result input. Stats are test-fixture party values only.
                py('''
from rpg.models import Action
a.battle.outcome='DEFEAT';a.session.settle()
a.dungeon.floor=0;a.begin_encounter();a.battle_input_blocked=False
for c in a.session.party:c.hp=c.max_hp;c.strength=c.intellect=c.agility=100
b=a.battle
for _ in range(60):
 if b.outcome:break
 b.begin_round(b.auto_actions())
 while b.queue and not b.outcome:b.step()
assert b.outcome=='VICTORY'
a.session.settle()
for i in list(a.session.pending_replacements):a.session.resolve_replacement(i,None)
a.set_result_pages(a.session.results);a.state='result';a.result_page=0
import time,pyxel
a.audio.play_victory()
a.fanfare_started_at=time.monotonic();a.fanfare_start_frame=pyxel.frame_count
a.fanfare_visual_frames=0;a.fanfare_timed_out=False
''')
                for _ in range(30):
                    if py('a.state=="explore"'):break
                    press('a')
                print('RETURN',mode,py('json.dumps((a.state,a.result_page,len(a.result_lines),a.overlay,a.battle_kind,list(a.session.pending_replacements),a.opening_input_blocked,a.battle_input_blocked))'),errors,flush=True)
                shot('return_before_assert')
                check('a.state=="explore"');shot('returned')
                assert not errors,errors
                results.append(dict(mode=mode,audio=label,release_debug_disabled=True,
                    keyboard_shortcuts_safe=True,actual_page_and_touch_inputs=True,
                    mastered_stars=True,training_relearn_and_12x=True,mastered_status_and_battle_screens=True,
                    dialog_overlay_blocked=True,dragon_stage=True,
                    victory_return=True,page_errors=errors,physical_ios=False,travel_and_party_fixtures=True))
                context.close();print('PASS',label,mode,flush=True)
    finally:server.shutdown()
    (ROOT/f'verification/phase8_browser_{label}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
