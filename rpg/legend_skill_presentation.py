"""Eight bounded, sprite-only LEGEND presentations. No battle rules or RNG."""

LEGEND_PRESENTATION_IDS = ('legend_seven_slash', 'legend_meteor', 'legend_full_heal',
    'legend_ragnarok', 'legend_starfall', 'legend_miracle', 'legend_sanctuary', 'legend_time_stop')
LEGEND_ASSET_BANK, LEGEND_FRAME_SIZE, LEGEND_FRAME_COUNT = 0, 32, 3
LEGEND_SPRITES = {
    'legend_seven_slash': (0, 128), 'legend_meteor': (96, 128),
    'legend_full_heal': (0, 160), 'legend_ragnarok': (96, 160),
    'legend_starfall': (0, 192), 'legend_miracle': (96, 192),
    'legend_sanctuary': (0, 224), 'legend_time_stop': (96, 224),
}
LEGEND_CHARGE_FRAMES, LEGEND_RESULT_FRAMES, LEGEND_AFTERGLOW_FRAMES = 6, 4, 4
LEGEND_MAIN_FRAMES = {ident: 14 if ident == 'legend_seven_slash' else 12
                      for ident in LEGEND_PRESENTATION_IDS}
LEGEND_DAMAGE_IDS = ('legend_seven_slash', 'legend_meteor', 'legend_ragnarok', 'legend_starfall')
LEGEND_SHAKE_OFFSETS = ((2, 0), (-2, 1), (1, -1))
LEGEND_PHASES = ('legend_charge', 'legend_main', 'legend_result', 'legend_afterglow')


def legend_presentation_id(skill):
    ident = getattr(skill, 'presentation_id', None)
    return ident if (getattr(skill, 'rarity', None) == 'LEGEND'
                     and isinstance(ident, str) and ident in LEGEND_SPRITES) else None


class LegendPresentation:
    """One reusable child of BattlePresentation; fixed targets, no particles list."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.id = self.name = None
        self.actor = None
        self.targets = ()
        self.hp_before = ()
        self.hp_changes = ()

    def begin(self, skill, actor, targets, battle):
        self.id = legend_presentation_id(skill)
        if self.id is None:
            return
        self.name, self.actor = skill.name, actor
        self.targets = tuple(targets)
        self.hp_before = tuple(unit.hp for unit in battle.party + battle.enemies)

    def resolved(self, battle):
        units = battle.party + battle.enemies
        changes = []
        for side, index in self.targets:
            offset = index if side == 'party' else len(battle.party) + index
            delta = units[offset].hp - self.hp_before[offset]
            if delta:
                changes.append((side, index, delta))
        self.hp_changes = tuple(changes)

    def limit(self, phase):
        return {'legend_charge': LEGEND_CHARGE_FRAMES,
                'legend_main': LEGEND_MAIN_FRAMES.get(self.id, 12),
                'legend_result': LEGEND_RESULT_FRAMES,
                'legend_afterglow': LEGEND_AFTERGLOW_FRAMES}[phase]

    def flashing(self, phase, frame, side, index):
        if phase != 'legend_main' or (side, index) not in self.targets:
            return False
        if self.id == 'legend_time_stop':
            return 4 <= frame < 6  # A single two-frame pulse, never a flashing loop.
        return self.id in LEGEND_DAMAGE_IDS and frame >= LEGEND_MAIN_FRAMES[self.id] - 2

    def shake(self, phase, frame):
        if self.id in LEGEND_DAMAGE_IDS and phase == 'legend_result' and frame < 3:
            return LEGEND_SHAKE_OFFSETS[frame]
        return 0, 0

    def sprite(self, pyxel, frame, x, y, flip_x=False, flip_y=False):
        u, v = LEGEND_SPRITES[self.id]
        pyxel.blt(x, y, LEGEND_ASSET_BANK, u + frame * 32, v,
                  -32 if flip_x else 32, -32 if flip_y else 32, 0)

    def draw_name(self, pyxel, phase):
        from .text import text
        if self.id and phase in ('legend_charge', 'legend_main'):
            # Decorate only the existing message panel. No name/acknowledgment wait.
            pyxel.rect(3, 82, 154, 27, 0)
            pyxel.rectb(3, 82, 154, 27, 2)
            text(7, 84, 'LEGEND', 2, 36)
            text(7, 96, self.name, 3, 36)

    def draw(self, pyxel, presentation):
        from .text import text
        phase, tick = presentation.phase, presentation.frame
        if phase == 'legend_result':
            for side, index, delta in self.hp_changes:
                x, y = presentation.effect_position(side, index)
                text(80 if side == 'party' else max(1, x - 1),
                     y + 4 if side == 'party' else max(11, y - 3),
                     str(delta) if delta < 0 else '+' + str(delta), 3, 8)
            if self.id != 'legend_time_stop':
                return
        targets = self.targets
        if phase == 'legend_charge' and self.id in (
                'legend_seven_slash', 'legend_ragnarok', 'legend_starfall', 'legend_time_stop'):
            targets = (('party', self.actor),)
        for side, index in targets:
            x, y = presentation.effect_position(side, index)
            pyxel.clip(0 if side == 'enemy' else 80, 11, 96 if side == 'enemy' else 35, 66)
            if phase == 'legend_charge':
                self.sprite(pyxel, 2 if self.id in LEGEND_DAMAGE_IDS else 0, x - 8, y - 8)
            elif phase == 'legend_afterglow':
                self.sprite(pyxel, 2, x - 8, y - 8)
            elif self.id == 'legend_seven_slash':
                # Six two-frame strokes, then the two-frame finishing stroke.
                stroke = tick // 2
                self.sprite(pyxel, 1 if stroke == 6 else 0, x - 8, y - 8,
                            flip_x=bool(stroke % 2), flip_y=bool(stroke % 3 == 1))
            elif self.id == 'legend_meteor':
                if tick < 8:
                    drop_y = -24 + (y + 16) * (tick + 1) // 8
                    self.sprite(pyxel, 0, x - 8, drop_y)
                else:
                    self.sprite(pyxel, 1, x - 8, y - 8)
            elif self.id == 'legend_full_heal':
                self.sprite(pyxel, 1 if tick >= 4 else 0, x - 8, y - 8)
                # Three fixed light crops ascend; no particle objects or per-pixel work.
                u, v = LEGEND_SPRITES[self.id]
                for offset in (-8, 0, 8):
                    pyxel.blt(x + 5 + offset, y + 15 - tick * 2, 0, u + 13, v, 7, 7, 0)
            elif self.id == 'legend_ragnarok':
                # One field-wide set, regardless of enemy count.
                if (side, index) == self.targets[0] and tick < 8:
                    for column in (0, 32, 64):
                        self.sprite(pyxel, 0, column, 14, flip_y=bool(tick // 4))
                        self.sprite(pyxel, 0, column, 38, flip_x=True)
                if tick >= 8:
                    self.sprite(pyxel, 1, x - 8, y - 8)
            elif self.id == 'legend_starfall':
                # Four visual stars, independent of targets and gameplay hit count.
                if (side, index) == self.targets[0] and tick < 8:
                    u, v = LEGEND_SPRITES[self.id]
                    for star in range(4):
                        pyxel.blt(8 + star * 20 + tick, -8 + tick * 6 - star * 3,
                                  0, u + 8, v + 8, 16, 16, 0)
                if tick >= 8:
                    self.sprite(pyxel, 1, x - 8, y - 8)
            elif self.id == 'legend_miracle':
                self.sprite(pyxel, 1 if tick >= 4 else 0, x - 8, y - 8)
                u, v = LEGEND_SPRITES[self.id]
                pyxel.blt(82 + index * 6, max(11, y + 8 - tick), 0, u + 13, v, 7, 7, 0)
            elif self.id == 'legend_sanctuary':
                self.sprite(pyxel, 1 if tick >= 4 else 0, x - 8, y - 8)
                if tick == 5 and (side, index) == self.targets[0]:
                    pyxel.rectb(80, 11, 35, 66, 3)
            elif self.id == 'legend_time_stop':
                # The hands stop at frame 4; only the picture holds, update keeps running.
                self.sprite(pyxel, 0 if phase == 'legend_main' and tick < 4 else 1,
                            x - 8, y - 8)
                if phase == 'legend_main' and 4 <= tick < 6 and (side, index) == self.targets[0]:
                    pyxel.rectb(0, 11, 96, 66, 3)
            pyxel.clip()
