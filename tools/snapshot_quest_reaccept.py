"""Freeze the received quest/UI data before the crash fix, without restoring it."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    target=ROOT/'tests/fixtures/quest_reaccept_before.json'
    if target.exists():raise FileExistsError(target)
    files=[ROOT/'main.py',*ROOT.glob('*.pyxres'),*ROOT.glob('*.pyxpal'),
           *(ROOT/'rpg').glob('*.py'),*(ROOT/'data').glob('*.json'),
           *[p for p in (ROOT/'assets').rglob('*') if p.is_file() and '__pycache__' not in p.parts]]
    files += [p for directory in ('save','rpg/save') for p in (ROOT/directory).glob('*') if p.is_file()]
    target.write_text(json.dumps(dict(hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files},dungeon_app=(ROOT/'rpg/dungeon_app.py').read_text(encoding='utf8')),
        ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Received tree captured:',len(files),'files; no game or SAVE writes')


if __name__=='__main__':main()
