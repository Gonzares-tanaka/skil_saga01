"""Real Pyxel rendering + injected input for new field and mastery flows."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import text_width, FONT_HEIGHT
from rpg.tiles import TILE_FLOOR, TILE_HEAL_POINT

app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
s, d, e = app.session, app.dungeon, app.exploration
output = ROOT / 'verification/screenshots'
output.mkdir(parents=True, exist_ok=True)
original_text, draws = pyxel.text, []


def bounded(x, y, value, color, font):
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    draws.append(value)
    original_text(x, y, value, color, font)


def key(code=None):
    with patch.object(pyxel, 'btnp', side_effect=lambda k, *a: k == code), patch.object(pyxel, 'btn', return_value=False):
        app.update()
    app.draw()


def close_event():
    for _ in range(20):
        if app.state != 'field_event':
            return
        key(pyxel.GAMEPAD1_BUTTON_A)
    raise AssertionError('Event did not terminate')


def capture(name):
    app.draw()
    pyxel.screenshot(str(output / ('feedback_' + name + '.png')), scale=4)


with patch.object(pyxel, 'text', side_effect=bounded), patch.object(pyxel, 'play') as sound:
    app.draw()
    capture('camp')
    key(pyxel.KEY_F1)
    assert app.overlay is None
    for _ in range(2):
        key(pyxel.KEY_DOWN)
    key(pyxel.GAMEPAD1_BUTTON_A)
    key(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'quest_board'
    key(pyxel.KEY_Z)
    assert e.active['id'] == 1
    capture('quest')
    app.quest_cursor = 1
    key(pyxel.KEY_Z)
    assert e.active['id'] == 1
    key(pyxel.KEY_X)
    key(pyxel.KEY_X)
    app.camp_cursor = 4
    key(pyxel.KEY_Z)
    close_event()
    # Reach the quest via an actual directional step; completion is not yet paid.
    d.floor, x, y = e.target
    d.x, d.y = x - 1, y
    key(pyxel.KEY_RIGHT)
    assert e.surveyed and s.treasure.banked == 0 and app.state == 'field_event'
    capture('objective')
    close_event()
    app.enter_camp(defeated=True)
    assert not e.surveyed and s.treasure.banked == 0
    assert app.state == 'field_event'
    close_event()
    assert app.state == 'camp'
    d.floor, d.x, d.y = e.target
    app.state = 'explore'
    key(pyxel.KEY_Z)
    close_event()
    # RETURN follows the real menu route; both treasure and quest are credited once.
    s.party[0].learn(s.skills['return'])
    s.party[0].skill_uses['return'] = 1
    s.treasure.unbanked = 3
    key(pyxel.KEY_X)
    app.menu_cursor = 3
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.state == 'return_result'
    assert s.treasure.banked == 5 and s.treasure.unbanked == 0
    assert 1 in e.completed and not e.active
    assert 'return' in s.mastered_skills
    assert sound.call_args.args == (0, 63)
    capture('return')
    key(pyxel.KEY_Z)
    # Walking home also reports a quest, including level 2's reward.
    d.defeated_bosses.add(4)
    e.accept(2)
    e.surveyed = True
    app.handle_event('base', '帰還')
    assert s.treasure.banked == 9 and 2 in e.completed
    key(pyxel.KEY_Z)
    app.enter_dungeon()
    close_event()
    # Each chest kind opens a paginated field modal and safely returns to the map.
    for reward in d.exploration_settings['CHEST_REWARD_TABLE']['NORMAL']:
        app.handle_event(*d.grant_chest(reward))
        if app.state == 'field_event':
            close_event()
        assert app.state == 'explore'
    capture('map')
    # Force a LEGEND spark into full inventories and decline/accept through shared UI.
    for c in s.party:
        for skill in s.skills.values():
            if len(c.skills) >= s.settings['skill_slots']:
                break
            if skill.id not in c.skills and skill.rarity != 'LEGEND':
                c.learn(skill)
    for decline in (True, False):
        with patch.object(s.rng, 'choices', return_value=['LEGEND']):
            app.handle_event(*d.grant_chest({'kind': 'SKILL_CHANCE', 'chance': 1}))
        close_event()
        assert app.state == 'replace'
        new = s.party[s.pending_replacements[0]].pending_skill
        capture('replacement')
        if decline:
            key(pyxel.KEY_X)
        key(pyxel.KEY_Z)
        key(pyxel.KEY_Z)
        assert app.state == 'explore' and not s.pending_replacements
        assert new in s.discovered_skills
    # Spring is single use per expedition, and touching again cannot heal repeatedly.
    d.x, d.y = 2, 1
    previous_tile = d.tile(d.floor, d.x, d.y)
    d.maps[d.floor].pset(d.x, d.y, TILE_HEAL_POINT)
    for c in s.party:
        c.hp = 1
    app.handle_event(*d.interact())
    close_event()
    hp = [c.hp for c in s.party]
    app.handle_event(*d.interact())
    close_event()
    assert hp == [c.hp for c in s.party]
    d.maps[d.floor].pset(d.x, d.y, previous_tile)
    app.enter_camp()
    app.enter_dungeon()
    assert not e.springs
    # Debug mastery and reacquisition: attack power changes, stock does not.
    app.enter_camp()
    key(pyxel.KEY_F9)
    key(pyxel.KEY_F10)
    app.catalog_cursor = list(s.skills).index('punch')
    c = s.party[0]
    for sid in list(c.skills)[1:]:
        c.forget(sid)
    key(pyxel.KEY_M)
    key(pyxel.KEY_R)
    assert c.skill_uses['punch'] == s.skills['punch'].max_uses
    assert c.power_multiplier(s.skills['punch']) == 1.2
    key(pyxel.KEY_X)
    app.state, app.archive_page = 'archive', 1
    app.archive_cursor = list(s.skills).index('punch')
    capture('archive')
    assert any('再取得POWER x1.2' in value for value in draws)
    app.enter_camp()
    key(pyxel.KEY_F1)
    for i in range(len(app.feedback_options())):
        app.feedback_cursor = i
        app.draw()
    capture('debug')
    app.feedback_cursor = next(i for i, (_, a) in enumerate(app.feedback_options()) if a == 3)
    key(pyxel.KEY_Z)
    assert e.active['id'] == 3
    app.feedback_cursor = next(i for i, (_, a) in enumerate(app.feedback_options()) if a == 'warp')
    key(pyxel.KEY_Z)
    assert (d.floor, d.x, d.y) == e.target and app.overlay is None
    assert app.state == 'explore'
    app.state = 'clear'
    key(pyxel.KEY_Z)
    assert app.state == 'explore'  # Final boss cannot prevent carrying a quest home.
    d.defeated_bosses.add(14)
    d.debug_floor(14)
    app.enter_camp(returned=True)
    key(pyxel.KEY_Z)
    app.camp_cursor = 4
    key(pyxel.KEY_Z)
    assert app.state == 'clear' and d.floor == 0
    key(pyxel.KEY_Z)
    assert app.state == 'explore' and d.floor == 0

print(f'PASS: quests/RETURN/death, chest replacement, spring, mastery/debug, {len(draws)} bounded text draws')
