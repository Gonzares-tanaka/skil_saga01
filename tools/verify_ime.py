"""Windows native IME regression probe. Run in separate processes per mode.

python tools/verify_ime.py --baseline  # old startup, window has an IME context
python tools/verify_ime.py             # fixed startup, no IME context
"""
from pathlib import Path
import ctypes
from ctypes import wintypes
import json
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.app import App


def main():
    if sys.platform != 'win32':
        print('Windows-only native IME probe')
        return
    baseline = '--baseline' in sys.argv
    lab = '--battle-lab' in sys.argv
    app_type = App if lab else DungeonApp
    if baseline:
        with patch('rpg.app.GameKeyboard'):
            app = app_type(Session(*load_content(), seed=52), run=False)
    else:
        app = app_type(Session(*load_content(), seed=52), run=False)
    app.draw()
    user32 = ctypes.WinDLL('user32')
    user32.GetActiveWindow.argtypes = []
    user32.GetActiveWindow.restype = wintypes.HWND
    hwnd = user32.GetActiveWindow()
    assert hwnd, 'No active Pyxel window in the UI thread'
    imm32 = ctypes.WinDLL('imm32')
    imm32.ImmGetContext.argtypes = [wintypes.HWND]
    imm32.ImmGetContext.restype = wintypes.HANDLE
    imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
    imm32.ImmReleaseContext.restype = wintypes.BOOL
    imm32.ImmAssociateContextEx.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.DWORD]
    imm32.ImmAssociateContextEx.restype = wintypes.BOOL
    context = imm32.ImmGetContext(hwnd)
    if context:
        imm32.ImmReleaseContext(hwnd, context)
    assert bool(context) == baseline, (baseline, context)
    # Check the same command routes without OS-wide keyboard injection.
    sequence = ((pyxel.KEY_Z, 'skill'), (pyxel.KEY_Z, 'target'), (pyxel.KEY_X, 'skill'),
                (pyxel.KEY_ESCAPE, 'command')) if lab else (
                (pyxel.KEY_Z, 'explore'), (pyxel.KEY_RIGHT, 'explore'),
                (pyxel.KEY_Z, 'explore'), (pyxel.KEY_X, 'menu'),
                (pyxel.KEY_X, 'explore'), (pyxel.KEY_ESCAPE, 'menu'))
    for key, state in sequence:
        if not baseline:
            # Simulate SDL restoring this window's IME context on focus return.
            assert imm32.ImmAssociateContextEx(hwnd, None, 0x10)  # IACE_DEFAULT
            restored = imm32.ImmGetContext(hwnd)
            assert restored
            imm32.ImmReleaseContext(hwnd, restored)
        with patch.object(pyxel, 'btnp', side_effect=lambda k, *a: k == key):
            app.update()
        app.draw()
        assert app.state == state, (key, app.state)
        current = imm32.ImmGetContext(hwnd)
        if current:
            imm32.ImmReleaseContext(hwnd, current)
        assert bool(current) == baseline
    print(json.dumps({'baseline': baseline, 'battle_lab': lab,
                      'ime_context_present': bool(context), 'z_x_escape': 'passed',
                      'ime_reassociation_cleared': not baseline}))


if __name__ == '__main__':
    main()
