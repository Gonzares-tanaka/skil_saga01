"""Compare this phase against its backup; never read or write player saves."""
import hashlib
import json
from pathlib import Path
import sys
import wave
import array
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_battle_extra_assets import snapshot
import pyxel
from rpg.content import ROOT
from rpg.battle_presentation import BATTLE_FLOOR_STRIPS
from rpg.sound import init_sound,SOUND_ENEMY_DEFEAT,ATTACK_SOUND


def main():
    backup=ROOT/'verification/backups/battle_hit_strip'
    baseline=json.loads((backup/'baseline.json').read_text(encoding='utf-8'))
    allowed={'rpg/app.py','rpg/battle_presentation.py','game.pyxres','assets/battle_music.pyxres'}
    protected=[]
    for name,digest in baseline.items():
        if name in allowed:continue
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        protected.append(name)
    pyxel.init(160,120,headless=True)
    before=snapshot(backup/'game.pyxres')
    after=snapshot(ROOT/'game.pyxres')
    assert before[1:]==after[1:]
    assert before[0][:2]==after[0][:2]
    changed=0
    for n,(old,new) in enumerate(zip(before[0][2],after[0][2])):
        if old==new:continue
        x,y=n%256,n//256
        assert x<96 and 208<=y<256,(x,y)
        assert old==0 and new in range(4),(x,y,old,new)
        changed+=1
    assert changed
    music_before=snapshot(backup/'assets/battle_music.pyxres')
    music_after=snapshot(ROOT/'assets/battle_music.pyxres')
    assert music_before[:2]==music_after[:2]
    assert music_before[3]==music_after[3]
    for i,(old,new) in enumerate(zip(music_before[2],music_after[2])):
        if i==SOUND_ENEMY_DEFEAT:assert old!=new
        else:assert old==new,('Unexpected sound change',i)
    expected=music_after[2][SOUND_ENEMY_DEFEAT]
    init_sound()
    s=pyxel.sounds[SOUND_ENEMY_DEFEAT]
    assert expected==(list(s.notes),list(s.tones),list(s.volumes),list(s.effects),s.speed)
    previews={}
    for label,index in (('enemy_defeat',SOUND_ENEMY_DEFEAT),('normal_hit',ATTACK_SOUND)):
        sound=pyxel.sounds[index]
        path=ROOT/'verification/backups/battle_hit_strip'/f'{label}.wav'
        sound.save(str(path),sound.total_sec())
        with wave.open(str(path),'rb') as wav:
            assert wav.getsampwidth()==2
            samples=array.array('h',wav.readframes(wav.getnframes()))
            assert any(samples)
            previews[label]=dict(seconds=sound.total_sec(),peak=max(abs(n) for n in samples),
                                 notes=list(sound.notes),tones=list(sound.tones),volumes=list(sound.volumes))
    result=dict(protected_files=protected,protected_files_unchanged=True,maps_unchanged=True,
                old_images_effects_ko_status_unchanged=True,new_strip_pixels=changed,
                empty_regions_only=True,palette_unchanged=True,strips=BATTLE_FLOOR_STRIPS,
                only_sound31_changed=True,bgm_unchanged=True,startup_preserves_sound=True,
                previews=previews)
    (ROOT/'verification/battle_hit_strip_preservation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS: maps/rules/SAVE/palette/old sprites preserved; only empty strips and Sound 31 changed')


if __name__=='__main__':main()
