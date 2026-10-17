"""Only Music2 and its eight private patterns; keep every other raw block."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pyxel
from tools.audio_pass02_resource import read_resource,replace_audio,assert_protected_resource
from tools.rework_title_area1_music import compile_score
AREA1_SOUNDS=set(range(14,21))|{58}


def verify_resource():
    before=json.loads((ROOT/'tests/fixtures/audio_pass03_before.json').read_text(encoding='utf8'))
    assert_protected_resource(ROOT/'game.pyxres',before,allowed_sounds=AREA1_SOUNDS,allowed_musics={2})
    return before


def main():
    pyxel.init(160,120,headless=True)
    before=verify_resource(); current=read_resource(ROOT/'game.pyxres')
    score=json.loads((ROOT/'tools/art/audio_pass_03.json').read_text(encoding='utf8'))
    sounds,musics=compile_score(score,expected_sounds=AREA1_SOUNDS)
    for kind,edits in (('sounds',sounds),('musics',musics)):
        for index,row in edits.items():
            assert current[kind][index] in (before['scene'][kind][index],row),f'User edited {kind} {index}; refusing overwrite'
    replace_audio(ROOT/'game.pyxres',sounds,musics)
    verify_resource()
    pyxel.load(str(ROOT/'game.pyxres'))
    for index,row in sounds.items():
        s=pyxel.sounds[index]
        assert row==dict(notes=list(s.notes),tones=list(s.tones),volumes=list(s.volumes),effects=list(s.effects),speed=s.speed)
    print('Imported AREA1 only: Music2 / Sounds14-20,58. TITLE, all other BGM/SE/images/maps byte-identical.')


if __name__=='__main__': main()
