"""Original pixel drawings, generated with Pyxel; editable in Pyxel Editor."""
from .content import ROOT

PALETTE = [0x152B24, 0x456849, 0x8EAD62, 0xDBE8A6]
RESOURCE = ROOT / "assets" / "sprites.pyxres"


def draw_defaults(pyxel):
    image = pyxel.images[0]
    image.cls(0)
    for i in range(4):
        x = i * 16
        image.circ(x + 7, 5, 4, 1)
        image.rect(x + 5, 4, 6, 5, 3)
        image.pset(x + 6, 5, 0)
        image.pset(x + 9, 5, 0)
        image.rect(x + 4, 9, 8, 5, 2)
        image.line(x + 4, 14, x + 3, 15, 1)
        image.line(x + 10, 14, x + 11, 15, 1)
        if i in (0, 3):
            image.rect(x + 4, 1, 8, 3, 2)
            image.line(x + 13, 4, x + 13, 13, 3)
            image.line(x + 11, 11, x + 15, 11, 1)
        elif i == 1:
            image.line(x + 3, 2, x + 11, 2, 3)
            image.line(x + 1, 3, x + 4, 4, 2)
            image.line(x + 13, 9, x + 14, 13, 3)
        else:
            image.tri(x + 2, 4, x + 8, 0, x + 12, 4, 2)
            image.line(x + 14, 5, x + 14, 15, 1)
            image.circ(x + 14, 5, 1, 3)
    # SLIME
    image.elli(1, 23, 14, 8, 2)
    image.circ(8, 24, 4, 2)
    image.pset(5, 25, 0)
    image.pset(10, 25, 0)
    image.line(6, 28, 9, 28, 1)
    image.line(3, 24, 5, 22, 3)
    # BAT
    image.tri(16, 20, 23, 24, 19, 29, 1)
    image.tri(31, 20, 24, 24, 28, 29, 1)
    image.elli(21, 21, 7, 9, 2)
    image.tri(21, 23, 21, 18, 24, 22, 2)
    image.tri(25, 22, 27, 18, 27, 23, 2)
    image.pset(23, 24, 3)
    image.pset(25, 24, 3)
    # GOBLIN
    image.tri(32, 21, 38, 22, 36, 25, 2)
    image.tri(47, 21, 41, 22, 43, 25, 2)
    image.rect(36, 20, 8, 7, 2)
    image.pset(38, 23, 0)
    image.pset(41, 23, 0)
    image.rect(36, 27, 8, 4, 1)
    image.line(39, 26, 42, 26, 3)
    # WISP
    image.tri(51, 27, 54, 17, 60, 28, 1)
    image.circ(56, 25, 6, 2)
    image.circ(56, 25, 3, 3)
    image.pset(55, 24, 0)
    image.pset(58, 24, 0)
    # GOLEM
    image.rect(68, 18, 8, 6, 2)
    image.rect(67, 25, 10, 6, 1)
    image.rect(64, 24, 3, 6, 2)
    image.rect(77, 24, 3, 6, 2)
    image.line(69, 20, 74, 20, 3)
    image.pset(70, 22, 0)
    image.pset(73, 22, 0)
    image.line(69, 26, 72, 29, 2)


def load_art(pyxel):
    pyxel.colors[:4] = PALETTE
    resource = ROOT / "game.pyxres"
    if not resource.exists():
        resource = RESOURCE
    if resource.exists():
        pyxel.load(str(resource), exclude_sounds=True, exclude_musics=True)
    else:
        draw_defaults(pyxel)
