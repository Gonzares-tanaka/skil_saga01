"""Headless checks for the four-piece wipe, input isolation and optional audio."""
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel

from rpg.battle import Session
from rpg.battle_transition import (BATTLE_TRANSITION_HOLD_FRAMES,
                                   BATTLE_TRANSITION_FRAMES,
                                   BATTLE_TRANSITION_SPEED,
                                   BATTLE_TRANSITION_FLASH_FRAMES,
                                   SOUND_BATTLE_TRANSITION)
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.sound import play_cue


app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True, start_at_title=False)
app.enter_dungeon()
assert app.state == "explore"
assert pyxel.sounds[SOUND_BATTLE_TRANSITION].notes
assert BATTLE_TRANSITION_HOLD_FRAMES == 3
assert BATTLE_TRANSITION_FRAMES == 18 and BATTLE_TRANSITION_SPEED == 5

with patch.object(pyxel, "play") as play:
    app.handle_event("battle", "")
assert app.state == "battle_transition"
play.assert_called_once_with(0, SOUND_BATTLE_TRANSITION)
assert app.battle and not app.battle_is_boss
app.draw()
snapshot = app.battle_transition_image
assert all(pyxel.screen.pget(x, y) == snapshot.pget(x, y)
           for y in range(pyxel.height) for x in range(pyxel.width))

output = ROOT / "verification" / "screenshots"
output.mkdir(parents=True, exist_ok=True)
pyxel.screenshot(str(output / "battle_transition_00.png"), scale=4)
for remaining in range(BATTLE_TRANSITION_HOLD_FRAMES - 1, -1, -1):
    with patch.object(pyxel, "btnp", return_value=True), \
         patch.object(pyxel, "btn", return_value=True):
        app.update()
    assert app.state == "battle_transition" and app.battle_transition_frame == 0
    assert app.battle_transition_hold == remaining
    app.draw()
    assert all(pyxel.screen.pget(x, y) == snapshot.pget(x, y)
               for y in range(pyxel.height) for x in range(pyxel.width))

real_blt = pyxel.blt
for frame in range(1, BATTLE_TRANSITION_FRAMES):
    with patch.object(pyxel, "btnp", return_value=True), \
         patch.object(pyxel, "btn", return_value=True):
        app.update()
    assert app.state == "battle_transition" and app.actor_position == 0
    pieces = []

    def record_blt(*args, **kwargs):
        if args[2] is snapshot:
            pieces.append(args)
        real_blt(*args, **kwargs)

    with patch.object(pyxel, "blt", side_effect=record_blt):
        app.draw()
    offset = frame * BATTLE_TRANSITION_SPEED
    assert pieces == [
        (-offset, -offset, snapshot, 0, 0, 80, 60),
        (80 + offset, -offset, snapshot, 80, 0, 80, 60),
        (-offset, 60 + offset, snapshot, 0, 60, 80, 60),
        (80 + offset, 60 + offset, snapshot, 80, 60, 80, 60),
    ]
    if frame in BATTLE_TRANSITION_FLASH_FRAMES:
        if frame == BATTLE_TRANSITION_FLASH_FRAMES[0]:
            pyxel.screenshot(str(output / "battle_transition_flash.png"), scale=4)
        flash_pixels = [pyxel.screen.pget(x, y)
                        for y in range(pyxel.height) for x in range(pyxel.width)]
        with patch("rpg.dungeon_app.BATTLE_TRANSITION_FLASH_FRAMES", ()):
            app.draw()
        assert flash_pixels != [pyxel.screen.pget(x, y)
                                for y in range(pyxel.height) for x in range(pyxel.width)]
        pyxel.pset(0, 0, 0)
        assert pyxel.screen.pget(0, 0) == 0  # Palette mapping was reset.
    if frame == BATTLE_TRANSITION_FRAMES // 2:
        pyxel.screenshot(str(output / "battle_transition_mid.png"), scale=4)
        # The opened center is the battle screen, with no overlay or seam.
        center = [[pyxel.screen.pget(x, y) for x in range(45, 115)]
                  for y in range(25, 95)]
        from rpg.app import App
        App.draw(app)
        assert center == [[pyxel.screen.pget(x, y) for x in range(45, 115)]
                          for y in range(25, 95)]

with patch.object(pyxel, "btnp", return_value=True), \
     patch.object(pyxel, "btn", return_value=True):
    app.update()
assert app.state == "command" and app.battle_input_blocked
assert not app.actions and app.actor_position == 0
with patch.object(pyxel, "btnp", return_value=True), \
     patch.object(pyxel, "btn", return_value=True):
    app.update()
assert app.state == "command" and not app.actions
with patch.object(pyxel, "btnp", return_value=False), \
     patch.object(pyxel, "btn", return_value=False):
    app.update()
assert not app.battle_input_blocked
with patch.object(pyxel, "btnp", side_effect=lambda key, *args: key == pyxel.KEY_Z), \
     patch.object(pyxel, "btn", return_value=False):
    app.update()
assert app.state == "skill"

# A muted/interrupted audio backend must never hold the transition state.
app.battle.outcome = "ESCAPE"
app.session.settle()
app.finish_results()
assert app.state == "explore"
for _ in range(10):
    with patch.object(pyxel, "play", side_effect=RuntimeError("audio unavailable")), \
         patch.object(pyxel, "playm", side_effect=RuntimeError("audio unavailable")):
        app.begin_encounter(animate=True)
        assert app.state == "battle_transition"
        for _ in range(BATTLE_TRANSITION_HOLD_FRAMES + BATTLE_TRANSITION_FRAMES):
            with patch.object(pyxel, "btnp", return_value=True), \
                 patch.object(pyxel, "btn", return_value=False):
                app.update()
        assert app.state == "command" and not app.actions
    app.battle.outcome = "ESCAPE"
    app.session.settle()
    app.finish_results()
    assert app.state == "explore"

app.session.debug = True
with patch.object(pyxel, "btnp", return_value=False), \
     patch.object(pyxel, "btn", return_value=False):
    app.update()  # Release the synthetic held input from the last transition.
with patch.object(pyxel, "btnp", side_effect=lambda key, *args: key == pyxel.KEY_T), \
     patch.object(pyxel, "btn", return_value=False):
    app.update()
assert app.state == "battle_transition" and not app.battle_is_boss
for _ in range(BATTLE_TRANSITION_HOLD_FRAMES + BATTLE_TRANSITION_FRAMES):
    with patch.object(pyxel, "btnp", return_value=False), \
         patch.object(pyxel, "btn", return_value=False):
        app.update()
assert app.state == "command"
app.battle.outcome = "ESCAPE"
app.session.settle()
app.finish_results()

app.dungeon.debug_floor(4)
app.begin_encounter(boss=True, animate=True)
assert app.state == "command" and app.battle_is_boss

# An Editor-style Sound change survives a .pyxres save/load; code still plays 59.
with tempfile.TemporaryDirectory() as temp:
    edited = Path(temp) / "battle_music.pyxres"
    shutil.copy2(ROOT / "assets" / "battle_music.pyxres", edited)
    original_notes = list(pyxel.sounds[SOUND_BATTLE_TRANSITION].notes)
    pyxel.sounds[SOUND_BATTLE_TRANSITION].set("c4", "p", "7", "f", 3)
    pyxel.save(str(edited), exclude_images=True, exclude_tilemaps=True)
    pyxel.load(str(ROOT / "assets" / "battle_music.pyxres"),
               exclude_images=True, exclude_tilemaps=True)
    assert list(pyxel.sounds[SOUND_BATTLE_TRANSITION].notes) == original_notes
    pyxel.load(str(edited), exclude_images=True, exclude_tilemaps=True)
    assert list(pyxel.sounds[SOUND_BATTLE_TRANSITION].notes) != original_notes
    with patch.object(pyxel, "play") as play:
        play_cue("battle_transition")
    play.assert_called_once_with(0, SOUND_BATTLE_TRANSITION)

print(f"PASS: {BATTLE_TRANSITION_HOLD_FRAMES}-frame field pause, four outward quadrants, center battle, {BATTLE_TRANSITION_FRAMES} movement frames/10 repeats, held input, muted audio, debug T, boss bypass and editable Sound 59")
