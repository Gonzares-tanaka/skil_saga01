"""Real Web keys/touches: predrawn countdown, held input, exact resume and silent audio."""
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
        with tempfile.TemporaryDirectory(prefix='encounter04-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
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
from rpg.tiles import FLOOR_TILES
a=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
def enc_pair(floor):
    d=a.dungeon
    return next((x,y) for x,y in sorted(d.reachable(floor))
        if d.tile(floor,x,y) in FLOOR_TILES and d.tile(floor,x+1,y) in FLOOR_TILES)
def enc_escape():
    a.battle.outcome='ESCAPE'
    a.battle.queue.clear()
    a.session.settle()
    a.finish_results()
enc_rolls=0
def enc_zero():
    global enc_rolls
    enc_rolls+=1
    return 0.0
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
                py('a.enter_dungeon(); a.dungeon.defeated_bosses.update((4,9))')
                assert py('a.dungeon.settings["encounter_step_ranges"] == [[7,16],[9,22],[9,22]]')
                intervals = []
                # Real key/touch movement, exact sampled N, and a real escape exit.
                for floor in (3,8,13):
                    py(f'a.dungeon.floor={floor}; a.dungeon.x,a.dungeon.y=enc_pair({floor}); a.begin_encounter(); enc_escape()')
                    check('a.state == "explore" and not a.battle_input_blocked')
                    n = py('a.dungeon.encounter_remaining')
                    assert (7 if floor==3 else 9) <= n <= (16 if floor==3 else 22)
                    intervals.append(n)
                    steps = py('a.dungeon.steps')
                    for i in range(n-1):
                        press('right' if i%2==0 else 'left')
                        check(f'a.state == "explore" and a.dungeon.encounter_remaining == {n-i-1}')
                    press('right' if (n-1)%2==0 else 'left')
                    check('a.state == "battle_transition"')
                    assert py('a.dungeon.steps')==steps+n
                    py('enc_escape()')
                    check('a.state == "explore" and not a.battle_input_blocked')
                    assert py('a.dungeon.encounter_remaining') >= (7 if floor==3 else 9)
                py('\nd=a.dungeon\nfor f in range(14):\n    w,h=d.map_bounds(f)\n    run=next(((x,y) for y in range(h) for x in range(w-8)\n        if all(d.tile(f,x+i,y) in FLOOR_TILES for i in range(9))),None)\n    if run:\n        d.floor,d.x,d.y=f,*run\n        break\nd.encounter_remaining=16\nenc_before=(d.steps,d.x,d.y)\n')
                press('right',900)
                held_steps = py('a.dungeon.steps-enc_before[0]')
                assert held_steps>=2
                assert py('a.dungeon.x-enc_before[1] == a.dungeon.steps-enc_before[0]')
                assert py('a.dungeon.encounter_remaining == 16-(a.dungeon.steps-enc_before[0])')
                py('a.dungeon.floor=8; a.dungeon.x,a.dungeon.y=enc_pair(8); a.dungeon.encounter_remaining=17')
                for button in ('right','left','right','left','right'): press(button)
                check('a.state == "explore" and a.dungeon.encounter_remaining == 12')
                rng = py('json.dumps(a.session.rng.getstate())')
                steps = py('a.dungeon.steps')
                press('b')
                page.wait_for_timeout(500)
                assert py('a.dungeon.encounter_remaining')==12
                for _ in range(5): press('down')
                press('a'); check('a.state == "suspend_confirm"')
                press('up'); press('a'); check('a.state == "title" and a.suspend_available')
                assert py('a.dungeon.steps')==steps
                page.reload(wait_until='domcontentloaded'); boot()
                press('down'); press('down'); press('a')
                check('a.state == "explore" and not a.opening_input_blocked')
                assert py('a.dungeon.encounter_remaining')==12
                assert py('a.dungeon.steps')==steps
                assert py('json.dumps(a.session.rng.getstate())')==rng
                assert not py('a.suspend_available')
                for i in range(11):
                    press('left' if i%2==0 else 'right')
                    check(f'a.state == "explore" and a.dungeon.encounter_remaining == {11-i}')
                page.screenshot(path=str(shots/f'encounter04_{mode}_{suffix}_resumed.png'))
                press('right'); check('a.state == "battle_transition"')
                assert not errors,errors
                results.append(dict(mode=mode,audio_unavailable=args.disable_audio,
                    sampled_real_steps_all_areas=intervals,exact_nth_encounter=True,
                    interval_redrawn_after_escape=True,held_move_cells=held_steps,
                    held_steps_match_position=True,menu_no_steps=True,
                    reload_remaining_twelve=True,reload_rng_exact=True,
                    suspend_consumed=True,page_errors=errors))
                print('PASS:',mode,suffix,'sampled N steps, held input, remaining-twelve resume',flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results,physical_ios_tested=False,
            physical_gkd_tested=False,battle_outcomes_seeded=True),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:
        server.shutdown()


if __name__=='__main__': main()
