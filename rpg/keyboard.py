"""Prevent Windows IME composition from consuming game command keys."""
import sys


class GameKeyboard:
    def __init__(self, enabled=True):
        self.user32 = self.imm32 = None
        if not enabled or sys.platform != "win32":
            return
        import ctypes
        from ctypes import wintypes

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetActiveWindow.argtypes = []
        self.user32.GetActiveWindow.restype = wintypes.HWND
        self.imm32 = ctypes.WinDLL("imm32", use_last_error=True)
        self.imm32.ImmGetContext.argtypes = [wintypes.HWND]
        self.imm32.ImmGetContext.restype = wintypes.HANDLE
        self.imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        self.imm32.ImmReleaseContext.restype = wintypes.BOOL
        self.imm32.ImmAssociateContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        self.imm32.ImmAssociateContext.restype = wintypes.HANDLE

    def update(self):
        if self.user32 is None:
            return
        # GetActiveWindow is scoped to this UI thread, unlike GetForegroundWindow.
        # Never touch another application's window or its IME open/closed setting.
        hwnd = self.user32.GetActiveWindow()
        if not hwnd:
            return
        context = self.imm32.ImmGetContext(hwnd)
        if context:
            self.imm32.ImmReleaseContext(hwnd, context)
            self.imm32.ImmAssociateContext(hwnd, None)
        # Recheck on later frames: SDL can reassociate IME after focus changes.
        # The context is OS-owned; do not destroy it or change its conversion mode.
