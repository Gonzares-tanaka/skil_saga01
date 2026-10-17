"""Offline score import into game.pyxres; preserve every old image/map/audio slot."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
import pyxel


def main():
    score = json.loads((ROOT / 'tools/art/audio_pass_01.json').read_text(encoding='utf8'))
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(ROOT / 'assets/battle_music.pyxres'))
    # Existing channel-0 cues, copied unchanged into both banks.
    common = {n: pyxel.sounds[n] for n in (30, 31, 59)}
    pyxel.load(str(ROOT / 'game.pyxres'))
    assert not any(s.notes for s in pyxel.sounds) and not any(any(m.seqs) for m in pyxel.musics), 'Occupied audio: refusing overwrite'
    for n, s in common.items(): pyxel.sounds[n] = s
    for n, args in {60: ('c2g1c1','n','642','f',3), 61: ('c3e3g3c4','p','3453','v',5),
                    62: ('c3g3c4','p','542','f',4), 63: ('g3c4e4g4','p','5542','v',5)}.items():
        pyxel.sounds[n].set(*args)
    slots = iter([n for n in range(50) if n not in (30, 31)] + [56])
    audit = []
    for song in score['songs']:
        numbers = [next(slots) for _ in range(7)]
        for n, notes in zip(numbers[:4], song['melodies']):
            assert len(notes.split()) == 32
            pyxel.sounds[n].set(notes, song['tone'], song['volume'], 'n', song['speed'])
        for n, roots in zip(numbers[4:6], (song['bass_roots'], list(reversed(song['bass_roots'])))):
            notes = ' '.join(note for root in roots for note in [root, 'r', root, 'r', root, root, 'r', root])
            pyxel.sounds[n].set(notes, 't', '3222', 'n', song['speed'])
        if song['backing'] == 'drums':
            pyxel.sounds[numbers[6]].set('c1 r g1 r c1 c1 g1 r ' * 4, 'n', '20102010', 'f', song['speed'])
        else:
            pyxel.sounds[numbers[6]].set(song['melodies'][0], 't', '1110', 'n', song['speed'])
        form = [0, 1, 2, 3] if song['sections'] == 4 else ([0, 1, 0, 2, 3, 3] if song['sections'] == 6 else [0, 1, 2, 1, 0, 2, 3, 3])
        seqs = [[], [numbers[i] for i in form], [numbers[4 + i % 2] for i in range(len(form))], [numbers[6]] * len(form)]
        pyxel.musics[song['music']].set(*seqs)
        audit.append(dict(id=song['id'], music=song['music'], sounds=numbers, channels=[1, 2, 3],
                          speed=song['speed'], bpm=round(3600 / song['speed'], 2),
                          seconds=round(32 * song['speed'] * len(form) / 120, 3), form=form))
    for row in score['se']:
        pyxel.sounds[row['sound']].set(row['notes'], row['tone'], row['volume'], row['effect'], row['speed'])
    pyxel.save(str(ROOT / 'game.pyxres'))
    (ROOT / 'verification/audio_pass_assets.json').write_text(json.dumps(dict(songs=audit, se=score['se']), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('Imported 7 original BGM / 6 SE; all patterns <=32 notes; Editor default slots; old battle resource untouched')


if __name__ == '__main__': main()
