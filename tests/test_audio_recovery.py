import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import pyxel

from rpg.app import App, FANFARE_MAX_WAIT_FRAMES, FANFARE_MAX_WAIT_SECONDS
from rpg.content import load_content
from rpg.items import Inventory
from rpg.sound import (music_is_playing, play_cue, play_victory_music,
                       start_battle_music, stop_battle_music, init_sound)


class AudioRecoveryTests(unittest.TestCase):
    def test_broken_audio_calls_do_not_raise(self):
        with patch.object(pyxel, "load", side_effect=RuntimeError("audio unavailable")):
            init_sound()
        with patch.object(pyxel, "play", side_effect=RuntimeError("audio suspended")), \
             patch.object(pyxel, "playm", side_effect=RuntimeError("audio suspended")), \
             patch.object(pyxel, "play_pos", side_effect=RuntimeError("audio suspended")), \
             patch.object(pyxel, "stop", side_effect=RuntimeError("audio suspended")):
            play_cue("mastered")
            start_battle_music()
            self.assertFalse(play_victory_music())
            self.assertFalse(music_is_playing())
            stop_battle_music()

    def test_stuck_fanfare_has_wall_clock_and_frame_deadlines(self):
        app = App.__new__(App)
        app.battle = SimpleNamespace(outcome="VICTORY")
        app.session = SimpleNamespace(debug=False)
        app.state = "result"
        app.fanfare_timed_out = False
        with patch("rpg.app.music_is_playing", return_value=True), \
             patch("rpg.app.stop_battle_music"), \
             patch.object(pyxel, "frame_count", 1000):
            app.fanfare_started_at = time.monotonic() - FANFARE_MAX_WAIT_SECONDS - 1
            app.fanfare_start_frame = 1000
            self.assertFalse(app.waiting_for_fanfare())
            self.assertTrue(app.fanfare_timed_out)
            app.fanfare_timed_out = False
            app.fanfare_started_at = time.monotonic()
            app.fanfare_start_frame = 1000 - FANFARE_MAX_WAIT_FRAMES
            self.assertFalse(app.waiting_for_fanfare())

    def test_run_chance_remains_low_even_with_extreme_agi(self):
        from rpg.battle import Battle
        from rpg.models import Enemy
        settings, skills, party, _ = load_content()
        enemy = Enemy("TEST", 10, 1, 1, 1, (0, 16))
        battle = Battle(party, [enemy], skills, inventory=Inventory())
        self.assertLessEqual(battle.run_chance(), 0.30)
        for actor in party:
            actor.agility = 999
        self.assertEqual(battle.run_chance(), 0.30)
        for actor in party:
            actor.agility = 1
        enemy.agility = 999
        self.assertEqual(battle.run_chance(), 0.10)


if __name__ == "__main__":
    unittest.main()
