"""Real Pyodide enemy actions in isolated desktop/touch browser profiles.

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
    args = parser.parse_args()
    if args.playwright_path:
        sys.path.insert(0, str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix='enemy-actions-web-', ignore_cleanup_errors=True) as td, sync_playwright() as pw:
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
                states = game.evaluate('''async () => {
                    await Promise.all(window.enemyTestContexts.map(async ctx => {
                        await ctx.suspend();
                        ctx.resume = () => Promise.reject(new Error('enemy-test audio unavailable'));
                    }));
                    return window.enemyTestContexts.map(ctx => ctx.state);
                }''')
                assert states and all(state == 'suspended' for state in states), states
                game.evaluate('''() => {
                    document.dispatchEvent(new Event('visibilitychange'));
                    window.dispatchEvent(new Event('blur'));
                    window.dispatchEvent(new Event('focus'));
                    window.dispatchEvent(new Event('pageshow'));
                }''')
                raw = game.evaluate('''() => window.pyxelContext.pyodide.runPython(`
import json, pyxel
from collections import deque
from unittest.mock import patch
from rpg.models import Enemy
from rpg.save import make_save_data
app = next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
app.start_new_game()
app.enter_camp()
app.opening_input_blocked = False
app.begin_encounter()
b = app.battle
row = next(r for r in app.session.enemy_data if r['id']=='berserker')
b.enemies = [Enemy.from_definition(row, max_hp=10000, strength=50, intellect=40)]
results = []
with patch.object(pyxel,'btnp',return_value=False), patch.object(pyxel,'btn',return_value=False), \\
     patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \\
     patch.object(pyxel,'playm',side_effect=RuntimeError('suspended')), \\
     patch.object(pyxel,'play_pos',side_effect=RuntimeError('interrupted')):
    for fast in (False,True):
        app.confirm=lambda: fast
        app.confirm_held=lambda: fast
        app.cancel=lambda: fast
        app.direction=lambda horizontal=False: int(fast)
        for ident in b.enemy_actions:
            for c in b.party:
                c.hp=c.max_hp=500; c.effects.clear(); c.guarding=False
            b.party[3].hp=0
            enemy=b.enemies[0]
            enemy.hp=enemy.max_hp; enemy.effects.clear(); enemy.guarding=False
            enemy.actions=[dict(id=ident,weight=100)]
            b.queue=deque([('enemy',0)]); b.outcome=None
            app.state='resolve'; app.delay=0; app.pending.clear()
            app.battle_visual().reset()
            phases=set(); visual_ticks=0; recoils=[]; offsets=[]
            for tick in range(500):
                app.update(); app.draw()
                v=app.battle_visual()
                if v.phase:
                    phases.add(v.phase); visual_ticks+=1
                    offsets.append(v.enemy_offset(0))
                    if any(v.actor_offset(i)==4 for i in range(4)): recoils.append(tick)
                if not b.queue and not app.pending and not v.active: break
            else: raise AssertionError(('action stalled',ident,app.state))
            assert b.party[3].hp==0
            if ident=='double_attack': assert len(recoils)==2 and recoils[1]-recoils[0]==8, (ident,fast,recoils)
            if ident=='heavy_attack': assert max(offsets)==9 and visual_ticks==9, (ident,fast,offsets,visual_ticks)
            if ident in ('magic','area_magic'): assert not any(offsets) and 'enemy_effect' in phases
            results.append(dict(action=ident,fast=fast,ticks=tick,visual_ticks=visual_ticks,
                phases=sorted(phases),recoil_ticks=recoils,hp=[c.hp for c in b.party]))
    # Real action damage drives KO and the existing RESULT -> exploration flow.
    app.session.settings['spark_chance']=0
    for c in b.party: c.hp=1
    enemy.actions=[dict(id='area_attack',weight=1)]
    b.queue=deque([('enemy',0)]); b.outcome=None
    app.state='resolve'; app.pending.clear(); app.delay=0; app.battle_visual().reset()
    for tick in range(500):
        app.update(); app.draw()
        if app.state=='result': break
    assert b.outcome=='DEFEAT' and app.state=='result'
    app.finish_results()
    assert app.state=='camp'
    data=make_save_data(app)
    assert data['save_version']==1 and 'enemy_actions' not in data
json.dumps(dict(actions=results,silent_defeat_return=True,save_version=data['save_version']))
`)''')
                data = json.loads(raw)
                assert len(data['actions']) == 22
                assert not errors, errors
                results.append(dict(mode=mode, engine='Edge Chromium', audio_states=states,
                                    errors=errors, **data))
                context.close()
        report = dict(cases=results, physical_ios_tested=False, physical_screen_lock_tested=False)
        (ROOT/'verification/enemy_actions_browser.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('PASS: all 11 enemy actions, normal/fast input, desktop/touch Pyodide with suspended/unavailable audio', flush=True)
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
