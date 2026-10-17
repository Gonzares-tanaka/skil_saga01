"""Actual Pyodide battle, desktop keys/touch emulation, silent audio and reload.

This is not a physical iOS Safari or screen-lock test. Test profiles are isolated.
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
sys.path.insert(0,str(ROOT/'tools'))
from verify_browser_save import QuietHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playwright-path',type=Path)
    args = parser.parse_args()
    if args.playwright_path:
        sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    reports = []
    try:
        with tempfile.TemporaryDirectory(prefix='battle-web-',ignore_cleanup_errors=True) as td, sync_playwright() as pw:
            for mobile in (False,True):
                options = dict(channel='msedge',headless=True,ignore_https_errors=True,
                               args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    options.update(pw.devices['Pixel 7'])
                    options.pop('default_browser_type',None)
                context = pw.chromium.launch_persistent_context(str(Path(td)/str(mobile)),**options)
                context.add_init_script('''(() => {
                    window.presentationTestContexts = [];
                    const Native = window.AudioContext;
                    if (Native) window.AudioContext = new Proxy(Native, {
                        construct(target,args,newTarget) {
                            const ctx = Reflect.construct(target,args,newTarget);
                            window.presentationTestContexts.push(ctx);
                            return ctx;
                        }
                    });
                })();''')
                page = context.pages[0]
                errors = []
                page.on('pageerror',lambda e: errors.append(str(e)))
                cdp = context.new_cdp_session(page)
                def boot():
                    page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded')
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
                    }''',timeout=120000)
                    game.evaluate('''() => window.pyxelContext.pyodide.runPython(`
test_app = next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
import pyxel,json
from unittest.mock import patch
from rpg.save import make_save_data
`)''')
                    return game
                game = boot()
                def py(code):
                    return game.evaluate('(code)=>window.pyxelContext.pyodide.runPython(code)',code)
                def button(name,hold=100):
                    if mobile:
                        box = game.locator(f'[data-gb="{name}"]').bounding_box()
                        assert box
                        point = dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[point]))
                        page.wait_for_timeout(hold)
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key = dict(a='z',b='x',down='ArrowDown',up='ArrowUp')[name]
                        page.keyboard.down(key)
                        page.wait_for_timeout(hold)
                        page.keyboard.up(key)
                    page.wait_for_timeout(150)
                print('START REAL BROWSER:', 'touch emulation' if mobile else 'desktop',flush=True)
                py('''
test_app.start_new_game()
test_app.enter_camp()
test_app.opening_input_blocked = False
test_app.session.settings['spark_chance'] = 0
test_app.begin_encounter()
b = test_app.battle
for c in b.party:
    c.agility = 100
b.enemies = b.enemies[:1]
b.enemies[0].hp = 1
test_app.begin_input()
test_app.actor.learn(test_app.session.skills['fire'])
test_app.session.discovered_skills.add('fire')
test_app.selected_skill = test_app.session.skills['fire']
test_app.state = 'target'
test_app.target_cursor = 0
browser_phases = set()
v = test_app.battle_visual()
normal_enter = v.enter
def observe_enter(phase):
    browser_phases.add(phase)
    normal_enter(phase)
v.enter = observe_enter
def unavailable(*args,**kwargs):
    raise RuntimeError('intentional suspended/interrupted audio test')
pyxel.play = pyxel.playm = pyxel.play_pos = pyxel.stop = unavailable
''')
                suspended = game.evaluate('''async () => {
                    const ctx = window.presentationTestContexts.find(c => c.state === 'running');
                    if (!ctx) throw new Error('Runtime AudioContext not found');
                    await ctx.suspend();
                    ctx.resume = () => Promise.reject(new Error('intentional audio resume failure'));
                    return window.sparkAudioState();
                }''')
                assert suspended == 'suspended',suspended
                button('a')
                for _ in range(3):
                    py('test_app.cursor = 2')
                    button('a')
                # Visibility events and a real background tab during resolution.
                hidden = context.new_page()
                hidden.goto('about:blank')
                page.wait_for_timeout(400)
                hidden.close()
                page.bring_to_front()
                lifecycle = game.evaluate('''() => {
                    for (const e of ['blur','pagehide','pageshow','focus']) window.dispatchEvent(new Event(e));
                    document.dispatchEvent(new Event('visibilitychange'));
                    return window.sparkAudioState?.();
                }''')
                for _ in range(35):
                    if py('test_app.state') == 'result':
                        break
                    button('a',hold=250)
                assert py('test_app.state') == 'result'
                phases = json.loads(py('json.dumps(sorted(browser_phases))'))
                assert all(p in phases for p in ('actor_step','skill_effect','enemy_death','actor_return')),phases
                screenshot = ROOT/'verification/screenshots'/f'battle_web_{"touch" if mobile else "desktop"}.png'
                screenshot.parent.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(screenshot))
                for _ in range(30):
                    if py('test_app.state') == 'explore':
                        break
                    button('a',hold=150)
                assert py('test_app.state') == 'explore'
                # Actual damage/KO in the live Web runtime, with audio unavailable.
                py('''
from collections import deque
test_app.begin_encounter()
test_app.dungeon.floor = 1
with patch.object(test_app.dungeon.rng,'randint',return_value=4):
    test_app.battle.enemies = test_app.dungeon.make_enemies()
test_app.dungeon.floor = 0
assert len(test_app.battle.enemies) == 4
if 'fire' not in test_app.actor.skills:
    test_app.actor.learn(test_app.session.skills['fire'])
test_app.selected_skill = test_app.session.skills['fire']
test_app.state,test_app.target_cursor = 'target',3
from rpg.battle_presentation import ENEMY_GRID_POSITIONS
with patch.object(pyxel,'blt',wraps=pyxel.blt) as calls:
    test_app.draw()
for enemy,(x,y) in zip(test_app.battle.enemies,ENEMY_GRID_POSITIONS):
    assert (x,y,0,*enemy.sprite,16,16,0) in [c.args for c in calls.call_args_list]
''')
                grid_shot = ROOT/'verification/screenshots'/f'battle_grid_web_{"touch" if mobile else "desktop"}.png'
                page.screenshot(path=str(grid_shot))
                button('a')
                assert py('test_app.actions[-1].target') == 3
                py('''
test_app.state,test_app.delay = 'resolve',0
b = test_app.battle
b.party[0].hp = 1
b.queue = deque([('enemy',0)])
test_app.pending.clear()
with patch.object(b.rng,'choice',return_value=b.party[0]):
    test_app.apply_visual_action()
v = test_app.battle_visual()
assert b.party[0].hp == 0 and v.phase == 'party_hit'
assert [v.actor_offset(i) for i in range(4)] == [4,0,0,0]
with patch.object(pyxel,'blt',wraps=pyxel.blt) as calls:
    test_app.draw()
assert (102,13,0,*b.party[0].sprite,16,16,0) in [c.args for c in calls.call_args_list]
''')
                page.wait_for_timeout(180)
                py('''
assert not test_app.battle_visual().hit_targets
with patch.object(pyxel,'blt',wraps=pyxel.blt) as calls:
    test_app.draw()
assert (98,13,2,240,0,16,16,0) in [c.args for c in calls.call_args_list]
b.outcome = 'ESCAPE'
test_app.set_result_pages(test_app.session.settle())
test_app.finish_results()
b.party[0].hp = b.party[0].max_hp
''')
                # New RUN presentation: real A press, suspended audio, fixed wait.
                py('''
test_app.begin_encounter()
test_app.battle.run_override = True
test_app.cursor = 3
''')
                button('a')
                page.wait_for_timeout(650)
                assert py('test_app.state') == 'explore'
                assert py('test_app.battle.outcome') == 'ESCAPE'
                # Filled slots + real A confirmations must never return to growth.
                py('''
test_app.begin_encounter()
test_app.battle.outcome = 'VICTORY'
test_app.set_result_pages(test_app.session.settle())
c = test_app.session.party[0]
for sid in ('punch','quick_hit','spark','fire','ice','heal'):
    if len(c.skills) >= test_app.session.settings['skill_slots']:
        break
    if sid not in c.skills:
        c.learn(test_app.session.skills[sid])
        test_app.session.discovered_skills.add(sid)
c.pending_skill = 'meteor'
test_app.session.discovered_skills.add('meteor')
test_app.state = 'result'
test_app.result_page = 0
test_app.fanfare_started_at = None
''')
                for _ in range(20):
                    if py('test_app.state') == 'replace':
                        break
                    button('a')
                assert py('test_app.state') == 'replace'
                button('a'); button('a')
                assert py('test_app.state') == 'explore'
                assert py("'meteor' in test_app.session.party[0].skills")
                resume_failures = game.evaluate('()=>window.sparkAudioEvents.filter(e=>e.includes("resume-failed"))')
                assert resume_failures
                # Save via the existing GUILD A/B menu, then a fresh Pyodide CONTINUE.
                py('test_app.enter_camp(); test_app.opening_input_blocked=False')
                expected = json.loads(py('json.dumps(make_save_data(test_app))'))
                button('a'); button('down'); button('down'); button('a'); button('a')
                assert py('test_app.state') == 'save_result'
                assert py('test_app.save_message') == 'セーブしました。',py('test_app.save_message')
                assert json.loads(game.evaluate('()=>localStorage.getItem("skill_seekers_save_v1")')) == expected
                game = boot()
                button('down'); button('a')
                assert py('test_app.state') == 'camp'
                assert json.loads(py('json.dumps(make_save_data(test_app))')) == expected
                assert not errors,errors
                reports.append(dict(mode='touch emulation' if mobile else 'desktop',engine='Edge Chromium',
                                    phases=phases,silent_battle_result_return=True,visibility_events=True,
                                    audio_state=lifecycle,save_reload_continue=True,errors=errors,
                                    actual_audio_suspended=True,resume_failures=len(resume_failures),
                                    silent_run=True,replacement_no_growth_replay=True,
                                    silent_hit_ko=True,
                                    four_enemy_grid=True,fourth_target_selected=True,
                                    screenshot=str(screenshot.relative_to(ROOT))))
                context.close()
        result = dict(cases=reports,physical_ios_tested=False,physical_screen_lock_tested=False)
        (ROOT/'verification/battle_presentation_browser.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('PASS: real PC/touch Web runtime, silent animation/result, visibility and SAVE/CONTINUE',flush=True)
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
