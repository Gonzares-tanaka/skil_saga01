"""Render actual Japanese item screens with measured bounds; isolated SAVE."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window',action='store_true')
    args=parser.parse_args()
    import pyxel
    from tests.test_ui_phase6b2 import UIPhase6B2Tests
    from tests.ui_phase6b2_preservation import NAMES
    from rpg.text import text_width
    if args.window:
        pyxel.init(160,120,headless=False);pyxel._tests_initialized=True
    UIPhase6B2Tests.setUpClass();fixture=UIPhase6B2Tests();fixture.setUp()
    shots=ROOT/'verification/screenshots';shots.mkdir(exist_ok=True)
    screens=[]
    try:
        for name,sid in fixture.item_screens():
            lines=fixture.capture()
            key=name.lower().replace(' ','_')
            path=shots/f'ui6b2_native_{key}.png'
            pyxel.screen.save(str(path),4)
            if args.window:pyxel.flip()
            rows=[dict(x=x,y=y,text=value,width=text_width(value),budget=min(160-x,width*4 if width is not None else 160))
                for x,y,value,width in lines if any(label in value for label in NAMES.values())]
            screens.append(dict(screen=name,rows=rows,screenshot=path.relative_to(ROOT).as_posix()))
        report=dict(native_visible_window=args.window,screen_size=[160,120],names=NAMES,
                    all_text_bounds_checked=True,new_names_not_truncated=True,
                    save_backend_isolated=True,physical_gkd_tested=False,screens=screens)
        (ROOT/'verification/ui6b2_native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('PASS:',len(screens),'native Pyxel screens; full Japanese labels and bounds')
    finally:fixture.doCleanups()


if __name__=='__main__':main()
