"""Exact received-tree protection, packaged sources and Python 3.11 syntax."""
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
from tests.quest_reaccept_preservation import baseline,assert_preserved
from tools.build_gkd import FILES


def main():
    assert_preserved(unittest.TestCase())
    before=baseline()
    changed=[name for name,digest in before['hashes'].items()
             if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    assert changed==['rpg/dungeon_app.py'],changed
    saves=[n for n in before['hashes'] if 'save' in Path(n).parts]
    files=[ROOT/n for n in FILES]
    files.extend(sorted((ROOT/'rpg').glob('*.py')))
    files.extend(sorted((ROOT/'data').glob('*.json')))
    files.extend(sorted(p for p in (ROOT/'assets').rglob('*') if p.is_file() and '__pycache__' not in p.parts))
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
                player_save_unchanged=True,assets_audio_maps_data_unchanged=True,
                only_production_change='observe_hunt_goal: require not session.settled',
                physical_gkd_tested=False)
    (ROOT/'verification/quest_reaccept_packages.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(files),'game files match Web/GKD/diagnostic; only victory observer guard changed')


if __name__=='__main__':main()
