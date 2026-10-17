"""One-time placeholder art in empty game.pyxres regions; never runs at boot."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.battle_presentation import ASSET_BANK, EFFECT_SPRITES, STATUS_SPRITES


def main():
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(ROOT / 'game.pyxres'))
    image = pyxel.images[ASSET_BANK]
    areas = [(240, 0, 16, 16), (192, 0, 32, 8), (192, 32, 48, 192)]
    assert all(image.pget(x, y) == 0 for u,v,w,h in areas
               for y in range(v,v+h) for x in range(u,u+w)), 'Reserved area contains edited art; refusing overwrite'
    # Tombstone, with a pale outline and a dark interior cross.
    image.rect(243, 5, 10, 9, 3)
    image.circ(248, 5, 4, 3)
    image.rect(244, 6, 8, 7, 1)
    image.line(248, 6, 248, 11, 3)
    image.line(246, 8, 250, 8, 3)
    image.rect(242, 14, 13, 2, 2)
    # Four future-status glyphs. They only become visible when UI data is supplied.
    u,v = STATUS_SPRITES['poison']
    image.circ(u+3,v+3,3,3); image.pset(u+2,v+2,1); image.pset(u+4,v+2,1)
    image.line(u+1,v+7,u+6,v+5,2); image.line(u+1,v+5,u+6,v+7,2)
    u,v = STATUS_SPRITES['paralyze']
    image.line(u+5,v,u+2,v+3,3); image.line(u+2,v+3,u+5,v+3,3); image.line(u+5,v+3,u+1,v+7,3)
    u,v = STATUS_SPRITES['sleep']
    image.line(u+1,v+1,u+6,v+1,3); image.line(u+6,v+1,u+1,v+6,3); image.line(u+1,v+6,u+6,v+6,3)
    u,v = STATUS_SPRITES['curse']
    image.circb(u+3,v+3,3,3); image.line(u,v,u+6,v+6,2); image.line(u+6,v,u,v+6,2)
    for key,(u,v) in EFFECT_SPRITES.items():
        for frame in range(3):
            x,y = u+frame*16,v
            radius = 3+frame*2
            if key == 'slash':
                image.line(x+12,y+2,x+3,y+12,3); image.line(x+11,y+3+frame,x+4,y+12,2)
            elif key == 'blunt':
                image.circb(x+8,y+8,radius,3)
                for dx,dy in ((1,0),(0,1),(-1,0),(0,-1)):
                    image.line(x+8+dx*3,y+8+dy*3,x+8+dx*radius,y+8+dy*radius,2)
            elif key == 'pierce':
                image.line(x+1,y+10,x+13,y+5,3); image.tri(x+13,y+5,x+9,y+5,x+12,y+8,2)
            elif key == 'fire':
                image.tri(x+2,y+14,x+7+frame,y+1,x+14,y+14,2)
                image.tri(x+5,y+13,x+8,y+5,x+11,y+13,3)
            elif key == 'ice':
                image.line(x+8,y+1,x+8,y+14,3); image.line(x+2,y+4,x+14,y+11,3)
                image.line(x+2,y+11,x+14,y+4,3); image.circb(x+8,y+8,radius,2)
            elif key == 'lightning':
                image.line(x+10,y+1,x+4,y+8,3); image.line(x+4,y+8,x+11,y+7,3)
                image.line(x+11,y+7,x+5,y+15,3); image.line(x+11,y+1,x+5,y+8,2)
            elif key in ('magic','legend'):
                image.circb(x+8,y+8,radius,3)
                image.line(x+8,y+1,x+8,y+14,2); image.line(x+1,y+8,x+14,y+8,2)
                if key == 'legend':
                    image.line(x+2,y+2,x+13,y+13,3); image.line(x+13,y+2,x+2,y+13,3)
            elif key == 'dark':
                image.circ(x+8,y+8,radius,1); image.circb(x+8,y+8,radius,3)
                image.line(x+4,y+8,x+12,y+8,2)
            elif key == 'heal':
                image.rect(x+7,y+3,3,10,3); image.rect(x+3,y+7,10,3,3)
                image.circb(x+8,y+8,radius,2)
            else:
                up = key == 'buff'
                image.line(x+8,y+3,x+8,y+13,3)
                image.line(x+8,y+(3 if up else 13),x+4,y+(7 if up else 9),3)
                image.line(x+8,y+(3 if up else 13),x+12,y+(7 if up else 9),3)
                image.circb(x+8,y+8,radius,2)
    pyxel.save(str(ROOT / 'game.pyxres'))
    print('Added editable KO, 12 x 3 effect frames and four status glyphs in Image Bank 2.')


if __name__ == '__main__':
    main()
