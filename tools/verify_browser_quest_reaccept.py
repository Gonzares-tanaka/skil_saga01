"""Real shipped Web runtime: quest reaccept after real combat, isolated profiles.

Travel uses the actual quest coordinates as a fixture; battle, reporting and
acceptance use the existing UI through keyboard or touch. No player saves.
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
    parser.add_argument('--expect-crash',action='store_true')
    parser.add_argument('--output-prefix',default='quest_reaccept')
    args=parser.parse_args()
    sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    label='before' if args.expect_crash else ('unavailable' if args.disable_audio else 'running')
    result=dict(cases=[],travel_position_fixture=True,physical_ios_tested=False,physical_gkd_tested=False)
    output=ROOT/f'verification/{args.output_prefix}_browser_{label}.json'
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='quest-reaccept-browser-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
            for mobile in ((False,) if args.expect_crash else (False,True)):
                mode='touch' if mobile else 'desktop';print('START:',label,mode,flush=True)
                options=dict(channel='msedge',headless=True,ignore_https_errors=True,
                             args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    options.update(pw.devices['Pixel 7']);options.pop('default_browser_type',None)
                context=pw.chromium.launch_persistent_context(str(Path(temp)/mode),**options)
                context.add_init_script('''window.qaContexts=[];const Native=window.AudioContext;
                    if(Native)window.AudioContext=new Proxy(Native,{construct(t,a,n){
                      const c=Reflect.construct(t,a,n);qaContexts.push(c);return c;}});''')
                page=context.pages[0];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded')
                page.locator('#play').click()
                frame=page.frame_locator('#game');frame.locator('#pyxel-prompt').wait_for(timeout=120000)
                frame.locator('#canvas').click();game=page.frames[-1]
                game.wait_for_function('''()=>{try{return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`)}catch(_){return false}}''',timeout=120000)
                def py(source):return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)',source)
                def check(source):game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)',arg=source,timeout=20000)
                py('''
import json,traceback
from copy import deepcopy
a=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
qa_trace=''
qa_old_observer=DungeonApp.observe_hunt_goal
def qa_observer(self):
    global qa_trace
    try:return qa_old_observer(self)
    except Exception:
        qa_trace=traceback.format_exc()
        raise
DungeonApp.observe_hunt_goal=qa_observer
def qa_snapshot():
    e=a.exploration
    return dict(state=a.state,overlay=a.overlay,battle_kind=a.battle_kind,
        outcome=a.battle.outcome if a.battle else None,settled=a.session.settled,
        active=deepcopy(e.active),clears=dict(e.quest_clear_counts),
        completed_ids=list(e.completed_quest_ids),banked=a.session.treasure.banked)
''')
                check('a.state=="title" and a.suspend_job is None')
                audio_states=[]
                if args.disable_audio:
                    audio_states=game.evaluate('''async()=>{
                        await Promise.all(qaContexts.map(async c=>{await c.suspend();
                          c.resume=()=>Promise.reject(new Error('intentional audio failure'))}));
                        document.dispatchEvent(new Event('visibilitychange'));
                        for(const e of ['blur','focus','pageshow'])window.dispatchEvent(new Event(e));
                        return qaContexts.map(c=>c.state)}''')
                    assert audio_states and all(s=='suspended' for s in audio_states)
                cdp=context.new_cdp_session(page) if mobile else None
                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box=game.locator(f'[data-gb="{button}"]').bounding_box();assert box
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)]))
                        page.wait_for_timeout(90);cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key=dict(a='z',b='x',up='ArrowUp',down='ArrowDown')[button]
                        page.keyboard.down(key);page.wait_for_timeout(90);page.keyboard.up(key)
                    page.wait_for_timeout(150)
                def settle():
                    for _ in range(180):
                        state=py('a.state');overlay=py('a.overlay')
                        if overlay=='rescue':
                            if py('a.rescue_input_blocked'):page.wait_for_timeout(100)
                            else:press('a')
                        elif state=='replace':press('b');press('a');press('a')
                        elif state in ('resolve','result','field_event','battle_transition'):
                            if py('a.battle_input_blocked'):page.wait_for_timeout(100)
                            else:press('a')
                        else:return
                    raise AssertionError(('unfinished battle',py('json.dumps(qa_snapshot())')))
                def accept(kind):
                    assert py('a.state=="camp"')
                    for _ in range(6):
                        if py('a.camp_cursor==2'):break
                        press('down')
                    press('a');press('a');check('a.state=="quest_board"');press('a')
                    for _ in range(('explore','investigate','hunt').index(kind)):press('down')
                    press('a');check('a.state=="quest_preview"')
                    while py('a.quest_flavor_page+1<len(a.quest_flavor_pages(a.exploration.pending_quest))'):press('a')
                    press('a')
                    page.wait_for_timeout(250)
                    if py('bool(qa_trace)'):return False
                    check('a.state=="quest_board" and a.exploration.active is not None')
                    press('b');press('b');check('a.state=="camp"');return True
                def complete_hunt():
                    q=json.loads(py('json.dumps(a.exploration.active)'))
                    while not py('a.camp_cursor==4'):press('down')
                    press('a');settle();check('a.state=="explore"')
                    py("q=a.exploration.active;a.dungeon.floor=q['target_floor']-1;a.dungeon.x,a.dungeon.y=q['points'][0]")
                    press('a');settle()
                    for _ in range(80):
                        if py('a.state!="command"'):break
                        while py('a.state=="command"'):
                            sid=py("choices=[s for s in a.actor.skills if a.actor.skill_uses.get(s,0)>0 and not a.actor.cooldowns.get(s,0) and a.session.skills[s].effect in ('damage','drain')];max(choices,key=lambda s:a.session.skills[s].power(a.actor)) if choices else ''")
                            if not sid:py('a.cursor=2');press('a');continue
                            py('a.cursor=0');press('a');check('a.state=="skill"')
                            while not py('a.skill_cursor==a.actor.skills.index('+repr(sid)+')'):press('down')
                            press('a')
                            if py('a.state=="target"'):press('a')
                        settle()
                    assert py('a.battle.outcome=="VICTORY" and a.exploration.surveyed')
                    settle();check('a.state=="explore"')
                    py('from rpg.tiles import TILE_ENTRANCE\na.dungeon.floor=0;a.dungeon.x,a.dungeon.y=a.dungeon.find(0,TILE_ENTRANCE)')
                    press('a');check('a.state=="quest_thanks"')
                    bank=py('a.session.treasure.banked')
                    for _ in range(py('len(a.quest_thanks_pages())')):press('a')
                    check('a.state=="quest_reward" and a.exploration.active is None')
                    assert py('a.session.treasure.banked')==bank+q['reward']
                    press('a');check('a.state=="camp"')
                press('a');check('a.state=="intro" and not a.opening_input_blocked')
                for _ in range(py('len(a.intro_pages)')):press('a')
                check('a.state=="hub_intro" and not a.opening_input_blocked');press('a');check('a.state=="camp"')
                assert accept('hunt');complete_hunt()
                first=json.loads(py('json.dumps(qa_snapshot())'))
                accepted=accept('hunt')
                trace=py('qa_trace')
                if args.expect_crash:
                    assert not accepted and 'ValueError: 討伐対象はいません。' in trace,trace
                    case=dict(mode=mode,reproduced=True,traceback=trace,first_report=first,
                              failed_state=json.loads(py('json.dumps(qa_snapshot())')))
                else:
                    assert accepted and not trace
                    complete_hunt();assert accept('explore')
                    assert py("a.exploration.active['type']=='explore' and a.exploration.active['progress']==0")
                    assert py("a.exploration.quest_clear_counts['hunt']==2")
                    assert not errors,errors
                    assert not py('qa_trace')
                    case=dict(mode=mode,success=True,audio_unavailable=args.disable_audio,
                        audio_states=audio_states,first_report=first,
                        final_state=json.loads(py('json.dumps(qa_snapshot())')),page_errors=errors)
                result['cases'].append(case)
                page.screenshot(path=str(shots/f'{args.output_prefix}_web_{label}_{mode}.png'))
                output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
                print('PASS:',label,mode,flush=True);context.close()
    finally:server.shutdown()


if __name__=='__main__':main()
