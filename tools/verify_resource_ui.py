"""Finite stock UI: debug menus, field healing, exhaustion and camp return."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import font, text_width, FONT_HEIGHT

app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
output = ROOT / "verification/screenshots"
output.mkdir(parents=True, exist_ok=True)
calls = 0
real_text = pyxel.text


def bounded(x, y, value, color, selected_font):
    global calls
    assert selected_font is font()
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
    pyxel.screenshot(str(output / f"uses_{name}.png"), scale=4)


with patch.object(pyxel, "text", side_effect=bounded), patch.object(pyxel, "play"):
    key(pyxel.KEY_F12)
    assert app.overlay is None
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F12)
    assert app.overlay == "debug_skills"
    key(pyxel.KEY_RIGHT)
    for _ in range(5):
        key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    c = app.session.party[1]
    assert len(c.skills) == 6 and len(app.session.party[0].skills) == 1
    capture("01_debug")
    key(pyxel.KEY_UP)
    key(pyxel.KEY_Z)
    assert app.state == "replace" and app.session.pending_replacements == [1]
    new = c.pending_skill
    assert app.session.skills[new].rarity == "LEGEND"
    for _ in range(5):
        key(pyxel.KEY_DOWN)
    before = dict(c.skill_uses)
    capture("02_replace")
    key(pyxel.KEY_Z)
    capture("03_confirm")
    key(pyxel.KEY_X)
    assert before == c.skill_uses and not app.replacement_confirm
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.state == "camp" and app.overlay == "debug_skills"
    assert c.skill_uses[new] == app.session.skills[new].max_uses
    key(pyxel.KEY_UP)  # RARE or LEGEND, then decline it.
    key(pyxel.KEY_Z)
    assert app.state == "replace"
    before = dict(c.skill_uses)
    key(pyxel.KEY_X)
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert c.skill_uses == before and not app.session.pending_replacements
    for _ in range(3):
        key(pyxel.KEY_UP)
    key(pyxel.KEY_Z)
    assert all(set(c.skill_uses.values()) == {1} for c in app.session.party)
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert all(c.skill_uses[s] == app.session.skills[s].max_uses for c in app.session.party for s in c.skills)
    key(pyxel.KEY_F9)
    assert app.overlay is None and not app.session.debug
    key(pyxel.KEY_F12)
    assert app.overlay is None
    key(pyxel.KEY_Z)  # Enter dungeon.
    assert app.state == "explore"
    c = app.session.party[0]
    c.learn(app.session.skills["heal"])
    c.skill_uses["heal"] = 1
    app.info_character = 0
    key(pyxel.KEY_D)
    key(pyxel.KEY_Z)
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_C)
    assert app.state == "field_heal"
    key(pyxel.KEY_Z)  # Full HP never spends the last charge.
    assert c.skill_uses["heal"] == 1
    c.hp = 10
    capture("04_field_heal")
    key(pyxel.KEY_Z)
    assert c.hp == 15 and "heal" not in c.skills
    key(pyxel.KEY_Z)
    assert c.hp == 15
    key(pyxel.KEY_X)
    assert app.overlay == "info" and app.scroll == 0
    key(pyxel.KEY_D)
    for actor in app.session.party:
        for sid in actor.skills:
            actor.skill_uses[sid] = 1
    app.begin_encounter()
    for enemy in app.battle.enemies:
        enemy.hp = enemy.max_hp = 999
        enemy.strength = enemy.intellect = enemy.agility = 1
    key(pyxel.KEY_F12)
    assert app.overlay is None
    key(pyxel.KEY_Z)
    capture("05_last_charge")
    key(pyxel.KEY_X)
    key(pyxel.KEY_A)
    for _ in range(600):
        key(pyxel.KEY_Z)
        if app.state == "command":
            break
    assert app.state == "command" and c.skill_uses["punch"] == 30
    assert any("消滅" in line for line in app.battle.resource_events)
    app.battle.outcome = "VICTORY"
    app.session.settings["spark_chance"] = 0
    app.state, app.delay = "resolve", 0
    app.pending.clear()
    key()
    capture("06_exhausted_result")
    for _ in range(100):
        key(pyxel.KEY_Z)
        if app.state == "explore":
            break
    assert app.state == "explore"
    before = [dict(c.skill_uses) for c in app.session.party]
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F11)
    assert app.state == "return_result"
    key(pyxel.KEY_Z)
    assert app.state == "camp"
    assert before == [c.skill_uses for c in app.session.party]
    assert all(c.hp == c.max_hp for c in app.session.party)
    for c in app.session.party:
        c.name = "非常に長い日本語の名前"
    key(pyxel.KEY_F12)
    capture("07_long_debug_name")
print(f"Resource UI passed: {calls} bounded text calls")
