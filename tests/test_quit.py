"""Handheld exit remains available through input gates and transient scenes."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pyxel

from rpg.app import App, QUIT_SELECT_HOLD_SECONDS
from rpg.dungeon_app import DungeonApp


class QuitInputTests(unittest.TestCase):
    def make_app(self, cls=App):
        app = cls.__new__(cls)
        app.keyboard = SimpleNamespace(update=lambda: None)
        app.quit_select_started_at = None
        app.save_manager = Mock()
        app.session = SimpleNamespace(marker="unsaved progress")
        return app

    def held(self, app, now, keys):
        with patch.object(pyxel, "btn", side_effect=lambda key: key in keys), \
             patch.object(pyxel, "btnp", return_value=False), \
             patch("rpg.app.time.monotonic", return_value=now):
            return app.handle_quit_input()

    def test_short_press_release_requires_a_new_full_hold(self):
        app = self.make_app()
        select = {pyxel.GAMEPAD1_BUTTON_BACK}
        with patch.object(pyxel, "quit") as quit_game:
            self.assertFalse(self.held(app, 10, select))
            self.assertFalse(self.held(app, 10.5, select))
            self.assertFalse(self.held(app, 10.6, set()))
            self.assertFalse(self.held(app, 20, select))
            self.assertFalse(self.held(app, 20.9, select))
            quit_game.assert_not_called()
            self.assertTrue(self.held(app, 20 + QUIT_SELECT_HOLD_SECONDS, select))
            quit_game.assert_called_once_with()
        app.save_manager.assert_not_called()
        self.assertEqual(app.save_manager.mock_calls, [])
        self.assertEqual(app.session.marker, "unsaved progress")

    def test_volume_and_brightness_combinations_cancel_exit_hold(self):
        app = self.make_app()
        select = {pyxel.GAMEPAD1_BUTTON_BACK}
        with patch.object(pyxel, "quit") as quit_game:
            for direction in (pyxel.GAMEPAD1_BUTTON_DPAD_UP,
                              pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,
                              pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,
                              pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
                with self.subTest(direction=direction):
                    self.assertFalse(self.held(app, 0, select))
                    self.assertFalse(self.held(app, 10, select | {direction}))
                    self.assertFalse(self.held(app, 20, select))
                    self.assertFalse(self.held(app, 20.5, select))
                    self.held(app, 21, set())
            quit_game.assert_not_called()

    def test_a_b_and_start_do_not_exit(self):
        app = self.make_app()
        keys = {pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B,
                pyxel.GAMEPAD1_BUTTON_START}
        with patch.object(pyxel, "quit") as quit_game:
            self.assertFalse(self.held(app, 0, keys))
            self.assertFalse(self.held(app, 10, keys))
            quit_game.assert_not_called()

    def test_exit_precedes_every_dungeon_state_and_input_gate(self):
        states = ("title", "title_no_save", "title_fade", "intro", "hub_preview",
                  "hub_intro", "camp", "facility", "explore", "menu",
                  "battle_transition", "command", "skill", "target", "resolve",
                  "result", "replacement", "guardian_warning", "guardian_between",
                  "guardian_after", "amrita_offer", "final_story", "final_retry",
                  "amrita_effect", "ending")
        for state in states:
            with self.subTest(state=state):
                app = self.make_app(DungeonApp)
                app.state = state
                app.opening_input_blocked = app.battle_input_blocked = True
                app.quit_select_started_at = 10
                with patch.object(pyxel, "btn", side_effect=lambda key: key == pyxel.GAMEPAD1_BUTTON_BACK), \
                     patch.object(pyxel, "btnp", return_value=False), \
                     patch("rpg.app.time.monotonic", return_value=11), \
                     patch.object(pyxel, "quit") as quit_game:
                    app.update()
                    quit_game.assert_called_once_with()
                self.assertEqual(app.state, state)
                self.assertEqual(app.save_manager.mock_calls, [])

    def test_battle_lab_effect_and_pc_q_can_exit(self):
        app = self.make_app()
        app.state = "amrita_effect"
        app.quit_select_started_at = 10
        with patch.object(pyxel, "btn", side_effect=lambda key: key == pyxel.GAMEPAD1_BUTTON_BACK), \
             patch.object(pyxel, "btnp", return_value=False), \
             patch("rpg.app.time.monotonic", return_value=11), \
             patch.object(pyxel, "quit") as quit_game:
            app.update()
            quit_game.assert_called_once_with()
        app = self.make_app(DungeonApp)
        app.state = "title"
        with patch.object(pyxel, "btnp", side_effect=lambda key, *args: key == pyxel.KEY_Q), \
             patch.object(pyxel, "quit") as quit_game:
            app.update()
            quit_game.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
