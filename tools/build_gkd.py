"""Build a Pixel2 source package without player SAVE, caches or PC dependencies."""
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'verification/packages/skill_seekers_gkd.zip'
FILES = ('main.py', 'game.pyxres', 'game.pyxpal', 'area2.pyxres', 'area2.pyxpal',
         'area3.pyxres', 'area3.pyxpal')


def main():
    sources = [ROOT / name for name in FILES]
    sources.extend(sorted((ROOT / 'rpg').glob('*.py')))
    sources.extend(sorted((ROOT / 'data').glob('*.json')))
    sources.extend(sorted(p for p in (ROOT / 'assets').rglob('*') if p.is_file()
                          and not any(part in ('save', '__pycache__', '.venv') for part in p.parts)))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT.parent) as tmp:
        candidate = Path(tmp) / OUTPUT.name
        with zipfile.ZipFile(candidate, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            launcher = zipfile.ZipInfo('Skill_Seekers.sh')
            launcher.create_system = 3
            launcher.external_attr = 0o100755 << 16
            launcher.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(launcher, (ROOT / 'tools/run_gkd.sh').read_bytes().replace(b'\r\n', b'\n'))
            for p in sources:
                z.write(p, 'Skill_Seekers/' + p.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(candidate) as z:
            assert not any('/save/' in n or '__pycache__' in n for n in z.namelist())
            assert z.read('Skill_Seekers/rpg/enemy_actions.py') == (ROOT / 'rpg/enemy_actions.py').read_bytes()
            for p in sources:
                assert z.read('Skill_Seekers/' + p.relative_to(ROOT).as_posix()) == p.read_bytes()
            count = len(z.namelist())
        candidate.replace(OUTPUT)
    print('Built:', OUTPUT.relative_to(ROOT).as_posix(), 'entries:', count, 'SAVE excluded; all sources match')


if __name__ == '__main__':
    main()
