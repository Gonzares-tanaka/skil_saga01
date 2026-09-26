"""Run the embedded Web payload with real Pyxel and simulated pad input."""
import base64
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "dist/game.html").read_text(encoding="utf-8")
assert 'gamepad: "disabled"' in html
assert html.count('data-gb="') == 6
assert all(f'data-gb="{name}"' in html for name in ('up', 'down', 'left', 'right', 'a', 'b'))
assert '_virtualGamepadStates[index] = true' in html
payload = base64.b64decode(re.search(r'base64: "([^"]+)"', html)[1])
with tempfile.TemporaryDirectory(prefix="verify_pyxel_web_") as temp:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in ("game", "area2", "area3"):
            for suffix in (".pyxpal", ".pyxres"):
                filename = name + suffix
                assert archive.read("spark_web/" + filename) == (ROOT / filename).read_bytes(), filename
        for source in (ROOT / "rpg").glob("*.py"):
            assert archive.read("spark_web/rpg/" + source.name) == source.read_bytes(), source.name
        for source in (ROOT / "data").glob("*.json"):
            assert archive.read("spark_web/data/" + source.name) == source.read_bytes(), source.name
        music = ROOT / 'assets/battle_music.pyxres'
        assert archive.read('spark_web/assets/battle_music.pyxres') == music.read_bytes()
        archive.extractall(temp)
    check = '''
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path.cwd()))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.tiles import TILE_FLOOR, TILE_WALL
app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
expected = [int(line, 16) for line in (ROOT / "game.pyxpal").read_text().splitlines()]
assert len(expected) == 32 and list(pyxel.colors) == expected
def press(button):
    with patch.object(pyxel, "btnp", side_effect=lambda code, *args: code == button), patch.object(pyxel, "btn", return_value=False):
        app.update()
    app.draw()
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "explore"
app.dungeon.settings["encounter_chance"] = 0
for button, dx, dy, facing in ((pyxel.GAMEPAD1_BUTTON_DPAD_UP,0,-1,"up"),(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,0,1,"down"),(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,-1,0,"left"),(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT,1,0,"right")):
    app.dungeon.x, app.dungeon.y = 6, 6
    app.dungeon.maps[0].pset(6+dx, 6+dy, TILE_FLOOR)
    press(button)
    assert (app.dungeon.x, app.dungeon.y) == (6+dx, 6+dy)
    assert app.player_facing == facing
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "menu"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "explore"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "menu"
press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.overlay == "info"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.overlay is None
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "explore"
press(pyxel.GAMEPAD1_BUTTON_B)
for _ in range(4):
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.overlay == "help"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.overlay is None
app.begin_encounter()
assert app.state == "command"
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "skill"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "command"
for _ in range(4):
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "resolve"
assert list(pyxel.colors) == expected
print("PASS: embedded resources/palette, all pad directions, menu, information, help and battle commands")
'''
    subprocess.run([sys.executable, "-c", check], cwd=Path(temp) / "spark_web", check=True)
