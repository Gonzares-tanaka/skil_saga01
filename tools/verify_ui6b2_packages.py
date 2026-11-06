"""Compare shipped files and ensure only authorized UI 6B-2 changes occurred."""
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
from tests.ui_phase6b2_preservation import baseline,assert_preserved,NAMES
from tools.build_gkd import FILES


def main():
    assert_preserved(unittest.TestCase())
    before=baseline()
    changed=[n for n,digest in before['hashes'].items()
             if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=digest]
    allowed={'data/items.json','data/pub_messages.json',*before['sources']}
    assert set(changed)==allowed,changed
    files=[ROOT/n for n in FILES]
    files.extend(sorted((ROOT/'rpg').glob('*.py')))
    files.extend(sorted((ROOT/'data').glob('*.json')))
    files.extend(sorted(p for p in (ROOT/'assets').rglob('*') if p.is_file() and '__pycache__' not in p.parts))
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
            for filename in z.namelist():
                if filename.endswith('.py'):
                    ast.parse(z.read(filename).decode('utf8'),filename=filename,feature_version=(3,11))
            reports.append(dict(package=name,matched_files=len(files),python311_syntax=True,
                                user_save_excluded=True,sha256=hashlib.sha256(data).hexdigest()))
    result=dict(packages=reports,changed_received_files=changed,names=NAMES,
        protected_saves=[n for n in before['hashes'] if 'save' in Path(n).parts],
        player_save_unchanged=True,other_sixteen_rumors_unchanged=True,
        protected_gameplay_assets_and_user_text_unchanged=True,
        game_code_and_data_identical_across_three_packages=True,
        physical_gkd_tested=False,physical_ios_tested=False)
    (ROOT/'verification/ui6b2_packages.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(files),'files match Web/GKD/diagnostic; seven authorized source/data files changed')


if __name__=='__main__':main()
