"""5C final Web payload: depletion, rescues, messages, donor independence and save."""
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
        with tempfile.TemporaryDirectory(prefix='skill-rescue5c-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
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
from copy import deepcopy
from rpg.models import Enemy,PARTY_IDS
from rpg.skill_resources import ensure_attack,RESCUE_SKILLS
from rpg.save import make_save_data,prepare_saved_game
import rpg.app as ui
probe_seen=[]
probe_original=ui.text

def probe_text(x,y,value,*args,**kwargs):
    if 80<=y<=105:probe_seen.append(str(value))
    return probe_original(x,y,value,*args,**kwargs)
ui.text=probe_text

def probe_fixture(index,startup=False):
    global probe_expected
    s=a.session
    s.battle=None;s.settled=True;s.pending_relearn=None;s.mastered_skills.clear();s.rescue_notices.clear()
    for j,c in enumerate(s.party):
        for sid in list(c.skills):c.forget(sid)
        c.pending_skill=None;c.mastered_copies.clear();c.reset_battle_state()
        c.hp=1000 if j==index else 0;c.max_hp=1000
        c.strength,c.agility,c.intellect=53,100 if j==index else 1,8
        c.learn(s.skills['fire'])
    c=s.party[index]
    for sid in list(c.skills):c.forget(sid)
    c.learn(s.skills['power_strike']);c.skill_uses['power_strike']=1
    if startup:
        c.forget('power_strike')
        for sid in ('heal','renew','first_aid','full_heal','counter','berserk'):c.learn(s.skills[sid])
    s.discovered_skills.update(sid for p in s.party for sid in p.skills)
    a.overlay=None;a.battle_presentation=None;a.notice_timer=0
    a.begin_encounter()
    a.battle.enemies=[Enemy('PROBE',5000,1,1,1,(0,0),defense=16,magic_defense=8)]
    a.opening_input_blocked=a.battle_input_blocked=False
    a.begin_input()
    clone=deepcopy(c)
    for sid in list(clone.skills):clone.forget(sid)
    probe_expected=ensure_attack(clone,s.skills)
    probe_seen.clear()
''')
                cases=[]
                for i,expected_id in enumerate(('spark','spark','punch','spark')):
                    py(f'probe_fixture({i})')
                    donor=2 if i!=2 else 0
                    assert py(f'a.session.party[{donor}].hp==0 and {expected_id!r} not in a.session.party[{donor}].skills')
                    donor_before=py(f'json.dumps(a.session.party[{donor}].skill_uses,sort_keys=True)')
                    for repetition in range(2):
                        if repetition:
                            py(f'a.session.party[{i}].skill_uses[{expected_id!r}]=1;probe_seen.clear()')
                        press('a');check('a.state=="skill"')
                        press('a');check('a.state=="target"')
                        press('a')
                        check(f'a.session.party[{i}].skills==[{expected_id!r}] and a.session.party[{i}].skill_uses[{expected_id!r}]==a.session.skills[{expected_id!r}].max_uses')
                        check('all(v in probe_seen for v in probe_expected)')
                        assert py('all(probe_seen.index(probe_expected[j])<probe_seen.index(probe_expected[j+1]) for j in range(len(probe_expected)-1))')
                        if not repetition:
                            page.screenshot(path=str(shots/f'skill_rescue5c_{mode}_{suffix}_{i}.png'))
                        check('a.state=="command"')
                        assert py(f'"power_strike" in a.session.mastered_skills and ({expected_id!r} in a.session.party[{i}].mastered_copies)=={bool(repetition)!r}')
                    assert py(f'json.dumps(a.session.party[{donor}].skill_uses,sort_keys=True)')==donor_before
                    cases.append(dict(party_id=py(f'a.session.party[{i}].party_id'),rescue=expected_id,
                        rescue_twice=True,donor_ko_absent_and_unspent=True,messages_drawn_in_order=True))
                py('probe_fixture(0,True)')
                check('a.overlay=="rescue" and not a.rescue_input_blocked')
                assert py('len(a.session.party[0].skills)==6 and a.session.party[0].skills[-1]=="spark"')
                offset=py('a.rescue_offset')
                press('down');assert py('a.rescue_offset')==offset
                press('a');check('a.overlay=="rescue" and a.rescue_offset==3 and not a.rescue_input_blocked')
                page.screenshot(path=str(shots/f'skill_rescue5c_{mode}_{suffix}_startup.png'))
                press('b');check('a.overlay is None and a.state=="command"')
                press('a');check('a.state=="skill"')
                # SKILL restores the last used skill; do not assume cursor 0.
                for _ in range(6):
                    if py('a.actor.skills[a.skill_cursor]=="spark"'):break
                    press('down')
                assert py('a.actor.skills[a.skill_cursor]=="spark"')
                press('b');check('a.state=="command"')
                # Same JSON via real Web localStorage, isolated test profile.
                py('saved5c=make_save_data(a);a.save_manager.backend.write(saved5c);loaded5c=prepare_saved_game(a,a.save_manager.backend.read())[0]')
                assert py('tuple(c.party_id for c in loaded5c.party)==PARTY_IDS')
                assert py('all(x.skills==y.skills and x.skill_uses==y.skill_uses and x.mastered_copies==y.mastered_copies for x,y in zip(a.session.party,loaded5c.party))')
                assert not errors,errors
                results.append(dict(mode=mode,audio_unavailable=args.disable_audio,cases=cases,
                    startup_full_slots_notice_ab=True,dpad_skill_selection=True,web_save_roundtrip=True,page_errors=errors))
                print('PASS:',mode,suffix,'four identities, repeat rescue, donor KO, A/B, Web save',flush=True)
                context.close()
        args.output.write_text(json.dumps(dict(cases=results,physical_ios_tested=False,
            physical_gkd_tested=False,battle_fixtures_seeded=True),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:
        server.shutdown()


if __name__=='__main__': main()
