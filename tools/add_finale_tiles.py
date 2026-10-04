"""Explicit one-time addition of small Editor glyphs, preserving existing artwork."""
import io
from pathlib import Path
import re
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def add(path):
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('pyxel_resource.toml')
        original = archive.read(info).decode('utf8')
    rows = tomllib.loads(original)['images'][1]['data']
    for index in range(21, 29):
        # Already drawn by the human? Keep it, including on a second invocation.
        if any(y < len(rows) and x < len(rows[y]) and rows[y][x]
               for y in range(8) for x in range(index * 8, (index + 1) * 8)):
            continue
        if index <= 26:
            pattern = ['00000000', '00111100', '01222210', '01233210',
                       '01222210', '01233210', '01111110', '00000000']
            # Tiny inscription variations identify separate messages in Editor.
            pattern[4] = '012' + format(index - 20, '03b').replace('0','2').replace('1','3') + '10'
        elif index == 27:
            pattern = ['00111100', '01233210', '01222210', '00133100',
                       '01133110', '01233210', '01222210', '01111110']
        else:
            pattern = ['00033000', '00033000', '00033000', '00033000',
                       '00033000', '00000000', '00033000', '00000000']
        for y, line in enumerate(pattern):
            while len(rows) <= y:
                rows.append([])
            rows[y].extend([0] * max(0, (index + 1) * 8 - len(rows[y])))
            rows[y][index * 8:(index + 1) * 8] = list(map(int, line))
    parts = original.split('[[images]]')
    parts[2], count = re.subn(r'(?m)^data = .*', 'data = '+repr(rows), parts[2], count=1)
    assert count == 1
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr(info, '[[images]]'.join(parts).encode('utf8'))
    temp = path.with_suffix('.finale.tmp')
    temp.write_bytes(output.getvalue())
    temp.replace(path)
    print('Added/preserved glyphs 21..28 in', path.name)


if __name__ == '__main__':
    if '--write' not in sys.argv:
        print('Use --write to add glyphs to game.pyxres and area3.pyxres. Never runs at startup.')
    else:
        for filename in ('game.pyxres', 'area3.pyxres'):
            add(ROOT/filename)
