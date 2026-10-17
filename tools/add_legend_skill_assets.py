"""One-time import into empty, unreferenced Editor cells; refuse all overwrites."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from import_pixel_svg import import_sheet
from rpg.legend_skill_presentation import LEGEND_SPRITES


def main():
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(ROOT / 'game.pyxres'))
    image = pyxel.images[0]
    assert all(image.pget(x, y) == 0 for y in range(128, 256) for x in range(192)), 'Occupied cells: refusing overwrite'
    for tm in pyxel.tilemaps:
        if tm.imgsrc == 0:
            assert not any(0 <= u < 24 and 16 <= v < 32
                           for y in range(256) for x in range(256) for u, v in [tm.pget(x, y)]), 'Map references these cells'
    image.blt(0, 128, import_sheet(ROOT / 'tools/art/legend_effects.svg', 192, 128), 0, 0, 192, 128)
    pyxel.save(str(ROOT / 'game.pyxres'))
    print('Imported eight dedicated LEGEND areas:', LEGEND_SPRITES, '; Image 0, 32x32, 3 frames')


if __name__ == '__main__': main()
