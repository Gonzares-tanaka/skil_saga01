"""Check release-only runtime, identical game payloads and received save/resources."""
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests.phase8_preservation import assert_preserved,baseline
from tools.build_gkd import FILES


def main():
    assert_preserved(unittest.TestCase())
    for name,digest in baseline()['hashes'].items():
        if 'save' in Path(name).parts:
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    files=[ROOT/n for n in FILES]+sorted((ROOT/'rpg').glob('*.py'))+sorted((ROOT/'data').glob('*.json'))
    files+=sorted(p for p in (ROOT/'assets').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    html=(ROOT/'dist/game.html').read_text(encoding='utf8')
    payload=base64.b64decode(re.search(r'base64: "([^"]+)"',html)[1]);reports=[]
    for name,data,prefix in (
        ('web',payload,'spark_web/'),
        ('gkd',(ROOT/'verification/packages/skill_seekers_gkd.zip').read_bytes(),'Skill_Seekers/'),
        ('gkd_diagnostic',(ROOT/'verification/packages/skill_seekers_gkd_diagnostic.zip').read_bytes(),'Skill_Seekers/')):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert not any('save' in Path(n).parts or '__pycache__' in n for n in z.namelist())
            for path in files:
                rel=path.relative_to(ROOT).as_posix();expected=path.read_bytes()
                if rel=='rpg/runtime.py':expected=expected.replace(b'DEVELOPMENT_BUILD = True',b'DEVELOPMENT_BUILD = False')
                assert z.read(prefix+rel)==expected,(name,rel)
            assert b'DEVELOPMENT_BUILD = False' in z.read(prefix+'rpg/runtime.py')
            for item in z.namelist():
                if item.endswith('.py'):ast.parse(z.read(item).decode('utf8'),feature_version=(3,11))
            reports.append(dict(package=name,matched_game_files=len(files),python311_syntax=True,
                                development_disabled=True,save_excluded=True,sha256=hashlib.sha256(data).hexdigest()))
    result=dict(packages=reports,player_save_unchanged=True,received_maps_art_audio_unchanged=True,
                same_game_content_in_normal_and_diagnostic=True,physical_gkd_tested=False)
    (ROOT/'verification/phase8_packages.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(files),'game files match all release payloads; resources and player SAVE preserved')


if __name__=='__main__':main()
