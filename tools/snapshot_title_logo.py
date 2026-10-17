"""Record the user-owned resource and all non-drawing game code before work."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from rpg.art import PALETTE


def main():
    output=ROOT/'tests/fixtures/title_logo_before.json'
    assert not output.exists(),'Baseline exists: refusing overwrite'
    files=list((ROOT/'rpg').glob('*.py'))+list((ROOT/'data').glob('*.json'))
    files+=list((ROOT/'assets').rglob('*'))
    files+=[ROOT/name for name in ('main.py','game.pyxres','game.pyxpal','area2.pyxres','area3.pyxres',
        'area2.pyxpal','area3.pyxpal','tools/gkd_diagnostic.py','tools/run_gkd.sh','tools/web_audio_guard.js')]
    source=(ROOT/'rpg/dungeon_app.py').read_text(encoding='utf8')
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='DungeonApp')
    methods={n.name:hashlib.sha256(ast.get_source_segment(source,n).encode()).hexdigest()
             for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    pyxel.init(160,120,headless=True); pyxel.colors[:4]=PALETTE
    pyxel.load(str(ROOT/'game.pyxres'))
    pixels=[pyxel.images[1].pget(x,y) for y in range(192,224) for x in range(128)]
    assert any(pixels),'The requested logo region is empty'
    border=[pyxel.images[1].pget(x,y) for x in range(128) for y in (192,223)]
    border += [pyxel.images[1].pget(x,y) for y in range(193,223) for x in (0,127)]
    result=dict(hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in files if p.is_file() and '__pycache__' not in p.parts},
        methods=methods,logo=dict(bank=1,u=0,v=192,width=128,height=32,
            sha256=hashlib.sha256(bytes(pixels)).hexdigest(),colors=dict(Counter(pixels)),border_colors=dict(Counter(border))))
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    out=ROOT/'verification/screenshots'; out.mkdir(exist_ok=True,parents=True)
    image=pyxel.Image(128,32); image.blt(0,0,1,0,192,128,32)
    image.save(str(out/'title_logo_original.png'),4)
    print('Captured',len(result['hashes']),'files;',result['logo'])


if __name__=='__main__': main()
