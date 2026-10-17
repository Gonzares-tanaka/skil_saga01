"""Capture current audio and protected bytes once; no player saves are read."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audio_pass02_resource import read_resource,raw_snapshot,digest


def main():
    target=ROOT/'tests/fixtures/audio_pass02_before.json'
    assert not target.exists(),'Baseline exists: refusing overwrite'
    backup=ROOT/'verification/backups/audio_pass02'; backup.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'game.pyxres',backup/'game.pyxres')
    scene=read_resource(ROOT/'game.pyxres')
    owners={i:[] for i in range(64)}
    for music,row in enumerate(scene['musics']):
        for seq in row['seqs']:
            for sound in seq: owners[sound].append(music)
    assert all(set(owners[i])=={0} for i in range(7))
    assert all(set(owners[i])=={2} for i in range(14,21))
    assert all(not scene['sounds'][i]['notes'] and not owners[i] for i in (57,58))
    reduced={key:value if key in ('sounds','musics') else digest(value) for key,value in scene.items()}
    files=list((ROOT/'rpg').glob('*.py'))+list((ROOT/'data').glob('*.json'))
    files+=list((ROOT/'assets').rglob('*'))
    files+=[ROOT/name for name in ('main.py','game.pyxres','game.pyxpal','area2.pyxres','area3.pyxres',
        'area2.pyxpal','area3.pyxpal','tools/gkd_diagnostic.py','tools/run_gkd.sh','tools/web_audio_guard.js')]
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()
            and '__pycache__' not in p.parts}
    result=dict(hashes=hashes,scene=reduced,raw=raw_snapshot(ROOT/'game.pyxres'),
        battle=read_resource(ROOT/'assets/battle_music.pyxres'),owners={i:sorted(set(v)) for i,v in owners.items()})
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Captured',len(hashes),'files. TITLE 0-6, AREA1 14-20; 57/58 empty and unreferenced.')
    print('Protected user stairs Sound 50:',scene['sounds'][50])


if __name__=='__main__': main()
