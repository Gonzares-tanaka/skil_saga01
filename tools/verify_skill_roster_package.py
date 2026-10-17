"""Check shipped Pixel2 sources without touching player data or launching SDL."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'verification/packages/skill_seekers_gkd.zip'


def main():
    with zipfile.ZipFile(PACKAGE) as archive:
        names=archive.namelist()
        assert not any(part in ('save','tests','__pycache__','.venv')
                       for name in names for part in Path(name).parts)
        sources=[]
        for name in names:
            if name=='Skill_Seekers.sh':
                assert archive.read(name)==(ROOT/'tools/run_gkd.sh').read_bytes().replace(b'\r\n',b'\n')
                continue
            assert name.startswith('Skill_Seekers/')
            path=ROOT/name.removeprefix('Skill_Seekers/')
            assert archive.read(name)==path.read_bytes(),name
            if name.endswith('.py'):
                ast.parse(archive.read(name).decode('utf8'),filename=name,feature_version=(3,11))
                sources.append(name)
        rows=json.loads(archive.read('Skill_Seekers/data/skills.json'))
        assert len(rows)==62
    report=dict(entries=len(names),python_311_sources=len(sources),roster_total=62,
                all_content_matches=True,save_excluded=True,launcher_unchanged=True,
                sha256=hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),physical_gkd_tested=False)
    (ROOT/'verification/skill_roster_package.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('PASS:',len(names),'package entries,',len(sources),'Python 3.11 source checks, 62 skills; SAVE excluded')


if __name__=='__main__': main()
