"""Frame-driven, four-piece exploration-to-battle wipe."""
import pyxel


BATTLE_TRANSITION_HOLD_FRAMES = 3  # Show the encountered field for 0.1 second.
BATTLE_TRANSITION_FRAMES = 18  # 0.6 seconds at the game's 30 FPS.
BATTLE_TRANSITION_SPEED = 5    # Fully off-screen before command input opens.
BATTLE_TRANSITION_FLASH_FRAMES = (2, 6)  # Two one-frame palette flashes.
SOUND_BATTLE_TRANSITION = 59   # assets/battle_music.pyxres, Sound Editor.


def draw_pieces(snapshot, frame):
    """Show the captured exploration screen opening toward all four corners."""
    left, top = pyxel.width // 2, pyxel.height // 2
    right, bottom = pyxel.width - left, pyxel.height - top
    offset = min(frame, BATTLE_TRANSITION_FRAMES) * BATTLE_TRANSITION_SPEED
    for source_x, source_y, width, height, sign_x, sign_y in (
        (0, 0, left, top, -1, -1),
        (left, 0, right, top, 1, -1),
        (0, top, left, bottom, -1, 1),
        (left, top, right, bottom, 1, 1),
    ):
        pyxel.blt(source_x + sign_x * offset, source_y + sign_y * offset,
                  snapshot, source_x, source_y, width, height)
