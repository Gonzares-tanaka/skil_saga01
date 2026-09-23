"""Editable battle music on channels 1-3; synthesized effects on channel 0."""
import pyxel
from .content import ROOT

ATTACK_SOUND = 60
SKILL_SOUND = 61
CHEST_SOUND = 62
MASTERED_SOUND = 63


def init_sound():
    pyxel.load(str(ROOT / "assets" / "battle_music.pyxres"),
               exclude_images=True, exclude_tilemaps=True)
    pyxel.sounds[ATTACK_SOUND].set("c2g1c1", "n", "642", "f", 3)
    pyxel.sounds[SKILL_SOUND].set("c3e3g3c4", "p", "3453", "v", 5)
    pyxel.sounds[CHEST_SOUND].set("c3g3c4", "p", "542", "f", 4)
    pyxel.sounds[MASTERED_SOUND].set("g3c4e4g4", "p", "5542", "v", 5)


def play_cue(cue):
    sounds = {"attack": ATTACK_SOUND, "skill": SKILL_SOUND,
              "chest": CHEST_SOUND, "mastered": MASTERED_SOUND}
    if cue in sounds:
        pyxel.play(0, sounds[cue])


def start_battle_music():
    pyxel.playm(0, loop=True)


def play_victory_music():
    pyxel.playm(1, loop=False)


def music_is_playing():
    return any(pyxel.play_pos(channel) is not None for channel in (1, 2, 3))


def stop_battle_music():
    for channel in (1, 2, 3):
        pyxel.stop(channel)
