"""Exercise real Pyxel drawing and UI input without opening a window."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.app import App
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.text import font, text_width, wrap_lines, FONT_HEIGHT
from rpg.sound import ATTACK_SOUND, SKILL_SOUND


app = App(Session(*load_content(), seed=42), run=False, headless=True)
output = ROOT / "verification" / "screenshots"
output.mkdir(parents=True, exist_ok=True)
real_text = pyxel.text
draw_calls = 0
drawn_text = []


def bounded_text(x, y, value, color, selected_font):
    global draw_calls
    assert selected_font is font()
    assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
    assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
    draw_calls += 1
    drawn_text.append((x, y, value))
    real_text(x, y, value, color, selected_font)


def key(keycode=None):
    with patch.object(pyxel, "btnp", side_effect=lambda k, *args: k == keycode), patch.object(pyxel, "btn", return_value=False):
        app.update()
    app.draw()


def give(actor, ids):
    for sid in list(actor.skills):
        actor.forget(sid)
    for sid in ids:
        actor.learn(app.session.skills[sid])


def capture(name):
    app.draw()
    pyxel.screenshot(str(output / f"{name}.png"), scale=4)


with (patch.object(pyxel, "text", side_effect=bounded_text),
      patch.object(pyxel, "play") as playback,
      patch.object(pyxel, "camera", wraps=pyxel.camera) as cameras):
    capture("01_battle")
    assert any(value.endswith("たたかう") for _, _, value in drawn_text)
    assert any(value.endswith("まもる") for _, _, value in drawn_text)
    assert not any(value == enemy.name and y < 80 for _, y, value in drawn_text for enemy in app.battle.enemies)
    key(pyxel.KEY_Z)
    assert app.state == "skill"
    key(pyxel.KEY_Z)
    assert app.state == "target"
    target_name = app.targets()[0][1].name
    target_lines = [value for _, y, value in drawn_text if 80 <= y < 111 and target_name in value]
    assert target_lines and all("HP" not in value for value in target_lines)
    capture("02_target")
    key(pyxel.KEY_X)
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.actor_index == 1
    key(pyxel.KEY_X)
    assert app.actor_index == 0 and not app.actions
    key(pyxel.KEY_F9)
    assert app.session.debug
    # Full battle -> result pages -> next battle, driven through update().
    for frame in range(15000):
        key(pyxel.KEY_A if app.state == "command" else pyxel.KEY_Z)
        if app.state == "result":
            break
    else:
        raise AssertionError("UI failed to finish battle")
    assert app.session.completed == 1
    assert any(c.args == (0, ATTACK_SOUND) for c in playback.call_args_list)
    assert any(c.args and c.args != (0, 0) for c in cameras.call_args_list), "Player damage did not shake the screen"
    app.notice_timer = 0
    capture("03_results")
    key(pyxel.KEY_D)
    capture("04_stats")
    key(pyxel.KEY_Z)
    capture("05_learned")
    key(pyxel.KEY_Z)
    capture("06_history")
    key(pyxel.KEY_D)
    for _ in range(20):
        key(pyxel.KEY_Z)
        if app.state == "command":
            break
    assert app.state == "command" and app.session.completed == 1
    assert all(c.hp == c.max_hp for c in app.session.party)
    actor = app.actor
    give(actor, ["punch", "fire", "heal", "counter", "seven_slash", "meteor"])
    key(pyxel.KEY_Z)
    assert app.state == "skill"
    for _ in range(5):
        key(pyxel.KEY_DOWN)
    assert app.skill_cursor == 5
    capture("07_legend_skill")
    actor.cooldowns["meteor"] = 4
    key(pyxel.KEY_Z)
    assert app.state == "skill"
    actor.cooldowns.clear()
    key(pyxel.KEY_Z)
    assert app.state == "target"
    key(pyxel.KEY_X)
    assert app.state == "skill"
    key(pyxel.KEY_UP)
    key(pyxel.KEY_UP)
    key(pyxel.KEY_UP)
    key(pyxel.KEY_Z)
    assert app.selected_skill.id == "heal"
    assert app.targets()[0][1] is app.session.party[0]
    capture("08_heal_target")
    key(pyxel.KEY_X)
    key(pyxel.KEY_X)
    key(pyxel.KEY_H)
    capture("09_help")
    key(pyxel.KEY_H)
    # Exercise all four full-slot decisions through result -> choice -> confirm.
    app.battle.outcome = "VICTORY"
    app.session.settings["debug_spark_chance"] = 1
    for c in app.session.party:
        give(c, list(app.session.skills)[:6])
    app.session.settle()
    assert len(app.session.pending_replacements) == 4
    app.result_lines = wrap_lines(app.session.results)
    app.state = "result"
    app.result_page = (len(app.result_lines) - 1) // 9
    key(pyxel.KEY_Z)
    assert app.state == "replace"
    old = list(app.session.party[0].skills)
    new_id = app.session.party[0].pending_skill
    for _ in range(5):
        key(pyxel.KEY_DOWN)
    capture("12_replace_last_slot")
    key(pyxel.KEY_Z)
    assert app.replacement_confirm
    capture("13_replace_confirm")
    key(pyxel.KEY_X)
    assert not app.replacement_confirm and app.session.party[0].skills == old
    key(pyxel.KEY_D)
    key(pyxel.KEY_D)
    assert app.state == "replace" and app.replacement_cursor == 5
    key(pyxel.KEY_Z)
    key(pyxel.KEY_Z)
    assert app.session.party[0].skills == old[:5] + [new_id]
    for expected in (1, 2, 3):
        assert app.session.pending_replacements[0] == expected
        key(pyxel.KEY_X)
        assert app.replacement_cursor == 6 and not app.replacement_confirm
        key(pyxel.KEY_Z)
        capture("14_decline_confirm")
        key(pyxel.KEY_Z)
    assert app.state == "result" and not app.session.pending_replacements
    capture("15_replaced_result")
    for _ in range(40):
        key(pyxel.KEY_Z)
        if app.state == "command":
            break
    assert app.session.completed == 2
    # Sound dispatch for a real UI-resolved skill, not menu selection.
    give(app.actor, ["fire"])
    from rpg.models import Action
    actions = [Action(0, "SKILL", 0, "fire")] + [Action(i, "DEFEND") for i in range(1, 4)]
    app.battle.begin_round(actions)
    app.state, app.delay = "resolve", 0
    playback.reset_mock()
    for _ in range(150):
        key(pyxel.KEY_Z)
        if app.state == "command":
            break
    assert any(c.args == (0, SKILL_SOUND) for c in playback.call_args_list)
    # Oversized edited names and long histories must remain inside the screen.
    for c in app.session.party:
        c.name = "とても長い日本語の仲間の名前"
        c.hp = c.max_hp = 12345
        c.history = ["B999 とても長い日本語の成長履歴 " * 10] * 100
    for e in app.battle.enemies:
        e.name = "とても長い日本語の敵の名前"
    capture("10_long_names")
    key(pyxel.KEY_D)
    for tab in range(3):
        app.info_tab = tab
        app.scroll = app.info_scroll_limit()
        app.draw()
    key(pyxel.KEY_D)
    app.battle.outcome = "DEFEAT"
    app.state, app.delay = "resolve", 0
    app.pending.clear()
    key()
    assert app.state == "result"
    capture("11_defeat")
    for _ in range(20):
        key(pyxel.KEY_Z)
        if app.state == "command":
            break
    assert app.session.losses == 1
print(f"UI checks passed; {draw_calls} bounded text draws; screenshots: {output}")
