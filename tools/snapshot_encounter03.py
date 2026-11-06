"""Capture received code/settings/resources before encounter-only changes."""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.snapshot_alpha_ux_methods import method_hashes


def main():
    target = ROOT/'tests/fixtures/alpha_encounter03_before.json'
    if target.exists():
        raise FileExistsError(target)
    paths = [ROOT/n for n in ('main.py','game.pyxres','game.pyxpal','area2.pyxres',
        'area2.pyxpal','area3.pyxres','area3.pyxpal','dist/index.html','tools/build_web.py',
        'tools/web_audio_guard.js','tools/web_suspend_store.js','tools/run_gkd.sh',
        'tools/gkd_diagnostic.py')]
    for directory in ('rpg','data','assets','dist/assets'):
        paths += [p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    hashes = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    methods = {p.relative_to(ROOT).as_posix():method_hashes(p.read_text(encoding='utf8'))
               for p in paths if p.suffix=='.py' and p.parent.name=='rpg'}
    source = (ROOT/'rpg/dungeon.py').read_text(encoding='utf8')
    node = next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Dungeon')
    move = next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='move')
    data = dict(hashes=hashes,methods=methods,settings=json.loads((ROOT/'data/dungeon.json').read_text(encoding='utf-8-sig')),
                legacy_move=ast.get_source_segment(source,move))
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Captured',len(hashes),'received files; legacy move and all encounter settings retained')


if __name__=='__main__': main()
