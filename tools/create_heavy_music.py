"""Generate the revised score; retain the previous editable asset in verification/audio."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT


def main():
    destination = ROOT / "assets/battle_music.pyxres"
    pyxel.init(160, 120, headless=True)
    if destination.exists():
        backup = ROOT / "verification/audio" / ("battle_music_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".pyxres")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup)
        pyxel.load(str(destination), exclude_images=True, exclude_tilemaps=True)
        print(f"Previous score: {backup}")
    # 150 BPM. Pedal tones, semitone tension, rising figures and a driving backbeat.
    bars = [
        "e2 e2 b2 e2 f3 e3 r b2 e2 e2 g2 a2 b2 r f3 e3",
        "e2 b2 e3 r f3 e3 b2 r g3 f#3 e3 b2 a2 g2 f#2 d#2",
        "c2 c2 g2 c2 d#3 e3 r g2 c2 c2 e2 f#2 g2 r d#3 e3",
        "c2 g2 c3 r d#3 e3 g3 r f#3 e3 d3 c3 b2 g2 d#3 e3",
        "a1 a1 e2 a1 b2 c3 r e2 a1 a1 c2 d2 e2 r b2 c3",
        "a2 e3 a3 r g3 f#3 e3 r d#3 e3 g3 e3 c3 b2 a2 a#2",
        "b1 b1 f#2 b1 c3 b2 r f#2 b1 b1 d#2 e2 f#2 r c3 b2",
        "b2 c3 d#3 r f#3 g3 a3 r g3 f#3 e3 d#3 c3 b2 f#2 d#2",
    ]
    for i in range(8):
        notes = (bars[i] + " " + bars[i ^ 1]).split()
        assert len(notes) == 32
        pyxel.sounds[i].set(" ".join(notes), "p", "64345434", "f", 12)
    for i, (root, fifth) in enumerate((("e0", "b0"), ("c0", "g0"), ("a0", "e1"), ("b0", "f#1"))):
        bar = [root, root, "r", root, fifth, root, root, "r", root, root, fifth, root, root, "r", fifth, root]
        pyxel.sounds[8 + i].set(" ".join(bar * 2), "t", "65444444", "f", 12)
    drums = "c0 c4 c4 c4 c2 c4 c0 c4 c0 c4 c4 c4 c2 c4 c0 c4"
    pyxel.sounds[12].set(drums + " " + drums, "n", "6222524262225242", "f", 12)
    pyxel.sounds[13].set(drums + " c0 c4 c0 c4 c2 c4 c0 c4 c2 c2 c4 c4 c2 c2 c2 c2",
                         "n", "6222524262425454", "f", 12)
    pyxel.musics[0].set([], list(range(8)), [8, 8, 9, 9, 10, 10, 11, 11], [12, 12, 12, 13] * 2)
    if destination.exists():
        # Existing fanfare and all other Editor slots stay as loaded.
        pyxel.save(str(destination), exclude_images=True, exclude_tilemaps=True)
        print("Updated Music 0: tense battle, 150 BPM / 25.6s; fanfare retained")
        return
    # 4.8-second E-major victory cadence, with final decay and silence.
    fanfare = [
        "b2 r b2 r b2 e3 g#3 b3 e4 r d#4 b3 c#4 r b3 r a3 c#4 e4 r b3 d#4 f#4 r e4 e4 e4 e4 e4 e4 r r",
        "e1 r e1 r e1 b1 e2 g#2 b2 r b2 g#2 a2 r g#2 r a1 e2 a2 r b1 f#2 b2 r e2 e2 e2 e2 e2 e2 r r",
        "c0 c4 c2 c4 c0 c4 c2 c2 c0 r c4 r c2 r c4 r c0 r c4 r c2 c2 c2 c2 c0 r r r r r r r",
    ]
    for i, (notes, tone) in enumerate(zip(fanfare, ("p", "t", "n"))):
        assert len(notes.split()) == 32
        volume = "55445555" + "54545454" * 2 + "65432100" if i < 2 else "53435344" + "60204020" * 2 + "60000000"
        pyxel.sounds[20 + i].set(notes, tone, volume, "f", 18)
    pyxel.musics[1].set([], [20], [21], [22])
    pyxel.save(str(destination), exclude_images=True, exclude_tilemaps=True)
    print("Created Music 0: tense battle, 150 BPM / 25.6s; Music 1: victory / 4.8s")


if __name__ == "__main__":
    main()
