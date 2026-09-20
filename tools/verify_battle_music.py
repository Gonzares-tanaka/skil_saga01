"""Validate the editable score, WAV render and battle lifecycle."""
from array import array
from pathlib import Path
import sys
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.sound import play_cue
from rpg.tiles import TILE_BOSS

app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
seqs = [list(seq) for seq in pyxel.musics[0].seqs]
assert not seqs[0] and all(seqs[i] for i in (1, 2, 3))
durations = [sum(pyxel.sounds[s].total_sec() for s in seqs[i]) for i in (1, 2, 3)]
assert max(durations) - min(durations) < 0.001
assert 25.59 < durations[0] < 25.61
assert all(s < 60 for seq in seqs for s in seq)
output = ROOT / "verification" / "audio" / "battle_preview.wav"
output.parent.mkdir(parents=True, exist_ok=True)
pyxel.musics[0].save(str(output), durations[0] * 2)
with wave.open(str(output), "rb") as wav:
    pcm = array("h", wav.readframes(wav.getnframes()))
    assert max(abs(x) for x in pcm) > 100
    assert sum(abs(x) >= 32767 for x in pcm) / len(pcm) < 0.001
with patch.object(pyxel, "playm") as music, patch.object(pyxel, "stop") as stop, patch.object(pyxel, "play") as effect:
    app.enter_dungeon()
    app.begin_encounter()
    music.assert_called_once_with(0, loop=True)
    play_cue("attack")
    assert effect.call_args.args[0] == 0
    assert stop.call_count == 0
    app.battle.outcome = "DEFEAT"
    app.state, app.delay = "resolve", 0
    app.update()
    assert app.state == "result"
    assert [call.args[0] for call in stop.call_args_list] == [1, 2, 3]
    app.finish_results()
    app.dungeon.floor = 4
    app.begin_encounter(boss=True)
    assert music.call_count == 1
assert list(pyxel.colors) == [int(line, 16) for line in (ROOT / "game.pyxpal").read_text().splitlines()]
fanfare_seqs = [list(seq) for seq in pyxel.musics[1].seqs]
assert not fanfare_seqs[0]
assert all(abs(sum(pyxel.sounds[s].total_sec() for s in seq) - 2.4) < 0.001 for seq in fanfare_seqs[1:4])
fanfare_output = output.with_name("victory_preview.wav")
pyxel.musics[1].save(str(fanfare_output), 2.4)
with wave.open(str(fanfare_output), "rb") as wav:
    pcm = array("h", wav.readframes(wav.getnframes()))
    assert max(abs(x) for x in pcm) > 100
    assert sum(abs(x) >= 32767 for x in pcm) / len(pcm) < 0.001
    rate = wav.getframerate() * wav.getnchannels()
    def rms(start, end):
        section = pcm[int(start * rate):int(end * rate)]
        return (sum(x * x for x in section) / len(section)) ** 0.5
    assert rms(1.3, 1.5) > rms(1.8, 2.0) > rms(2.25, 2.39)
with patch.object(pyxel, "playm") as music:
    # Current battle is a boss battle; victory uses the same fanfare.
    app.battle.outcome = "VICTORY"
    app.state, app.delay = "resolve", 0
    app.update()
    music.assert_called_once_with(1, loop=False)
    for _ in range(10):
        app.update()
    assert music.call_count == 1
    for actor_index in app.session.pending_replacements:
        app.session.resolve_replacement(actor_index)
    app.dungeon.floor = 0
    app.begin_encounter()
    app.battle.outcome = "DRAW"
    app.state, app.delay = "resolve", 0
    music.reset_mock()
    app.update()
    music.assert_not_called()
# Reproduce repeated confirmation while only the final music channel is active.
app.battle.outcome = "VICTORY"
app.result_lines, app.result_page = ["Victory"], 0
with patch.object(pyxel, "btnp", side_effect=lambda key, *args: key == pyxel.KEY_Z), patch.object(pyxel, "play_pos", side_effect=lambda ch: (22, 1.0) if ch == 3 else None):
    for _ in range(10):
        app.update()
        app.draw()
    app.finish_results()
    assert app.state == "result"
with patch.object(pyxel, "btnp", return_value=False), patch.object(pyxel, "play_pos", return_value=None):
    app.update()
    assert app.state == "result"  # No deferred confirm, requires a fresh press.
with patch.object(pyxel, "btnp", side_effect=lambda key, *args: key == pyxel.GAMEPAD1_BUTTON_A), patch.object(pyxel, "play_pos", return_value=None), patch.object(pyxel, "stop") as stop:
    app.update()
    assert app.state == "explore"
    assert [call.args[0] for call in stop.call_args_list] == [1, 2, 3]
# Boss victory must wait before its after-battle dialogue too.
app.state, app.battle_is_boss = "result", True
app.battle_position = (4, *app.dungeon.find(4, TILE_BOSS))
with patch.object(pyxel, "play_pos", return_value=(20, 0.5)):
    app.finish_results()
    assert app.state == "result"
with patch.object(pyxel, "play_pos", return_value=None):
    app.finish_results()
    assert app.state == "boss_after"
print(f"PASS: aligned {durations[0]:.2f}s loop, audio render, SFX isolation, normal/boss/result lifecycle, palette unchanged")
print(output)
print(fanfare_output)
