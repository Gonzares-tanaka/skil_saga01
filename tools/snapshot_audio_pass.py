"""One-time baseline for AUDIO PASS; never rewrites an existing baseline."""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tests'))
import pyxel
from legend_presentation_helpers import rare_trace
from test_rare_skill_presentation import make_battle


def sound_row(s):
    return dict(notes=list(s.notes), tones=list(s.tones), volumes=list(s.volumes),
                effects=list(s.effects), speed=s.speed)


def main():
    output = ROOT / 'tests/fixtures/audio_pass_before.json'
    assert not output.exists(), 'Baseline exists: refusing overwrite'
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(ROOT / 'game.pyxres'))
    images = [hashlib.sha256(bytes(im.pget(x, y) for y in range(256) for x in range(256))).hexdigest()
              for im in pyxel.images]
    maps = [(tm.imgsrc, [[tm.pget(x, y) for x in range(256)] for y in range(256)]) for tm in pyxel.tilemaps]
    game_audio = dict(sounds=[sound_row(s) for s in pyxel.sounds],
                      musics=[[list(seq) for seq in m.seqs] for m in pyxel.musics])
    pyxel.load(str(ROOT / 'assets/battle_music.pyxres'))
    battle_audio = dict(sounds=[sound_row(s) for s in pyxel.sounds],
                        musics=[[list(seq) for seq in m.seqs] for m in pyxel.musics])
    files = list((ROOT / 'rpg').glob('*.py')) + list((ROOT / 'data').glob('*.json'))
    files += list((ROOT / 'assets').rglob('*.pyxres'))
    files += [ROOT / n for n in ('game.pyxres', 'game.pyxpal', 'area2.pyxres', 'area3.pyxres',
                                'area2.pyxpal', 'area3.pyxpal', 'tools/gkd_diagnostic.py', 'tools/run_gkd.sh')]
    skills = json.loads((ROOT / 'data/skills.json').read_text(encoding='utf8'))
    traces = {r['id']: rare_trace(make_battle(r['id'])) for r in skills if r['rarity'] in ('RARE', 'LEGEND')}
    result = dict(hashes={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  image_hashes=images, map_hash=hashlib.sha256(json.dumps(maps, separators=(',', ':')).encode()).hexdigest(),
                  game_audio=game_audio, battle_audio=battle_audio, visual_traces=traces)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('Saved AUDIO baseline:', len(files), 'files;', len(traces), 'visual traces')


if __name__ == '__main__': main()
