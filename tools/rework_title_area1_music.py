"""Import only AUDIO PASS 02's two scores; all other resource bytes stay intact."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from tools.audio_pass02_resource import read_resource,replace_audio,assert_protected_resource,ALLOWED_SOUNDS


def sound_row(notes,tones,volumes,effects,speed):
    sound=pyxel.Sound(); sound.set(' '.join(notes),tones,volumes,effects,speed)
    return dict(notes=list(sound.notes),tones=list(sound.tones),volumes=list(sound.volumes),
                effects=list(sound.effects),speed=sound.speed)


def compile_score(score,*,expected_sounds=ALLOWED_SOUNDS):
    sounds={}; musics={}
    for song in score['songs']:
        title=song['id']=='bgm_title'; speed=song['speed']
        for slot,bars in zip(song['lead_slots'],song['lead_bars']):
            notes=[]; volumes=[]
            for bar in bars:
                steps=0
                for event in bar:
                    pitch,duration=event.split(':'); duration=int(duration); steps+=duration
                    notes.extend([pitch]*duration)
                    # Repeated pitches encode longer beats, with a gentle volume taper.
                    volumes.extend([5]+[4]*(duration-1))
                assert steps==8,'Each bar has eight eighth-note steps'
            assert len(notes)==32
            sounds[slot]=sound_row(notes,'p',''.join(map(str,volumes)),'n',speed)
        for slot,bars in zip(song['bass_slots'],song['bass_bars']):
            notes=[]
            for root,fifth in bars:
                pattern=song.get('bass_pattern')
                notes.extend([dict(root=root,fifth=fifth,r='r')[token] for token in pattern] if pattern else
                    [root,root,root,root,fifth,fifth,root,root] if title else [root,'r',fifth,'r',root,root,fifth,'r'])
            sounds[slot]=sound_row(notes,'t',song.get('bass_volumes','33223222' if title else '30303320'),'n',speed)
        for slot,bars in zip(song['backing_slots'],song['chord_bars']):
            notes=[]
            for root,third,fifth in bars:
                notes.extend([dict(root=root,third=third,fifth=fifth).get(token,token)
                    for token in song.get('backing_pattern',['c1','fifth','third','fifth','g1','fifth','root','fifth'])])
            # One channel alternates quiet percussion with chord tones, leaving
            # channel zero entirely available for the user's original SE.
            sounds[slot]=sound_row(notes,'ntttnttt',song.get('backing_volumes','21211121' if title else '21212121'),'fnnnfnnn',speed)
        form=song['harmony_form']
        musics[song['music']]=dict(seqs=[[],song['lead_slots'],
            [song['bass_slots'][i] for i in form],[song['backing_slots'][i] for i in form]])
    assert set(sounds)==expected_sounds
    return sounds,musics


def main():
    before=json.loads((ROOT/'tests/fixtures/audio_pass02_before.json').read_text(encoding='utf8'))
    score=json.loads((ROOT/'tools/art/audio_pass_02.json').read_text(encoding='utf8'))
    pyxel.init(160,120,headless=True)
    sounds,musics=compile_score(score)
    path=ROOT/'game.pyxres'; current=read_resource(path)
    assert_protected_resource(path,before)
    for kind,edits in (('sounds',sounds),('musics',musics)):
        for index,value in edits.items():
            assert current[kind][index] in (before['scene'][kind][index],value),f'User edited {kind} {index}; refusing overwrite'
    replace_audio(path,sounds,musics)
    assert_protected_resource(path,before)
    # Verify the actual Editor/runtime reader accepts this surgical edit.
    pyxel.load(str(path))
    for index,row in sounds.items():
        sound=pyxel.sounds[index]
        assert row==dict(notes=list(sound.notes),tones=list(sound.tones),volumes=list(sound.volumes),
                        effects=list(sound.effects),speed=sound.speed)
    for index,row in musics.items(): assert [list(seq) for seq in pyxel.musics[index].seqs]==row['seqs']
    print('Imported TITLE Music0 / AREA1 Music2, 16 private Sound patterns; all SE and other blocks byte-identical.')


if __name__=='__main__': main()
