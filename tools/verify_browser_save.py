"""Real Pyxel/Pyodide + localStorage in Chromium, desktop and touch emulation.

Optional test dependency: pip install playwright (not needed to play the game).
Use --channel msedge for an installed Microsoft Edge, or install Chromium via
python -m playwright install chromium. Isolated profiles never use user saves.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import sys

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel', default=None)
    parser.add_argument('--playwright-path', type=Path)
    args = parser.parse_args()
    if args.playwright_path:
        sys.path.insert(0, str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright

    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'dist')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:%s/' % server.server_port
    reports = {}
    try:
        with tempfile.TemporaryDirectory(prefix='seekers_browser_', ignore_cleanup_errors=True) as profiles, sync_playwright() as playwright:
            for mobile in (False, True):
                name = 'mobile_emulation' if mobile else 'desktop'
                print('START:', name, flush=True)
                settings = dict(headless=True, channel=args.channel, ignore_https_errors=True,
                                args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    settings.update(playwright.devices['Pixel 7'])
                    settings.pop('default_browser_type', None)
                else:
                    settings.update(viewport=dict(width=960, height=850))
                profile = Path(profiles) / name
                context = playwright.chromium.launch_persistent_context(str(profile), **settings)
                page_errors, messages = [], []

                def boot(page):
                    page.on('pageerror', lambda error: page_errors.append(str(error)))
                    page.on('console', lambda message: messages.append(message.text) if message.type == 'error' else None)
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
any(isinstance(obj, DungeonApp) for obj in gc.get_objects())
`); } catch (_) { return false; }
                    }''', timeout=120000)
                    game.evaluate('''() => window.pyxelContext.pyodide.runPython(`
import gc, json
from rpg.save import make_save_data, BROWSER_SAVE_KEY
test_app = next(obj for obj in gc.get_objects() if isinstance(obj, DungeonApp))
`)''')
                    return game

                page = context.pages[0]
                game = boot(page)
                cdp = context.new_cdp_session(page)

                def py(code):
                    return game.evaluate('(code) => window.pyxelContext.pyodide.runPython(code)', code)

                def state():
                    return py('test_app.state')

                def wait_opening(target):
                    game.wait_for_function('''(target) => window.pyxelContext.pyodide.runPython(
                        "test_app.state == " + JSON.stringify(target) + " and not test_app.opening_input_blocked"
                    )''', arg=target)

                def snapshot():
                    return json.loads(py('json.dumps(make_save_data(test_app), ensure_ascii=False)'))

                key = py('BROWSER_SAVE_KEY')

                def raw():
                    return game.evaluate('(key) => localStorage.getItem(key)', key)

                def press(button):
                    if mobile:
                        rect = game.locator('[data-gb="' + button + '"]').bounding_box()
                        assert rect, button
                        point = dict(x=rect['x'] + rect['width'] / 2, y=rect['y'] + rect['height'] / 2)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[point]))
                        page.wait_for_timeout(100)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                    else:
                        code = dict(a='z', b='x', down='ArrowDown', up='ArrowUp', right='ArrowRight', left='ArrowLeft')[button]
                        page.keyboard.down(code)
                        page.wait_for_timeout(100)
                        page.keyboard.up(code)
                    page.wait_for_timeout(120)

                def continue_game():
                    assert state() == 'title'
                    if py('test_app.title_cursor') == 0:
                        press('down')
                    press('a')

                def save():
                    assert state() == 'camp', state()
                    press('a'); press('down'); press('down'); press('a')
                    assert state() == 'save_confirm', state()
                    press('a')
                    assert state() == 'save_result', state()

                assert py('type(test_app.save_manager.backend).__name__') == 'BrowserSaveBackend'
                assert py('__import__("sys").platform') == 'emscripten'
                continue_game()
                assert state() == 'title_no_save' and 'ありません' in py('test_app.title_save_message')
                press('b'); press('up'); press('a')
                wait_opening('intro')
                for _ in range(py('len(test_app.intro_pages)')):
                    press('a')
                wait_opening('hub_intro')
                press('a')
                assert state() == 'camp' and snapshot()['banked_trz'] == 3, state()
                # Prepared persistent data; no source data or balance changes.
                py('''
s, d, e = test_app.session, test_app.dungeon, test_app.exploration
s.treasure.banked, s.total_battles = 17, 128
s.inventory.counts.update({'POTION': 2, 'PHOENIX ASH': 7, 'REMEDY': 9})
s.discovered_skills.update(('fire', 'return'))
s.mastered_skills.add('fire')
s.party[0].learn(s.skills['fire']); s.party[0].learn(s.skills['return'])
s.party[0].skill_uses.update(punch=17, fire=2, **{'return': 2})
for actor in s.party:
    actor.max_hp = actor.hp = 500
    actor.strength, actor.agility, actor.intellect = 70, 55, 70
s.party[0].history.append('日本語の成長記録：探索を続けよう')
d.defeated_bosses.update((4, 9, 14))
d.finale.guardians_defeated = True
d.finale.claim_amrita()
e.accept(2, quest_type='investigate')
e.active['flavor_id'] = 'investigate_l2_01'
e.active['progress'] = 1
e.active['investigated_points'] = [e.active['points'][0]]
e.quest_clear_counts.update(explore=5, investigate=3, hunt=2)
e.completed_quest_ids = ['explore_l1_01', 'investigate_l2_02', 'hunt_l1_01']
''')
                expected = snapshot()
                flavor = py('json.dumps(test_app.exploration.quest_flavor(), ensure_ascii=False)')
                save()
                assert py('test_app.save_message') == 'セーブしました。'
                assert json.loads(raw()) == expected and '日本語' in raw()
                assert py('not __import__("pathlib").Path("save/save.json").exists()')
                screen_dir = ROOT / 'verification/screenshots'
                screen_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screen_dir / ('browser_save_' + name + '.png')))
                print('PASS: SAVE actual localStorage', name, flush=True)

                page.reload(wait_until='domcontentloaded')
                game = boot(page)
                continue_game()
                assert state() == 'camp' and snapshot() == expected
                assert py('json.dumps(test_app.exploration.quest_flavor(), ensure_ascii=False)') == flavor
                assert not py('test_app.camp_offer_pending')
                assert py('test_app.final_checkpoint is None')
                page.wait_for_timeout(100)
                print('PASS: Reload -> CONTINUE full SaveData', name, flush=True)
                # Three real model battles, bounded resolution, then new quest
                # progress/TRZ. Only fixture stats make these battles brief.
                py('''
for _ in range(3):
    battle = test_app.session.next_battle()
    for turn in range(80):
        if battle.outcome: break
        battle.begin_round(battle.auto_actions())
        while battle.queue: battle.step()
    assert battle.outcome == 'VICTORY'
    test_app.session.settle()
    for index in list(test_app.session.pending_replacements):
        test_app.session.resolve_replacement(index)
test_app.enter_camp()
test_app.session.treasure.banked += 5
test_app.exploration.active['progress'] = 2
test_app.exploration.active['investigated_points'] = test_app.exploration.active['points'][:2]
''')
                expected = snapshot()
                assert expected['banked_trz'] == 22 and expected['total_battles'] == 131
                save()
                valid_raw = raw()
                page.close()
                page = context.new_page()
                cdp = context.new_cdp_session(page)
                game = boot(page)
                continue_game()
                assert state() == 'camp' and snapshot() == expected
                # Reentry keeps the existing Amrita confirmation semantics.
                py("test_app.enter_dungeon(); test_app.handle_event('base', '')")
                assert state() == 'return_result'
                press('a')
                assert state() == 'amrita_offer'
                press('down'); press('a')
                assert state() == 'camp'

                # Audio failure cannot block either storage operation.
                py('''
import pyxel
def test_audio_failure(*args, **kwargs): raise RuntimeError('audio suspended')
pyxel.play = pyxel.playm = test_audio_failure
''')
                save()
                assert py('test_app.save_message') == 'セーブしました。'
                press('b')
                # Fail writes/reads, including the localStorage property getter.
                game.evaluate('''() => {
                    window.testOriginalSet = Storage.prototype.setItem;
                    Storage.prototype.setItem = function() { throw new DOMException('test', 'QuotaExceededError'); };
                }''')
                py("test_app.state = 'camp'; test_app.camp_cursor = 0")
                save()
                assert 'できません' in py('test_app.save_message') and raw() == valid_raw
                game.evaluate('() => { Storage.prototype.setItem = window.testOriginalSet; }')
                press('b')
                before = snapshot()
                game.evaluate('''() => {
                    window.testStorageDescriptor = Object.getOwnPropertyDescriptor(window, 'localStorage');
                    Object.defineProperty(window, 'localStorage', { configurable: true, get() {
                        throw new DOMException('test', 'SecurityError');
                    }});
                }''')
                py('test_app.continue_game()')
                assert state() == 'title_no_save' and snapshot() == before
                game.evaluate('() => Object.defineProperty(window, "localStorage", window.testStorageDescriptor)')
                press('b')

                for invalid in ('{broken', '{"save_version":999}', '{"save_version":1}', '{"save_version":true}'):
                    game.evaluate('([key, value]) => localStorage.setItem(key, value)', [key, invalid])
                    continue_game()
                    assert state() == 'title_no_save' and snapshot() == before and raw() == invalid, state()
                    assert '読み込めません' in py('test_app.title_save_message')
                    press('b')
                game.evaluate('(key) => localStorage.removeItem(key)', key)
                continue_game()
                assert state() == 'title_no_save' and 'ありません' in py('test_app.title_save_message')
                press('b')
                game.evaluate('([key, value]) => localStorage.setItem(key, value)', [key, valid_raw])
                continue_game()
                assert state() == 'camp' and snapshot() == expected

                # Normal SAVE must not overwrite checkpoint semantics.
                py('''
test_app.start_final_story()
test_app.begin_final_battle()
test_checkpoint_hp = [c.hp for c in test_app.session.party]
test_checkpoint_uses = [dict(c.skill_uses) for c in test_app.session.party]
test_checkpoint_items = dict(test_app.session.inventory.counts)
for c in test_app.session.party: c.hp = 0
test_app.session.inventory.counts['POTION'] = 0
test_app.battle.outcome = 'DEFEAT'
test_app.session.settle()
test_app.state = 'result'
test_app.finish_results()
''')
                assert state() == 'final_retry'
                page.wait_for_timeout(150)
                press('a')
                assert py('[c.hp for c in test_app.session.party] == test_checkpoint_hp')
                assert py('[dict(c.skill_uses) for c in test_app.session.party] == test_checkpoint_uses')
                assert py('test_app.session.inventory.counts == test_checkpoint_items')
                assert py('test_app.dungeon.finale.has_amrita and test_app.battle.elysion_barrier_active')
                assert raw() == valid_raw
                # NEW GAME must preserve the old slot until explicit SAVE.
                py("test_app.state = 'title'; test_app.title_cursor = 0; test_app.opening_input_blocked = False")
                press('a')
                assert raw() == valid_raw
                wait_opening('intro')
                for _ in range(py('len(test_app.intro_pages)')): press('a')
                wait_opening('hub_intro')
                press('a'); save()
                assert json.loads(raw())['banked_trz'] == 3 and json.loads(raw())['total_battles'] == 0
                assert raw() != valid_raw
                # Verify persistence across browser-process restart, same profile.
                context.close()
                context = playwright.chromium.launch_persistent_context(str(profile), **settings)
                page = context.pages[0]
                game = boot(page)
                cdp = context.new_cdp_session(page)
                continue_game()
                assert state() == 'camp' and snapshot()['banked_trz'] == 3
                assert not page_errors, page_errors
                reports[name] = dict(actual_pyxel_pyodide=True, actual_local_storage=True,
                    new_game_save=True, reload_continue=True, full_save_data_equal=True,
                    japanese_roundtrip=True, resave_after_three_battles=True, tab_close_reopen=True,
                    browser_process_restart=True, no_initial_trz_added=True,
                    amrita_offer_deferred_until_reentry=True, checkpoint_retry=True,
                    missing_save=True, invalid_save_untouched=True, quota_failure=True,
                    security_read_failure=True, silent_save_load=True,
                    new_game_preserves_slot_until_explicit_save=True, backend_selected_emscripten=True,
                    physical_smartphone=False, touch_emulation=mobile, page_errors=page_errors,
                    browser_version=cdp.send('Browser.getVersion')['product'])
                context.close()
                print('PASS:', name, flush=True)
        (ROOT / 'verification/browser_save.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
