"""Create a separate Editor audio resource; never overwrite user-edited assets."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def compile_score(pyxel):
    score = json.loads((ROOT/'tools/art/omen_music.json').read_text(encoding='utf8'))
    sounds = []
    for row in score['patterns']:
        notes, volumes = [], []
        for event in row['events']:
            note, duration = event.split(':')
            duration = int(duration)
            notes.extend([note] * duration)
            volumes.extend([0 if note == 'r' else max(1, row['volume'] - int(i > 0))
                            for i in range(duration)])
        assert len(notes) == 32, row['slot']
        sound = pyxel.Sound()
        sound.set(' '.join(notes), row['tone'], ''.join(map(str, volumes)),
                  row['effect'], score['speed'])
        sounds.append((row['slot'], sound))
    assert [slot for slot, _ in sounds] == list(range(6))
    return score, sounds


def main():
    path = ROOT/'assets/omen_music.pyxres'
    if path.exists():
        raise FileExistsError('Resource exists; edit it in Pyxel Editor instead of overwriting')
    import pyxel
    pyxel.init(160, 120, headless=True)
    score, sounds = compile_score(pyxel)
    for slot, sound in sounds:
        pyxel.sounds[slot] = sound
    pyxel.musics[score['music']].set(*score['sequences'])
    pyxel.save(str(path), exclude_images=True, exclude_tilemaps=True)
    seconds = sum(pyxel.sounds[n].total_sec() for n in score['sequences'][1])
    assert seconds == 32
    out = ROOT/'verification/audio/omen'; out.mkdir(parents=True, exist_ok=True)
    pyxel.musics[0].save(str(out/'offering_omen.wav'), seconds)
    print('Created', path.relative_to(ROOT), '/ Music 0, Sounds 0-5, 32-second loop')


if __name__ == '__main__':
    main()
