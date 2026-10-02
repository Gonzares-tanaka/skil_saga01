"""Render all five maps and exercise the switch using only the existing pad buttons."""
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import text_width, FONT_HEIGHT
from rpg.tiles import TILE_DOOR, TILE_SWITCH, TILE_BOSS, TILE_HEAL_POINT

app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True, start_at_title=False)
d, s = app.dungeon, app.session
output = ROOT / 'verification' / 'screenshots'
output.mkdir(parents=True, exist_ok=True)
real_text, draws = pyxel.text, []


def bounded(x, y, value, color, font):
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    draws.append(value)
    real_text(x, y, value, color, font)


def press(button=None):
    with patch.object(pyxel, 'btnp', side_effect=lambda code, *args: code == button), patch.object(pyxel, 'btn', return_value=False):
        app.update()
    app.draw()


def close_event():
    for _ in range(20):
        if app.state != 'field_event':
            return
        press(pyxel.GAMEPAD1_BUTTON_A)
    raise AssertionError('Event failed to end')


def shot(name):
    app.draw()
    pyxel.screenshot(str(output / f'phase5_{name}.png'), scale=4)


with patch.object(pyxel, 'text', side_effect=bounded), patch.object(pyxel, 'play'):
    app.enter_dungeon()
    d.settings['encounter_chance'] = 0
    for floor in range(5, 10):
        d.debug_floor(floor)
        app.draw()
        shot(f'B{floor+1}_arrival')
        preview = pyxel.Image(192, 192)
        preview.bltm(0, 0, d.maps[floor], 0, 0, 192, 192)
        preview.save(str(output / f'phase5_B{floor+1}_tilemap'), scale=2)
    d.debug_floor(6)
    door = d.positions(6, TILE_DOOR)[0]
    d.x, d.y = door[0]-1, door[1]
    press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
    assert (d.x, d.y) == (door[0]-1, door[1])
    shot('door_closed')
    sx, sy = d.positions(6, TILE_SWITCH)[0]
    d.x, d.y = sx, sy-1
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    assert not d.activated_switches and app.state == 'explore'
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert d.activated_switches == {6} and app.state == 'field_event'
    shot('switch_ON')
    close_event()
    d.x, d.y = door[0]-1, door[1]
    shot('door_open')
    press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
    assert (d.x, d.y) == door and app.state == 'explore'
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == 'menu'
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == 'explore'
    # A real B9 spring: no uses/items/KO recovery, once per expedition.
    d.debug_floor(8)
    hx, hy = d.positions(8, TILE_HEAL_POINT)[0]
    for actor in s.party:
        actor.hp = 1
    s.party[0].hp = 0
    uses = [dict(c.skill_uses) for c in s.party]
    inventory = dict(s.inventory.counts)
    d.x, d.y = hx-1, hy
    press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
    close_event()
    assert [c.hp for c in s.party] == [0] + [c.max_hp for c in s.party[1:]]
    assert uses == [dict(c.skill_uses) for c in s.party] and inventory == s.inventory.counts
    s.party[1].hp = 1
    press(pyxel.GAMEPAD1_BUTTON_A)
    close_event()
    assert s.party[1].hp == 1
    shot('B9_spring_used')
    # Boss contact presents text first; B permits stepping away to reconsider RETURN.
    d.debug_floor(9)
    bx, by = d.positions(9, TILE_BOSS)[0]
    d.x, d.y = bx, by+1
    press(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
    assert app.state == 'boss_message' and app.battle is None
    shot('B10_boss_message')
    press(pyxel.GAMEPAD1_BUTTON_B)
    assert app.state == 'explore'
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    for actor in s.party:
        actor.recover()
    s.party[0].learn(s.skills['return'])
    press(pyxel.GAMEPAD1_BUTTON_B)
    app.menu_cursor = 3
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'return_result'
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'camp'
    app.enter_dungeon()
    assert not d.activated_switches and not app.exploration.springs
    # QUEST Lv2 uses the new editable candidates; no changes to payment/gates.
    d.defeated_bosses.add(4)
    app.exploration.accept(2)
    d.floor, d.x, d.y = app.exploration.target
    press(pyxel.GAMEPAD1_BUTTON_A)
    close_event()
    assert app.exploration.surveyed
    app.enter_camp(returned=True)
    assert 2 in app.exploration.completed
    assert any('スイッチON' in value for value in draws)

print(f'PASS: pad-only switch/door, B9 spring, B10 boss/RETURN, quest Lv2; {len(draws)} bounded text draws')
