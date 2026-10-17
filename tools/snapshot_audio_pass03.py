"""One-time actual starting baseline; never read live saves."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audio_pass02_resource import read_resource,raw_snapshot,digest


def main():
    output=ROOT/'tests/fixtures/audio_pass03_before.json'
    assert not output.exists(),'Baseline exists: refusing overwrite'
    backup=ROOT/'verification/backups/audio_pass03'; backup.mkdir(parents=True,exist_ok=True)
    for name in ('game.pyxres','rpg/dungeon_app.py'):
        shutil.copy2(ROOT/name,backup/Path(name).name)
    resource=read_resource(ROOT/'game.pyxres')
    area=set(range(14,21))|{58}
    for music,row in enumerate(resource['musics']):
        if music!=2: assert not area.intersection(n for seq in row['seqs'] for n in seq)
    files=list((ROOT/'rpg').glob('*.py'))+list((ROOT/'data').glob('*.json'))
    files+=list((ROOT/'assets').rglob('*'))
    files+=[ROOT/name for name in ('main.py','game.pyxres','game.pyxpal','area2.pyxres','area3.pyxres',
        'area2.pyxpal','area3.pyxpal','tools/gkd_diagnostic.py','tools/run_gkd.sh','tools/web_audio_guard.js')]
    before=dict(scene={k:v if k in ('sounds','musics') else digest(v) for k,v in resource.items()},
        raw=raw_snapshot(ROOT/'game.pyxres'),
        hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files if p.is_file() and '__pycache__' not in p.parts})
    output.write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Captured',len(before['hashes']),'files. TITLE/SE protected. Only Music2 and Sounds14-20/58 may change.')
    print('Actual stairs:',resource['sounds'][50])


if __name__=='__main__': main()
