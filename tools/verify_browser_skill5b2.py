"""5B-2 final Web payload: real keyboard/touch cure reservation and field hints."""
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
        with tempfile.TemporaryDirectory(prefix='skill5b2-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
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
from dataclasses import replace
from rpg.models import Enemy
import rpg.app as ui
import rpg.dungeon_app as dui
from rpg.text import text_width
balance_rows={}
balance_original_text=ui.text
def capture(x,y,value,*args,**kwargs):
    balance_rows[y]=str(value)
    return balance_original_text(x,y,value,*args,**kwargs)
ui.text=dui.text=capture

def fixture(sid,gained=False,field=False):
    s=a.session
    s.battle=None; s.settled=True; s.mastered_skills.clear(); s.pending_relearn=None
    for i,c in enumerate(s.party):
        for old in list(c.skills): c.forget(old)
        c.pending_skill=None
        c.reset_battle_state()
        c.hp=500 if not i else 0
        c.max_hp=1000; c.agility=20; c.intellect=c.strength=20
    c=s.party[0]
    c.learn(s.skills[sid]); c.learn(s.skills['punch'])
    s.discovered_skills.update(c.skills)
    a.overlay=None; a.notice_timer=0
    if field:
        a.state,a.overlay='explore','info'
        a.info_tab=1; a.info_character=0; a.scroll=0
    else:
        a.begin_encounter()
        e=Enemy('PROBE',5000,1,200 if gained else 1,1,(0,0))
        if gained: e.actions=[dict(id='poison_bite',weight=1)]
        a.battle.enemies=[e]
        a.battle.enemy_actions=dict(a.battle.enemy_actions)
        a.battle.enemy_actions['poison_bite']=replace(a.battle.enemy_actions['poison_bite'],status_chance=100)
        a.battle_presentation=None
        a.begin_input()
    a.opening_input_blocked=a.battle_input_blocked=False
    balance_rows.clear()
''')
                cases=[]
                for sid in ('cure','purify_wind'):
                    for gained in (False,True):
                        py(f'fixture({sid!r},{gained!r})')
                        press('a'); check('a.state == "skill"')
                        if sid=='purify_wind':
                            check("balance_rows.get(92)=='治療対象なし / 予約可'")
                            page.screenshot(path=str(shots/f'skill5b2_{mode}_{suffix}_group.png'))
                        press('a')
                        if sid=='cure':
                            check('a.state == "target"')
                            check("balance_rows.get(100)=='治療対象なし / 予約可'")
                            page.screenshot(path=str(shots/f'skill5b2_{mode}_{suffix}_target.png'))
                            press('a')
                        check('a.state == "command" and a.battle.round == 1')
                        assert py(f'a.session.party[0].skill_uses[{sid!r}] == a.session.skills[{sid!r}].max_uses - {int(gained)}')
                        assert py("not a.session.party[0].statuses")
                        cases.append(dict(skill=sid,gained_after_reservation=gained,uses_spent=int(gained)))
                    py(f'fixture({sid!r},field=True)')
                    if sid=='purify_wind': check("balance_rows.get(92)=='治療対象なし'")
                    press('a')
                    if sid=='cure':
                        check('a.state == "field_heal"')
                        check("balance_rows.get(99)=='治療対象なし / 消費なし'")
                        page.screenshot(path=str(shots/f'skill5b2_{mode}_{suffix}_field.png'))
                        press('a')
                    check("a.notice == '治療対象なし'")
                    assert py(f'a.session.party[0].skill_uses[{sid!r}] == a.session.skills[{sid!r}].max_uses')
                    # Actual field cure following no-op, using the same control flow.
                    py("a.session.party[0].statuses={'poison':3}; a.notice_timer=0")
                    press('a')
                    check('not a.session.party[0].statuses')
                    assert py(f'a.session.party[0].skill_uses[{sid!r}] == a.session.skills[{sid!r}].max_uses-1')
                    cases.append(dict(skill=sid,field_noop_and_treatment=True))
                for sid in ('power_up','focus','sanctuary'):
                    py(f'fixture({sid!r})')
                    press('a'); check('a.state == "skill"')
                    expected=4 if sid!='sanctuary' else 3
                    check(f"'{expected}ターン' in balance_rows.get(84,'') and '{expected}ターン' in balance_rows.get(100,'')")
                    assert py('text_width(balance_rows[100]) <= 148')
                    page.screenshot(path=str(shots/f'skill5b2_{mode}_{suffix}_{sid}.png'))
                assert not errors,errors
                results.append(dict(mode=mode,audio_unavailable=args.disable_audio,cases=cases,page_errors=errors,
                                    support_descriptions_fit=True,healthy_targets_selectable=True))
                print('PASS:',mode,suffix,'queued cures, field cures, three support descriptions',flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results,physical_ios_tested=False,
            physical_gkd_tested=False,battle_fixtures_seeded=True),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:
        server.shutdown()

if __name__=='__main__': main()
