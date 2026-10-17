"""Real Pyodide status ailments and Remedy in isolated desktop/touch profiles.

Touch emulation is not a physical iOS Safari or screen-lock test.
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
    parser.add_argument('--playwright-path', type=Path)
    parser.add_argument('--fixture', type=Path, default=ROOT/'tools/browser_status_case.py')
    parser.add_argument('--output', type=Path, default=ROOT/'verification/statuses_browser.json')
    parser.add_argument('--expected-count', type=int, default=10)
    parser.add_argument('--keep-audio', action='store_true', help='Check running AudioContext rather than forced suspension')
    parser.add_argument('--title-menu', action='store_true', help='Exercise real TITLE/CONTINUE/NEW GAME input instead of the skill picker')
    parser.add_argument('--offering-menu', action='store_true', help='Exercise offering choice and story-to-boss input')
    parser.add_argument('--base-fixture', type=Path)
    parser.add_argument('--unit-fixture', type=Path,
                        help='Load fixture-only unittest module inside the actual Web runtime')
    parser.add_argument('--save-fixture', type=Path)
    parser.add_argument('--extra-fixture', type=Path, action='append', default=[],
                        help='Copy a test-only fixture into the isolated Pyodide filesystem')
    args = parser.parse_args()
    if args.playwright_path:
        sys.path.insert(0, str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix='statuses-web-', ignore_cleanup_errors=True) as td, sync_playwright() as pw:
            for mobile in (False, True):
                mode = 'touch_emulation' if mobile else 'desktop'
                print('START:', mode, flush=True)
                settings = dict(channel='msedge', headless=True, ignore_https_errors=True,
                                args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    settings.update(pw.devices['Pixel 7'])
                    settings.pop('default_browser_type', None)
                context = pw.chromium.launch_persistent_context(str(Path(td)/mode), **settings)
                context.add_init_script('''(() => {
                    window.enemyTestContexts = [];
                    const Native = window.AudioContext;
                    if (Native) window.AudioContext = new Proxy(Native, {
                        construct(target,args,newTarget) {
                            const ctx = Reflect.construct(target,args,newTarget);
                            window.enemyTestContexts.push(ctx); return ctx;
                        }
                    });
                })();''')
                page = context.pages[0]
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='domcontentloaded')
                page.locator('#play').click()
                frame = page.frame_locator('#game')
                frame.locator('#pyxel-prompt').wait_for(timeout=120000)
                frame.locator('#canvas').click()
                game = page.frames[-1]
                game.wait_for_function('''() => {
                    try { return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`); } catch (_) { return false; }
                }''', timeout=120000)
                states = game.evaluate('''async (keepAudio) => {
                    await Promise.all(window.enemyTestContexts.map(async ctx => {
                        if (keepAudio) await ctx.resume();
                        else {
                            await ctx.suspend();
                            ctx.resume = () => Promise.reject(new Error('enemy-test audio unavailable'));
                        }
                    }));
                    return window.enemyTestContexts.map(ctx => ctx.state);
                }''', args.keep_audio)
                assert states and all(state == ('running' if args.keep_audio else 'suspended') for state in states), states
                game.evaluate('''() => {
                    document.dispatchEvent(new Event('visibilitychange'));
                    window.dispatchEvent(new Event('blur'));
                    window.dispatchEvent(new Event('focus'));
                    window.dispatchEvent(new Event('pageshow'));
                }''')
                fixture = args.fixture.read_text(encoding='utf8')
                if args.extra_fixture:
                    prelude = 'from rpg.content import ROOT\n'
                    for path in args.extra_fixture:
                        relative = path.resolve().relative_to(ROOT).as_posix()
                        prelude += (f'_test_path = ROOT / {relative!r}\n'
                                    '_test_path.parent.mkdir(parents=True, exist_ok=True)\n'
                                    f'_test_path.write_text({path.read_text(encoding="utf-8-sig")!r}, encoding="utf8")\n')
                if args.unit_fixture:
                    source = args.unit_fixture.read_text(encoding='utf8')
                    # Fixture files must exist before the test module runs.
                    fixture_prelude = prelude if args.extra_fixture else ''
                    fixture = (fixture_prelude + 'import types, sys, pyxel\n'
                               'pyxel._tests_initialized = True\n'
                               '_skill_test_module = types.ModuleType("_skill_foundation_tests")\n'
                               'sys.modules[_skill_test_module.__name__] = _skill_test_module\n'
                               f'exec({source!r}, _skill_test_module.__dict__)\n') + fixture
                elif args.extra_fixture:
                    fixture = prelude + fixture
                if args.base_fixture:
                    prelude = args.base_fixture.read_text(encoding='utf8')
                    assert prelude.rstrip().endswith('run_cases()')
                    fixture = prelude.rstrip()[:-len('run_cases()')] + '\n' + fixture
                if args.save_fixture:
                    fixture = f'import json\n_old_skill_save = json.loads({args.save_fixture.read_text(encoding="utf8")!r})\n' + fixture
                raw = game.evaluate('(source) => window.pyxelContext.pyodide.runPython(source)', fixture)
                data = json.loads(raw)
                assert data['count'] == args.expected_count
                if args.unit_fixture:
                    # Actual runtime input: keyboard on desktop, HTML D-PAD/A/B
                    # pointer events on touch. The fixture starts at skill #0.
                    def check(expression):
                        game.wait_for_function('(s) => window.pyxelContext.pyodide.runPython(s)',
                                               arg=expression, timeout=10000)
                    cdp = context.new_cdp_session(page) if mobile else None
                    def press(button):
                        if mobile:
                            box=game.locator(f'[data-gb="{button}"]').bounding_box()
                            point=dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)
                            cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[point]))
                            page.wait_for_timeout(100)
                            cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                        else:
                            code=dict(up='ArrowUp',down='ArrowDown',a='z',b='x')[button]
                            page.keyboard.down(code)
                            page.wait_for_timeout(100)
                            page.keyboard.up(code)
                        page.wait_for_timeout(120)
                    if args.offering_menu:
                        press('b')
                        check('_foundation_live_app.state == "camp" and _foundation_live_app.audio.current_bgm == "bgm_hub"')
                        game.evaluate('() => window.pyxelContext.pyodide.runPython("_foundation_live_app.show_amrita_offer()")')
                        press('a')
                        check('_foundation_live_app.state == "final_story" and _foundation_live_app.audio.current_bgm == "bgm_omen"')
                        shots=ROOT/'verification/screenshots'; shots.mkdir(parents=True,exist_ok=True)
                        suffix='running' if args.keep_audio else 'unavailable'
                        shot=shots/f'omen_music_{mode}_{suffix}.png'
                        page.screenshot(path=str(shot))
                        pages=game.evaluate('() => window.pyxelContext.pyodide.runPython("len(_foundation_live_app.final_story_pages())")')
                        for story_page in range(1, pages):
                            press('a')
                            check(f'_foundation_live_app.final_story_page == {story_page} and _foundation_live_app.audio.current_bgm == "bgm_omen"')
                        press('a')
                        check('_foundation_live_app.state == "command" and _foundation_live_app.audio.current_bgm == "bgm_boss" and _foundation_live_app.battle.elysion_barrier_active')
                        data.update(real_offering_input=True, later_keeps_hub=True,
                                    story_omen_then_boss=True, screenshot=shot.relative_to(ROOT).as_posix())
                    elif args.title_menu:
                        shots=ROOT/'verification/screenshots'; shots.mkdir(parents=True,exist_ok=True)
                        suffix='running' if args.keep_audio else 'unavailable'
                        shot=shots/f'title_logo_web_{mode}_{suffix}.png'
                        page.screenshot(path=str(shot))
                        press('down'); check('_foundation_live_app.title_cursor == 1')
                        press('a'); check('_foundation_live_app.state == "title_no_save"')
                        press('b'); check('_foundation_live_app.state == "title"')
                        game.evaluate('() => window.pyxelContext.pyodide.runPython("_title_backend.write(_title_saved)")')
                        press('a')
                        check('_foundation_live_app.state == "camp" and _foundation_live_app.session.treasure.banked == 17')
                        game.evaluate('() => window.pyxelContext.pyodide.runPython("_title_show_again()")')
                        press('up'); check('_foundation_live_app.title_cursor == 0')
                        press('a')
                        check('_foundation_live_app.state == "intro" and _foundation_live_app.audio.current_bgm == "bgm_title"')
                        for story_page in (1,2,3):
                            press('a')
                            check(f'_foundation_live_app.intro_page == {story_page} and _foundation_live_app.state == "intro" and _foundation_live_app.audio.current_bgm == "bgm_title"')
                        press('a')
                        check('_foundation_live_app.state == "hub_preview" and _foundation_live_app.audio.current_bgm == "bgm_hub"')
                        check('_foundation_live_app.state == "hub_intro"')
                        # The existing opening code requires a released-input
                        # frame after PREVIEW, before a fresh A is accepted.
                        check('not _foundation_live_app.opening_input_blocked')
                        press('a'); check('_foundation_live_app.state == "camp"')
                        data.update(real_title_menu_continue_new_game=True,missing_save_B_back=True,
                                    opening_title_then_hub=True,screenshot=shot.relative_to(ROOT).as_posix())
                    else:
                        press('down')
                        check('_foundation_live_app.skill_cursor == 1')
                        press('a')
                        check('len(_foundation_live_app.actions) == 1 and _foundation_live_app.state == "command"')
                        press('b')
                        check('_foundation_live_app.actor_position == 0 and not _foundation_live_app.actions')
                    data['real_runtime_input'] = 'D-PAD/A/B pointer events' if mobile else 'keyboard down/Z/X'
                assert not errors, errors
                results.append(dict(mode=mode, engine='Edge Chromium', audio_states=states,
                                    errors=errors, **data))
                context.close()
        report = dict(cases=results, physical_ios_tested=False, physical_screen_lock_tested=False)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('PASS: desktop/touch Pyodide; audio', 'running' if args.keep_audio else 'suspended/unavailable', flush=True)
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
