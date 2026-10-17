"""One-time 8x8 confusion icon in an empty bank 2 cell, editable in Pyxel."""
from pathlib import Path
import pyxel

ROOT = Path(__file__).resolve().parents[1]


def main():
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(ROOT / 'game.pyxres'))
    image = pyxel.images[2]
    x, y = 224, 0
    assert all(image.pget(u, v) == 0 for v in range(8) for u in range(x, x + 8)), 'Edited art: refusing overwrite'
    image.line(x + 2, y + 1, x + 5, y + 1, 3)
    image.line(x + 1, y + 2, x + 1, y + 3, 2)
    image.line(x + 6, y + 2, x + 6, y + 3, 3)
    image.line(x + 5, y + 4, x + 3, y + 5, 3)
    image.pset(x + 3, y + 7, 3)
    pyxel.save(str(ROOT / 'game.pyxres'))
    print('Added confusion icon: game.pyxres Image 2 (224,0), 8x8')


if __name__ == '__main__':
    main()
