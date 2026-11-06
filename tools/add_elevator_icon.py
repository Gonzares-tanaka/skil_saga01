"""One-time addition to empty Image 2 (80,0); keep every other block bytewise."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audio_pass02_resource import read_resource, blocks


def main():
    import pyxel
    pyxel.init(160, 120, headless=True)
    path = ROOT / 'game.pyxres'
    scene = read_resource(path)
    image = deepcopy(scene['images'][2])
    assert all(v == 0 for row in image['data'][:16] for v in row[80:96]), 'Occupied: refusing overwrite'
    # No Tilemap in any area may reference the proposed icon cells.
    for resource in ('game.pyxres', 'area2.pyxres', 'area3.pyxres'):
        for tilemap in read_resource(ROOT/resource)['tilemaps']:
            if tilemap['imgsrc'] == 2:
                assert not any(10 <= u < 12 and 0 <= v < 2
                               for row in tilemap['data'] for u, v in row)
    canvas = pyxel.Image(16, 16)
    canvas.cls(0)
    canvas.rect(1, 1, 14, 14, 1)
    canvas.rectb(1, 1, 14, 14, 3)
    canvas.rect(3, 5, 10, 9, 2)
    canvas.line(7, 5, 7, 13, 0)
    canvas.line(8, 5, 8, 13, 3)
    canvas.tri(4, 4, 6, 2, 8, 4, 3)
    canvas.tri(9, 2, 11, 4, 13, 2, 2)
    canvas.line(3, 14, 12, 14, 0)
    for y in range(16):
        image['data'][y].extend([0] * max(0, 96-len(image['data'][y])))
        for x in range(16):
            image['data'][y][80+x] = canvas.pget(x, y)
    with zipfile.ZipFile(path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    candidate = path.with_suffix('.elevator.tmp')
    try:
        with zipfile.ZipFile(candidate, 'w') as archive:
            for info, raw in entries:
                if info.filename == 'pyxel_resource.toml':
                    raw = b''.join((('[[images]]\n' + '\n'.join(
                        f'{key} = {json.dumps(value)}' for key, value in image.items()) + '\n\n').encode()
                        if kind == 'images' and index == 2 else block)
                        for kind, index, block in blocks(raw))
                archive.writestr(info, raw)
        expected = deepcopy(scene)
        expected['images'][2] = image
        assert read_resource(candidate) == expected
        candidate.replace(path)
    finally:
        candidate.unlink(missing_ok=True)
    print('Added 16x16 icon: Image Bank 2 (80,0), colors 0-3; other pixels/blocks untouched')


if __name__ == '__main__':
    main()
