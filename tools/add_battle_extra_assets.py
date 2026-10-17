"""One-time editor assets. Refuses to overwrite occupied art or sounds."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.battle_presentation import BATTLE_BACKGROUNDS
from rpg.sound import SOUND_RUN_SUCCESS, SOUND_ENEMY_DEFEAT


def main():
    pyxel.init(160,120,headless=True)
    pyxel.load(str(ROOT/'game.pyxres'))
    image = pyxel.images[2]
    for data in BATTLE_BACKGROUNDS.values():
        for bank,u,v,w,h in data.values():
            assert all(image.pget(x,y)==0 for y in range(v,v+h) for x in range(u,u+w)), 'Edited background; refusing overwrite'
    for area,data in BATTLE_BACKGROUNDS.items():
        _,u,v,_,_ = data['wall']
        if area == 1:
            # Small, irregular masonry and restrained moss.
            for row in range(4):
                y=v+row*8
                image.line(u,y,u+31,y,1)
                for x in range(u+(8 if row%2 else 0),u+32,16):
                    image.line(x,y,x,y+7,1)
            image.line(u+18,v+12,u+22,v+12,1)
            image.pset(u+20,v+13,2)
        elif area == 2:
            # Large blocks, thin pillars and a low water channel.
            image.line(u,v+15,u+31,v+15,1)
            image.line(u+15,v,u+15,v+30,1)
            image.rect(u+2,v+3,3,24,1)
            image.rect(u+1,v+2,5,2,1)
            image.line(u+7,v+29,u+31,v+29,1)
            image.line(u+13,v+30,u+23,v+30,2)
        else:
            # Deep chambers: broad stones, fissures and a quiet glyph.
            image.line(u,v+23,u+31,v+23,1)
            image.line(u+25,v,u+25,v+22,1)
            image.line(u+5,v,u+8,v+5,1)
            image.line(u+8,v+5,u+6,v+11,1)
            image.line(u+6,v+11,u+10,v+17,1)
            image.rectb(u+16,v+7,5,8,1)
            image.line(u+18,v+9,u+18,v+12,1)
        _,u,v,_,_ = data['floor']
        image.rect(u,v,32,16,area-1)
        if area == 1:
            image.line(u,v+7,u+31,v+7,1)
            image.line(u+11,v,u+11,v+6,1)
            image.line(u+23,v+8,u+23,v+15,1)
        elif area == 2:
            image.line(u,v,u+31,v,2)
            image.line(u,v+5,u+31,v+5,0)
            image.line(u,v+13,u+31,v+13,0)
            for x in (8,24):
                image.line(u+x,v+6,u+x,v+12,0)
        else:
            image.line(u+4,v+2,u+10,v+5,1)
            image.line(u+10,v+5,u+8,v+9,1)
            image.line(u+8,v+9,u+16,v+12,1)
            image.line(u+16,v+12,u+18,v+15,1)
    pyxel.save(str(ROOT/'game.pyxres'))
    pyxel.load(str(ROOT/'assets/battle_music.pyxres'))
    for index in (SOUND_RUN_SUCCESS,SOUND_ENEMY_DEFEAT):
        assert not list(pyxel.sounds[index].notes), 'Edited sound; refusing overwrite'
    pyxel.sounds[SOUND_RUN_SUCCESS].set('c1rc1rc1r','n','505040','f',4)
    pyxel.sounds[SOUND_ENEMY_DEFEAT].set('g1e1c1g0c0','n','65421','f',5)
    pyxel.save(str(ROOT/'assets/battle_music.pyxres'))
    print('Created 3 wall/floor pairs in game Image 2 and editable Sound 30/31 in battle_music')


if __name__ == '__main__':
    main()
