"""Match every Web/GKD gameplay file to the validated received-tree changes."""
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
from tests.skill_balance5b2_preservation import assert_preserved

def main():
    assert_preserved(unittest.TestCase())
    web=ROOT/'dist/game.html'
    payload=base64.b64decode(re.search(r'base64: "([^"]+)"',web.read_text(encoding='utf8'))[1])
    report=[]
    for label,data,prefix in (
        ('web',payload,'spark_web/'),
        ('gkd',(ROOT/'verification/packages/skill_seekers_gkd.zip').read_bytes(),'Skill_Seekers/'),
        ('gkd_diagnostic',(ROOT/'verification/packages/skill_seekers_gkd_diagnostic.zip').read_bytes(),'Skill_Seekers/')):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert not any('save' in Path(n).parts or '__pycache__' in n for n in z.namelist())
            files=[ROOT/'main.py',*ROOT.glob('*.pyxres'),*ROOT.glob('*.pyxpal'),
                   *(ROOT/'rpg').glob('*.py'),*(ROOT/'data').glob('*.json'),
                   *[p for p in (ROOT/'assets').rglob('*') if p.is_file()]]
            # Only root resources actually used by builds (exclude editor extras).
            files=[p for p in files if p.name in ('main.py','game.pyxres','game.pyxpal','area2.pyxres','area2.pyxpal','area3.pyxres','area3.pyxpal') or p.parent!=ROOT]
            for path in files:
                name=prefix+path.relative_to(ROOT).as_posix()
                assert z.read(name)==path.read_bytes(),name
            python=0
            for name in z.namelist():
                if name.endswith('.py'):
                    ast.parse(z.read(name).decode('utf8'),filename=name,feature_version=(3,11)); python+=1
            assert len(json.loads(z.read(prefix+'data/skills.json')))==62
            report.append(dict(package=label,entries=len(z.namelist()),matched_files=len(files),
                               python311_sources=python,save_excluded=True,all_sources_match=True,
                               sha256=hashlib.sha256(data).hexdigest()))
    (ROOT/'verification/skill_balance5b2_packages.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('PASS:',report)

if __name__=='__main__': main()
