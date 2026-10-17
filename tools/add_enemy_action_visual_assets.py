"""One-time Pyxel drawing in verified empty bank 2 cells. Not run at startup."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from rpg.battle_presentation import ENEMY_EFFECT_SPRITES, ASSET_BANK


def shield(image, x, y, color):
    image.line(x + 3, y + 3, x + 12, y + 3, color)
    image.line(x + 3, y + 3, x + 3, y + 9, color)
    image.line(x + 12, y + 3, x + 12, y + 9, color)
    image.line(x + 3, y + 9, x + 8, y + 13, color)
    image.line(x + 12, y + 9, x + 8, y + 13, color)


def main():
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(ROOT / 'game.pyxres'))
    image = pyxel.images[ASSET_BANK]
    assert all(image.pget(x, y) == 0 for u, v in ENEMY_EFFECT_SPRITES.values()
               for y in range(v, v + 16) for x in range(u, u + 48)), 'Edited/occupied art: refusing overwrite'
    for key, (u, v) in ENEMY_EFFECT_SPRITES.items():
        for frame in range(3):
            x, y = u + frame * 16, v
            if key == 'heavy_hit':
                radius = 4 + frame
                image.circb(x + 8, y + 8, radius, 3)
                image.line(x + 8, y + 1, x + 8, y + 15, 3)
                image.line(x + 1, y + 8, x + 15, y + 8, 3)
                image.line(x + 3, y + 3, x + 13, y + 13, 2)
                image.line(x + 13, y + 3, x + 3, y + 13, 2)
                image.rect(x + 6, y + 6, 5, 5, 3 if frame == 1 else 2)
            elif key == 'guard':
                shield(image, x, y, 3)
                image.line(x + 8, y + 5, x + 8, y + 11, 2)
                image.line(x + 5, y + 7, x + 10, y + 7, 2)
                image.line(x + 1, y + 4 + frame, x + 1, y + 10, 2)
                image.line(x + 14, y + 4 + frame, x + 14, y + 10, 2)
            elif key == 'armor_down':
                shield(image, x - 1, y - 1, 2)
                image.line(x + 7, y + 3, x + 5, y + 6, 3)
                image.line(x + 5, y + 6, x + 8, y + 7, 3)
                image.line(x + 8, y + 7, x + 6, y + 10, 3)
                image.line(x + 13, y + 8 + frame, x + 13, y + 13 + frame, 3)
                image.line(x + 13, y + 13 + frame, x + 11, y + 11 + frame, 3)
                image.line(x + 13, y + 13 + frame, x + 15, y + 11 + frame, 3)
            elif key == 'slow':
                # Hourglass plus progressively fewer speed strokes.
                image.line(x + 5, y + 2, x + 13, y + 2, 3)
                image.line(x + 5, y + 14, x + 13, y + 14, 3)
                image.line(x + 6, y + 3, x + 12, y + 13, 2)
                image.line(x + 12, y + 3, x + 6, y + 13, 2)
                image.line(x + 7, y + 11 - frame, x + 11, y + 11 - frame, 3)
                for stroke in range(3 - frame):
                    image.line(x, y + 4 + stroke * 3, x + 3, y + 4 + stroke * 3, 2)
    pyxel.save(str(ROOT / 'game.pyxres'))
    print('Added heavy_hit/guard/armor_down/slow: Image 2, x=144/160/176, y=96/112/128/144')


if __name__ == '__main__':
    main()
