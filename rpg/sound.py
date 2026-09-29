"""Editable battle music on channels 1-3; synthesized effects on channel 0."""
import pyxel
from .content import ROOT
from .battle_transition import SOUND_BATTLE_TRANSITION

ATTACK_SOUND = 60
SKILL_SOUND = 61
CHEST_SOUND = 62
MASTERED_SOUND = 63


def init_sound():
    try:
        pyxel.load(str(ROOT / "assets" / "battle_music.pyxres"),
                   exclude_images=True, exclude_tilemaps=True)
        pyxel.sounds[ATTACK_SOUND].set("c2g1c1", "n", "642", "f", 3)
        pyxel.sounds[SKILL_SOUND].set("c3e3g3c4", "p", "3453", "v", 5)
        pyxel.sounds[CHEST_SOUND].set("c3g3c4", "p", "542", "f", 4)
        pyxel.sounds[MASTERED_SOUND].set("g3c4e4g4", "p", "5542", "v", 5)
    except Exception:
        # Audio is optional. A suspended or unavailable backend must not block play.
        pass


def play_cue(cue):
    sounds = {"battle_transition": SOUND_BATTLE_TRANSITION,
              "attack": ATTACK_SOUND, "skill": SKILL_SOUND,
              "chest": CHEST_SOUND, "mastered": MASTERED_SOUND}
    if cue in sounds:
        try:
            pyxel.play(0, sounds[cue])
        except Exception:
            pass


def start_battle_music():
    try:
        pyxel.playm(0, loop=True)
    except Exception:
        pass


def play_victory_music():
    try:
        pyxel.playm(1, loop=False)
        return True
    except Exception:
        return False


def music_is_playing():
    try:
        return any(pyxel.play_pos(channel) is not None for channel in (1, 2, 3))
    except Exception:
        return False


def stop_battle_music():
    for channel in (1, 2, 3):
        try:
            pyxel.stop(channel)
        except Exception:
            pass
