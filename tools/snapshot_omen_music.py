"""Capture current user assets and game code before adding the offering cue."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def methods(path, class_name):
    source = path.read_text(encoding='utf8')
    cls = next(n for n in ast.parse(source).body
               if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {n.name: hashlib.sha256(ast.get_source_segment(source, n).encode()).hexdigest()
            for n in cls.body if isinstance(n, ast.FunctionDef)}


def main():
    path = ROOT / 'tests/fixtures/omen_music_before.json'
    if path.exists():
        raise FileExistsError('Baseline exists; refusing overwrite')
    files = list((ROOT/'rpg').glob('*.py')) + list((ROOT/'data').glob('*.json'))
    files += [p for p in (ROOT/'assets').rglob('*') if p.is_file()]
    files += [ROOT/name for name in ('main.py', 'game.pyxres', 'game.pyxpal',
        'area2.pyxres', 'area2.pyxpal', 'area3.pyxres', 'area3.pyxpal',
        'tools/gkd_diagnostic.py', 'tools/run_gkd.sh', 'tools/web_audio_guard.js')]
    data = dict(hashes={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files if '__pycache__' not in p.parts},
        app_methods=methods(ROOT/'rpg/dungeon_app.py', 'DungeonApp'),
        audio_methods=methods(ROOT/'rpg/sound.py', 'AudioManager'))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print('Captured', len(data['hashes']), 'current files, DungeonApp and AudioManager methods')


if __name__ == '__main__':
    main()
