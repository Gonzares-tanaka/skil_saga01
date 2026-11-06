"""UI 6A: real browser description scroll, B15 lift, saves and silent input."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_browser_save import QuietHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playwright-path',type=Path,required=True)
    parser.add_argument('--disable-audio',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--screenshot-prefix',default='ui_phase6a')
    args = parser.parse_args()
    sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    shots = ROOT/'verification/screenshots'
    shots.mkdir(parents=True,exist_ok=True)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix='ui-phase6a-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
            for mobile in (False,True):
                mode = 'touch_emulation' if mobile else 'desktop'
                suffix = 'silent' if args.disable_audio else 'running'
                print('START:',mode,suffix,flush=True)
                settings = dict(channel='msedge',headless=True,ignore_https_errors=True,
                    args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    settings.update(pw.devices['Pixel 7'])
                    settings.pop('default_browser_type',None)
                context = pw.chromium.launch_persistent_context(str(Path(temp)/mode),**settings)
                context.add_init_script('''(()=>{
                    window.encAudioContexts=[];
                    const Native=window.AudioContext;
                    if(Native) window.AudioContext=new Proxy(Native,{construct(t,a,n){
                        const c=Reflect.construct(t,a,n); encAudioContexts.push(c); return c;
                    }});
                })();''')
                page = context.pages[0]
                errors = []
                page.on('pageerror',lambda e:errors.append(str(e)))
                game = None
                def py(source):
                    return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)',source)
                def check(expression):
                    game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)',arg=expression,timeout=20000)
                def boot():
                    nonlocal game
                    page.locator('#play').click()
                    frame = page.frame_locator('#game')
                    frame.locator('#pyxel-prompt').wait_for(timeout=120000)
                    frame.locator('#canvas').click()
                    game = page.frames[-1]
                    game.wait_for_function('''()=>{try{return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`);}catch(_){return false;}}''',timeout=120000)
                    py('''
import json
a=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
''')
                    check('a.state == "title" and a.suspend_job is None')
                    if args.disable_audio:
                        states = game.evaluate('''async()=>{
                            await Promise.all(encAudioContexts.map(async c=>{
                                await c.suspend(); c.resume=()=>Promise.reject(new Error('test unavailable'));
                            }));
                            document.dispatchEvent(new Event('visibilitychange'));
                            for(const e of ['blur','focus','pageshow']) window.dispatchEvent(new Event(e));
                            return encAudioContexts.map(c=>c.state);
                        }''')
                        assert states and all(s=='suspended' for s in states)
                cdp = context.new_cdp_session(page) if mobile else None
                def press(button,hold_ms=90):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box = game.locator(f'[data-gb="{button}"]').bounding_box()
                        assert box,button
                        p = dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[p]))
                        page.wait_for_timeout(hold_ms)
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key = dict(a='z',b='x',up='ArrowUp',down='ArrowDown',left='ArrowLeft',right='ArrowRight')[button]
                        page.keyboard.down(key)
                        page.wait_for_timeout(hold_ms)
                        page.keyboard.up(key)
                    page.wait_for_timeout(150)

                page.goto(url,wait_until='domcontentloaded')
                boot()
                press('a')
                check('a.state == "intro" and not a.opening_input_blocked')
                for _ in range(py('len(a.intro_pages)')): press('a')
                check('a.state == "hub_intro" and not a.opening_input_blocked')
                press('a'); check('a.state == "camp" and not a.opening_input_blocked')
                py('''
from rpg.elevator import b15_elevator_point, B15_ELEVATOR_SPRITE
from rpg.save import make_save_data,prepare_saved_game
from rpg.text import text_width
from rpg.suspend import make_suspend_data
c=a.session.party[0]
for sid in list(c.skills):c.forget(sid)
for sid in ('power_up','full_heal','punch'):c.learn(a.session.skills[sid])
a.session.discovered_skills.update(c.skills)
a.session.treasure.banked=15
saved_ui6=make_save_data(a)
a.save_manager.backend.write(saved_ui6)
loaded_ui6=prepare_saved_game(a,a.save_manager.backend.read())
''')
                assert py('loaded_ui6[0].treasure.banked==15 and loaded_ui6[0].treasure.unbanked==0')
                press('a'); check('a.state=="facility"')
                press('a'); check('a.overlay=="info"')
                press('a'); check('a.info_tab==1')
                assert py('a.description_scroll.offset')==0
                page.screenshot(path=str(shots/f'{args.screenshot_prefix}_{mode}_{suffix}_status_start.png'))
                check('a.description_scroll.offset == text_width(a.session.skills["power_up"].description)-148')
                page.screenshot(path=str(shots/f'{args.screenshot_prefix}_{mode}_{suffix}_status_end.png'))
                press('down')
                assert py('a.scroll==1 and a.description_scroll.offset==0')
                press('b');check('a.overlay is None')
                press('a');press('a')
                assert py('a.overlay=="info" and a.info_tab==1 and a.description_scroll.offset==0')
                press('b');press('b');check('a.state=="camp"')
                py('a.begin_encounter();a.begin_input()')
                press('a');check('a.state=="skill"')
                assert py('a.description_scroll.offset')==0
                page.screenshot(path=str(shots/f'{args.screenshot_prefix}_{mode}_{suffix}_battle_start.png'))
                check('a.description_scroll.offset == text_width(a.session.skills["power_up"].description)-148')
                page.screenshot(path=str(shots/f'{args.screenshot_prefix}_{mode}_{suffix}_battle_end.png'))
                press('down');assert py('a.skill_cursor==1 and a.description_scroll.offset==0')
                press('b');check('a.state=="command"')
                py('''
a.session.battle=None;a.battle=None;a.battle_presentation=None;a.session.settled=True
a.state,a.overlay,a.opening_input_blocked='explore',None,False
d=a.dungeon
d.floor,d.x,d.y=14,11,0
d.finale.guardians_defeated=True
d.finale.demon_defeated=False;d.defeated_bosses.discard(14)
probe_sprites=set()
probe_blt=__import__('pyxel').blt
def observe_blt(*args,**kwargs):
    if isinstance(args[2],int):probe_sprites.add(tuple(args[2:7]))
    return probe_blt(*args,**kwargs)
__import__('pyxel').blt=observe_blt
''')
                press('left')
                assert py('(d.x,d.y)==(11,0) and B15_ELEVATOR_SPRITE not in probe_sprites')
                py('notice=d.defeat_boss();d.x,d.y=11,2')
                check('B15_ELEVATOR_SPRITE in probe_sprites')
                assert py('(2,80,0,16,16) not in probe_sprites')
                assert py('d.finale.has_amrita and b15_elevator_point(d)==(12,0)')
                page.screenshot(path=str(shots/f'{args.screenshot_prefix}_{mode}_{suffix}_elevator.png'))
                py('d.x,d.y=11,0; a.session.treasure.unbanked=7')
                press('right');assert py('(d.x,d.y)==(12,0)')
                py('''
loaded_ui6=prepare_saved_game(a,make_save_data(a))
''')
                # Normal LOAD resumes at BASE with no unbanked TRZ; only the
                # one-use suspend restores the full expedition and its 7 TRZ.
                assert py('loaded_ui6[0].treasure.banked==15 and loaded_ui6[0].treasure.unbanked==0 and loaded_ui6[1].can_enter(14,12,0)')
                expected=py('json.dumps(make_suspend_data(a),sort_keys=True)')
                press('b')
                for _ in range(5):press('down')
                press('a');check('a.state=="suspend_confirm"')
                press('up');press('a');check('a.state=="title" and a.suspend_available')
                page.reload(wait_until='domcontentloaded');boot()
                press('down');press('down');press('a')
                check('a.state=="explore" and not a.opening_input_blocked')
                py('from rpg.suspend import make_suspend_data')
                assert py('json.dumps(make_suspend_data(a),sort_keys=True)')==expected
                assert py('(a.dungeon.x,a.dungeon.y)==(12,0) and not a.suspend_available')
                press('a');check('a.state=="elevator_return"')
                press('up');press('a')
                check('a.state=="return_result" and not a.opening_input_blocked')
                assert py('a.session.treasure.banked==22 and a.session.treasure.unbanked==0')
                page.screenshot(path=str(shots/f'{args.screenshot_prefix}_{mode}_{suffix}_return.png'))
                press('a');check('a.state=="amrita_offer"')
                assert py('a.dungeon.finale.has_amrita and not a.dungeon.finale.final_event_started')
                assert not errors,errors
                results.append(dict(mode=mode,audio_unavailable=args.disable_audio,
                    long_description_start_end=True,selection_and_reopen_reset=True,
                    battle_ab_dpad=True,status_ab_dpad=True,b15_left_wall_before=True,
                    lift_sprite=[1,120,8,8,8],lift_point=[12,0],legacy_icon_absent=True,
                    normal_save_roundtrip=True,indexeddb_suspend_reload_exact_once=True,
                    lift_return_banked=22,amrita_offer=True,page_errors=errors))
                print('PASS:',mode,suffix,'scroll start/end/reset, A/B/D-pad, B15 lift, SAVE/suspend/reload/return',flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results,physical_ios_tested=False,
            physical_gkd_tested=False,boss_progress_and_party_seeded=True),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:
        server.shutdown()


if __name__=='__main__': main()
