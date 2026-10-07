"""Final-boss drawing and a bounded visual effect; never changes battle rules."""
import math
import time

from .final_battle import load_final_battle_data

AMRITA_EFFECT_FRAMES = 45  # 30 FPS: 1.5 seconds; independent of sound.
AMRITA_EFFECT_MAX_SECONDS = 2.0  # Also releases after a suspended/background tab.
AMRITA_FLASH_FRAMES = (4, 5, 10, 11)
AMRITA_IMPACT_FRAME = 24
AMRITA_BREAK_FRAME = 32
AMRITA_MESSAGE_FRAME = 38
DEFAULT_BOSS_SPRITE = dict(bank=0, u=144, v=64, width=48, height=48, colkey=0)


class FinalPresentation:
    def __init__(self, data=None):
        self.sprite = dict((data or load_final_battle_data()).get('boss_sprite', DEFAULT_BOSS_SPRITE))
        s = self.sprite
        if (set(s) != set(DEFAULT_BOSS_SPRITE) or any(type(v) is not int for v in s.values())
                or not 0 <= s['bank'] <= 2 or not 0 <= s['colkey'] <= 31
                or not 16 <= s['width'] <= 48 or not 16 <= s['height'] <= 48
                or not 0 <= s['u'] <= 256 - s['width'] or not 0 <= s['v'] <= 256 - s['height']):
            raise ValueError('final_battle.json: boss_spriteは48×48以内の有効な画像領域です。')
        self.frame = 0
        self.started_at = None

    @property
    def active(self):
        return self.started_at is not None

    def start(self):
        self.frame, self.started_at = 0, time.monotonic()

    def reset(self):
        self.frame, self.started_at = 0, None

    def advance(self):
        self.frame += 1
        return self.frame >= AMRITA_EFFECT_FRAMES or time.monotonic() - self.started_at >= AMRITA_EFFECT_MAX_SECONDS

    def bounds(self):
        # Left battlefield ends at x=96, below the title and above the y=80 panel.
        s = self.sprite
        return (48 - s['width'] // 2, 48 - s['height'] // 2, s['width'], s['height'])

    def barrier_points(self):
        x, y, w, h = self.bounds()
        return [(round(x + w / 2 + (w / 2 + 4) * math.cos(i * math.tau / 16)),
                 round(y + h / 2 + (h / 2 + 4) * math.sin(i * math.tau / 16)))
                for i in range(16)]

    def draw_boss(self, pyxel, enemy, barrier_active):
        x, y, w, h = self.bounds()
        f = self.frame
        shaking = self.active and AMRITA_IMPACT_FRAME <= f < AMRITA_MESSAGE_FRAME
        offset = (-2, 2, -1, 1)[f % 4] if shaking else 0
        flashing = self.active and AMRITA_IMPACT_FRAME <= f < AMRITA_BREAK_FRAME and f % 4 < 2
        try:
            if flashing:
                pyxel.pal(1, 3)
                pyxel.pal(2, 3)
            s = self.sprite
            pyxel.blt(x + offset, y, s['bank'], s['u'], s['v'], w, h, s['colkey'])
        finally:
            if flashing:
                pyxel.pal()
        # The real barrier is already released by the existing ITEM action.
        # Keep a temporary visual shell only during its destruction animation.
        shell = barrier_active or (self.active and f < AMRITA_MESSAGE_FRAME)
        if not shell:
            return
        phase = f if self.active else pyxel.frame_count
        for i, (px, py) in enumerate(self.barrier_points()):
            if self.active and f >= AMRITA_BREAK_FRAME:
                distance = (f - AMRITA_BREAK_FRAME) * 0.7
                angle = i * math.tau / 16
                px += round(math.cos(angle) * distance)
                py += round(math.sin(angle) * distance)
                color = 3 if f < 35 else 2
            else:
                color = 3 if (i + phase // 4) % 4 < 2 else 1
                if self.active and AMRITA_IMPACT_FRAME <= f < AMRITA_BREAK_FRAME and f % 4 >= 2:
                    continue
            # Constrain all particles to the battlefield; never cover name/party/log.
            if 2 <= px <= 92 and 21 <= py <= 77:
                pyxel.pset(px, py, color)
                if color == 3:
                    pyxel.pset(px + 1, py, color)

    def draw_light(self, pyxel):
        f = self.frame
        if f in AMRITA_FLASH_FRAMES:
            pyxel.rect(0, 0, 160, 120, 3)
        if 12 <= f < AMRITA_IMPACT_FRAME:
            # Three rays descend from directly above the boss, below the title.
            x, y, w, h = self.bounds()
            cx, cy = x + w // 2, y + h // 2
            start_y = max(14, y - 9)
            t = (f - 12) / (AMRITA_IMPACT_FRAME - 13)
            px = cx
            py = round(start_y + (cy - start_y) * t)
            for delta in (-3, 0, 3):
                pyxel.line(cx + delta, start_y, px, py, 2 if delta else 3)
            pyxel.line(px - 3, py, px + 3, py, 3)
            pyxel.line(px, py - 3, px, py + 3, 3)
            pyxel.circb(cx, start_y, 2 + f % 2, 3)
