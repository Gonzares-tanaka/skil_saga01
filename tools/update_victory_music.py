"""A connected victory phrase with a sustained release; preserve other music."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT


def write_fanfare():
    parts = (
        ("e3 g#3 b3 b3 a3 f#3 b3 d#4", "p", "45554455"),
        ("e2 e2 g#2 e2 a1 a1 b1 b1", "t", "44444444"),
        ("c0 r c4 r c2 r c4 r", "n", "30203010"),
    )
    for index, (notes, tone, volume) in enumerate(parts, 20):
        pyxel.sounds[index].set(notes, tone, volume, "f" if tone == "n" else "n", 18)
    # One long note instead of retriggered short notes: a smooth 1.2-second release.
    pyxel.sounds[23].set("e4", "p", "5", "f", 144)
    pyxel.sounds[24].set("e2", "t", "4", "f", 144)
    pyxel.sounds[25].set("r", "n", "0", "n", 144)
    pyxel.musics[1].set([], [20, 23], [21, 24], [22, 25])


def main():
    path = ROOT / "assets/battle_music.pyxres"
    backup = ROOT / "verification/audio" / ("before_short_fanfare_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".pyxres")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(path), exclude_images=True, exclude_tilemaps=True)
    write_fanfare()
    pyxel.save(str(path), exclude_images=True, exclude_tilemaps=True)
    print(f"Victory: 1.2s phrase + 1.2s sustained decay. Previous asset: {backup}")


if __name__ == "__main__":
    main()
