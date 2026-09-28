"""One-time editable placeholder art for Image Bank 2 in game.pyxres.

Run only when intentionally replacing the hub placeholders; normal startup and
Web builds never regenerate them, so Pyxel Editor changes remain intact.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel

from rpg.content import ROOT
from rpg.hub import HUB_IMAGE_BANK, HUB_ICONS, HUB_PICTURES


class Canvas:
    def __init__(self, image, x, y, scale=1):
        self.image, self.x, self.y, self.scale = image, x, y, scale

    def rect(self, x, y, w, h, color):
        s = self.scale
        self.image.rect(self.x + x * s, self.y + y * s, w * s, h * s, color)

    def border(self, x, y, w, h, color):
        s = self.scale
        self.image.rectb(self.x + x * s, self.y + y * s, w * s, h * s, color)

    def line(self, x1, y1, x2, y2, color):
        s = self.scale
        self.image.line(self.x + x1 * s, self.y + y1 * s,
                        self.x + x2 * s, self.y + y2 * s, color)

    def tri(self, x1, y1, x2, y2, x3, y3, color):
        s = self.scale
        self.image.tri(self.x + x1 * s, self.y + y1 * s,
                       self.x + x2 * s, self.y + y2 * s,
                       self.x + x3 * s, self.y + y3 * s, color)


def draw_icon(index, c):
    if index == 0:  # Guild shield
        c.rect(3, 2, 10, 9, 2)
        c.line(3, 10, 8, 15, 2)
        c.line(12, 10, 8, 15, 2)
        c.border(5, 4, 6, 6, 3)
        c.rect(7, 5, 2, 7, 1)
        c.rect(5, 7, 6, 2, 1)
    elif index == 1:  # Open book
        c.rect(1, 3, 6, 10, 2)
        c.rect(9, 3, 6, 10, 3)
        c.line(8, 2, 8, 14, 1)
        c.line(2, 5, 6, 5, 3)
        c.line(10, 6, 14, 6, 1)
        c.line(1, 13, 7, 14, 3)
        c.line(9, 14, 15, 13, 2)
    elif index == 2:  # Mug
        c.rect(2, 4, 10, 9, 2)
        c.rect(3, 5, 8, 3, 3)
        c.border(11, 6, 4, 6, 3)
        c.rect(1, 13, 12, 2, 1)
        c.rect(4, 2, 2, 2, 3)
        c.rect(8, 1, 2, 3, 3)
    elif index == 3:  # Supply sack
        c.rect(5, 2, 6, 3, 3)
        c.rect(3, 5, 10, 9, 2)
        c.rect(5, 7, 6, 5, 3)
        c.line(5, 5, 11, 5, 1)
        c.rect(7, 8, 2, 4, 1)
        c.rect(5, 9, 6, 2, 1)
    else:  # Dungeon gate
        c.rect(1, 11, 14, 4, 1)
        c.rect(2, 7, 12, 5, 2)
        c.rect(4, 4, 8, 8, 2)
        c.rect(6, 7, 4, 8, 0)
        c.line(4, 4, 8, 1, 3)
        c.line(8, 1, 12, 4, 3)


def draw_picture(index, c):
    # Five buildings use only the established 0-3 Game Boy colors.
    c.rect(0, 27, 32, 5, 1)
    if index == 4:  # Cave entrance
        c.tri(0, 27, 14, 3, 21, 27, 2)
        c.tri(11, 27, 24, 5, 31, 27, 1)
        c.rect(11, 17, 12, 12, 0)
        c.rect(13, 14, 8, 15, 0)
        c.line(3, 25, 14, 6, 3)
        c.line(17, 8, 24, 22, 2)
        c.rect(14, 25, 6, 2, 3)
        return
    if index == 1:  # Training hall with open book sign
        c.rect(3, 12, 26, 17, 2)
        c.tri(1, 13, 16, 3, 31, 13, 1)
        c.line(3, 12, 16, 4, 3)
        c.line(16, 4, 29, 12, 3)
        c.rect(6, 16, 7, 6, 3)
        c.rect(19, 16, 7, 6, 3)
        c.rect(13, 20, 6, 9, 1)
        c.line(16, 7, 16, 15, 3)
        c.rect(11, 9, 10, 2, 3)
    elif index == 2:  # Pub and hanging mug
        c.rect(3, 12, 26, 17, 2)
        c.rect(1, 9, 30, 5, 1)
        c.line(2, 9, 10, 4, 3)
        c.line(10, 4, 28, 9, 3)
        c.rect(11, 20, 10, 9, 1)
        c.rect(5, 16, 4, 6, 3)
        c.rect(23, 16, 4, 6, 3)
        c.rect(13, 11, 6, 5, 3)
        c.rect(18, 12, 2, 3, 1)
    elif index == 3:  # Shop awning and supplies
        c.rect(2, 12, 28, 17, 2)
        c.rect(1, 7, 30, 6, 3)
        for x in (4, 11, 18, 25):
            c.rect(x, 9, 3, 4, 1)
        c.rect(7, 17, 18, 3, 1)
        c.rect(9, 20, 5, 6, 3)
        c.rect(18, 19, 5, 7, 3)
        c.rect(14, 24, 4, 5, 1)
    else:  # Guild with shield over doorway
        c.rect(3, 12, 26, 17, 2)
        c.tri(1, 13, 16, 3, 31, 13, 1)
        c.line(3, 12, 16, 4, 3)
        c.line(16, 4, 29, 12, 3)
        c.rect(6, 17, 6, 7, 3)
        c.rect(20, 17, 6, 7, 3)
        c.rect(13, 20, 6, 9, 1)
        c.rect(13, 10, 6, 7, 3)
        c.line(13, 16, 16, 19, 3)
        c.line(19, 16, 16, 19, 3)
    c.line(1, 29, 30, 29, 3)


def main():
    pyxel.init(160, 120, headless=True)
    resource = ROOT / "game.pyxres"
    pyxel.load(str(resource))
    image = pyxel.images[HUB_IMAGE_BANK]
    image.cls(0)  # Explicit regeneration of Bank 2 only; keep other banks and Tilemaps intact.
    for index, (icon, picture) in enumerate(zip(HUB_ICONS, HUB_PICTURES)):
        draw_icon(index, Canvas(image, *icon))
        draw_picture(index, Canvas(image, *picture, scale=2))
    pyxel.save(str(resource))
    print("Image Bank 2 hub placeholders saved to game.pyxres")


if __name__ == "__main__":
    main()
