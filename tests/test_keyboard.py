import unittest
from unittest.mock import Mock, call, patch

from rpg.keyboard import GameKeyboard


class KeyboardTests(unittest.TestCase):
    def test_headless_and_non_windows_do_not_load_windows_libraries(self):
        with patch('rpg.keyboard.sys.platform', 'win32'):
            keyboard = GameKeyboard(enabled=False)
            keyboard.update()
            self.assertIsNone(keyboard.user32)
        with patch('rpg.keyboard.sys.platform', 'linux'):
            keyboard = GameKeyboard()
            keyboard.update()
            self.assertIsNone(keyboard.imm32)

    def test_no_active_game_window_does_not_touch_ime(self):
        keyboard = GameKeyboard(enabled=False)
        keyboard.user32, keyboard.imm32 = Mock(), Mock()
        keyboard.user32.GetActiveWindow.return_value = None
        keyboard.update()
        self.assertEqual(keyboard.imm32.mock_calls, [])

    def test_reassociated_context_is_removed_without_changing_global_ime(self):
        keyboard = GameKeyboard(enabled=False)
        keyboard.user32, keyboard.imm32 = Mock(), Mock()
        keyboard.user32.GetActiveWindow.return_value = 12345
        keyboard.imm32.ImmGetContext.side_effect = [456, None, 789]
        for _ in range(3):
            keyboard.update()
        self.assertEqual(keyboard.imm32.mock_calls, [
            call.ImmGetContext(12345), call.ImmReleaseContext(12345, 456),
            call.ImmAssociateContext(12345, None),
            call.ImmGetContext(12345),
            call.ImmGetContext(12345), call.ImmReleaseContext(12345, 789),
            call.ImmAssociateContext(12345, None)])
        self.assertEqual(keyboard.user32.mock_calls, [call.GetActiveWindow()] * 3)


if __name__ == '__main__':
    unittest.main()
