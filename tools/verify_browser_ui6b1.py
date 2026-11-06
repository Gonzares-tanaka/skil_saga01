"""Shipped Web UI 6B-1: real keyboard/touch, readonly quests and silent resume."""
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
    args=parser.parse_args()
    sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True)
    results=[];suffix='unavailable' if args.disable_audio else 'running'
    try:
        with tempfile.TemporaryDirectory(prefix='ui6b1-browser-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
            for mobile in (False,True):
                mode='touch' if mobile else 'desktop';print('START:',mode,suffix,flush=True)
                options=dict(channel='msedge',headless=True,ignore_https_errors=True,
                             args=['--mute-audio','--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    options.update(pw.devices['Pixel 7']);options.pop('default_browser_type',None)
                context=pw.chromium.launch_persistent_context(str(Path(temp)/mode),**options)
                context.add_init_script('''window.ui6Contexts=[];const Native=window.AudioContext;
                    if(Native)window.AudioContext=new Proxy(Native,{construct(t,a,n){
                      const c=Reflect.construct(t,a,n);ui6Contexts.push(c);return c;}});''')
                page=context.pages[0];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                game=None
                def py(source):return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)',source)
                def check(source):game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)',arg=source,timeout=20000)
                def boot():
                    nonlocal game
                    page.locator('#play').click()
                    frame=page.frame_locator('#game');frame.locator('#pyxel-prompt').wait_for(timeout=120000)
                    frame.locator('#canvas').click();game=page.frames[-1]
                    game.wait_for_function('''()=>{try{return window.pyxelContext?.pyodide?.runPython(`
import gc
from rpg.dungeon_app import DungeonApp
any(isinstance(o,DungeonApp) for o in gc.get_objects())
`)}catch(_){return false}}''',timeout=120000)
                    py('''
import json
a=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
from rpg import dungeon_app as ui
def ui_words(method):
    lines=[]
    real=ui.text
    def record(x,y,value,*args,**kwargs):
        lines.append(str(value));return real(x,y,value,*args,**kwargs)
    ui.text=record
    try:getattr(a,method)()
    finally:ui.text=real
    return lines
''')
                    check('a.state=="title" and a.suspend_job is None')
                    if args.disable_audio:
                        states=game.evaluate('''async()=>{
                            await Promise.all(ui6Contexts.map(async c=>{await c.suspend();
                              c.resume=()=>Promise.reject(new Error('intentional audio failure'))}));
                            document.dispatchEvent(new Event('visibilitychange'));
                            for(const e of ['blur','focus','pageshow'])window.dispatchEvent(new Event(e));
                            return ui6Contexts.map(c=>c.state)}''')
                        assert states and all(s=='suspended' for s in states)
                cdp=context.new_cdp_session(page) if mobile else None
                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box=game.locator(f'[data-gb="{button}"]').bounding_box();assert box
                        cdp.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[dict(x=box['x']+box['width']/2,y=box['y']+box['height']/2)]))
                        page.wait_for_timeout(90);cdp.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]))
                    else:
                        key=dict(a='z',b='x',up='ArrowUp',down='ArrowDown',left='ArrowLeft',right='ArrowRight')[button]
                        page.keyboard.down(key);page.wait_for_timeout(90);page.keyboard.up(key)
                    page.wait_for_timeout(150)
                def shot(name):page.screenshot(path=str(shots/f'ui6b1_web_{mode}_{suffix}_{name}.png'))
                page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded');boot()
                press('a');check('a.state=="intro" and not a.opening_input_blocked')
                for _ in range(py('len(a.intro_pages)')):press('a')
                check('a.state=="hub_intro" and not a.opening_input_blocked');press('a');check('a.state=="camp"')
                assert py("list(ui.HUB_FACILITY_LABELS)")==['ギルド','訓練場','パブ','ショップ','ダンジョン','エレベーター']
                assert py("[a.session.skills[s].name for s in ('return','revive')]")==['リターン','リバイブ']
                shot('hub')
                py('''
from rpg.quests import spawn_candidates
a.dungeon.defeated_bosses.update((4,9))
a.exploration.accept(3,quest_type='investigate')
q=a.exploration.active_quest;q['target_floor']=14
q['points']=[list(p) for p in spawn_candidates(a.dungeon,13)[:3]]
q['progress']=1;q['investigated_points']=[q['points'][0]]
''')
                for _ in range(4):press('down')
                press('a');check('a.state=="explore"');press('b')
                for _ in range(6):press('down')
                press('a');check('a.overlay=="field_quest"')
                assert py("ui_words('draw_field_quest')")==['調査 Lv3','対象：B14F','進捗：1/3']
                shot('quest_partial');press('b');check('a.overlay is None and a.state=="menu"')
                press('b');check('a.state=="explore"');press('b')
                press('down');press('down');press('a');check('a.state=="items"')
                expected=['味方1人のHPを回復する','戦闘不能の味方1人を蘇生する',
                          '味方の状態異常を治療する','ダンジョンから帰還 / 1個消費']
                for i,text in enumerate(expected):
                    assert py("ui_words('draw_items')")[-1]==text
                    if i==0:shot('potion')
                    press('down')
                press('b');press('b');check('a.state=="explore"')
                py('''
a.dungeon.floor=13;a.dungeon.x,a.dungeon.y=q['points'][1]
from rpg.suspend import make_suspend_data
expected_suspend=json.dumps(make_suspend_data(a),sort_keys=True)
''')
                expected_suspend=py('expected_suspend')
                press('b')
                for _ in range(5):press('down')
                press('a');check('a.state=="suspend_confirm"');press('up');press('a')
                check('a.state=="title" and a.suspend_available')
                page.reload(wait_until='domcontentloaded');boot()
                press('down');press('down');press('a');check('a.state=="explore" and not a.opening_input_blocked')
                py('from rpg.suspend import make_suspend_data')
                assert py('json.dumps(make_suspend_data(a),sort_keys=True)')==expected_suspend
                assert py('not a.suspend_available')
                press('b')
                for _ in range(6):press('down')
                press('a');check('a.overlay=="field_quest"')
                assert py("ui_words('draw_field_quest')")==['調査 Lv3','対象：B14F','進捗：1/3']
                py("a.exploration.active_quest.update(progress=3,completed=True)")
                assert '拠点に戻って報告' in py("ui_words('draw_field_quest')")
                shot('quest_return')
                press('b');press('b')
                py("a.exploration.active_quest.update(progress=1,completed=False);a.safe_return([])")
                check('a.state=="return_result"');press('a');check('a.state=="camp"')
                py('''
a.session.treasure.banked=20
c=a.session.party[0]
if 'punch' in c.skills:c.forget('punch')
a.session.discovered_skills.add('punch');a.session.mastered_skills.add('punch')
''')
                press('down');press('a');check('a.state=="facility"');press('down');press('a')
                check('a.state=="relearn_character"');press('a');check('a.state=="relearn_list"')
                py("a.relearn_cursor=next(i for i,s in enumerate(a.session.relearn_candidates()) if s.id=='punch')")
                press('a');check('a.state=="relearn_confirm"')
                assert any('予定威力' in s and 'MASTER x1.2' in s for s in py("ui_words('draw_camp_resources')"))
                shot('preview');press('b');assert py('a.session.treasure.banked==20')
                py("a.state='pub';a.overlay=None;a.pub_cursor=0;a.notice_timer=0")
                press('a');check('a.state=="field_event"')
                assert py('a.field_after=="pub" and a.session.treasure.banked==19')
                shot('rumor')
                while py('a.state=="field_event"'):press('a')
                assert py('a.state=="pub"')
                assert not errors,errors
                results.append(dict(mode=mode,audio_unavailable=args.disable_audio,
                    localized_labels=True,item_hints=True,quest_readonly_summary=True,
                    indexeddb_exact_once=True,quest_after_resume=True,
                    mastered_next_copy_preview=True,pub_heading_fee_return=True,page_errors=errors))
                print('PASS:',mode,suffix,flush=True);context.close()
        (ROOT/f'verification/ui6b1_browser_{suffix}.json').write_text(json.dumps(dict(cases=results,
            physical_ios_tested=False,physical_gkd_tested=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:server.shutdown()


if __name__=='__main__':main()
