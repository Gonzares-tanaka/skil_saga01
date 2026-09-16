"""Skill Archive and exact-skill debug UI integration checks."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import font, text_width, FONT_HEIGHT


app = DungeonApp(Session(*load_content(), seed=73), run=False, headless=True)
output = ROOT / "verification" / "screenshots"
output.mkdir(parents=True, exist_ok=True)
real_text = pyxel.text
calls = 0
drawn = []


def bounded(x, y, value, color, selected_font):
    global calls
    assert selected_font is font()
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    calls += 1
    drawn.append(str(value))
    real_text(x, y, value, color, selected_font)


def key(code=None):
    with patch.object(pyxel, "btnp", side_effect=lambda k, *args: k == code), \
            patch.object(pyxel, "btn", return_value=False):
        app.update()
    app.draw()


def capture(name):
    app.notice_timer = 0
    app.draw()
    pyxel.screenshot(str(output / f"archive_{name}.png"), scale=4)


with patch.object(pyxel, "text", side_effect=bounded), patch.object(pyxel, "play"):
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert app.state == "archive" and app.archive_page == 0
    assert app.session.archive_summary()["discovered"] == 3
    capture("01_summary")
    assert any("DISCOVERED 3/30" in line for line in drawn)
    assert any("MASTERED   0/30" in line for line in drawn)

    drawn.clear()
    key(pyxel.KEY_Z)
    assert app.archive_page == 1
    capture("02_hidden_list")
    assert any("????????" in line for line in drawn)
    for _ in range(len(app.session.skills) - 1):
        key(pyxel.KEY_DOWN)
    assert app.archive_cursor == len(app.session.skills) - 1

    # F10 can force one exact catalog entry and then set only that skill to 1.
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F10)
    assert app.overlay == "catalog"
    for _ in range(3):
        key(pyxel.KEY_DOWN)
    selected = list(app.session.skills)[app.catalog_cursor]
    key(pyxel.KEY_C)
    assert selected in app.session.party[0].skills
    assert selected in app.session.discovered_skills
    assert selected not in app.session.mastered_skills
    key(pyxel.KEY_V)
    assert app.session.party[0].skill_uses[selected] == 1

    # A full loadout uses the normal replacement screen and returns to F10.
    app.session.debug_skills("fill", 0)
    candidate = next(sid for sid in app.session.skills
                     if sid not in app.session.party[0].skills)
    app.catalog_cursor = list(app.session.skills).index(candidate)
    key(pyxel.KEY_C)
    assert app.state == "replace" and app.session.pending_replacements == [0]
    key(pyxel.KEY_F10)
    assert app.state == "replace" and app.overlay is None
    key(pyxel.KEY_X)
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.state == "archive" and app.overlay == "catalog"
    assert candidate in app.session.discovered_skills
    assert candidate not in app.session.mastered_skills
    key(pyxel.KEY_X)
    assert app.overlay is None and app.state == "archive"
    key(pyxel.KEY_X)
    assert app.state == "camp"

print(f"Archive UI passed: {calls} bounded text calls")
