"""Headless A-E lock/resume fault injection and repeated result transitions."""
from collections import deque
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp


def press(app, key):
    with patch.object(pyxel, "btnp", side_effect=lambda code, *args: code == key), \
         patch.object(pyxel, "btn", side_effect=lambda code: key == pyxel.KEY_Z and code == pyxel.KEY_Z):
        app.update()


def resolve_to_result(app):
    for _ in range(500):
        press(app, pyxel.KEY_A if app.state == "command" else pyxel.KEY_Z)
        if app.state == "result":
            return
    raise AssertionError("Battle did not reach RESULT")


def leave_result(app):
    for index in list(app.session.pending_replacements):
        app.session.resolve_replacement(index)
    app.finish_results()
    assert app.state == "explore"


session = Session(*load_content(), seed=29)
app = DungeonApp(session, run=False, headless=True)
app.enter_dungeon()

# A: Input still works after a background/foreground cycle. A real device lock
# is unavailable in headless mode; this checks the game-side input path.
press(app, pyxel.KEY_X)
assert app.state == "menu"
press(app, pyxel.KEY_X)
assert app.state == "explore"
print("A: explore A/B resume path OK")

def no_audio(*args, **kwargs):
    raise RuntimeError("AudioContext interrupted")


with patch.object(pyxel, "play", side_effect=no_audio), \
     patch.object(pyxel, "playm", side_effect=no_audio), \
     patch.object(pyxel, "play_pos", side_effect=no_audio), \
     patch.object(pyxel, "stop", side_effect=no_audio):
    # B: Enter a normal fight after audio loss, win and return to the map.
    app.begin_encounter()
    for enemy in app.battle.enemies:
        enemy.hp = 1
    resolve_to_result(app)
    assert not app.waiting_for_fanfare()
    leave_result(app)
    print("B: silent normal victory -> explore OK")

    # C: A battle already in resolution remains controllable after audio loss.
    app.begin_encounter()
    for enemy in app.battle.enemies:
        enemy.hp = 1
    press(app, pyxel.KEY_A)
    assert app.state == "resolve"
    resolve_to_result(app)
    leave_result(app)
    print("C: silent mid-battle continuation OK")

    # E: Exhaustion/MASTERED and spark still settle when all audio APIs fail.
    actor = session.party[0]
    for sid in ("heal", "counter", "return", "berserk", "power_up"):
        if sid not in actor.skills:
            actor.learn(session.skills[sid])
    actor.skill_uses["punch"] = 1
    actor.agility = 100
    session.debug = True
    session.settings["debug_spark_chance"] = 1
    app.begin_encounter()
    app.battle.enemies = app.battle.enemies[:1]
    app.battle.enemies[0].hp = 12
    resolve_to_result(app)
    assert "punch" in session.mastered_skills
    assert session.pending_replacements
    leave_result(app)
    print("E: silent MASTERED + spark + replacement -> explore OK")

    # Repeated victory/result/map transitions with mixed KO and inventory.
    before = session.completed
    with redirect_stdout(StringIO()):
        for index in range(100):
            for actor in session.party:
                if actor.hp == 0:
                    actor.hp = 1
            app.begin_encounter()
            if index % 7 == 0:
                session.party[1].hp = 0
            if index % 9 == 0:
                session.party[0].hp = max(1, session.party[0].hp - 1)
                session.inventory.use("POTION", session.party[0])
            app.battle.outcome = "VICTORY"
            app.state, app.delay, app.pending = "resolve", 0, deque()
            press(app, pyxel.KEY_Z)
            assert app.state == "result" and session.settled
            leave_result(app)
    assert session.completed - before == 100
    print("100 silent victory/result/map cycles OK")

    app.dungeon.debug_floor(4)
    app.begin_encounter(boss=True)
    app.battle.outcome = "VICTORY"
    app.state, app.delay, app.pending = "resolve", 0, deque()
    press(app, pyxel.KEY_Z)
    for index in list(session.pending_replacements):
        session.resolve_replacement(index)
    app.finish_results()
    assert app.state == "boss_after"
    print("Silent boss victory -> boss dialogue OK")

# D: A stuck play_pos cannot hold the result screen beyond its deadline.
app.state = "result"
app.battle.outcome = "VICTORY"
app.fanfare_started_at = time.monotonic() - 10
app.fanfare_start_frame = pyxel.frame_count
app.fanfare_timed_out = False
with patch("rpg.app.music_is_playing", return_value=True):
    assert not app.waiting_for_fanfare()
print("D: stuck fanfare releases RESULT after timeout OK")
