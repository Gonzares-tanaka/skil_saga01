"""Two synthesized effects, with no external audio files."""
import pyxel

ATTACK_SOUND = 60
SKILL_SOUND = 61


def init_sound():
    pyxel.sounds[ATTACK_SOUND].set("c2g1c1", "n", "642", "f", 3)
    pyxel.sounds[SKILL_SOUND].set("c3e3g3c4", "p", "3453", "v", 5)


def play_cue(cue):
    if cue in ("attack", "skill"):
        pyxel.play(0, ATTACK_SOUND if cue == "attack" else SKILL_SOUND)
