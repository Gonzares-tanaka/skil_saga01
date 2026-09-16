"""Real Pyxel render/input integration checks for the exploration loop."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import font, text_width, FONT_HEIGHT
from rpg.tiles import TILE_BOSS, TILE_CHEST, TILE_FLOOR, TILE_ENTRANCE, TILE_STAIRS_DOWN


app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
output = ROOT / "verification" / "screenshots"
output.mkdir(parents=True, exist_ok=True)
real_text, real_bltm = pyxel.text, pyxel.bltm
calls = 0
map_calls = 0


def bounded_text(x, y, value, color, selected_font):
    global calls
    assert selected_font is font()
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    calls += 1
    real_text(x, y, value, color, selected_font)


def tilemap_draw(*args):
    global map_calls
    map_calls += 1
    real_bltm(*args)


def key(code=None):
    with patch.object(pyxel, "btnp", side_effect=lambda k, *args: k == code), patch.object(pyxel, "btn", return_value=False):
        app.update()
    app.draw()


def capture(name):
    app.notice_timer = 0
    app.draw()
    pyxel.screenshot(str(output / f"dungeon_{name}.png"), scale=4)


def finish_pages():
    for _ in range(100):
        if app.state != "result":
            return
        key(pyxel.KEY_Z)
    raise AssertionError("Results did not finish")


with patch.object(pyxel, "text", side_effect=bounded_text), patch.object(pyxel, "bltm", side_effect=tilemap_draw), patch.object(pyxel, "play"):
    assert app.state == "camp"
    capture("01_camp")
    key(pyxel.KEY_Z)
    assert app.state == "explore" and app.dungeon.floor == 0
    initial = app.dungeon.x, app.dungeon.y
    key(pyxel.KEY_LEFT)
    assert (app.dungeon.x, app.dungeon.y) == initial
    capture("02_floor1")
    key(pyxel.KEY_RIGHT)
    assert (app.dungeon.x, app.dungeon.y) != initial
    key(pyxel.KEY_X)
    capture("03_menu")
    key(pyxel.KEY_Z)
    assert app.overlay == "info"
    key(pyxel.KEY_X)
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert app.overlay == "info" and app.info_tab == 1
    key(pyxel.KEY_X)
    key(pyxel.KEY_DOWN)
    key(pyxel.KEY_Z)
    assert app.state == "items"
    c = app.session.party[0]
    c.hp = 5
    key(pyxel.KEY_Z)
    assert c.hp == 35 and app.dungeon.potions == 1
    capture("04_items")
    key(pyxel.KEY_X)
    key(pyxel.KEY_X)
    assert app.state == "explore"
    # A real encounter and natural Battle resolution, with wounds carried over.
    for actor in app.session.party:
        actor.skills.clear()
        actor.skill_uses.clear()
        for sid in list(app.session.skills)[:6]:
            actor.learn(app.session.skills[sid])
    app.dungeon.settings["encounter_chance"] = 1
    app.dungeon.grace = 0
    app.dungeon.x, app.dungeon.y = 2, 1
    key(pyxel.KEY_RIGHT)
    assert app.state == "command"
    origin = app.dungeon.floor, app.dungeon.x, app.dungeon.y
    assert c.hp == 35
    capture("05_battle")
    app.session.settings["spark_chance"] = 1
    for rates in app.session.settings["growth_rates"].values():
        rates.update(HP=1, STR=1, AGI=1, INT=1)
    for _ in range(3000):
        key(pyxel.KEY_A if app.state == "command" else pyxel.KEY_Z)
        if app.state == "result":
            break
    assert app.battle.outcome == "VICTORY"
    hp = [actor.hp for actor in app.session.party]
    assert all(actor.skills for actor in app.session.party)
    capture("06_growth")
    finish_pages()
    assert app.state == "replace" and len(app.session.pending_replacements) == 4
    learned = app.session.party[0].pending_skill
    grown_stats = [(actor.max_hp, actor.strength, actor.agility, actor.intellect) for actor in app.session.party]
    for _ in range(5):
        key(pyxel.KEY_DOWN)
    capture("06b_replace_sixth")
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.session.party[0].skills[5] == learned
    for _ in range(3):
        key(pyxel.KEY_X)  # Select decline, then explicitly confirm.
        key(pyxel.KEY_Z)
        key(pyxel.KEY_Z)
    assert not app.session.pending_replacements and app.state == "result"
    finish_pages()
    assert app.state == "explore"
    assert grown_stats == [(actor.max_hp, actor.strength, actor.agility, actor.intellect) for actor in app.session.party]
    assert all(len(actor.skills) == 6 for actor in app.session.party)
    assert (app.dungeon.floor, app.dungeon.x, app.dungeon.y) == origin
    assert [actor.hp for actor in app.session.party] == hp
    assert any(actor.hp < actor.max_hp for actor in app.session.party)
    capture("07_return_wounded")
    # Walking back into the actual entrance tile heals and preserves possessions.
    app.dungeon.settings["encounter_chance"] = 0
    app.dungeon.x, app.dungeon.y = 2, 1
    app.dungeon.treasure.unbanked = 5
    app.dungeon.treasure.banked = 7
    before = app.dungeon.potions, list(c.skills), c.strength
    key(pyxel.KEY_LEFT)
    assert app.state == "return_result"
    key(pyxel.KEY_Z)
    assert app.state == "camp"
    assert all(actor.hp == actor.max_hp for actor in app.session.party)
    assert before == (app.dungeon.potions, c.skills, c.strength)
    assert (app.dungeon.treasure.unbanked, app.dungeon.treasure.banked) == (0, 12)
    key(pyxel.KEY_Z)
    # Chests and all five maps draw from the resource.
    app.dungeon.x, app.dungeon.y = app.dungeon.positions(0, TILE_CHEST)[0]
    key(pyxel.KEY_Z)
    capture("08_open_chest")
    for floor in range(1, 5):
        app.dungeon.x, app.dungeon.y = app.dungeon.find(floor - 1, TILE_STAIRS_DOWN)
        key(pyxel.KEY_Z)
        assert app.dungeon.floor == floor
        capture(f"floor{floor + 1}")
    # Debug controls are gated, including in the boss floor.
    key(pyxel.KEY_F7)
    key(pyxel.KEY_F11)
    assert app.state == "explore" and app.dungeon.floor == 4
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F5)
    assert app.dungeon.floor == 3
    key(pyxel.KEY_F6)
    assert app.dungeon.floor == 4
    key(pyxel.KEY_F10)
    assert app.overlay == "catalog"
    for _ in range(len(app.session.skills) - 1):
        key(pyxel.KEY_DOWN)
    capture("09_all_skills")
    key(pyxel.KEY_X)
    key(pyxel.KEY_F11)
    assert app.state == "return_result"
    key(pyxel.KEY_Z)
    assert app.state == "camp"
    key(pyxel.KEY_F8)
    assert app.state == "explore" and app.dungeon.floor == 4
    # Natural defeat by the fixed boss, then safe camp return.
    for actor in app.session.party:
        actor.hp = 1
    app.dungeon.x, app.dungeon.y = app.dungeon.find(4, TILE_BOSS)
    key(pyxel.KEY_Z)
    assert app.state == "boss_message"
    capture("10_boss_message")
    key(pyxel.KEY_Z)
    assert app.state == "command" and len(app.battle.enemies) == 1
    capture("10_boss_battle")
    for _ in range(3000):
        key(pyxel.KEY_A if app.state == "command" else pyxel.KEY_Z)
        if app.state == "result":
            break
    assert app.battle.outcome == "DEFEAT"
    capture("11_defeat")
    finish_pages()
    assert app.state == "camp"
    assert all(actor.hp == actor.max_hp for actor in app.session.party)
    # Debug-prepared successful boss battle, exercising normal battle rules.
    key(pyxel.KEY_F8)
    for actor in app.session.party:
        actor.strength = 80
    app.dungeon.x, app.dungeon.y = app.dungeon.find(4, TILE_BOSS)
    key(pyxel.KEY_Z)
    assert app.state == "boss_message"
    key(pyxel.KEY_Z)
    for _ in range(3000):
        key(pyxel.KEY_A if app.state == "command" else pyxel.KEY_Z)
        if app.state == "result":
            break
    assert app.battle.outcome == "VICTORY"
    finish_pages()
    # A boss victory can also queue new skills when all slots are full.
    if app.state == "replace":
        assert not app.dungeon.cleared
        for _ in range(len(app.session.pending_replacements)):
            key(pyxel.KEY_X)
            key(pyxel.KEY_Z)
            key(pyxel.KEY_Z)
        finish_pages()
    assert app.state == "boss_after" and not app.dungeon.cleared
    assert app.dungeon.defeated_bosses == {4}
    capture("12_boss5_after")
    key(pyxel.KEY_Z)
    assert app.state == "explore"
    for floor in range(5, 15):
        app.dungeon.x, app.dungeon.y = app.dungeon.find(floor - 1, TILE_STAIRS_DOWN)
        key(pyxel.KEY_Z)
        assert app.dungeon.floor == floor
        capture(f"floor{floor + 1}")
        if floor in (9, 14):
            for actor in app.session.party:
                actor.hp = actor.max_hp = 300
                actor.strength = actor.intellect = 80
            if floor == 9:
                app.dungeon.x, app.dungeon.y = app.dungeon.find(floor, TILE_STAIRS_DOWN)
                key(pyxel.KEY_Z)
                assert app.dungeon.floor == 9 and app.state == "explore"
            app.dungeon.x, app.dungeon.y = app.dungeon.find(floor, TILE_BOSS)
            key(pyxel.KEY_Z)
            assert app.state == "boss_message"
            capture(f"boss{floor + 1}_message")
            key(pyxel.KEY_Z)
            assert app.state == "command"
            for _ in range(3000):
                key(pyxel.KEY_A if app.state == "command" else pyxel.KEY_Z)
                if app.state == "result":
                    break
            assert app.battle.outcome == "VICTORY"
            finish_pages()
            if app.state == "replace":
                for _ in range(len(app.session.pending_replacements)):
                    key(pyxel.KEY_X)
                    key(pyxel.KEY_Z)
                    key(pyxel.KEY_Z)
                finish_pages()
            assert app.state == "boss_after"
            assert floor in app.dungeon.defeated_bosses
            capture(f"boss{floor + 1}_after")
            key(pyxel.KEY_Z)
    assert app.state == "clear" and app.dungeon.cleared
    capture("12_clear")
    key(pyxel.KEY_Z)
    key(pyxel.KEY_F8)
    assert app.state == "clear"
    key(pyxel.KEY_D)
    assert app.overlay == "info"
    key(pyxel.KEY_D)
    key(pyxel.KEY_H)
    capture("13_help")
    key(pyxel.KEY_H)
    # Long edited Japanese names and large inventories stay inside the screen.
    for actor in app.session.party:
        actor.name = "非常に長い日本語のキャラクター名"
        actor.hp = actor.max_hp = 12345
    app.dungeon.treasure.unbanked = 1234567
    for state in ("camp", "explore", "menu", "items", "clear"):
        app.state = state
        app.draw()
assert map_calls > 0
print(f"Dungeon UI passed: {calls} bounded text calls / {map_calls} Tilemap draws")
