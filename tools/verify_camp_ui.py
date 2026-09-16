"""Exercise treasure, camp purchases and RETURN through real Pyxel UI."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import text_width, FONT_HEIGHT

app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
s = app.session
output = ROOT / "verification/screenshots"
output.mkdir(parents=True, exist_ok=True)
real_text = pyxel.text
calls = 0


def bounded(x, y, value, color, selected_font):
    global calls
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    calls += 1
    real_text(x, y, value, color, selected_font)


def key(code=None):
    with patch.object(pyxel, "btnp", side_effect=lambda k, *args: k == code), patch.object(pyxel, "btn", return_value=False):
        app.update()
    app.draw()


def capture(name):
    app.notice_timer = 0
    app.draw()
    pyxel.screenshot(str(output / f"camp_{name}.png"), scale=4)


with patch.object(pyxel, "text", side_effect=bounded), patch.object(pyxel, "play"):
    key(pyxel.KEY_F2)
    assert app.overlay is None
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F2)
    assert app.overlay == "treasure_debug"
    key(pyxel.KEY_Z)
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert (s.treasure.unbanked, s.treasure.banked) == (5, 5)
    capture("debug")
    key(pyxel.KEY_X)
    key(pyxel.KEY_F9)
    s.discovered_skills.update(("return", "fire"))
    for _ in range(3):
        key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert app.state == "relearn_character"
    key(pyxel.KEY_Z)
    assert app.state == "relearn_list"
    app.relearn_cursor = [k.id for k in s.relearn_candidates()].index("return")
    capture("list")
    key(pyxel.KEY_Z)
    capture("confirm")
    key(pyxel.KEY_X)
    assert s.treasure.banked == 5
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert s.party[0].skill_uses["return"] == 1 and s.treasure.banked == 2
    key(pyxel.KEY_X)
    key(pyxel.KEY_X)
    app.camp_cursor = 0
    key(pyxel.KEY_Z)
    assert app.state == "explore"
    key(pyxel.KEY_X)
    for _ in range(3):
        key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert app.state == "field_return"
    capture("caster")
    key(pyxel.KEY_Z)
    assert app.state == "return_result"
    assert (s.treasure.unbanked, s.treasure.banked) == (0, 7)
    assert "return" in s.mastered_skills and "return" not in s.party[0].skills
    capture("returned")
    key(pyxel.KEY_Z)
    assert app.state == "camp"
    c = s.party[0]
    for skill in s.skills.values():
        if skill.id not in ("fire", "return") and skill.id not in c.skills:
            c.learn(skill)
        if len(c.skills) == 6:
            break
    app.state, app.relearn_skill = "relearn_confirm", "fire"
    before = dict(c.skill_uses)
    key(pyxel.KEY_Z)
    assert app.state == "replace" and s.treasure.banked == 7
    capture("replace")
    key(pyxel.KEY_X)
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.state == "relearn_list" and c.skill_uses == before and s.treasure.banked == 7
    app.state = "relearn_confirm"
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.state == "relearn_list"
    assert c.skill_uses["fire"] == s.skills["fire"].relearn_uses
    assert s.treasure.banked == 7 - s.skills["fire"].relearn_cost
    app.enter_camp(returned=True)
    assert app.return_secured == 0
    capture("empty_return")

print(f"PASS: camp purchase/cancel/replacement, RETURN/mastery/banking, DEBUG, {calls} bounded text draws")
