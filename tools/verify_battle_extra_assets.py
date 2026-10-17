"""Verify extra assets changed only reserved backgrounds and Sound 30/31."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.battle_presentation import BATTLE_BACKGROUNDS
from rpg.sound import SOUND_RUN_SUCCESS,SOUND_ENEMY_DEFEAT,init_sound


def snapshot(path):
    pyxel.load(str(path))
    return (
        [tuple(i.pget(x,y) for y in range(256) for x in range(256)) for i in pyxel.images],
        [tuple(t.pget(x,y) for y in range(256) for x in range(256)) for t in pyxel.tilemaps],
        [(list(s.notes),list(s.tones),list(s.volumes),list(s.effects),s.speed) for s in pyxel.sounds],
        [[list(seq) for seq in m.seqs] for m in pyxel.musics])


def main():
    backup=ROOT/'verification/backups/battle_presentation_extra'
    baseline=json.loads((backup/'baseline.json').read_text(encoding='utf-8'))
    allowed={'rpg/battle_presentation.py','rpg/app.py','rpg/dungeon_app.py','rpg/sound.py',
             'game.pyxres','assets/battle_music.pyxres'}
    protected=[]
    for name,digest in baseline.items():
        if name in allowed:continue
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        protected.append(name)
    pyxel.init(160,120,headless=True)
    before=snapshot(backup/'game.pyxres')
    after=snapshot(ROOT/'game.pyxres')
    assert before[1:]==after[1:], 'Game maps/sound/music changed'
    assert before[0][:2]==after[0][:2], 'Existing sprite/map chips changed'
    changed=0
    for n,(old,new) in enumerate(zip(before[0][2],after[0][2])):
        if old==new:continue
        x,y=n%256,n//256
        assert (160<=y<208 and any(u<=x<u+32 for u in (0,64,128))
                or x<96 and 208<=y<256),(x,y)
        assert old==0, 'Occupied pixel overwritten'
        assert new in range(4), 'New palette color used'
        changed+=1
    assert changed
    music_before=snapshot(backup/'assets/battle_music.pyxres')
    music_after=snapshot(ROOT/'assets/battle_music.pyxres')
    assert music_before[:2]==music_after[:2]
    assert music_before[3]==music_after[3], 'BGM sequence changed'
    for i,(old,new) in enumerate(zip(music_before[2],music_after[2])):
        if i in (SOUND_RUN_SUCCESS,SOUND_ENEMY_DEFEAT):
            assert not old[0] and new[0]
        else:
            assert old==new,('Existing sound changed',i)
    editable=[music_after[2][i] for i in (SOUND_RUN_SUCCESS,SOUND_ENEMY_DEFEAT)]
    init_sound()
    loaded=[(list(s.notes),list(s.tones),list(s.volumes),list(s.effects),s.speed)
            for s in (pyxel.sounds[SOUND_RUN_SUCCESS],pyxel.sounds[SOUND_ENEMY_DEFEAT])]
    assert loaded==editable, 'Startup overwrote edited sound data'
    result=dict(protected_files=protected,balance_save_quest_maps_unchanged=True,
                existing_images_music_sounds_unchanged=True,
                new_background_pixels=changed,only_empty_regions_used=True,
                editable_sounds_preserved_at_startup=True,backgrounds=BATTLE_BACKGROUNDS,
                sound_bank='assets/battle_music.pyxres',sounds=[SOUND_RUN_SUCCESS,SOUND_ENEMY_DEFEAT])
    (ROOT/'verification/battle_extra_preservation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: rules/SAVE/QUEST/maps and existing assets unchanged; only reserved BG and Sound 30/31 added')


if __name__=='__main__':main()
