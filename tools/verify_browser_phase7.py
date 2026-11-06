"""Real browser storage/ending/touch flow. Combat and travel fixtures disclosed."""
import argparse
import ast
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
    helper=(ROOT/'tools/verify_phase7.py').read_text(encoding='utf8')
    functions='\n\n'.join(ast.get_source_segment(helper,n) for n in ast.parse(helper).body
                         if isinstance(n,ast.FunctionDef) and n.name in ('prepare_party','fight'))
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    label='unavailable' if args.disable_audio else 'running';results=[]
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='phase7-browser-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
            for mobile in (False,True):
                mode='touch' if mobile else 'desktop';print('START',label,mode,flush=True)
                options=dict(channel='msedge',headless=True,ignore_https_errors=True,args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:options.update(pw.devices['Pixel 7']);options.pop('default_browser_type',None)
                context=pw.chromium.launch_persistent_context(str(Path(temp)/mode),**options)
                context.add_init_script('''window.phase7Contexts=[];const Native=window.AudioContext;
                if(Native)window.AudioContext=new Proxy(Native,{construct(t,a,n){
                  const c=Reflect.construct(t,a,n);phase7Contexts.push(c);return c;}});''')
                page=context.pages[0];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                game=None
                def py(code):return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)',code)
                def check(code):game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)',arg=code,timeout=25000)
                def boot():
                    nonlocal game
                    page.locator('#play').click();frame=page.frame_locator('#game')
                    frame.locator('#pyxel-prompt').wait_for(timeout=120000);frame.locator('#canvas').click();game=page.frames[-1]
                    game.wait_for_function('''()=>{try{return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`)}catch(_){return false}}''',timeout=120000)
                    py('import json\nfrom unittest.mock import patch\na=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))\n'+functions)
                    check('a.state=="title" and a.suspend_job is None')
                    assert py('a.save_manager.backend.__class__.__name__')=='BrowserSaveBackend'
                    if args.disable_audio:
                        states=game.evaluate('''async()=>{await Promise.all(phase7Contexts.map(async c=>{
                          await c.suspend();c.resume=()=>Promise.reject(new Error('intentional failure'))}));
                          document.dispatchEvent(new Event('visibilitychange'));
                          for(const e of ['blur','focus','pageshow'])window.dispatchEvent(new Event(e));
                          return phase7Contexts.map(c=>c.state)}''')
                        assert states and all(s=='suspended' for s in states)
                cdp=context.new_cdp_session(page) if mobile else None
                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box=game.locator(f'[data-gb="{button}"]').bounding_box();assert box
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)]))
                        page.wait_for_timeout(90);cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key=dict(a='z',b='x',up='ArrowUp',down='ArrowDown')[button]
                        page.keyboard.down(key);page.wait_for_timeout(90);page.keyboard.up(key)
                    page.wait_for_timeout(150)
                def shot(name):page.screenshot(path=str(shots/f'phase7_web_{label}_{mode}_{name}.png'))
                def final_battle():
                    py('a.show_amrita_offer()');press('a');check('a.state=="final_story"')
                    for _ in range(py('len(a.final_story_pages())')):press('a')
                    check('a.state=="command"');py('fight(a)')
                page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded');boot()
                press('a');check('a.state=="intro" and not a.opening_input_blocked')
                for _ in range(py('len(a.intro_pages)')):press('a')
                check('a.state=="hub_intro" and not a.opening_input_blocked');press('a');check('a.state=="camp"')
                py('''
from rpg.save import make_save_data
prepare_party(a.session)
a.save_manager.backend.write(make_save_data(a))
old_save=json.dumps(a.save_manager.backend.read(),sort_keys=True)
before_party=[(c.strength,dict(c.skill_uses)) for c in a.session.party]
f=a.dungeon.finale;f.guardians_defeated=f.demon_defeated=f.has_amrita=True
a.dungeon.defeated_bosses.update((4,9,14))
class FailedStorage:
    def setItem(self,*args):raise RuntimeError('intentional quota failure')
a.save_manager.backend.storage=FailedStorage()
''')
                final_battle();check('a.state=="clear_save_error"');shot('save_failure')
                assert not py('a.dungeon.completion.main_game_cleared')
                py('a.save_manager.backend.storage=None')
                assert py('json.dumps(a.save_manager.backend.read(),sort_keys=True)==old_save')
                press('a');check('a.state=="ending"')
                assert py('a.save_manager.backend.read()["completion"]["main_game_cleared"]')
                for _ in range(py('len(a.final_ending_pages())')):press('a')
                check('a.state=="credits"');shot('credits')
                assert py("a.credits_data['lines'].count('GONZARES TANAKA')==4")
                assert py('a.audio.current_bgm=="bgm_credits"')
                py("a.postgame_frame=(120+len(a.credits_data['lines'])*a.credits_data['line_height'])*a.credits_data['scroll_frames_per_pixel']-2")
                check('a.state=="ending_end"');shot('end');check('a.state=="extra_quest_title"');shot('extra')
                press('a');check('a.state=="extra_quest_story"')
                for _ in range(10):
                    if py('a.state=="title"'):break
                    press('a')
                check('a.state=="title"');press('a');check('a.state=="camp"')
                assert py('a.dungeon.completion.main_game_cleared and a.dungeon.finale.has_amrita')
                assert py('[(c.strength,dict(c.skill_uses)) for c in a.session.party]==before_party')
                py('''
from rpg.postgame import dragon_location
floor,point=dragon_location(a.dungeon)
a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point;a.state='explore'
''')
                shot('symbol');press('a');check('a.state=="dragon_warning"');press('b');check('a.state=="explore"')
                press('a');press('up');press('a');check('a.battle_kind=="dragon" and a.state=="command"')
                py('fight(a)');check('a.state=="dragon_victory_story"');shot('dragon_victory')
                best=py('a.dungeon.completion.ancient_dragon_best_turns');assert best>0
                for _ in range(15):
                    if py('a.state=="camp"'):break
                    press('a')
                check('a.state=="camp"');assert py('a.save_manager.backend.read()["completion"]["ancient_dragon_victories"]==1')
                py('a.continue_game();a.session.party[0].strength+=3')
                final_battle();check('a.state=="ending"');assert not py('a.ending_first')
                assert py('a.save_manager.backend.read()["completion"]["ancient_dragon_best_turns"]')==best
                strength=py('a.save_manager.backend.read()["party"][0]["strength"]')
                # Closing/reloading during ending must resume a valid cleared HUB.
                page.reload(wait_until='domcontentloaded');boot();press('down');press('a');check('a.state=="camp"')
                assert py('a.session.party[0].strength')==strength
                assert py('a.dungeon.completion.ancient_dragon_best_turns')==best
                final_battle();check('a.state=="ending"')
                for _ in range(py('len(a.final_ending_pages())')):press('a')
                check('a.state=="credits"');press('a');check('a.state=="ending_end"');check('a.state=="title"')
                assert not errors,errors
                result=dict(mode=mode,audio_unavailable=args.disable_audio,success=True,
                    real_localstorage=True,clear_save_failure_preserved_old_data=True,
                    first_end_extra_then_continue=True,dragon_best_turns=best,
                    reload_mid_ending_preserved_growth_and_records=True,repeat_credits_skip_no_extra=True,
                    combat_model_fixture=True,credits_clock_fastforward_fixture=True,
                    actual_keyboard_or_touch_for_UI=True,page_errors=errors)
                results.append(result);context.close();print('PASS',label,mode,flush=True)
        (ROOT/f'verification/phase7_browser_{label}.json').write_text(json.dumps(dict(cases=results,
            physical_ios_tested=False,physical_gkd_tested=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:server.shutdown()


if __name__=='__main__':main()
