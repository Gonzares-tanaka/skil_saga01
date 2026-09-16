"""New debug operations, support archive/effects and editable boss pagination."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Action
from rpg.text import text_width, FONT_HEIGHT
from rpg.tiles import TILE_BOSS

app = DungeonApp(Session(*load_content(), seed=9), run=False, headless=True)
output = ROOT / 'verification/screenshots'
output.mkdir(parents=True, exist_ok=True)
drawn, calls = [], 0
real_text = pyxel.text


def bounded(x, y, value, color, font):
    global calls
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    drawn.append(value)
    calls += 1
    real_text(x, y, value, color, font)


def key(code=None):
    with patch.object(pyxel, 'btnp', side_effect=lambda k, *a: k == code), patch.object(pyxel, 'btn', return_value=False):
        app.update()
    app.draw()


def shot(name):
    app.notice_timer = 0
    app.draw()
    pyxel.screenshot(str(output / f'depth_{name}.png'), scale=4)


with patch.object(pyxel, 'text', side_effect=bounded), patch.object(pyxel, 'play'):
    key(pyxel.KEY_F4)
    assert app.overlay is None
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F4)
    assert app.overlay == 'dungeon_debug'
    assert app.notice_timer == 0
    shot('01_floor1_debug')
    assert any('15.0%' in s for s in drawn)
    key(pyxel.KEY_UP)
    assert app.floor_cursor == 14
    assert any('30.0%' in s for s in drawn)
    shot('02_floor15_debug')
    for keycode in (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3):
        key(keycode)
    assert app.dungeon.defeated_bosses == {4, 9, 14}
    shot('03_flags')
    for keycode in (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3):
        key(keycode)
    assert not app.dungeon.defeated_bosses
    key(pyxel.KEY_Z)
    assert app.state == 'explore' and app.dungeon.floor == 14
    key(pyxel.KEY_F4)
    key(pyxel.KEY_B)
    assert app.dungeon.tile(14, app.dungeon.x, app.dungeon.y) == TILE_BOSS
    assert app.state == 'explore'
    key(pyxel.KEY_F11)
    assert app.state == 'return_result'
    key(pyxel.KEY_Z)
    for floor in (4, 9, 14, 4):
        key(pyxel.KEY_F8)
        assert app.dungeon.floor == floor
        assert app.dungeon.tile(floor, app.dungeon.x, app.dungeon.y) == TILE_BOSS
    # F10 obtains the exact support skill with normal stock and archive registration.
    key(pyxel.KEY_F10)
    for sid in ('armor_break', 'focus'):
        app.catalog_cursor = list(app.session.skills).index(sid)
        key(pyxel.KEY_C)
        key(pyxel.KEY_V)
        assert app.session.party[0].skill_uses[sid] == 1
        assert sid in app.session.discovered_skills and sid not in app.session.mastered_skills
    shot('04_support_catalog')
    key(pyxel.KEY_X)
    # Long data-driven messages wrap without loss; only the last Z starts a fight.
    original_message = app.dungeon.boss_data['message']
    messages = ['編集したボスの会話です。' * 15, '最後の行です。']
    app.dungeon.boss_data['message'] = messages
    key(pyxel.KEY_Z)
    assert app.state == 'boss_message' and app.battle is None
    assert ''.join(app.message_lines) == ''.join(messages)
    shot('05_long_message')
    key(pyxel.KEY_X)
    assert app.state == 'explore' and app.battle is None
    key(pyxel.KEY_Z)
    pages = (len(app.message_lines) + 7) // 8
    for _ in range(pages - 1):
        key(pyxel.KEY_Z)
        assert app.state == 'boss_message'
    key(pyxel.KEY_Z)
    assert app.state == 'command'
    app.dungeon.boss_data['message'] = original_message
    # Natural skill actions spend the last charges; the inspector freezes combat.
    app.battle._party_action(Action(0, 'SKILL', 0, 'armor_break'))
    app.session.party[0].cooldowns.clear()
    app.battle._party_action(Action(0, 'SKILL', 0, 'focus'))
    assert {'armor_break', 'focus'} <= app.session.mastered_skills
    key(pyxel.KEY_F3)
    assert app.overlay == 'effects'
    assert app.notice_timer == 0
    assert app.battle.enemies[0].effects['armor_break'] == (.7, 3)
    shot('06_enemy_effect')
    key(pyxel.KEY_DOWN)
    shot('07_ally_effect')
    assert app.session.party[0].effects['focus'] == (1.5, 3)
    key(pyxel.KEY_F9)
    assert app.overlay is None and not app.session.debug
    # A defeat clears all effects, preserves boss progress, and returns to camp.
    app.dungeon.defeated_bosses.add(9)
    app.battle.outcome = 'DEFEAT'
    app.session.settle()
    app.finish_results()
    assert app.state == 'camp' and app.dungeon.defeated_bosses == {9}
    assert not app.session.party[0].effects and not app.battle.enemies[0].effects
    app.state, app.archive_page = 'archive', 1
    app.archive_cursor = list(app.session.skills).index('armor_break')
    drawn.clear()
    shot('08_support_archive')
    assert any('TYPE SUPPORT' in s for s in drawn)
    app.dungeon.defeated_bosses.add(14)
    app.enter_camp()
    key(pyxel.KEY_Z)
    assert app.state == 'clear'  # A debug-marked final boss must not crash camp entry.

print(f'Depth UI passed: {calls} bounded text calls')
