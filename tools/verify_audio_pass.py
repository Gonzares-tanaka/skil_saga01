"""Render editable audio and exercise actual native boss/final BGM switches."""
from array import array
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
import wave
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.sound import BGM_IDS, SE_IDS, area_bgm


def wav_stats(path):
    with wave.open(str(path), 'rb') as wav:
        pcm = array('h', wav.readframes(wav.getnframes()))
        seconds = wav.getnframes() / wav.getframerate()
    peak = max(abs(n) for n in pcm)
    clipped = sum(abs(n) >= 32767 for n in pcm) / len(pcm)
    assert peak > 100 and clipped < .001, (path, peak, clipped)
    return dict(seconds=round(seconds, 3), peak=peak, clipped_fraction=clipped,
                rms=round((sum(n*n for n in pcm) / len(pcm)) ** .5, 2))


def main():
    start = time.monotonic()
    app = DungeonApp(Session(*load_content(), seed=819), run=False, headless=True)
    audio = app.audio
    out = ROOT / 'verification/audio/pass01'; out.mkdir(parents=True, exist_ok=True)
    scores = {}
    for ident, (bank, index) in BGM_IDS.items():
        audio._install_bank(bank)
        seqs = [list(seq) for seq in pyxel.musics[index].seqs]
        durations = [sum(pyxel.sounds[n].total_sec() for n in seqs[c]) for c in (1,2,3)]
        assert max(durations) - min(durations) < .001
        path = out / (ident + '.wav')
        pyxel.musics[index].save(str(path), durations[0])
        scores[ident] = dict(resource=bank, music=index, sequences=seqs, channels=[1,2,3],
                             wav=path.relative_to(ROOT).as_posix(), **wav_stats(path))
    effects = {}
    for ident, slot in SE_IDS.items():
        path = out / (ident + '.wav')
        pyxel.sounds[slot].save(str(path), pyxel.sounds[slot].total_sec())
        effects[ident] = dict(sound=slot, channel=0, wav=path.relative_to(ROOT).as_posix(), **wav_stats(path))
    audio._install_bank('battle')
    path = out / 'victory_original.wav'; pyxel.musics[1].save(str(path), 2.4)
    original_victory = wav_stats(path)
    starts = {}
    with patch.object(pyxel, 'playm', side_effect=AssertionError('native playm forbidden')), \
         patch.object(pyxel, 'btn', return_value=False), patch.object(pyxel, 'btnp', return_value=False):
        for label, floor, guardian in (('B5',4,None), ('B10',9,None), ('guardian1',14,0),
                                     ('guardian2',14,1), ('guardian3',14,2), ('demon',14,None)):
            for _ in range(100):
                app.session.battle = None; app.session.settled = True
                app.dungeon.debug_floor(floor); app.audio.play_bgm(area_bgm(floor))
                app.begin_encounter(boss=True, guardian_index=guardian)
                for _ in range(3): app.update(); app.draw()
                assert app.state == 'command' and app.audio.current_bgm == 'bgm_boss'
            starts[label] = 100
        f = app.dungeon.finale; f.has_amrita = f.final_event_started = True
        for _ in range(100):
            app.session.battle = None; app.session.settled = True
            app.audio.play_bgm('bgm_hub'); app.begin_final_battle()
            for _ in range(3): app.update(); app.draw()
            assert app.state == 'command' and not app.battle_input_blocked
            assert app.audio.current_bgm == 'bgm_boss'  # Final theme begins at Amrita barrier break.
        starts['final'] = 100
    before = json.loads((ROOT / 'tests/fixtures/audio_pass_before.json').read_text(encoding='utf8'))
    allowed = {'rpg/sound.py', 'rpg/app.py', 'rpg/dungeon_app.py', 'game.pyxres'}
    from tests.test_enemy_balance import ALLOWED
    allowed |= ALLOWED
    protected = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h
                 for n,h in before['hashes'].items() if n not in allowed}
    assert all(protected.values())
    result = dict(bgm=scores, se=effects, original_victory=original_victory,
                  native_starts=starts, native_starts_passed=sum(starts.values()),
                  protected=protected, protected_count=len(protected),
                  seconds=round(time.monotonic()-start, 2), physical_gkd_tested=False)
    (ROOT / 'verification/audio_pass.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print('PASS: 8 BGM / 6 SE / original victory WAV; 700 native boss/final switches;', len(protected), 'protected files')


if __name__ == '__main__': main()
