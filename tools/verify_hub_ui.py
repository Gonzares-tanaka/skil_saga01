"""Headless hub layout, editable art, gamepad routing and existing facility actions."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel

from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.hub import (HUB_DESCRIPTIONS, HUB_FACILITIES, HUB_ICONS, HUB_MENUS, HUB_PICTURES,
                     HUB_IMAGE_BANK, HUB_PICTURE_SIZE)
from rpg.text import FONT_HEIGHT, font, text_width


app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
assert all(text_width(description) <= 84 for description in HUB_DESCRIPTIONS)
assert all(text_width(">" + label) <= 84 for menu in HUB_MENUS for label in menu)
assert len({(x + dx, y + dy) for x, y in HUB_PICTURES
            for dy in range(HUB_PICTURE_SIZE) for dx in range(HUB_PICTURE_SIZE)}) == 5 * HUB_PICTURE_SIZE ** 2
shots = ROOT / "verification/screenshots"
shots.mkdir(parents=True, exist_ok=True)
real_text = pyxel.text
real_blt = pyxel.blt
drawn = []
blits = []


def bounded_text(x, y, value, color, selected_font):
    assert selected_font is font()
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    drawn.append((x, y, value))
    real_text(x, y, value, color, selected_font)


def record_blt(*args, **kwargs):
    blits.append(args)
    real_blt(*args, **kwargs)


def press(button):
    with patch.object(pyxel, "btnp", side_effect=lambda code, *args: code == button), \
         patch.object(pyxel, "btn", return_value=False):
        app.update()
    app.draw()


def screenshot(name):
    app.draw()
    pyxel.screenshot(str(shots / f"hub_{name}.png"), scale=4)


with patch.object(pyxel, "text", side_effect=bounded_text), \
     patch.object(pyxel, "blt", side_effect=record_blt), \
     patch.object(pyxel, "play"):
    assert app.state == "camp"
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "camp"
    for index, name in enumerate(HUB_FACILITIES):
        if index:
            press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        assert app.camp_cursor == index
        drawn.clear()
        blits.clear()
        screenshot(name.lower())
        assert sum(args[2] == HUB_IMAGE_BANK and args[5:7] == (16, 16) for args in blits) == 5
        assert any(args[0:2] == (94, 20) and args[2] == HUB_IMAGE_BANK
                   and args[3:7] == (*HUB_PICTURES[index], HUB_PICTURE_SIZE, HUB_PICTURE_SIZE)
                   for args in blits)
        assert any(value.endswith(name) and x == 24 for x, _, value in drawn)
        for x, y, w, h in ((*HUB_ICONS[index], 16, 16),
                           (*HUB_PICTURES[index], HUB_PICTURE_SIZE, HUB_PICTURE_SIZE)):
            assert any(pyxel.images[HUB_IMAGE_BANK].pget(x + dx, y + dy)
                       for dy in range(h) for dx in range(w))

    app.camp_cursor = 0
    press(pyxel.GAMEPAD1_BUTTON_A)  # GUILD
    assert app.state == "facility"
    screenshot("guild_menu")
    assert any(args[0:2] == (94, 20) and args[2] == HUB_IMAGE_BANK
               and args[3:7] == (*HUB_PICTURES[0], HUB_PICTURE_SIZE, HUB_PICTURE_SIZE)
               for args in blits)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.overlay == "info"
    press(pyxel.GAMEPAD1_BUTTON_B)
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.overlay == "help"
    press(pyxel.GAMEPAD1_BUTTON_B)
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "camp"

    app.camp_cursor = 1
    press(pyxel.GAMEPAD1_BUTTON_A)  # TRAINING
    screenshot("training_menu")
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "archive"
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "facility"
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "relearn_character"
    press(pyxel.GAMEPAD1_BUTTON_B)
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "camp"

    app.camp_cursor = 2
    press(pyxel.GAMEPAD1_BUTTON_A)  # PUB
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "quest_board"
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "facility"
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "pub"
    app.session.treasure.banked = 20
    before = app.session.treasure.banked
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "field_event" and app.session.treasure.banked < before
    while app.state == "field_event":
        press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "pub"
    press(pyxel.GAMEPAD1_BUTTON_B)
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "camp"

    app.camp_cursor = 3
    press(pyxel.GAMEPAD1_BUTTON_A)  # SHOP
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "shop"
    before = app.session.inventory.counts["POTION"]
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.session.inventory.counts["POTION"] == before + 1
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "facility"
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "camp"

    app.camp_cursor = 4
    press(pyxel.GAMEPAD1_BUTTON_A)  # DUNGEON
    assert app.state == "explore" and app.dungeon.floor == 0

print("PASS: five icons/pictures, bounds, virtual D-PAD/A/B and all five facility routes")
