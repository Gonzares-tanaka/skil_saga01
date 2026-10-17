"""Real Web/Pyodide quest symbols before SAVE and after reload/CONTINUE.

Uses an isolated browser profile and localStorage. Floor/boss progress and
camera placement are fixtures; controls use actual keyboard or touch input.
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
sys.path.insert(0, str(ROOT / 'tools'))
from verify_browser_save import QuietHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel', default='msedge')
    parser.add_argument('--engine', choices=('chromium', 'webkit'), default='chromium')
    parser.add_argument('--playwright-path', type=Path)
    parser.add_argument('--before-fix', action='store_true')
    parser.add_argument('--b14-only', action='store_true')
    args = parser.parse_args()
    if args.playwright_path:
        sys.path.insert(0, str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    reports = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        with tempfile.TemporaryDirectory(prefix='quest-web-', ignore_cleanup_errors=True) as td, sync_playwright() as pw:
            for mobile in (False, True):
                options = dict(headless=True, ignore_https_errors=True)
                if args.engine == 'chromium':
                    options.update(channel=args.channel,
                                   args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    options.update(pw.devices['iPhone 13' if args.engine == 'webkit' else 'Pixel 7'])
                    options.pop('default_browser_type', None)
                context = getattr(pw, args.engine).launch_persistent_context(str(Path(td)/str(mobile)), **options)
                page = context.pages[0]
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                cdp = context.new_cdp_session(page) if args.engine == 'chromium' else None

                def boot():
                    page.goto(url, wait_until='domcontentloaded')
                    page.locator('#play').click()
                    frame = page.frame_locator('#game')
                    frame.locator('#pyxel-prompt').wait_for(timeout=120000)
                    frame.locator('#canvas').click()
                    game = page.frames[-1]
                    game.wait_for_function('''() => {
                        try { return !!window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o, DungeonApp) for o in gc.get_objects())
`); } catch (_) { return false; }
                    }''', timeout=120000)
                    game.evaluate('''() => window.pyxelContext.pyodide.runPython(`
test_app = next(o for o in gc.get_objects() if isinstance(o, DungeonApp))
import json, pyxel
from unittest.mock import patch
from rpg.save import make_save_data
from rpg.quests import QUEST_SYMBOLS
`)''')
                    return game

                game = boot()

                def py(code):
                    return game.evaluate('(code) => window.pyxelContext.pyodide.runPython(code)', code)

                def press(button):
                    if mobile:
                        if cdp is None:
                            game.locator(f'[data-gb="{button}"]').tap()
                            page.wait_for_timeout(220)
                            return
                        box = game.locator(f'[data-gb="{button}"]').bounding_box()
                        assert box
                        point = dict(x=box['x']+box['width']/2, y=box['y']+box['height']/2)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[point]))
                        page.wait_for_timeout(100)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                    else:
                        key = {'a':'z','b':'x','down':'ArrowDown','up':'ArrowUp'}[button]
                        page.keyboard.down(key)
                        page.wait_for_timeout(100)
                        page.keyboard.up(key)
                    page.wait_for_timeout(120)

                def draw_symbols():
                    return json.loads(py('''
d, e = test_app.dungeon, test_app.exploration
points = e.visible_points()
if points:
    target = points[0]
    from rpg.tiles import FLOOR_TILES
    view = next(p for p in sorted(d.reachable(d.floor))
                if d.tile(d.floor, *p) in FLOOR_TILES
                and 2 <= max(abs(p[0]-target[0]), abs(p[1]-target[1])) <= 4)
    d.x, d.y = view
captured = []
original_blt = pyxel.blt
def capture(*args, **kwargs):
    if args[2:7] == (*QUEST_SYMBOLS[e.active['type']], 8, 8):
        captured.append(list(args[:7]))
    original_blt(*args, **kwargs)
with patch.object(pyxel, 'blt', side_effect=capture):
    test_app.draw()
assert len(captured) == len(points), (captured, points)
if points:
    # A blit outside the clipped map is not proof of an on-screen symbol.
    assert 2 <= captured[0][0] <= 90 and 13 <= captured[0][1] <= 101, captured[0]
json.dumps({'points': points, 'draws': captured, 'progress': e.active['progress']})
'''))

                cases = [(13, 'investigate')]
                if not args.before_fix and not args.b14_only:
                    cases = [(f, kind) for f in (0,5,9,10,13,14)
                             for kind in ('explore','investigate','hunt')]
                for floor, kind in cases:
                    print('START WEB QUEST:', 'touch' if mobile else 'desktop', kind, floor+1, flush=True)
                    py(f'''
test_app.start_new_game()
test_app.enter_camp()
test_app.opening_input_blocked = False
s, d, e = test_app.session, test_app.dungeon, test_app.exploration
d.defeated_bosses.update((4,9))
with patch.object(s.rng, 'choice', return_value={floor}):
    e.accept({floor//5+1}, quest_type={kind!r})
assert e.active['target_floor'] == {floor+1}
d.debug_floor({floor})
d.x, d.y = e.active['points'][0][0] + 3, e.active['points'][0][1]
test_app.state = 'explore'
''')
                    before = draw_symbols()
                    expected = json.loads(py('json.dumps(make_save_data(test_app))'))
                    py('test_app.enter_camp()')
                    # Real GUILD/SAVE menu, A/B only; SAVE must not mutate the contract.
                    press('a'); press('down'); press('down'); press('a'); press('a')
                    assert py('test_app.state') == 'save_result'
                    assert py('test_app.save_message') == 'セーブしました。'
                    assert json.loads(py('json.dumps(make_save_data(test_app))')) == expected
                    raw = game.evaluate('() => localStorage.getItem("skill_seekers_save_v1")')
                    assert json.loads(raw) == expected
                    assert 'points' not in expected['active_quest']
                    py(f"test_app.dungeon.debug_floor({floor}); test_app.state='explore'")
                    after_save = draw_symbols()
                    assert after_save['points'] == before['points']
                    reloaded = args.before_fix or kind == 'investigate' and floor in (5,13,14)
                    if reloaded:
                        game = boot()  # New Pyodide/game process, same localStorage.
                    else:
                        py("test_app.state='title'; test_app.title_cursor=0; test_app.opening_input_blocked=False")
                    press('down'); press('a')
                    assert py('test_app.state') == 'camp'
                    assert json.loads(py('json.dumps(make_save_data(test_app))')) == expected
                    py(f"test_app.dungeon.debug_floor({floor}); test_app.state='explore'")
                    after_load = draw_symbols()
                    assert len(after_load['points']) == len(before['points'])
                    if kind == 'investigate':
                        # Partial progress persisted without storing coordinates.
                        py('''
d, e = test_app.dungeon, test_app.exploration
d.x, d.y = e.active['points'][0]
e.investigate()
test_app.enter_camp()
''')
                        press('a'); press('down'); press('down'); press('a'); press('a')
                        if reloaded:
                            game = boot()
                        else:
                            py("test_app.state='title'; test_app.title_cursor=0; test_app.opening_input_blocked=False")
                        press('down'); press('a')
                        py(f"test_app.dungeon.debug_floor({floor}); test_app.state='explore'")
                        remaining = draw_symbols()
                        assert remaining['progress'] == 1
                        assert len(remaining['points']) == len(before['points']) - 1
                        py('''
d, e = test_app.dungeon, test_app.exploration
d.x, d.y = e.active['investigated_points'][0]
assert not e.investigate()
assert e.active['progress'] == 1
''')
                        # The duplicate-check fixture moved onto a surveyed point.
                        # Refocus on a remaining symbol before taking visual evidence.
                        remaining = draw_symbols()
                    row = dict(floor=floor+1, type=kind, touch_emulation=mobile, engine=args.engine,
                               no_save_symbols=len(before['points']), save_symbols=len(after_save['points']),
                               reload_continue_symbols=len(after_load['points']), actual_local_storage=True,
                               full_browser_reload=reloaded,
                               partial_progress_checked=kind=='investigate', physical_phone=False)
                    reports.append(row)
                    if floor == 13 and kind == 'investigate':
                        output = ROOT/'verification/screenshots'
                        output.mkdir(parents=True, exist_ok=True)
                        phase = 'before' if args.before_fix else 'after'
                        page.wait_for_timeout(100)
                        page.screenshot(path=str(output/f'quest_b14_{phase}_{args.engine}_{mobile}.png'))
                    print('PASS WEB QUEST:', row, flush=True)
                assert not errors, errors
                context.close()
        name = ('quest_spawn_web_before.json' if args.before_fix else
                'quest_spawn_web_b14.json' if args.b14_only else 'quest_spawn_web.json')
        if args.engine != 'chromium':
            name = name.replace('.json', '_'+args.engine+'.json')
        (ROOT/'verification'/name).write_text(json.dumps(reports, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
