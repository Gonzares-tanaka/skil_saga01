"""Real title captures and checks; never saves or edits any pyxres."""
import io
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from tests.test_title_logo import TitleLogoTests


def main():
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TitleLogoTests))
    assert result.wasSuccessful(),stream.getvalue()
    case=TitleLogoTests(); case.setUp(); app=case.a
    out=ROOT/'verification/screenshots'; out.mkdir(parents=True,exist_ok=True)
    screenshots=[]
    for state,cursor,name in (('title',0,'new_game'),('title',1,'continue'),('title_no_save',1,'no_save')):
        app.state=state; app.title_cursor=cursor; app.draw()
        path=out/f'title_logo_{name}.png'; pyxel.screenshot(str(path),scale=4)
        screenshots.append(path.relative_to(ROOT).as_posix())
    before=case.before
    report=dict(test_count=result.testsRun,passed=result.testsRun,source=before['logo'],
        destination=dict(x=16,y=23,width=128,height=32,colkey=None,scale=1),
        full_resource_files_unchanged=True,other_app_methods_unchanged=True,
        resource_and_game_files_protected=len(before['hashes'])-1,
        logo_pixels_verified=4096,menu_unchanged=True,opening_audio_unchanged=True,
        screenshots=screenshots,physical_ios_tested=False,physical_gkd_tested=False)
    (ROOT/'verification/title_logo.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',result.testsRun,'tests, all4096 screen pixels equal source, 64 unchanged files, draw-only method change.')


if __name__=='__main__': main()
