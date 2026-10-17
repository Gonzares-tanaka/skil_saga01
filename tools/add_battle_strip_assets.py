"""One-time strip artwork and adjusted defeat sound. Never run at startup."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.battle_presentation import BATTLE_FLOOR_STRIPS
from rpg.sound import SOUND_ENEMY_DEFEAT


def main():
    pyxel.init(160,120,headless=True)
    pyxel.load(str(ROOT/'game.pyxres'))
    image=pyxel.images[2]
    for bank,u,v,w,h in BATTLE_FLOOR_STRIPS.values():
        assert all(image.pget(x,y)==0 for y in range(v,v+h) for x in range(u,u+w)), 'Edited strip; refusing overwrite'
    for area,(_,u,v,w,h) in BATTLE_FLOOR_STRIPS.items():
        if area==1:
            image.rect(u,v+7,w,9,1)
            image.line(u,v+12,u+w-1,v+12,0)
            for x in (16,45,76):image.line(u+x,v+8,u+x,v+11,0)
            image.rect(u+8,v+2,5,8,1)
            image.rect(u+6,v+1,9,2,1)
            image.rect(u+57,v+6,8,3,1)
            image.pset(u+83,v+8,2)
        elif area==2:
            image.rect(u,v+8,w,8,1)
            image.line(u,v+10,u+w-1,v+10,0)
            image.line(u,v+11,u+w-1,v+11,2)
            for x in (13,32,61,86):image.line(u+x,v+12,u+x,v+15,0)
            image.rect(u+24,v+1,4,8,1)
            image.rect(u+22,v,8,2,1)
            image.rect(u+23,v+7,6,2,1)
        else:
            image.rect(u,v+8,w,8,1)
            image.line(u+7,v+9,u+16,v+12,0)
            image.line(u+16,v+12,u+12,v+15,0)
            image.line(u+58,v+8,u+65,v+11,0)
            image.line(u+65,v+11,u+71,v+15,0)
            image.rect(u+78,v+5,5,5,1)
            image.line(u+78,v+4,u+81,v+2,1)
            image.rectb(u+39,v+3,5,4,1)
            image.pset(u+41,v+4,2)
    pyxel.save(str(ROOT/'game.pyxres'))
    pyxel.load(str(ROOT/'assets/battle_music.pyxres'))
    pyxel.sounds[SOUND_ENEMY_DEFEAT].set('g1e1c1g0e0c0c0','n','7776531','ssfffff',5)
    assert 0.2 <= pyxel.sounds[SOUND_ENEMY_DEFEAT].total_sec() <= 0.4
    pyxel.save(str(ROOT/'assets/battle_music.pyxres'))
    print('3 editable 96x16 strips added; defeat Sound 31 adjusted to',pyxel.sounds[SOUND_ENEMY_DEFEAT].total_sec(),'seconds')


if __name__=='__main__':main()
