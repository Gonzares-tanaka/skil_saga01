"""Check payload parity, Python 3.11 syntax and untouched assets/player saves."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.ui_phase6b1_preservation import baseline,assert_preserved
from tools.build_gkd import FILES


def main():
    assert_preserved(unittest.TestCase())
    before=baseline()
    changed=[name for name,digest in before['hashes'].items()
             if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    saves=[name for name in before['hashes'] if 'save' in Path(name).parts]
    assert not set(saves).intersection(changed),'Player SAVE changed'
    assert not any(name.endswith(('.pyxres','.pyxpal','.bdf')) for name in changed)
    files=[ROOT/name for name in FILES]
    files.extend((ROOT/'rpg').glob('*.py'));files.extend((ROOT/'data').glob('*.json'))
    files.extend(p for p in (ROOT/'assets').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    html=(ROOT/'dist/game.html').read_text(encoding='utf8')
    payload=base64.b64decode(re.search(r'base64: "([^"]+)"',html)[1])
    packages=[]
    for name,data,prefix in (
        ('web',payload,'spark_web/'),
        ('gkd',(ROOT/'verification/packages/skill_seekers_gkd.zip').read_bytes(),'Skill_Seekers/'),
        ('gkd_diagnostic',(ROOT/'verification/packages/skill_seekers_gkd_diagnostic.zip').read_bytes(),'Skill_Seekers/')):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert not any('save' in Path(n).parts or '__pycache__' in n for n in z.namelist())
            for path in files:
                rel=path.relative_to(ROOT).as_posix()
                assert z.read(prefix+rel)==path.read_bytes(),(name,rel)
            for filename in z.namelist():
                if filename.endswith('.py'):
                    ast.parse(z.read(filename).decode('utf8'),filename=filename,feature_version=(3,11))
            if name!='web':
                assert z.read('PLAY_GUIDE_JA.txt')==(ROOT/'verification/GKD_PLAY_GUIDE_JA.txt').read_bytes()
            packages.append(dict(package=name,matched_files=len(files),save_excluded=True,
                python311_syntax=True,all_sources_match=True,sha256=hashlib.sha256(data).hexdigest()))
    result=dict(packages=packages,received_files=len(before['hashes']),
                changed_received_files=changed,protected_saves=saves,
                player_save_unchanged=True,assets_audio_maps_unchanged=True,
                skill_changes_only_two_display_names=True)
    (ROOT/'verification/ui6b1_packages.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(files),'game files match Web/GKD/diagnostic; assets and player SAVE unchanged')


if __name__=='__main__':main()
