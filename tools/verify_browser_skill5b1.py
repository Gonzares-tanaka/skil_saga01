"""5B-1 final Web payload: real keys/touches, previews, acquisition and attacks."""
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
        with tempfile.TemporaryDirectory(prefix='skill5b1-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
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
from rpg.models import Enemy
import rpg.app as ui
balance_rows={}
balance_original_text=ui.text

def balance_text(x,y,value,*args,**kwargs):
    balance_rows[y]=str(value)
    return balance_original_text(x,y,value,*args,**kwargs)
ui.text=balance_text

def balance_fixture(sid, mastered, training):
    s=a.session
    s.mastered_skills.clear()
    for actor in s.party:
        actor.pending_skill=None
        for old in list(actor.skills): actor.forget(old)
    c=s.party[0]
    c.strength,c.agility,c.intellect=53,20,40
    c.recover()
    for old in ('punch','fire','ice','quick_hit','spark','wild_edge'): c.learn(s.skills[old])
    s.discovered_skills.update(c.skills+[sid])
    s.mastered_skills.add('punch')
    if mastered: s.mastered_skills.add(sid)
    c.pending_skill=sid
    s.pending_relearn=(0,sid) if training else None
    s.treasure.banked=999
    s.settled=True
    a.state,a.overlay='replace',None
    a.replacement_cursor,a.replacement_confirm=0,False
    a.debug_return_state='camp'
    a.notice_timer=0
    balance_rows.clear()

def balance_battle(sid,mastered=False):
    s=a.session
    # Independent combat probes; do not start another live battle in the
    # preceding fixture. The real game correctly rejects that operation.
    s.battle=None
    s.settled=True
    s.mastered_skills.clear()
    s.pending_relearn=None
    for i,c in enumerate(s.party):
        c.pending_skill=None
        for old in list(c.skills): c.forget(old)
        c.hp=0 if i else 300
        c.max_hp=1000
        c.strength,c.agility,c.intellect=53,20,40
    c=s.party[0]
    if mastered: s.mastered_skills.add(sid)
    c.learn(s.skills[sid])
    if sid=='full_heal': c.learn(s.skills['punch'])
    s.discovered_skills.update(c.skills)
    a.begin_encounter()
    a.battle.enemies=[Enemy('PROBE',5000,1,1,1,(0,0),defense=16)]
    a.battle_presentation=None
    a.opening_input_blocked=a.battle_input_blocked=False
    a.begin_input()
''')
                acquisitions=[]
                for training in (False,True):
                    for mastered in (False,True):
                        for sid in ('double_slash','triple_slash','rapid_edge','seven_slash'):
                            if training and not py(f'a.session.skills[{sid!r}].can_relearn'):
                                continue
                            py(f'balance_fixture({sid!r},{mastered!r},{training!r})')
                            check('23 in balance_rows and 88 in balance_rows')
                            expected=py(f'a.session.skills[{sid!r}].power(a.session.party[0],next_copy=True)')
                            assert py(f'str({expected}) in balance_rows[23]')
                            assert py("'53' in balance_rows[88] and 'punch' not in a.session.party[0].mastered_copies")
                            if sid=='seven_slash' and mastered:
                                page.screenshot(path=str(shots/f'skill5b1_{mode}_{suffix}_preview.png'))
                            if sid=='double_slash' and not mastered and not training:
                                press('down'); check('a.replacement_cursor == 1')
                                press('up'); check('a.replacement_cursor == 0')
                                press('a'); check('a.replacement_confirm')
                                press('b'); check('not a.replacement_confirm')
                            press('a'); check('a.replacement_confirm')
                            press('a'); check('a.state == "camp"')
                            assert py(f'a.session.skills[{sid!r}].power(a.session.party[0])')==expected
                            assert py(f'{sid!r} in a.session.party[0].mastered_copies')==mastered
                            acquisitions.append(dict(skill=sid,mastered=mastered,training=training,power=expected))
                attacks=[]
                for sid in ('double_slash','triple_slash','rapid_edge','seven_slash'):
                    py(f'balance_battle({sid!r},True)')
                    expected=py(f'round(max(1,a.session.skills[{sid!r}].power(a.session.party[0],apply_mastery=False)-16)*1.2)')
                    press('a'); check('a.state == "skill"')
                    press('a'); check('a.state == "target"')
                    press('a'); check(f'a.session.party[0].used_skills.get({sid!r}) == 1')
                    assert py('5000-a.battle.enemies[0].hp')==expected
                    page.wait_for_timeout(900)
                    assert py('5000-a.battle.enemies[0].hp')==expected
                    assert py(f'a.session.party[0].skill_uses[{sid!r}]==a.session.skills[{sid!r}].max_uses-1')
                    attacks.append(dict(skill=sid,mastered_damage=expected,damage_once=True))
                py("balance_battle('full_heal')")
                press('a'); check('a.state == "skill"')
                press('a'); check('a.state == "target"')
                press('a'); check("a.session.party[0].skill_uses.get('full_heal') == 1")
                check('a.state == "command"')
                press('a'); check('a.state == "skill"')
                check("any(v=='1/2' for v in balance_rows.values())")
                assert py("a.session.skills['full_heal'].description.endswith(chr(0x521d)+chr(0x671f)+'2'+chr(0x56de)+chr(0x3002))")
                page.screenshot(path=str(shots/f'skill5b1_{mode}_{suffix}_fullheal.png'))
                assert not errors,errors
                results.append(dict(mode=mode,audio_unavailable=args.disable_audio,
                    acquisition_cases=acquisitions,actual_attack_cases=attacks,
                    full_heal_remaining_one=True,page_errors=errors))
                print('PASS:',mode,suffix,'10 acquisitions, four attacks, full heal 1/2',flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results,physical_ios_tested=False,
            physical_gkd_tested=False,battle_fixtures_seeded=True),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:
        server.shutdown()


if __name__=='__main__': main()
