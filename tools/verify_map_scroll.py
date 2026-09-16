"""Render a larger map at edges/center and verify the fixed player position."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import (DungeonApp, MAP_X, MAP_Y, MAP_WIDTH, MAP_HEIGHT,
                             PLAYER_WIDTH, PLAYER_HEIGHT, PLAYER_SPRITES)
from rpg.text import font, text_width, FONT_HEIGHT


app = DungeonApp(Session(*load_content(), seed=91), run=False, headless=True)
app.enter_dungeon()
app.dungeon.width, app.dungeon.height = 32, 24
output = ROOT / "verification" / "screenshots"
output.mkdir(parents=True, exist_ok=True)
real_text, real_blt, real_bltm = pyxel.text, pyxel.blt, pyxel.bltm
text_calls, image_calls, map_calls = 0, [], []


def bounded_text(x, y, value, color, selected_font):
    global text_calls
    assert selected_font is font()
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    text_calls += 1
    real_text(x, y, value, color, selected_font)


def image_draw(*args):
    image_calls.append(args)
    real_blt(*args)


def map_draw(*args):
    map_calls.append(args)
    real_bltm(*args)


expected_x = MAP_X + MAP_WIDTH // 2 - PLAYER_WIDTH // 2
expected_y = MAP_Y + MAP_HEIGHT // 2 - PLAYER_HEIGHT // 2
actor = app.session.party[0]

with patch.object(pyxel, "text", side_effect=bounded_text), \
        patch.object(pyxel, "blt", side_effect=image_draw), \
        patch.object(pyxel, "bltm", side_effect=map_draw):
    sources = []
    for index, point in enumerate(((0, 0), (15, 12), (31, 23))):
        app.dungeon.x, app.dungeon.y = point
        image_calls.clear()
        app.draw()
        player = [call for call in image_calls
                  if call[:7] == (expected_x, expected_y, 0, *PLAYER_SPRITES[app.player_facing],
                                  PLAYER_WIDTH, PLAYER_HEIGHT)]
        assert player and player[-1][7] == 0, image_calls
        sources.append(map_calls[-1][3:5])
        pyxel.screenshot(str(output / f"map_scroll_{index + 1}.png"), scale=4)

    assert sources[0] == (0, 0)
    assert sources[1][0] > 0 and sources[1][1] > 0
    assert sources[2][0] > sources[1][0] and sources[2][1] > sources[1][1]

    # Key routing and facing against walls; changes stay in memory only.
    from rpg.tiles import TILE_FLOOR, TILE_WALL
    app.dungeon.settings["encounter_chance"] = 0
    for code, facing, delta in ((pyxel.KEY_UP, "up", (0, -1)),
                                (pyxel.KEY_DOWN, "down", (0, 1)),
                                (pyxel.KEY_RIGHT, "right", (1, 0)),
                                (pyxel.KEY_LEFT, "left", (-1, 0))):
        for blocked in (False, True):
            app.dungeon.x, app.dungeon.y = 6, 6
            dx, dy = delta
            app.dungeon.maps[0].pset(6 + dx, 6 + dy, TILE_WALL if blocked else TILE_FLOOR)
            with patch.object(pyxel, "btnp", side_effect=lambda k, *args: k == code), patch.object(pyxel, "btn", return_value=False):
                app.update()
            assert app.player_facing == facing
            assert (app.dungeon.x, app.dungeon.y) == ((6, 6) if blocked else (6 + dx, 6 + dy))
            image_calls.clear()
            app.draw()
            assert (expected_x, expected_y, 0, *PLAYER_SPRITES[facing], 16, 16, 0) in image_calls
    with patch.object(pyxel, "btnp", return_value=False), patch.object(pyxel, "btn", return_value=False):
        app.update()
    assert app.player_facing == "left"
    app.enter_dungeon()
    assert app.player_facing == "down"

print(f"Map scroll UI passed: {text_calls} bounded text calls / "
      f"player fixed at ({expected_x},{expected_y})")
