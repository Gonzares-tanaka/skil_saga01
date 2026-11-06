"""Verify original assets/user SAVE, all three payloads, credits and licenses."""
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
from tests.phase7_preservation import assert_preserved,baseline
from tools.build_gkd import FILES


def main():
    assert_preserved(unittest.TestCase())
    before=baseline()
    changed=[]
    for name,digest in before['hashes'].items():
        actual=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if actual!=digest:changed.append(name)
        if 'save' in Path(name).parts:assert actual==digest,name
    files=[ROOT/n for n in FILES]+sorted((ROOT/'rpg').glob('*.py'))+sorted((ROOT/'data').glob('*.json'))
    files+=sorted(p for p in (ROOT/'assets').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    html=(ROOT/'dist/game.html').read_text(encoding='utf8')
    payload=base64.b64decode(re.search(r'base64: "([^"]+)"',html)[1])
    reports=[]
    for name,data,prefix in (
        ('web',payload,'spark_web/'),
        ('gkd',(ROOT/'verification/packages/skill_seekers_gkd.zip').read_bytes(),'Skill_Seekers/'),
        ('gkd_diagnostic',(ROOT/'verification/packages/skill_seekers_gkd_diagnostic.zip').read_bytes(),'Skill_Seekers/')):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert not any('save' in Path(n).parts or '__pycache__' in n for n in z.namelist())
            for path in files:
                rel=path.relative_to(ROOT).as_posix()
                assert z.read(prefix+rel)==path.read_bytes(),(name,rel)
            for item in z.namelist():
                if item.endswith('.py'):ast.parse(z.read(item).decode('utf8'),feature_version=(3,11))
            for item in ('data/ending_credits.json','data/postgame.json','assets/postgame.pyxres',
                         'assets/licenses/PYXEL_LICENSE.txt','assets/licenses/THIRD_PARTY_NOTICES.txt'):
                assert prefix+item in z.namelist()
            reports.append(dict(package=name,matched_files=len(files),python311_syntax=True,
                                save_excluded=True,sha256=hashlib.sha256(data).hexdigest()))
    result=dict(packages=reports,changed_received_files=changed,
        original_maps_images_audio_data_unchanged=True,player_save_unchanged=True,
        credits_music_and_dragon_data_included=True,licenses_included=True,
        same_game_content_in_normal_and_diagnostic=True,physical_gkd_tested=False)
    (ROOT/'verification/phase7_packages.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(files),'game files match all payloads; original resources/data/user SAVE preserved')


if __name__=='__main__':main()
