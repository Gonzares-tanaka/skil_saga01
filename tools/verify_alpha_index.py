"""Check alpha landing layout and unchanged Pyxel keyboard/touch input."""
import argparse
from functools import partial
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from verify_browser_save import QuietHandler

IMAGE_HASHES = {
    'title_logo.png': 'a98cdcb8757ab8031f649b0ac8f1b022ee0a6ba8378b11cee02a4a79af7d0e0b',
    'skill_seekers_party.png': '9fb4457d734f9cab2d12c20dbdaf5b46e12dd17a84b8a76df37c3627da1cef5c',
}


def preservation():
    before = json.loads((ROOT/'verification/alpha_index_before.json').read_text(encoding='utf-8-sig'))
    for name, digest in before['hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    html = (ROOT/'dist/index.html').read_text(encoding='utf8')
    scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.S)
    assert len(scripts) == 1
    assert scripts[0] == before['startup_script'].replace('\r\n', '\n')
    for name, digest in IMAGE_HASHES.items():
        assert hashlib.sha256((ROOT/'dist/assets'/name).read_bytes()).hexdigest() == digest
    return len(before['hashes'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playwright-path', type=Path, required=True)
    args = parser.parse_args()
    protected = preservation()
    sys.path.insert(0, str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT/'dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    shots = ROOT/'verification/screenshots'; shots.mkdir(parents=True, exist_ok=True)
    layouts, games = [], []
    try:
        with tempfile.TemporaryDirectory(prefix='alpha-index-', ignore_cleanup_errors=True) as temp, sync_playwright() as pw:
            for mobile in (False, True):
                mode = 'touch_emulation' if mobile else 'desktop'
                print('START:', mode, flush=True)
                settings = dict(channel='msedge', headless=True, ignore_https_errors=True,
                    args=['--mute-audio', '--autoplay-policy=no-user-gesture-required'])
                if mobile:
                    settings.update(pw.devices['Pixel 7'])
                    settings.pop('default_browser_type', None)
                else:
                    settings['viewport'] = dict(width=1280, height=960)
                context = pw.chromium.launch_persistent_context(str(Path(temp)/mode), **settings)
                page = context.pages[0]
                errors, bad_responses = [], []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('response', lambda r: bad_responses.append(dict(url=r.url, status=r.status)) if r.status >= 400 else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='networkidle')
                sizes = [(390, 844), (320, 740)] if mobile else [(1280, 960), (768, 1024)]
                for width, height in sizes:
                    page.set_viewport_size(dict(width=width, height=height))
                    layout = page.evaluate('''() => {
                        const images = [...document.images].map(img => {
                            const box=img.getBoundingClientRect();
                            return {src:img.getAttribute('src'), width:img.naturalWidth, height:img.naturalHeight,
                                loaded:img.complete && img.naturalWidth>0,
                                ratio_error:Math.abs(box.width/box.height-img.naturalWidth/img.naturalHeight),
                                fits:box.left>=0 && box.right<=innerWidth};
                        });
                        const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
                        const anchors=[...document.querySelectorAll('a[href^="#"]')].every(a=>document.querySelector(a.getAttribute('href')));
                        return {viewport:innerWidth, document_width:document.documentElement.scrollWidth,
                            background:getComputedStyle(document.documentElement).backgroundColor,
                            main_width:document.querySelector('main').getBoundingClientRect().width,
                            columns:getComputedStyle(document.querySelector('.character-grid')).gridTemplateColumns,
                            duplicate_ids:ids.length-new Set(ids).size, anchors, images,
                            sections:[...document.querySelectorAll('h2')].map(e=>e.textContent),
                            h1_count:document.querySelectorAll('h1').length,
                            iframe_loaded:!!document.querySelector('#game').getAttribute('src')};
                    }''')
                    assert layout['document_width'] == width, layout
                    assert layout['background'] == 'rgb(255, 255, 255)'
                    assert layout['main_width'] <= 880
                    assert layout['duplicate_ids'] == 0 and layout['anchors']
                    assert layout['h1_count'] == 1 and not layout['iframe_loaded']
                    assert len(layout['images']) == 2
                    for image in layout['images']:
                        assert image['loaded'] and image['fits'] and image['ratio_error'] < .01, image
                    for label in ('ストーリー', 'ゲームをプレイ', '基本操作', 'ダンジョンメニュー', '冒険に役立つヒント', '登場人物'):
                        if label == 'ストーリー':
                            assert page.locator('.story').inner_text()
                        else:
                            assert any(label in h for h in layout['sections']), (label, layout)
                    page.screenshot(path=str(shots/f'alpha_index_{width}.png'), full_page=True)
                    layouts.append(dict(mode=mode, **layout))
                # Chromium's full-page capture/viewport resize can lose the
                # primary coarse-pointer emulation while retaining touch points.
                # Use a fresh, unresized device context for real pad events.
                assert not errors and not bad_responses, (errors, bad_responses)
                context.close()
                context = pw.chromium.launch_persistent_context(str(Path(temp)/(mode+'-game')), **settings)
                page = context.pages[0]
                errors, bad_responses = [], []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('response', lambda r: bad_responses.append(dict(url=r.url, status=r.status)) if r.status >= 400 else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='networkidle')
                page.screenshot(path=str(shots/f'alpha_index_{mode}_top.png'))
                page.locator('#play').click()
                assert page.locator('#play').is_hidden()
                assert 'game.html?v=' in page.locator('#game').get_attribute('src')
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

                def py(source):
                    return game.evaluate('(s)=>window.pyxelContext.pyodide.runPython(s)', source)

                py('_alpha_app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))')
                assert py('_alpha_app.state') == 'title'
                cdp = context.new_cdp_session(page) if mobile else None
                if mobile:
                    device_state = game.evaluate('''() => ({
                        coarse:matchMedia('(pointer: coarse)').matches,
                        touch:navigator.maxTouchPoints, width:innerWidth, height:innerHeight,
                        display:getComputedStyle(document.querySelector('#gb-controls')).display
                    })''')
                    print('TOUCH MEDIA:', device_state, flush=True)
                    assert device_state['coarse'] and device_state['display'] != 'none', device_state

                def press(button):
                    if mobile:
                        page.locator('#game').scroll_into_view_if_needed()
                        box=game.locator(f'[data-gb="{button}"]').bounding_box()
                        assert box is not None, game.evaluate('''() => ({
                            coarse:matchMedia('(pointer: coarse)').matches,
                            display:getComputedStyle(document.querySelector('#gb-controls')).display,
                            html:document.querySelector('#gb-controls').outerHTML
                        })''')
                        point=dict(x=box['x']+box['width']/2, y=box['y']+box['height']/2)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', touchPoints=[point]))
                        page.wait_for_timeout(100)
                        cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
                    else:
                        key=dict(up='ArrowUp', down='ArrowDown', left='ArrowLeft', right='ArrowRight', a='z', b='x')[button]
                        page.keyboard.down(key); page.wait_for_timeout(100); page.keyboard.up(key)
                    page.wait_for_timeout(150)

                def check(expr):
                    game.wait_for_function('(s)=>window.pyxelContext.pyodide.runPython(s)', arg=expr, timeout=10000)

                press('down'); check('_alpha_app.title_cursor == 1')
                press('a'); check('_alpha_app.state == "title_no_save"')
                press('b'); check('_alpha_app.state == "title"')
                press('up'); press('a')
                check('_alpha_app.state == "intro" and not _alpha_app.opening_input_blocked')
                for _ in range(py('len(_alpha_app.intro_pages)')):
                    press('a')
                check('_alpha_app.state == "hub_intro" and not _alpha_app.opening_input_blocked')
                press('a'); check('_alpha_app.state == "camp" and not _alpha_app.opening_input_blocked')
                for _ in range(4):
                    press('down')
                check('_alpha_app.camp_cursor == 4')
                press('a'); check('_alpha_app.state == "explore"')
                press('b'); check('_alpha_app.state == "menu"')
                press('b'); check('_alpha_app.state == "explore"')
                pad = game.evaluate('''() => {
                    const buttons=[...document.querySelectorAll('[data-gb]')];
                    const rects=buttons.map(b=>b.getBoundingClientRect());
                    let overlap=false;
                    for(let i=0;i<rects.length;i++) for(let j=i+1;j<rects.length;j++) {
                        const a=rects[i],b=rects[j];
                        if(a.left<b.right && b.left<a.right && a.top<b.bottom && b.top<a.bottom) overlap=true;
                    }
                    return {count:buttons.length, empty_labels:buttons.every(b=>!b.textContent.trim()),
                        overlap, display:getComputedStyle(document.querySelector('#gb-controls')).display};
                }''')
                assert pad['count'] == 6 and pad['empty_labels'] and not pad['overlap']
                if mobile:
                    assert pad['display'] != 'none'
                    for button in ('left', 'right', 'up', 'down'):
                        press(button)
                    assert game.evaluate('_virtualGamepadStates.every(v=>!v)')
                else:
                    assert pad['display'] == 'none'
                page.locator('#game').scroll_into_view_if_needed()
                page.screenshot(path=str(shots/f'alpha_index_{mode}_playing.png'))
                assert page.evaluate('document.documentElement.scrollWidth === innerWidth')
                assert not errors and not bad_responses, (errors, bad_responses)
                games.append(dict(mode=mode, boot=True, title_menu_A_B=True, new_game_to_hub=True,
                    dungeon_B_menu=True, pad=pad, page_errors=errors, failed_responses=bad_responses))
                context.close()
        preservation()
        report=dict(protected_files_unchanged=protected, startup_script_unchanged=True,
            source_images_byte_identical=True, layouts=layouts, games=games,
            physical_ios_tested=False, physical_android_tested=False)
        (ROOT/'verification/alpha_index.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        print('PASS: four responsive widths, both images, unchanged launch/game, real keyboard/touch A/B and pad', flush=True)
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
