"""Headless title, no-save, editable introduction and hub-to-battle check."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel

from rpg.battle import Session
from rpg.battle_transition import BATTLE_TRANSITION_HOLD_FRAMES, BATTLE_TRANSITION_FRAMES
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.opening import (GAME_TITLE, TITLE_FADE_FRAMES, HUB_PREVIEW_FRAMES,
                         load_intro_pages, load_hub_intro_lines)
from rpg.text import FONT_HEIGHT, font, text_width


app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
assert app.state == "title" and GAME_TITLE == "Skill Seekers!!~深淵のアムリタ~"
assert len(app.intro_pages) == 4
shots = ROOT / "verification" / "screenshots"
shots.mkdir(parents=True, exist_ok=True)
real_text = pyxel.text
drawn = []
positions = []


def bounded_text(x, y, value, color, selected_font):
    assert selected_font is font()
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    drawn.append(value)
    positions.append((x, y, value, color))
    real_text(x, y, value, color, selected_font)


def press(button=None, held=False):
    with patch.object(pyxel, "btnp", side_effect=lambda code, *args: code == button), \
         patch.object(pyxel, "btn", return_value=held):
        app.update()
    app.draw()


with patch.object(pyxel, "text", side_effect=bounded_text), \
     patch.object(pyxel, "play", side_effect=RuntimeError("audio unavailable")), \
     patch.object(pyxel, "playm", side_effect=RuntimeError("audio unavailable")):
    app.draw()
    assert "Skill Seekers!!" in drawn and "~深淵のアムリタ~" in drawn
    for x, _, value, _ in positions:
        if value.strip() in ("> はじめから", "つづきから"):
            assert abs(2 * x + text_width(value) - pyxel.width) <= 1
    pyxel.screenshot(str(shots / "opening_title.png"), scale=4)
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "title"
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    assert app.title_cursor == 1
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "title_no_save"
    drawn.clear()
    app.draw()
    assert "セーブデータがありません" in drawn
    pyxel.screenshot(str(shots / "opening_no_save.png"), scale=4)
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "title"
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "title_no_save"
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "title"
    press(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
    assert app.title_cursor == 0

    # NEW GAME must replace every mutable run-owned system.
    original_party = [(a.max_hp, a.strength, tuple(a.skills)) for a in app.session.party]
    app.session.party[0].strength += 99
    app.session.treasure.banked = 77
    app.session.inventory.counts["POTION"] = 0
    app.session.mastered_skills.add("PUNCH")
    app.exploration.completed.add("TEST")
    app.dungeon.defeated_bosses.add(4)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "title_fade" and app.title_fade_remaining == TITLE_FADE_FRAMES
    assert [(a.max_hp, a.strength, tuple(a.skills)) for a in app.session.party] == original_party
    assert app.session.treasure.banked == 0 and not app.session.mastered_skills
    assert app.session.inventory.counts["POTION"] > 0
    assert not app.exploration.completed and not app.dungeon.defeated_bosses
    for _ in range(TITLE_FADE_FRAMES):
        press(pyxel.GAMEPAD1_BUTTON_A, held=True)
    assert app.state == "intro" and app.intro_page == 0
    press(pyxel.GAMEPAD1_BUTTON_A, held=True)
    assert app.intro_page == 0  # Held title input cannot skip the first page.
    press()  # Release frame.
    drawn.clear()
    positions.clear()
    app.draw()
    assert "王国に伝わる秘宝" in drawn
    assert all(value in app.intro_pages[0] for value in drawn)
    assert pyxel.screen.pget(0, 0) == 3
    assert all(color == 0 and abs(2 * x + text_width(value) - pyxel.width) <= 1
               for x, _, value, color in positions)
    assert [y for _, y, _, _ in positions] == [49, 63]
    pyxel.screenshot(str(shots / "opening_intro1.png"), scale=4)
    for page in range(4):
        press(pyxel.GAMEPAD1_BUTTON_B)
        assert app.state == "intro" and app.intro_page == page
        press(pyxel.GAMEPAD1_BUTTON_A)
        if page < 3:
            assert app.state == "intro" and app.intro_page == page + 1
        else:
            assert app.state == "hub_preview" and not app.hub_intro_shown
            assert app.hub_preview_remaining == HUB_PREVIEW_FRAMES
    drawn.clear()
    app.draw()
    assert all(any(name in value for value in drawn)
               for name in ("GUILD", "TRAINING", "PUB", "SHOP", "DUNGEON"))
    pyxel.screenshot(str(shots / "opening_hub_preview.png"), scale=4)
    preview_pixels = tuple(pyxel.screen.pget(x, y)
                           for y in range(pyxel.height) for x in range(pyxel.width))
    for _ in range(HUB_PREVIEW_FRAMES - 1):
        press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, held=True)
        assert app.state == "hub_preview" and app.camp_cursor == 0
    press(pyxel.GAMEPAD1_BUTTON_A, held=True)
    assert app.state == "hub_intro" and app.camp_cursor == 0
    press(pyxel.GAMEPAD1_BUTTON_A, held=True)
    assert app.state == "hub_intro" and not app.hub_intro_shown
    press()  # The preview input must be released before the guide accepts A.
    drawn.clear()
    positions.clear()
    app.draw()
    assert drawn == [line for line in app.hub_intro_lines if line]
    assert pyxel.screen.pget(0, 0) == 3
    assert all(color == 0 and abs(2 * x + text_width(value) - pyxel.width) <= 1
               for x, _, value, color in positions)
    assert [y for _, y, _, _ in positions] == [12, 23, 45, 56, 78, 89, 100]
    pyxel.screenshot(str(shots / "opening_hub_intro.png"), scale=4)
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == "hub_intro"
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "camp" and app.hub_intro_shown
    press(pyxel.GAMEPAD1_BUTTON_A, held=True)
    assert app.state == "camp" and app.camp_cursor == 0
    press()
    pyxel.screenshot(str(shots / "opening_hub.png"), scale=4)
    assert preview_pixels == tuple(pyxel.screen.pget(x, y)
                                   for y in range(pyxel.height) for x in range(pyxel.width))
    for _ in range(4):
        press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    assert app.camp_cursor == 4
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "explore"
    app.handle_event("battle", "")
    assert app.state == "battle_transition"
    for _ in range(BATTLE_TRANSITION_HOLD_FRAMES + BATTLE_TRANSITION_FRAMES):
        press()
    assert app.state == "command"
    app.state = "explore"
    app.handle_event("base", "")
    assert app.state == "return_result" and app.hub_intro_shown
    app.enter_camp(defeated=True)
    assert app.state == "camp" and app.hub_intro_shown
    app.state = "title"
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "title_fade" and not app.hub_intro_shown
    for _ in range(TITLE_FADE_FRAMES):
        press()
    press()  # Release the title confirmation before page turning.
    for _ in range(len(app.intro_pages)):
        press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == "hub_preview"
    for _ in range(HUB_PREVIEW_FRAMES):
        press()
    assert app.state == "hub_intro"

with tempfile.TemporaryDirectory() as temp:
    source = Path(temp) / "intro.json"
    data = json.loads((ROOT / "data" / "intro.json").read_text(encoding="utf-8"))
    data["pages"][0][0] = "編集した冒頭"
    data["pages"].append(["追加した5ページ目"])
    data["hub_intro"][0] = "編集した城下町の説明"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    edited_pages = load_intro_pages(source)
    edited_hub_intro = load_hub_intro_lines(source)
    assert len(edited_pages) == 5 and edited_pages[0][0] == "編集した冒頭"
    assert edited_hub_intro[0] == "編集した城下町の説明"
    app.intro_pages, app.intro_page, app.state = edited_pages, 4, "intro"
    drawn.clear()
    positions.clear()
    with patch.object(pyxel, "text", side_effect=bounded_text):
        app.draw()
    assert "追加した5ページ目" in drawn
    assert abs(2 * positions[0][0] + text_width(positions[0][2]) - pyxel.width) <= 1
    app.intro_page = 0
    drawn.clear()
    with patch.object(pyxel, "text", side_effect=bounded_text):
        app.draw()
    assert "編集した冒頭" in drawn
    app.hub_intro_lines, app.state = edited_hub_intro, "hub_intro"
    drawn.clear()
    positions.clear()
    with patch.object(pyxel, "text", side_effect=bounded_text):
        app.draw()
    assert "編集した城下町の説明" in drawn
    assert all(abs(2 * x + text_width(value) - pyxel.width) <= 1
               for x, _, value, _ in positions)

print(f"PASS: centered title/story, {HUB_PREVIEW_FRAMES}-frame input-free hub preview, guide input release, first-arrival only, resets and battle transition")
