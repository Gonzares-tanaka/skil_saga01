"""Import the credits score; preserve every image/tile and non-credits sound byte."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audio_pass02_resource import blocks,read_resource,raw_snapshot

SLOTS=[n for n in range(50) if n not in (30,31)]


def compile_score(score,pyxel):
    voices=[score[key] for key in ('lead','harmony','bass')]
    if not all(len(bars)==16 for bars in voices):raise ValueError('16 bars per voice are required')
    sounds={};sequences=[[],[],[],[]]
    for voice,bars in enumerate(voices):
        for bar,events in enumerate(bars):
            notes=[];volumes=[];effects=[]
            for event in events.split():
                pitch,length=event.split(':');length=int(length)
                if not 1<=length<=8:raise ValueError('Invalid note duration')
                notes.extend([pitch]*length)
                # Sustained half/whole notes and restrained harmony, no rapid ostinato.
                base=(5,2,4)[voice]
                volumes.extend([base]+[max(1,base-1)]*(length-1))
                effects.extend(['n']+['v' if voice==0 and i>=2 else 'n' for i in range(1,length)])
            if len(notes)!=8:raise ValueError('Each bar must contain eight eighth-note steps')
            if bar==15:
                # Resolve into a major/add9 horizon, then rest before END.
                notes+=['r']*2;volumes+=[0,0];effects+=['n','n']
            sound=pyxel.Sound()
            sound.set(' '.join(notes),('p','p','t')[voice],''.join(map(str,volumes)),''.join(effects),score['speed'])
            slot=SLOTS[bar*3+voice]
            sounds[slot]=dict(notes=list(sound.notes),tones=list(sound.tones),volumes=list(sound.volumes),
                              effects=list(sound.effects),speed=sound.speed)
            sequences[voice+1].append(slot)
    return sounds,{'seqs':sequences}


def import_music(path,sounds,music):
    before=raw_snapshot(path)
    with zipfile.ZipFile(path) as archive:
        entries=[(info,archive.read(info.filename)) for info in archive.infolist()]
    candidate=path.with_suffix('.credits.tmp')
    try:
        with zipfile.ZipFile(candidate,'w') as archive:
            for info,raw in entries:
                if info.filename=='pyxel_resource.toml':
                    output=[]
                    for kind,index,block in blocks(raw):
                        row=sounds.get(index) if kind=='sounds' else music if kind=='musics' and index==0 else None
                        if row is not None:
                            block=(f'[[{kind}]]\n'+'\n'.join(f'{key} = {json.dumps(value)}' for key,value in row.items())+'\n\n').encode()
                        output.append(block)
                    raw=b''.join(output)
                archive.writestr(info,raw)
        after=raw_snapshot(candidate)
        assert before['other_entries']==after['other_entries']
        assert before['blocks'].keys()==after['blocks'].keys()
        for key,digest in before['blocks'].items():
            kind,index=key.split(':');index=int(index)
            if kind=='sounds' and index in SLOTS or kind=='musics' and index==0:continue
            assert after['blocks'][key]==digest,key
        resource=read_resource(candidate)
        for slot,row in sounds.items():assert resource['sounds'][slot]==row,slot
        assert resource['musics'][0]==music
        candidate.replace(path)
    finally:
        if candidate.exists():candidate.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render',action='store_true',help='Also export verification/audio/credits_journey.wav')
    args=parser.parse_args()
    import pyxel
    score=json.loads((ROOT/'tools/art/credits_journey_music.json').read_text(encoding='utf8'))
    pyxel.init(160,120,headless=True)
    sounds,music=compile_score(score,pyxel)
    path=ROOT/'assets/postgame.pyxres'
    import_music(path,sounds,music)
    pyxel.load(str(path),exclude_images=True,exclude_tilemaps=True)
    lengths=[sum(pyxel.sounds[n].total_sec() for n in seq) for seq in music['seqs'][1:]]
    assert max(lengths)-min(lengths)<.001 and abs(lengths[0]-52)<.001
    print('Imported credits Music0: 75 BPM, 16 bars,',round(lengths[0],3),'seconds; images and other sounds untouched')
    if args.render:
        out=ROOT/'verification/audio/credits_journey.wav';out.parent.mkdir(parents=True,exist_ok=True)
        pyxel.musics[0].save(str(out),lengths[0])
        from tools.verify_audio_pass import wav_stats
        stats=wav_stats(out)
        (ROOT/'verification/credits_journey_audio.json').write_text(json.dumps(dict(
            title=score['title'],key=score['key'],speed=score['speed'],quarter_bpm=75,
            music=0,sounds=SLOTS,channels=[1,2,3],seconds=lengths[0],wave=out.relative_to(ROOT).as_posix(),
            waveform=stats,images_and_noncredits_audio_preserved=True,physical_speaker_tested=False),indent=2)+'\n',encoding='utf8')
        print('Rendered:',out.relative_to(ROOT).as_posix(),stats)


if __name__=='__main__':main()
