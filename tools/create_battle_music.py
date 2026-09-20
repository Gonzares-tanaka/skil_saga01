"""Create the original editable battle score once; never overwrite editor work."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT

DESTINATION = ROOT / "assets" / "battle_music.pyxres"


def main():
    if DESTINATION.exists():
        raise SystemExit("battle_music.pyxres exists; keep your Editor changes. No overwrite.")
    pyxel.init(160, 120, headless=True)
    # 120 engine ticks/sec: speed 10 = sixteenth notes at 180 BPM.
    # Each sound is two bars, 32 steps, with deliberate rests and accents.
    phrases = [
        "e3 r e3 g3 b3 r a3 g3 e3 r b2 r d3 e3 g3 r | a3 r g3 e3 d3 r e3 r b2 r d3 e3 g3 a3 b3 r",
        "c4 r b3 g3 e3 r g3 r a3 r g3 e3 d3 e3 g3 r | d4 r c4 a3 f3 r a3 r g3 r f3 e3 d3 r d3 r",
        "e3 b3 e4 r d4 b3 a3 r g3 a3 b3 r a3 g3 e3 r | g3 d4 g4 r e4 d4 b3 r a3 b3 d4 r b3 a3 g3 r",
        "a3 e4 a4 r g4 e4 d4 r c4 d4 e4 r d4 c4 a3 r | b3 r b3 d#4 f#4 r e4 d#4 b3 r a3 f#3 d#3 r b2 r",
        "e4 r r b3 d4 e4 g4 r f#4 e4 d4 b3 a3 r b3 r | c4 r r g3 b3 c4 e4 r d4 c4 b3 g3 e3 r g3 r",
        "a3 r c4 r e4 r g4 e4 d4 c4 a3 r c4 d4 e4 r | b3 r d4 r f#4 r a4 f#4 e4 d4 b3 r a3 b3 d4 r",
        "g4 r f#4 e4 b3 r d4 e4 g4 r a4 g4 e4 d4 b3 r | e4 r d4 c4 g3 r b3 c4 e4 r g4 e4 c4 b3 g3 r",
        "a3 c4 e4 r g4 e4 c4 a3 f#3 a3 d4 r f#4 d4 a3 r | b3 r d#4 r f#4 r a4 r g4 f#4 e4 d#4 b3 a3 f#3 d#3",
    ]
    for i, phrase in enumerate(phrases):
        notes = phrase.replace("|", "").split()
        assert len(notes) == 32
        pyxel.sounds[i].set(" ".join(notes), "p", "54434443", "f", 10)
    for i, (root, fifth, octave) in enumerate((("e1", "b1", "e2"), ("c1", "g1", "c2"),
                                              ("a1", "e2", "a2"), ("b1", "f#2", "b2"))):
        bar = [root, "r", root, root, fifth, "r", root, "r", octave, "r", root, root, fifth, root, "r", fifth]
        pyxel.sounds[8 + i].set(" ".join(bar * 2), "t", "53334333", "f", 10)
    drums = "c1 r c4 r c3 r c4 c4 c1 r c4 r c3 r c4 r".split()
    pyxel.sounds[12].set(" ".join(drums * 2), "n", "5030402250204020", "f", 10)
    pyxel.sounds[13].set(" ".join(drums + "c1 r c4 r c3 r c4 c4 c3 c3 c4 c4 c3 c3 c3 c3".split()),
                         "n", "5030402250204033", "f", 10)
    pyxel.musics[0].set([], list(range(8)) * 2,
                        [8, 9, 10, 11, 8, 9, 10, 11] * 2,
                        [12, 12, 12, 13] * 4)
    pyxel.save(str(DESTINATION), exclude_images=True, exclude_tilemaps=True)
    print(f"Created {DESTINATION}: Music 0, Sound 0-13, 180 BPM, 42.67 sec loop")


if __name__ == "__main__":
    main()
