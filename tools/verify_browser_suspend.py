"""Real Web reload, single-use IndexedDB, failures and keyboard/touch UX.

Uses temporary profiles and synthetic party data; never accesses player saves.
"""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_browser_save import QuietHandler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playwright-path',type=Path,required=True)
    parser.add_argument('--disable-audio',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/'
    results=[]
    shots=ROOT/'verification/screenshots'; shots.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='ux-suspend-',ignore_cleanup_errors=True) as td, sync_playwright() as pw:
            for mobile in (False,True):
                mode='touch_emulation' if mobile else 'desktop'
                print('START:',mode,'audio disabled:',args.disable_audio,flush=True)
                settings=dict(channel='msedge',headless=True,ignore_https_errors=True,
                    args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    settings.update(pw.devices['Pixel 7']); settings.pop('default_browser_type',None)
                context=pw.chromium.launch_persistent_context(str(Path(td)/mode),**settings)
                context.add_init_script('''(() => {
                    window.uxAudioContexts=[];
                    const Native=window.AudioContext;
                    if(Native) window.AudioContext=new Proxy(Native,{construct(t,a,n){
                        const ctx=Reflect.construct(t,a,n); window.uxAudioContexts.push(ctx); return ctx;
                    }});
                })();''')
                page=context.pages[0]; errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                game=None

                def py(source):
                    return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)',source)

                def check(expression):
                    game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)',arg=expression,timeout=20000)

                def boot():
                    nonlocal game
                    page.locator('#play').click()
                    frame=page.frame_locator('#game')
                    frame.locator('#pyxel-prompt').wait_for(timeout=120000)
                    frame.locator('#canvas').click()
                    game=page.frames[-1]
                    game.wait_for_function('''() => {try {return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`);} catch(_){return false;}}''',timeout=120000)
                    py('''
import json
from rpg.suspend import make_suspend_data
from rpg.save import BROWSER_SAVE_KEY
from rpg.quests import spawn_candidates
from rpg.tiles import TILE_CHEST, TILE_RARE_CHEST, TILE_HEAL_POINT
_ux_app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
''')
                    check('_ux_app.state == "title" and _ux_app.suspend_job is None')
                    if args.disable_audio:
                        states=game.evaluate('''async () => {
                            await Promise.all(window.uxAudioContexts.map(async c=>{
                                await c.suspend(); c.resume=()=>Promise.reject(new Error('UX audio unavailable'));
                            }));
                            document.dispatchEvent(new Event('visibilitychange'));
                            for(const e of ['blur','focus','pageshow']) window.dispatchEvent(new Event(e));
                            return window.uxAudioContexts.map(c=>c.state);
                        }''')
                        assert states and all(s=='suspended' for s in states)

                cdp=context.new_cdp_session(page) if mobile else None
                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box=game.locator(f'[data-gb="{button}"]').bounding_box(); assert box,button
                        p=dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[p]))
                        page.wait_for_timeout(100)
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key=dict(a='z',b='x',up='ArrowUp',down='ArrowDown')[button]
                        page.keyboard.down(key); page.wait_for_timeout(100); page.keyboard.up(key)
                    page.wait_for_timeout(180)

                def io(operation,payload=''):
                    game.evaluate('([op,p])=>{window.uxJob=window.sparkSuspendStore.start(op,p);}',[operation,payload])
                    game.wait_for_function('window.uxJob.done',timeout=15000)
                    return game.evaluate('({result:window.uxJob.result,error:window.uxJob.error})')

                def normal_raw():
                    return game.evaluate('(k)=>localStorage.getItem(k)',py('BROWSER_SAVE_KEY'))

                def choose_suspend():
                    press('b'); check('_ux_app.state == "menu"')
                    for _ in range(5): press('down')
                    press('a'); check('_ux_app.state == "suspend_confirm"')

                def resume_attempt():
                    py("_ux_app.state='title'; _ux_app.opening_input_blocked=False; _ux_app.refresh_suspend()")
                    check('_ux_app.suspend_available and _ux_app.suspend_job is None')
                    py('_ux_app.title_cursor=2')
                    press('a')

                page.goto(url,wait_until='domcontentloaded'); boot()
                assert py('len(_ux_app.title_options())')==2
                assert not io('exists')['result']
                press('a'); check('_ux_app.state == "intro" and not _ux_app.opening_input_blocked')
                for _ in range(py('len(_ux_app.intro_pages)')): press('a')
                check('_ux_app.state == "hub_intro" and not _ux_app.opening_input_blocked')
                press('a'); check('_ux_app.state == "camp" and not _ux_app.opening_input_blocked')
                # Create a normal save via the unchanged GUILD UI.
                press('a'); press('down'); press('down'); press('a')
                check('_ux_app.state == "save_confirm"'); press('a')
                check('_ux_app.state == "save_result"')
                normal=normal_raw(); assert json.loads(normal)['save_version']==1
                press('b'); press('b'); check('_ux_app.state == "camp"')
                py('''
_ux_app.enter_dungeon()
s,d,e=_ux_app.session,_ux_app.dungeon,_ux_app.exploration
d.defeated_bosses.update((4,9)); d.debug_floor(6); d.steps=29; d.grace=2
s.treasure.banked=17; s.treasure.unbanked=13
s.inventory.counts.update({'POTION':7,'PHOENIX ASH':2,'REMEDY':1})
c=s.party[0]
for sid in ('fire','ice'):
    c.learn(s.skills[sid]); s.discovered_skills.add(sid)
c.hp=17; c.statuses={'poison':3}; c.skill_uses['fire']=2; c.cooldowns['fire']=2
c.remember_skill('fire'); s.party[1].hp=0
e.accept(2,quest_type='investigate')
q=e.active; q['target_floor']=7
q['points']=[list(p) for p in spawn_candidates(d,6)[-3:]][::-1]
q['investigated_points']=[q['points'][1]]; q['progress']=1
for floor in range(15):
    points=d.positions(floor,TILE_HEAL_POINT)
    if points: e.springs.add((floor,*points[0]))
chests=d.positions(6,TILE_CHEST)+d.positions(6,TILE_RARE_CHEST)
if chests:
    point=(6,*chests[0]); d.opened.add(point); d.chest_loot[point]={'kind':'TREASURE','amount':2}
_ux_app.player_facing='left'; _ux_app.state='explore'; _ux_app.opening_input_blocked=False
''')
                expected=json.loads(py('json.dumps(make_suspend_data(_ux_app))'))
                game.evaluate('''() => {
                    document.dispatchEvent(new Event('visibilitychange'));
                    window.dispatchEvent(new Event('pagehide')); window.dispatchEvent(new Event('pageshow'));
                }''')
                assert not io('exists')['result']  # No automatic/lifecycle save.
                choose_suspend(); press('b'); check('_ux_app.state == "menu"')
                press('a'); check('_ux_app.state == "suspend_confirm"')
                suffix='unavailable' if args.disable_audio else 'running'
                page.screenshot(path=str(shots/f'ux01_{mode}_{suffix}_confirm.png'))
                press('up'); press('a'); check('_ux_app.state == "title" and _ux_app.suspend_available')
                raw=io('read')['result']; assert json.loads(raw)['suspend_version']==1
                assert normal_raw()==normal
                # Reload destroys the entire Python game, then restore from IDB.
                page.reload(wait_until='domcontentloaded'); boot()
                check('_ux_app.suspend_available')
                assert py('len(_ux_app.title_options())')==3
                page.screenshot(path=str(shots/f'ux01_{mode}_{suffix}_title.png'))
                press('down'); press('down'); press('a')
                check('_ux_app.state == "explore" and not _ux_app.opening_input_blocked')
                actual=json.loads(py('json.dumps(make_suspend_data(_ux_app))'))
                assert actual==expected
                assert not io('exists')['result'] and normal_raw()==normal
                assert py('_ux_app.audio.current_bgm')=='bgm_area2'
                page.screenshot(path=str(shots/f'ux01_{mode}_{suffix}_resumed.png'))
                press('b'); check('_ux_app.state == "menu"'); press('b')
                py('_ux_app.begin_encounter()')
                check('_ux_app.state == "command" and not _ux_app.battle_input_blocked')
                press('a'); check('_ux_app.state == "skill" and _ux_app.skill_cursor == 1')
                press('down'); press('b'); check('_ux_app.state == "command"')
                press('a'); check('_ux_app.skill_cursor == 1')
                assert py('_ux_app.actor.last_skill_id')=='fire'
                # Two transactions for the same ticket must yield one winner.
                assert not io('write',raw)['error']
                other=context.new_page()
                other.goto(url,wait_until='domcontentloaded')
                other.add_script_tag(content=(ROOT/'tools/web_suspend_store.js').read_text(encoding='utf8'))
                start_at=page.evaluate('Date.now()+400')
                for target in (game,other):
                    target.evaluate('''({raw,when})=>{
                        window.uxClaim={done:false};
                        setTimeout(()=>{window.uxClaim=window.sparkSuspendStore.start('consume',raw);},
                                   Math.max(0,when-Date.now()));
                    }''',dict(raw=raw,when=start_at))
                claims=[]
                for target in (game,other):
                    target.wait_for_function('window.uxClaim.done',timeout=15000)
                    claims.append(target.evaluate('({result:window.uxClaim.result,error:window.uxClaim.error})'))
                other.close(); page.bring_to_front()
                assert sum(not j['error'] for j in claims)==1,claims
                assert not io('exists')['result']
                # Real IndexedDB abort: a failed delete retains the entire row.
                assert not io('write',raw)['error']
                game.evaluate('''() => {
                    window.uxDelete=IDBObjectStore.prototype.delete;
                    IDBObjectStore.prototype.delete=function(){throw new Error('simulated delete failure');};
                }''')
                resume_attempt(); check('_ux_app.state == "title_no_save"')
                game.evaluate('() => { IDBObjectStore.prototype.delete=window.uxDelete; }')
                assert io('read')['result']==raw
                assert not io('consume',raw)['error']
                # Malformed content is retained; the live party isn't replaced.
                malformed='{"suspend_version":999}'
                assert not io('write',malformed)['error']
                party_id=py('id(_ux_app.session.party)')
                resume_attempt(); check('_ux_app.state == "title_no_save"')
                assert py('id(_ux_app.session.party)')==party_id
                assert io('read')['result']==malformed
                assert not io('consume',malformed)['error']
                # Real storage write failure; keep exploring instead of quitting.
                py('''
_ux_app.start_new_game(); _ux_app.enter_camp(); _ux_app.enter_dungeon()
_ux_app.opening_input_blocked=False
''')
                game.evaluate('''() => {
                    window.uxPut=IDBObjectStore.prototype.put;
                    IDBObjectStore.prototype.put=function(){throw new Error('simulated quota failure');};
                }''')
                choose_suspend(); press('up'); press('a')
                check('_ux_app.state == "suspend_confirm" and bool(_ux_app.suspend_error) and not _ux_app.opening_input_blocked')
                game.evaluate('() => { IDBObjectStore.prototype.put=window.uxPut; }')
                assert not io('exists')['result'] and normal_raw()==normal
                press('b'); check('_ux_app.state == "menu"')
                assert not errors,errors
                results.append(dict(mode=mode,engine='Edge Chromium',audio_unavailable=args.disable_audio,
                    manual_save_only=True,normal_save_unchanged=True,reload_exact_state=True,
                    banked_trz=actual['game']['banked_trz'],unbanked_trz=actual['session']['unbanked_trz'],
                    resumed_floor=actual['dungeon']['floor']+1,poison=actual['party_runtime'][0]['statuses'],
                    single_use=True,concurrent_consumers_one_winner=True,corruption_preserved=True,
                    delete_abort_preserved=True,write_failure_stays_in_game=True,
                    skill_cursor_cancel_safe=True,real_A_B_DPAD=mobile,real_Z_X=not mobile,page_errors=errors))
                print('PASS:',mode,'reload, atomic consume, failed delete/write, cursor, normal SAVE preserved',flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results,physical_ios_tested=False,
            physical_gkd_tested=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:
        server.shutdown()


if __name__=='__main__': main()
