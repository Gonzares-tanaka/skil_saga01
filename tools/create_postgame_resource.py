"""Create only the new editable credits music/dragon art bank, once."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    import pyxel
    target=ROOT/'assets/postgame.pyxres'
    if target.exists():raise FileExistsError('Editor edits are protected: '+str(target))
    pyxel.init(160,120,headless=True)
    image=pyxel.images[0];image.cls(0)
    # Horned dragon head marker, separate from the three QUEST glyphs.
    image.tri(0,0,3,3,1,5,2);image.tri(7,0,4,3,6,5,2)
    image.rect(2,2,4,5,2);image.pset(2,3,3);image.pset(5,3,3);image.rect(3,6,2,2,3)
    # 32x32 boss at (16,0): original Pyxel primitives, same four GB colors.
    u=16
    image.tri(u,4,u+12,12,u+3,25,1);image.tri(u+31,4,u+19,12,u+28,25,1)
    image.tri(u+1,6,u+11,13,u+4,19,2);image.tri(u+30,6,u+20,13,u+27,19,2)
    image.elli(u+9,12,15,18,2);image.elli(u+13,17,7,12,1)
    image.rect(u+10,5,14,11,2);image.tri(u+10,1,u+15,8,u+9,9,3)
    image.tri(u+23,1,u+19,8,u+25,9,3)
    image.rect(u+11,9,4,2,3);image.rect(u+20,9,3,2,3)
    image.pset(u+13,9,0);image.pset(u+21,9,0)
    image.rect(u+13,13,8,2,0);image.pset(u+14,13,3);image.pset(u+20,13,3)
    image.line(u+9,27,u+5,31,3);image.line(u+23,27,u+27,31,3)
    image.line(u+12,20,u+3,23,2);image.line(u+22,20,u+29,23,2)
    # 64 bars: ceremonial opening, two lyrical themes, bridge and reprise.
    fanfare=[['c3','e3','g3','c4','r','g3','c4','r'],['f3','a3','c4','f4','r','e4','d4','c4'],
             ['g3','b3','d4','g4','r','f4','e4','d4'],['c4','r','g3','r','e3','g3','c4','r']]
    theme=[['e3','g3','c4','r','b3','g3','e3','g3'],['a3','r','g3','e3','f3','a3','c4','r'],
           ['b3','d4','g4','r','f4','d4','b3','g3'],['c4','r','e4','d4','c4','b3','a3','g3']]
    second=[['c4','e4','g4','r','e4','d4','c4','g3'],['a3','c4','f4','r','e4','c4','a3','f3'],
            ['b3','d4','g4','a4','g4','f4','e4','d4'],['e4','r','d4','c4','b3','g3','c4','r']]
    bridge=[['a3','c4','e4','g4','e4','c4','a3','e3'],['f3','a3','c4','e4','c4','a3','f3','c3'],
            ['g3','b3','d4','f4','d4','b3','g3','d3'],['g3','r','a3','b3','c4','d4','e4','g4']]
    bars=fanfare+theme*4+second*4+bridge*3+theme*4
    chords=[('c2','e2','g2'),('f2','a2','c3'),('g2','b2','d3'),('c2','e2','g2')]
    slots=[n for n in range(50) if n not in (30,31)]
    sequences=[[],[],[]]
    for group in range(16):
        melody=sum(bars[group*4:group*4+4],[])
        if group==15:melody[-8:]=['e4','r','d4','c4','g3','b3','c4','r']
        arpeggio=[];bass=[]
        for offset in range(4):
            chord=chords[offset]
            arpeggio += [chord[n%3] for n in (0,1,2,1,0,1,2,1)]
            bass += [chord[0],'r','r','r',chord[2],'r','r','r']
        for voice,notes in enumerate((melody,arpeggio,bass)):
            if group==15:notes=notes+['r']*8 # Natural cadence + silence before END.
            slot=slots[group*3+voice]
            pyxel.sounds[slot].set(' '.join(notes),('p','t','t')[voice],('5','2','4')[voice],'n',12)
            sequences[voice].append(slot)
    pyxel.musics[0].set([],sequences[0],sequences[1],sequences[2])
    pyxel.save(str(target))
    print('Created',target,'64 bars;',sum(pyxel.sounds[n].total_sec() for n in sequences[0]),'seconds; channels 1/2/3')


if __name__=='__main__':main()
