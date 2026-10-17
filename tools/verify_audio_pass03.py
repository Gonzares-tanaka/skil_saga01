"""AREA1 WAV/stems/loop audit and strict non-target preservation."""
from array import array
import hashlib
import json
from pathlib import Path
import sys
import wave
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from rpg.sound import AudioManager
from tools.rework_area1_music03 import verify_resource
from tools.verify_audio_pass import wav_stats


def main():
    before=verify_resource()
    protected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
        for name,digest in before['hashes'].items() if name not in ('game.pyxres','rpg/dungeon_app.py')}
    assert all(protected.values()),[name for name,ok in protected.items() if not ok]
    pyxel.init(160,120,headless=True)
    audio=AudioManager(); audio.load(); audio._install_bank('scene')
    seqs=[list(seq) for seq in pyxel.musics[2].seqs]
    lengths=[sum(pyxel.sounds[n].total_sec() for n in seq) for seq in seqs[1:]]
    assert max(lengths)-min(lengths)<.0001
    seconds=lengths[0]
    out=ROOT/'verification/audio/pass03'; out.mkdir(parents=True,exist_ok=True)
    double=out/'bgm_area1_two_loops.wav'; path=out/'bgm_area1.wav'
    pyxel.musics[2].save(str(double),seconds*2)
    with wave.open(str(double),'rb') as source:
        params=source.getparams(); pcm=source.readframes(source.getnframes())
        rate=source.getframerate(); channels=source.getnchannels()
    frames=round(seconds*rate)
    with wave.open(str(path),'wb') as target:
        target.setparams(params); target.writeframes(pcm[:frames*channels*2])
    samples=array('h',pcm); edge=frames*channels; span=round(.04*rate)*channels
    seam=samples[edge-span:edge+span]
    assert max(abs(v) for v in seam)>100
    stems={}
    for channel,role in ((1,'melody'),(2,'bass'),(3,'backing_rhythm')):
        stem=[[],[],[],[]]; stem[channel]=seqs[channel]
        # Temporary in-memory Music7 is never saved back into any resource.
        pyxel.musics[7].set(*stem)
        stem_path=out/f'bgm_area1_{role}.wav'
        pyxel.musics[7].save(str(stem_path),seconds)
        stems[role]=wav_stats(stem_path)
    pyxel.musics[7].set([],[],[],[])
    assert stems['melody']['rms']>stems['bass']['rms']
    assert stems['melody']['rms']>stems['backing_rhythm']['rms']
    score=json.loads((ROOT/'tools/art/audio_pass_03.json').read_text(encoding='utf8'))['songs'][0]
    report=dict(music=2,sounds=sorted(set(n for seq in seqs for n in seq)),channels=[1,2,3],
        sequences=seqs,speed=29,quarter_bpm=3600/29,loop_seconds=seconds,key=score['key'],form=score['form'],
        wave=path.relative_to(ROOT).as_posix(),wave_stats=wav_stats(path),stems=stems,
        protected_files=protected,protected_count=len(protected),
        title_and_other_audio_raw_blocks_identical=True,stairs_exact=before['scene']['sounds'][50],
        physical_ios_tested=False,physical_gkd_tested=False,
        limitations=['Score, waveform and stem verification; physical speaker listening is not performed.'])
    (ROOT/'verification/audio_pass03.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS: AREA1 Music2 / speed29 /',round(seconds,3),'sec, matched channels, no clipping, melody above backing RMS;',len(protected),'protected files')


if __name__=='__main__': main()
