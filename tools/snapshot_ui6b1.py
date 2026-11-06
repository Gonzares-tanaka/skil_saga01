"""Record the received working tree once; never restore or overwrite user data."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    target = ROOT / 'tests/fixtures/ui_phase6b1_before.json'
    if target.exists():
        raise FileExistsError('Received-tree snapshot already exists')
    sources = [ROOT / 'main.py', *ROOT.glob('*.pyxres'), *ROOT.glob('*.pyxpal'),
               *(ROOT / 'rpg').glob('*.py'), *(ROOT / 'data').glob('*.json'),
               *[p for p in (ROOT / 'assets').rglob('*') if p.is_file()],
               ROOT / 'README.md', ROOT / 'dist/index.html', ROOT / 'tools/run_gkd.sh']
    saves = list((ROOT / 'save').glob('*')) + list((ROOT / 'rpg/save').glob('*'))
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sources + saves if p.is_file() and '__pycache__' not in p.parts}
    changed_sources = ('rpg/dungeon_app.py', 'rpg/app.py', 'rpg/hub.py',
                       'rpg/labels.py', 'rpg/battle.py', 'rpg/elevator.py')
    before = dict(hashes=hashes,
                  sources={name: (ROOT / name).read_text(encoding='utf8') for name in changed_sources},
                  skills=json.loads((ROOT / 'data/skills.json').read_text(encoding='utf8')))
    temp = Path(tempfile.mkdtemp(prefix='skillseekers-ui6b1-before-'))
    for directory in ('rpg', 'data', 'assets', 'tests', 'tools'):
        shutil.copytree(ROOT / directory, temp / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'save'))
    for p in sources:
        if p.parent == ROOT:
            shutil.copy2(p, temp / p.name)
    before['temporary_before_copy'] = temp.as_posix()
    target.write_text(json.dumps(before, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('Received snapshot:', len(hashes), 'files; isolated before copy:', temp)


if __name__ == '__main__':
    main()
