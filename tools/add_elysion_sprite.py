"""One-time editable 48px placeholder; refuses to replace human artwork."""
import io
from pathlib import Path
import re
import shutil
import sys
import tomllib
import zipfile

import pyxel

ROOT = Path(__file__).resolve().parents[1]
U, V, SIZE = 144, 64, 48  # Image Bank 0, deliberately unused at Phase 6B.5.


def add():
    resource = ROOT / 'game.pyxres'
    with zipfile.ZipFile(resource) as archive:
        members = [(info, archive.read(info)) for info in archive.infolist()]
        source = archive.read('pyxel_resource.toml').decode('utf-8')
    original = tomllib.loads(source)
    rows = original['images'][0]['data']
    if any(y < len(rows) and x < len(rows[y]) and rows[y][x]
           for y in range(V, V + SIZE) for x in range(U, U + SIZE)):
        print('Existing artwork preserved; no write:', resource.name, 'Image 0 (144,64) 48x48')
        return
    backup = ROOT / 'verification/backups/phase6b5/game.pyxres'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(resource, backup)

    # Draw a new silhouette at native resolution, never scale the small enemy.
    pyxel.init(160, 120, headless=True)
    art = pyxel.Image(SIZE, SIZE)
    art.cls(0)
    # Wings / mantle frame the armoured king, echoing the existing guardian.
    for side in (0, 1):
        x = 5 if side == 0 else 31
        art.tri(x, 19, x + 11, 15, x + 7, 39, 1)
        art.line(x + 1, 21, x + 6, 33, 2)
    art.tri(23, 15, 8, 45, 39, 45, 1)
    art.tri(23, 20, 15, 43, 32, 43, 2)
    art.rect(18, 37, 5, 9, 1)
    art.rect(25, 37, 5, 9, 1)
    art.line(17, 46, 22, 46, 2)
    art.line(25, 46, 31, 46, 2)
    art.rect(14, 18, 19, 15, 2)
    art.rect(18, 19, 11, 13, 1)
    art.line(18, 21, 23, 25, 3)
    art.line(23, 25, 29, 21, 3)
    art.circ(23, 25, 2, 3)
    art.rect(11, 19, 5, 9, 1)
    art.rect(31, 19, 5, 9, 1)
    art.rect(17, 8, 13, 9, 2)
    art.rect(19, 10, 9, 6, 1)
    art.line(20, 12, 26, 12, 3)
    art.rect(21, 14, 5, 2, 0)
    art.rect(16, 6, 15, 3, 3)
    for x, top in ((16, 3), (22, 1), (28, 3)):
        art.rect(x, top, 3, 6 - top, 2)
        art.pset(x + 1, top, 3)
    # Sword, held away from the mantle, recognizable without fine detail.
    art.line(39, 13, 39, 40, 3)
    art.line(40, 14, 40, 35, 2)
    art.line(35, 33, 43, 33, 2)
    art.rect(37, 25, 3, 4, 2)
    for y in range(SIZE):
        while len(rows) <= V + y:
            rows.append([])
        rows[V + y].extend([0] * max(0, U + SIZE - len(rows[V + y])))
        rows[V + y][U:U + SIZE] = [art.pget(x, y) for x in range(SIZE)]
    parts = source.split('[[images]]')
    parts[1], count = re.subn(r'(?m)^data = .*', 'data = ' + repr(rows), parts[1], count=1)
    assert count == 1
    changed = '[[images]]'.join(parts)
    check = tomllib.loads(changed)
    assert all(check[key] == original[key] for key in original if key != 'images')
    assert check['images'][1:] == original['images'][1:]
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for info, blob in members:
            archive.writestr(info, changed.encode('utf-8') if info.filename == 'pyxel_resource.toml' else blob)
    resource.write_bytes(output.getvalue())
    print('Added Image 0 (144,64) 48x48; all other images/maps/audio preserved')


if __name__ == '__main__':
    if '--write' in sys.argv:
        add()
    else:
        print('Use --write once; startup/build never generates or replaces the sprite.')
