"""Capture the received UX01 tree before the narrowly scoped gameplay pass."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audio_pass02_resource import read_resource, raw_snapshot
from tools.snapshot_alpha_ux_methods import method_hashes


def main():
    target = ROOT / 'tests/fixtures/alpha_gameplay02_before.json'
    if target.exists():
        raise FileExistsError(target)
    names = ['main.py', 'game.pyxres', 'game.pyxpal', 'area2.pyxres', 'area2.pyxpal',
             'area3.pyxres', 'area3.pyxpal', 'dist/index.html', 'tools/build_web.py',
             'tools/web_suspend_store.js', 'tools/run_gkd.sh', 'tools/gkd_diagnostic.py']
    names += [str(p.relative_to(ROOT)).replace('\\', '/') for folder in ('rpg', 'data', 'assets')
              for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    hashes = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    methods = {n: method_hashes((ROOT / n).read_text(encoding='utf8'))
               for n in names if n.startswith('rpg/') and n.endswith('.py')}
    result = dict(hashes=hashes, methods=methods, scene=read_resource(ROOT/'game.pyxres'),
                  raw=raw_snapshot(ROOT/'game.pyxres'))
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print('Captured', len(hashes), 'files before gameplay edits')
    image = result['scene']['images'][2]
    print('Image2 keys:', list(image))
    print('Image2 data sample:', repr(image['data'][:2]))


if __name__ == '__main__':
    main()
