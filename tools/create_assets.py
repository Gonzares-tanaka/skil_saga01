"""Create the editable resource, refusing to overwrite existing artwork."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.art import PALETTE, RESOURCE, draw_defaults

if RESOURCE.exists():
    print(f"Already exists (left untouched): {RESOURCE}")
else:
    RESOURCE.parent.mkdir(exist_ok=True)
    pyxel.init(160, 120, headless=True)
    pyxel.colors[:4] = PALETTE
    draw_defaults(pyxel)
    pyxel.save(str(RESOURCE))
    pyxel.save_pal(str(RESOURCE.with_suffix(".pyxpal")))
    print(f"Created: {RESOURCE}")
