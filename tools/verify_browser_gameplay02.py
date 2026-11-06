"""Final Web payload: real keyboard/touch travel, purchases, suspend and returns.

Temporary browser profiles and synthetic progress never touch player saves.
Boss flags/quest coordinates are seeded; menu decisions use real input events.
"""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from verify_browser_save import QuietHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playwright-path', type=Path, required=True)
    parser.add_argument('--disable-audio', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    shots = ROOT/'verification/screenshots'
    shots.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix='gameplay02-', ignore_cleanup_errors=True) as temp, sync_playwright() as pw:
            for mobile in (False, True):
                mode = 'touch_emulation' if mobile else 'desktop'
                suffix = 'silent' if args.disable_audio else 'running'
                print('START:', mode, suffix, flush=True)
                settings = dict(channel='msedge', headless=True, ignore_https_errors=True,
                    args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    settings.update(pw.devices['Pixel 7'])
                    settings.pop('default_browser_type', None)
                context = pw.chromium.launch_persistent_context(str(Path(temp)/mode), **settings)
                context.add_init_script('''(() => {
                    window.gameplayContexts=[];
                    const Native=window.AudioContext;
                    if(Native) window.AudioContext=new Proxy(Native,{construct(t,a,n){
                        const c=Reflect.construct(t,a,n); window.gameplayContexts.push(c); return c;
                    }});
                })();''')
                page = context.pages[0]
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                game = None
                def py(source):
                    return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)', source)
                def check(expression):
                    game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)', arg=expression, timeout=20000)
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
`);}catch(_){return false;}}''', timeout=120000)
                    py('''
import json
from rpg.items import RETURN_FEATHER
from rpg.suspend import make_suspend_data
from rpg.quests import spawn_candidates
from rpg.elevator import unlocked_destinations, b15_elevator_point
from rpg.save import make_save_data
a=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
''')
                    check('a.state == "title" and a.suspend_job is None')
                    if args.disable_audio:
                        states = game.evaluate('''async()=>{
                            await Promise.all(gameplayContexts.map(async c=>{
                                await c.suspend(); c.resume=()=>Promise.reject(new Error('test audio unavailable'));
                            }));
                            document.dispatchEvent(new Event('visibilitychange'));
                            for(const e of ['blur','focus','pageshow']) window.dispatchEvent(new Event(e));
                            return gameplayContexts.map(c=>c.state);
                        }''')
                        assert states and all(s == 'suspended' for s in states)
                cdp = context.new_cdp_session(page) if mobile else None
                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box = game.locator(f'[data-gb="{button}"]').bounding_box()
                        assert box, button
                        p = dict(x=box['x']+box['width']/2, y=box['y']+box['height']/2)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[p]))
                        page.wait_for_timeout(90)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                    else:
                        key = dict(a='z', b='x', up='ArrowUp', down='ArrowDown', left='ArrowLeft', right='ArrowRight')[button]
                        page.keyboard.down(key)
                        page.wait_for_timeout(90)
                        page.keyboard.up(key)
                    page.wait_for_timeout(160)
                def finish_field():
                    for _ in range(12):
                        if py('a.state') != 'field_event': return
                        press('a')
                    raise AssertionError('field message did not finish')
                def camp(index):
                    py(f'a.enter_camp(); a.camp_cursor={index}; a.opening_input_blocked=False')
                    check('a.state == "camp"')
                def elevator(index):
                    camp(4)
                    press('right'); check('a.camp_cursor == 5')
                    press('a'); check('a.state == "elevator"')
                    for _ in range(index): press('down')
                    press('a')
                    check('not a.opening_input_blocked')
                    finish_field()
                    check('a.state == "explore"')

                page.goto(url, wait_until='domcontentloaded')
                boot()
                py('a.start_new_game(); a.enter_camp(); a.opening_input_blocked=False')
                assert py('a.session.treasure.banked') == 3
                camp(4); press('right'); press('a')
                check('a.state == "elevator"')
                assert py('unlocked_destinations(a.dungeon) == []')
                press('a'); check('a.state == "camp"')
                # Four products; purchase the new one using real SHOP input.
                camp(3); press('a'); press('a'); check('a.state == "shop"')
                py('a.session.treasure.banked=20')
                for _ in range(3): press('down')
                press('a')
                assert py('a.session.inventory.counts[RETURN_FEATHER]') == 1
                assert py('a.session.treasure.banked') == 17
                page.screenshot(path=str(shots/f'gameplay02_{mode}_{suffix}_shop.png'))
                # Save at GUILD, destroy the Python instance, then CONTINUE.
                camp(0); press('a'); press('down'); press('down'); press('a'); press('a')
                check('a.state == "save_result"')
                page.reload(wait_until='domcontentloaded'); boot()
                press('down'); press('a'); check('a.state == "camp" and not a.opening_input_blocked')
                assert py('a.session.inventory.counts[RETURN_FEATHER]') == 1
                assert py('a.session.treasure.banked') == 17
                # Seed cleared bosses. This does not claim real boss playthrough.
                py('''
a.dungeon.floor=4
notice2=a.dungeon.defeat_boss()
a.dungeon.floor=9
notice3=a.dungeon.defeat_boss()
''')
                assert py('any("LV2" in line for line in notice2)')
                assert py('any("LV3" in line for line in notice3)')
                # Accept Lv2 EXPLORE through actual flavor/accept UI.
                camp(2); press('a'); press('a'); press('down'); press('a'); press('a')
                check('a.state == "quest_preview"')
                for _ in range(py('len(a.quest_flavor_pages(a.exploration.pending_quest))')): press('a')
                check('a.state == "quest_board" and a.exploration.active is not None')
                py('''
q=a.exploration.active
q['target_floor']=6
q['points']=[list(spawn_candidates(a.dungeon,5)[0])]
''')
                elevator(0)
                assert py('a.dungeon.floor') == 5
                assert py('a.audio.current_bgm') == 'bgm_area2'
                py('a.session.treasure.unbanked=9; a.session.party[0].statuses={"poison":3}')
                expected = json.loads(py('json.dumps(make_suspend_data(a))'))
                press('b')
                for _ in range(5): press('down')
                press('a'); check('a.state == "suspend_confirm"')
                press('up'); press('a'); check('a.state == "title" and a.suspend_available')
                page.reload(wait_until='domcontentloaded'); boot()
                press('down'); press('down'); press('a')
                check('a.state == "explore" and not a.opening_input_blocked')
                assert json.loads(py('json.dumps(make_suspend_data(a))')) == expected
                assert not py('a.suspend_available')
                # Complete controlled quest, cancel feather once, then return.
                py('a.dungeon.x,a.dungeon.y=a.exploration.active["points"][0]')
                press('a'); finish_field()
                assert py('a.exploration.surveyed')
                press('b'); press('down'); press('down'); press('a')
                check('a.state == "items"')
                for _ in range(3): press('down')
                press('a'); check('a.state == "feather_return"')
                press('b'); check('a.state == "items" and not a.opening_input_blocked')
                assert py('a.session.inventory.counts[RETURN_FEATHER]') == 1
                press('a'); press('up'); press('a')
                check('a.state == "quest_thanks" and not a.opening_input_blocked')
                for _ in range(py('len(a.quest_thanks_pages())')): press('a')
                check('a.state == "quest_reward"')
                assert py('a.session.inventory.counts[RETURN_FEATHER]') == 0
                assert py('a.session.treasure.banked') == 30
                assert py('a.session.treasure.unbanked') == 0
                assert py('a.exploration.quest_clear_counts["explore"]') == 1
                assert py('a.audio.current_bgm') == 'bgm_hub'
                press('a'); check('a.state == "camp"')
                elevator(1)
                assert py('a.dungeon.floor') == 10
                assert py('a.audio.current_bgm') == 'bgm_area3'
                assert py('[f for f,_ in unlocked_destinations(a.dungeon)] == [5,10]')
                # Demon completion, B15 arrival, return and Amrita offer.
                py('''
a.dungeon.floor=14
a.dungeon.finale.guardians_defeated=True
notice15=a.dungeon.defeat_boss()
''')
                assert py('any("B15" in line for line in notice15)')
                elevator(2)
                assert py('(a.dungeon.floor,a.dungeon.x,a.dungeon.y) == (14,4,28)')
                assert py('a.audio.current_bgm') == 'bgm_area3'
                page.screenshot(path=str(shots/f'gameplay02_{mode}_{suffix}_b15.png'))
                press('a'); check('a.state == "elevator_return"')
                press('up'); press('a'); check('a.state == "return_result" and not a.opening_input_blocked')
                press('a'); check('a.state == "amrita_offer"')
                assert py('a.dungeon.finale.has_amrita and not a.dungeon.finale.final_event_started')
                assert not errors, errors
                results.append(dict(mode=mode, audio_unavailable=args.disable_audio,
                    six_facilities=True, locked_gate_refused=True, feather_price=3,
                    normal_save_reload_feather=1, old_phase_single_use_suspend=True,
                    exact_elevator_suspend=True, quest_lv2_flavor_accept=True,
                    feather_cancel_no_charge=True, quest_return_banked=30,
                    b6_area2=True, b11_b15_area3=True, b15_point=[4,28],
                    b15_return_amrita_offer=True, page_errors=errors))
                print('PASS:', mode, suffix, 'SHOP, SAVE/LOAD, QUEST, ELEVATOR, SUSPEND, feather, B15 offer', flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results, physical_ios_tested=False,
            physical_gkd_tested=False, boss_progress_seeded=True), ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
