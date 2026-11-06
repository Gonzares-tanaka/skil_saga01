"""Web UI 6B-2: Japanese items plus the existing save, quest and silent UI flow."""
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
        with tempfile.TemporaryDirectory(prefix='ui6b2-browser-',ignore_cleanup_errors=True) as temp,sync_playwright() as pw:
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
                def shot(name):page.screenshot(path=str(shots/f'ui6b2_web_{mode}_{suffix}_{name}.png'))
                page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='domcontentloaded');boot()
                press('a');check('a.state=="intro" and not a.opening_input_blocked')
                for _ in range(py('len(a.intro_pages)')):press('a')
                check('a.state=="hub_intro" and not a.opening_input_blocked');press('a');check('a.state=="camp"')
                py("""
from rpg import app as item_ui
from rpg.text import text_width,fit
item_names=['ポーション','不死鳥の灰','妖精のしずく','帰還の羽根']
item_ids=['POTION','PHOENIX ASH','REMEDY','return_feather']
item_hints=['味方1人のHPを回復する','戦闘不能の味方1人を蘇生する','味方の状態異常を治療する','ダンジョンから帰還 / 1個消費']
def item_words(method):
    rows=[];real=ui.text;other=item_ui.text
    def record(x,y,value,color=3,width=None):
        value=str(value);rows.append(value)
        if any(label in value for label in item_names):
            budget=min(160-x,width*4 if width is not None else 160)
            assert text_width(value)<=budget,(x,y,value,budget)
            assert fit(value,budget)==value
        return real(x,y,value,color,width)
    ui.text=item_ui.text=record
    try:getattr(a,method)()
    finally:ui.text=real;item_ui.text=other
    return rows
""")
                py('a.session.treasure.banked=40') # Isolated purchase fixture only.
                for _ in range(3):press('down')
                press('a');press('a');check('a.state=="shop"')
                assert py("all(any(n in line for line in item_words('draw_shop')) for n in item_names)")
                shot('japanese_shop')
                for index in range(4):
                    old_bank=py('a.session.treasure.banked')
                    old_count=py('a.session.inventory.counts[item_ids[a.shop_cursor]]')
                    price=py('a.session.inventory.data["items"][item_ids[a.shop_cursor]]["price"]')
                    press('a')
                    assert py('a.session.treasure.banked')==old_bank-price
                    assert py('a.session.inventory.counts[item_ids[a.shop_cursor]]')==old_count+1
                    assert py('item_names[a.shop_cursor] in a.notice')
                    py('a.notice_timer=0');press('down')
                press('b');press('b');check('a.state=="camp"')
                press('down');press('a');check('a.state=="explore"')
                press('b');press('down');press('down');press('a');check('a.state=="items"')
                for index in range(4):
                    assert py("item_hints[a.item_kind_cursor] in item_words('draw_items')")
                    assert py("all(any(n in line for line in item_words('draw_items')) for n in item_names)")
                    shot('japanese_field_'+str(index));press('down')
                press('down');press('down');press('a');check('a.state=="item_target"')
                assert py("any(item_names[2] in s for s in item_words('draw_item_target'))")
                py("from rpg.statuses import apply_status\na.session.party[2].hp=1;apply_status(a.session.party[2],'poison')")
                press('down');press('down')
                old_count=py("a.session.inventory.counts['REMEDY']")
                press('a')
                assert py("not a.session.party[2].statuses and a.session.party[2].hp==1")
                assert py("a.session.inventory.counts['REMEDY']")==old_count-1
                shot('japanese_remedy_target');press('b');press('b');press('b')
                check('a.state=="explore"')
                py("""
a.begin_encounter()
a.session.inventory.counts.update({sid:9 for sid in item_ids})
a.session.party[0].hp=1;a.session.party[1].hp=0
apply_status(a.session.party[2],'poison')
a.state='battle_item';a.actions=[];a.item_cursor=0;a.notice_timer=0
""")
                for index in range(3):
                    assert py("all(any(n in s for s in item_words('draw_battle_items')) for n in item_names[:3])")
                    assert py("item_hints[a.item_cursor] in item_words('draw_battle_items')")
                    shot('japanese_battle_'+str(index));press('a');check('a.state=="target"')
                    assert py("any(item_names[item_ids.index(a.selected_item)] in s for s in item_words('draw_battle'))")
                    shot('japanese_battle_target_'+str(index));press('b');press('down')
                py("""
a.battle.outcome='ESCAPE';a.session.settle();a.battle=None;a.battle_kind='normal';a.actions=[]
a.enter_camp();a.item_kind_cursor=0
assert a.rumors['gameplay'][6]=='ダンジョンの深淵で迷ったら、左手を頼りに進め。'
assert a.rumors['gameplay'][7]=='アムリタには、まだ知られぬ力があるらしい。'
assert len(a.rumors['gameplay'])+len(a.rumors['flavor'])==18
""")
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
                    localized_labels=True,item_hints=True,japanese_item_labels=True,item_bounds=True,
                    item_purchase_and_remedy_effect=True,two_rumors_verified=True,quest_readonly_summary=True,
                    indexeddb_exact_once=True,quest_after_resume=True,
                    mastered_next_copy_preview=True,pub_heading_fee_return=True,page_errors=errors))
                print('PASS:',mode,suffix,flush=True);context.close()
        (ROOT/f'verification/ui6b2_browser_{suffix}.json').write_text(json.dumps(dict(cases=results,
            physical_ios_tested=False,physical_gkd_tested=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    finally:server.shutdown()


if __name__=='__main__':main()
