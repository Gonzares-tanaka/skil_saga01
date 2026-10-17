"""Small, bounded visual phases. No random numbers or battle rules here."""
from collections import Counter
from .statuses import default_statuses
from .skill_targets import target_refs
from .rare_skill_presentation import (rare_presentation_id, RARE_ASSET_BANK, RARE_SPRITES,
    RARE_FRAME_SIZE, RARE_FRAME_COUNT, RARE_CAST_FRAMES, RARE_EFFECT_FRAMES,
    RARE_FEEDBACK_FRAMES, RARE_SHAKE_OFFSETS)
import re
import time
from .legend_skill_presentation import LegendPresentation, LEGEND_PHASES

ASSET_BANK = 2
KO_SPRITE_U, KO_SPRITE_V = 240, 0
KO_SPRITE_W, KO_SPRITE_H = 16, 16
EFFECT_IDS = ('slash', 'blunt', 'pierce', 'fire', 'ice', 'lightning',
              'magic', 'dark', 'heal', 'buff', 'debuff', 'legend')
EFFECT_SPRITES = {key: (192, 32 + i * 16) for i, key in enumerate(EFFECT_IDS)}
ENEMY_EFFECT_SPRITES = {'heavy_hit': (144, 96), 'guard': (144, 112),
                      'armor_down': (144, 128), 'slow': (144, 144)}
EFFECT_SPRITES.update(ENEMY_EFFECT_SPRITES)
EFFECT_FRAMES, EFFECT_FRAME_TICKS = 3, 3
ENEMY_STEP_PIXELS, HEAVY_STEP_PIXELS = 3, 9
HEAVY_EFFECT_FRAMES = 6
DOUBLE_EFFECT_FRAMES, DOUBLE_GAP_FRAMES = 3, 2
HEAVY_SHAKE_OFFSETS = ((3, 0), (-2, 1), (1, -1))
STATUS_SPRITES = {'poison': (192, 0), 'paralyze': (200, 0),
                  'sleep': (208, 0), 'curse': (216, 0), 'weak': (216, 0), 'confusion': (224, 0)}
STATUS_EFFECT_FRAMES = 6
STEP_PIXELS, STEP_FRAMES, RETURN_FRAMES = 6, 4, 3
DEATH_FRAMES, DEATH_FLASH_FRAMES = 18, 12
DEATH_BLINK_FRAMES, DEATH_SINK_PIXELS = 3, 8
RUN_PIXELS, RUN_FRAMES, RUN_SECONDS = 16, 15, 0.5
HIT_PIXELS, HIT_FRAMES, HIT_SECONDS = 4, 3, 0.1
DOUBLE_HIT_CYCLE = DOUBLE_EFFECT_FRAMES + HIT_FRAMES + DOUBLE_GAP_FRAMES
PHASES = ('actor_step', 'skill_effect', 'rare_cast', 'rare_effect', 'rare_feedback',
          'enemy_effect', 'status_effect', 'party_hit', 'enemy_death', 'actor_return', 'run_success') + LEGEND_PHASES
MAX_PRESENTATION_SECONDS = 2.0
BATTLE_BACKGROUNDS = {
    1: {'wall': (2, 0, 160, 32, 32), 'floor': (2, 0, 192, 32, 16)},
    2: {'wall': (2, 64, 160, 32, 32), 'floor': (2, 64, 192, 32, 16)},
    3: {'wall': (2, 128, 160, 32, 32), 'floor': (2, 128, 192, 32, 16)},
}
BATTLE_STRIP_X, BATTLE_STRIP_Y = 0, 64
BATTLE_STRIP_WIDTH, BATTLE_STRIP_HEIGHT = 96, 16
BATTLE_FLOOR_STRIP_AREA1 = (2, 0, 208, 96, 16)
BATTLE_FLOOR_STRIP_AREA2 = (2, 0, 224, 96, 16)
BATTLE_FLOOR_STRIP_AREA3 = (2, 0, 240, 96, 16)
BATTLE_FLOOR_STRIPS = {1: BATTLE_FLOOR_STRIP_AREA1, 2: BATTLE_FLOOR_STRIP_AREA2,
                      3: BATTLE_FLOOR_STRIP_AREA3}
ENEMY_GRID_POSITIONS = ((22, 18), (50, 18), (22, 42), (50, 42))


def enemy_position(index, count):
    """Stable battle slots: defeated units never cause survivors to move."""
    if count == 1:
        return 38, 16  # Preserve the existing single-enemy/boss placement.
    return ENEMY_GRID_POSITIONS[index]


def battle_area(floor):
    return max(1, min(3, floor // 5 + 1))


def draw_battle_background(pyxel, area):
    """One editable strip. Upper field stays clear; old wall art is unused."""
    data = BATTLE_FLOOR_STRIPS.get(area)
    if data is None:
        return  # Special/outside-dungeon battles keep their existing background.
    pyxel.clip(BATTLE_STRIP_X, BATTLE_STRIP_Y, BATTLE_STRIP_WIDTH, BATTLE_STRIP_HEIGHT)
    pyxel.blt(BATTLE_STRIP_X, BATTLE_STRIP_Y, *data)
    pyxel.clip()


def effect_id(skill):
    key = getattr(skill, 'effect_id', None)
    return key if isinstance(key, str) and key in EFFECT_SPRITES else 'blunt'


def draw_status_icons(pyxel, actor, x, y, limit=3, vertical=False, definitions=None):
    """Future status data is display-only. No status is applied by this function."""
    if not actor.alive:
        return
    statuses = getattr(actor, 'statuses', ()) or ()
    if isinstance(statuses, str):
        statuses = (statuses,)
    keys = [key for key in dict.fromkeys(statuses) if key in STATUS_SPRITES][:limit]
    definitions = definitions if definitions is not None else default_statuses()
    if keys:
        pyxel.rect(x, y, 8 if vertical else len(keys) * 8, len(keys) * 8 if vertical else 8, 0)
    for i, key in enumerate(keys):
        icon = definitions[key].icon_id if key in definitions else key
        pyxel.blt(x + (0 if vertical else i * 8), y + (i * 8 if vertical else 0),
                  ASSET_BANK, *STATUS_SPRITES[icon], 8, 8, 0)


def dungeon_floor_color(dungeon, pyxel):
    """Read the shared Image Bank's actual floor pixels for the current area."""
    from .tiles import FLOOR_TILES, MAP_IMAGE_BANK
    first = dungeon.floor // 5 * 5
    tiles = Counter()
    for floor in range(first, first + 5):
        w, h = dungeon.map_bounds(floor)
        tiles.update(dungeon.tile(floor, x, y) for y in range(h) for x in range(w)
                     if dungeon.tile(floor, x, y) in FLOOR_TILES)
    colors = Counter()
    image = pyxel.images[MAP_IMAGE_BANK]
    for (u, v), weight in tiles.items():
        for y in range(8):
            for x in range(8):
                colors[image.pget(u * 8 + x, v * 8 + y)] += weight
    return colors.most_common(1)[0][0] if colors else 0


def result_pages(lines, party):
    """Group already calculated growth; never infer or roll new stat gains."""
    gains = {i: [] for i in range(len(party))}
    other = []
    for line in lines:
        found = False
        for i, actor in enumerate(party):
            match = re.fullmatch(re.escape(actor.name) + r' (HP|STR|AGI|INT) \+(\d+)', line)
            if match:
                gains[i].append(f'{match[1]:3} +{match[2]}')
                found = True
                break
            if line == actor.name + ' 変化なし':
                found = True
                break
        if not found:
            other.append(line)
    from .text import wrap_lines
    other = wrap_lines(other)
    pages = [dict(kind='growth', actor=i, lines=[party[i].name, *rows])
              for i, rows in gains.items() if rows]
    pages += [dict(kind='summary', lines=other[i:i + 9]) for i in range(0, len(other), 9)]
    return pages or [dict(kind='summary', lines=[])]


class BattlePresentation:
    def __init__(self, battle):
        self.battle = battle
        self.phase = None
        self.frame = 0
        self.started_at = None
        self.actor = None
        self.target = None
        self.skill_effect_targets = []
        self.effect = 'blunt'
        self.deaths = []
        self.hit_targets = []
        self.enemy_effect_targets = []
        self.enemy_effect_repeats = 1
        self.enemy_actor = None
        self.enemy_action = None
        self.hp_before = []
        self.status_events = []
        self.presentation_id = None
        self.rare_debuff = False
        self.rare_drain = False
        self.rare_hp_before = []
        self.rare_hp_changes = []
        self.legend = LegendPresentation()

    @property
    def active(self):
        return self.phase is not None

    def start(self):
        """Preview a legal queued party action without popping or evaluating it."""
        b = self.battle
        self.actor = self.target = None
        self.skill_effect_targets = []
        self.presentation_id = None
        self.rare_hp_changes = []
        self.legend.reset()
        if not b.queue:
            return False
        side, action = b.queue[0]
        if side != 'party' or action.kind in ('GUARD', 'DEFEND') or not b.party[action.actor].alive:
            return False
        if b.prepare_turn()[2] is not None or action.kind == 'STATUS':
            return False  # Control check is cached; no false attack/Uses preview.
        if action.kind == 'ITEM' and action.item_id == 'AMRITA':
            return False  # Existing dedicated light/barrier effect has priority.
        skill = b.skills.get(action.skill_id) if action.kind == 'SKILL' else None
        if skill and (action.skill_id not in b.party[action.actor].skills or
                      b.party[action.actor].skill_uses.get(action.skill_id, 0) <= 0 or
                      b.party[action.actor].cooldowns.get(action.skill_id, 0)):
            return False
        self.actor = action.actor
        self.effect = effect_id(skill) if skill else 'heal'
        self.presentation_id = rare_presentation_id(skill)
        self.rare_debuff = bool(skill and skill.effect_id == 'debuff')
        self.rare_drain = bool(skill and skill.effect == 'drain')
        self.rare_hp_before = [unit.hp for unit in b.party + b.enemies] if self.presentation_id else []
        if skill:
            self.skill_effect_targets = target_refs(skill, action.actor, b.party, b.enemies, action.target)
            # Random selection is deferred to battle execution, never preview RNG.
            if not self.skill_effect_targets and skill.target != 'random_enemy':
                self.actor = None
                self.presentation_id = None
                return False
            self.target = self.skill_effect_targets[0] if self.skill_effect_targets else None
            self.legend.begin(skill, action.actor, self.skill_effect_targets, b)
            self.enter('actor_step')
            return True
        side = 'party' if action.kind == 'ITEM' or skill and skill.target in ('ally', 'self') else 'enemy'
        group = b.party if side == 'party' else b.enemies
        index = action.actor if skill and skill.target == 'self' else action.target
        # Retarget exactly as the battle does, without advancing its RNG.
        if not (0 <= index < len(group)):
            self.actor = None
            return False
        if not group[index].alive and not (skill and skill.effect == 'revive' or
                                          action.kind == 'ITEM' and action.item_id == 'PHOENIX ASH'):
            index = next((i for i, unit in enumerate(group) if unit.alive), index)
        self.target = (side, index)
        self.skill_effect_targets = [self.target]
        self.enter('actor_step')
        return True

    def enter(self, phase):
        self.phase, self.frame = phase, 0
        self.started_at = time.monotonic()

    def start_run(self):
        self.reset()
        self.enter('run_success')

    def after_action(self, alive_before, hp_before=None):
        self.hp_before = list(hp_before or ())
        self.status_events = list(getattr(self.battle, 'status_visual_events', ()))
        self.hit_targets = [i for i, hp in enumerate(hp_before or ())
                            if hp > self.battle.party[i].hp]
        self.deaths = [i for i, was_alive in enumerate(alive_before)
                       if was_alive and not self.battle.enemies[i].alive]
        # The final boss's existing presentation/ENDING path takes priority.
        if self.battle.is_elysion_battle:
            self.deaths = []
        payload = getattr(self.battle, 'enemy_action_visual', None)
        random_payload = getattr(self.battle, 'player_skill_visual', None)
        if self.legend.id:
            self.legend.resolved(self.battle)
            self.enter('legend_result')
            return
        if self.presentation_id:
            # Battle.step has already resolved damage, statuses and outcome once.
            # Keep their feedback separate without delaying any gameplay check.
            units = self.battle.party + self.battle.enemies
            self.rare_hp_changes = []
            for side, index in self.skill_effect_targets:
                offset = index if side == 'party' else len(self.battle.party) + index
                delta = units[offset].hp - self.rare_hp_before[offset]
                if delta:
                    self.rare_hp_changes.append((side, index, delta))
            self.enter('rare_feedback')
            return
        if random_payload:
            self.effect = random_payload['effect_id'] if random_payload['effect_id'] in EFFECT_SPRITES else 'blunt'
            self.enemy_effect_targets = random_payload['targets']
            self.enemy_effect_repeats = 1
            self.enemy_actor = self.enemy_action = None
            self.enter('enemy_effect')
            return
        if payload:
            self.effect = payload.get('effect_id') if payload.get('effect_id') in EFFECT_SPRITES else 'blunt'
            self.enemy_effect_targets = payload.get('targets', [])
            self.enemy_effect_repeats = max(1, min(8, payload.get('repeats', 1)))
            self.enemy_actor = payload.get('enemy_index')
            self.enemy_action = payload.get('action_id')
            if self.enemy_action == 'attack':
                self.after_effects()
            else:
                self.enter('enemy_effect')
        else:
            self.after_effects()

    def reset(self):
        self.phase = None
        self.actor = self.target = None
        self.skill_effect_targets = []
        self.deaths = []
        self.hit_targets = []
        self.enemy_effect_targets = []
        self.enemy_effect_repeats = 1
        self.enemy_actor = self.enemy_action = None
        self.hp_before = []
        self.status_events = []
        self.presentation_id = None
        self.rare_hp_before = []
        self.rare_hp_changes = []
        self.rare_debuff = self.rare_drain = False
        self.legend.reset()

    def after_effects(self):
        if self.status_events:
            self.enter('status_effect')
        elif self.hit_targets:
            self.enter('party_hit')
        elif self.deaths:
            self.enter('enemy_death')
        elif self.actor is not None:
            self.enter('actor_return')
        else:
            self.reset()

    def enemy_effect_frames(self):
        if self.enemy_action == 'double_attack':
            return DOUBLE_HIT_CYCLE * self.enemy_effect_repeats - DOUBLE_GAP_FRAMES
        if self.enemy_action == 'heavy_attack':
            return HEAVY_EFFECT_FRAMES
        return EFFECT_FRAMES * EFFECT_FRAME_TICKS * self.enemy_effect_repeats

    def advance(self):
        """Return apply once at impact. All waits have a frame and wall timeout."""
        if not self.active:
            return None
        self.frame += 1
        if self.phase == 'run_success':
            if self.frame >= RUN_FRAMES or time.monotonic() - self.started_at >= RUN_SECONDS:
                self.reset()
                return 'escaped'
            return None
        if self.phase == 'party_hit':
            if self.frame < HIT_FRAMES and time.monotonic() - self.started_at < HIT_SECONDS:
                return None
            if self.actor in self.hit_targets:
                self.actor = None  # Hit reaction already returned this actor to base.
            self.hit_targets = []
            if self.deaths:
                self.enter('enemy_death')
            elif self.actor is not None:
                self.enter('actor_return')
            else:
                self.reset()
            return None
        if self.phase == 'enemy_effect':
            limit = self.enemy_effect_frames()
            if self.frame < limit and time.monotonic() - self.started_at < MAX_PRESENTATION_SECONDS:
                return None
            if self.enemy_action == 'double_attack':
                self.hit_targets = []  # Each hit already displayed its own recoil.
            self.after_effects()
            return None
        if self.phase == 'status_effect':
            if self.frame < STATUS_EFFECT_FRAMES and time.monotonic() - self.started_at < MAX_PRESENTATION_SECONDS:
                return None
            self.status_events = []
            self.after_effects()
            return None
        if self.phase in ('rare_cast', 'rare_effect', 'rare_feedback'):
            limit = {'rare_cast': RARE_CAST_FRAMES, 'rare_effect': RARE_EFFECT_FRAMES,
                     'rare_feedback': RARE_FEEDBACK_FRAMES}[self.phase]
            if self.frame < limit and time.monotonic() - self.started_at < MAX_PRESENTATION_SECONDS:
                return None
            if self.phase == 'rare_cast':
                self.enter('rare_effect')
            elif self.phase == 'rare_effect':
                return 'apply'  # Same one-shot execution event as the legacy effect.
            else:
                self.after_effects()  # Damage/HP feedback precedes successful status feedback.
            return None
        if self.phase in LEGEND_PHASES:
            if self.frame < self.legend.limit(self.phase) and time.monotonic() - self.started_at < MAX_PRESENTATION_SECONDS:
                return None
            if self.phase == 'legend_charge':
                self.enter('legend_main')
            elif self.phase == 'legend_main':
                return 'apply'
            elif self.phase == 'legend_result':
                self.enter('legend_afterglow')
            else:
                self.after_effects()
            return None
        limit = {'actor_step': STEP_FRAMES, 'skill_effect': EFFECT_FRAMES * EFFECT_FRAME_TICKS,
                 'enemy_death': DEATH_FRAMES, 'actor_return': RETURN_FRAMES}[self.phase]
        if self.frame < limit and time.monotonic() - self.started_at < MAX_PRESENTATION_SECONDS:
            return None
        if self.phase == 'actor_step':
            self.enter('legend_charge' if self.legend.id else
                       'rare_cast' if self.presentation_id else 'skill_effect')
        elif self.phase == 'skill_effect':
            return 'apply'
        elif self.phase == 'enemy_death' and self.actor is not None:
            self.enter('actor_return')
            self.deaths = []
        else:
            self.reset()
        return None

    def actor_offset(self, index):
        if self.phase == 'run_success':
            return round(RUN_PIXELS * min(1, self.frame / RUN_FRAMES))
        if self.phase == 'party_hit' and index in self.hit_targets:
            return round(HIT_PIXELS * max(0, 1 - self.frame / HIT_FRAMES))
        if self.phase == 'enemy_effect' and self.enemy_action == 'double_attack' and index in self.hit_targets:
            tick = self.frame % DOUBLE_HIT_CYCLE - DOUBLE_EFFECT_FRAMES
            return round(HIT_PIXELS * (1 - tick / HIT_FRAMES)) if 0 <= tick < HIT_FRAMES else 0
        if index != self.actor or not self.active or not self.battle.party[index].alive:
            return 0
        if self.phase == 'actor_step':
            return -round(STEP_PIXELS * self.frame / STEP_FRAMES)
        if self.phase == 'actor_return':
            return -round(STEP_PIXELS * (1 - self.frame / RETURN_FRAMES))
        return -STEP_PIXELS

    def enemy_offset(self, index):
        """Physical actions move toward the party; casting and support stay put."""
        if index != self.enemy_actor or self.enemy_action not in ('attack', 'heavy_attack', 'double_attack', 'area_attack'):
            return 0
        pixels = HEAVY_STEP_PIXELS if self.enemy_action == 'heavy_attack' else ENEMY_STEP_PIXELS
        if self.phase == 'party_hit':
            return round(pixels * max(0, 1 - self.frame / HIT_FRAMES))
        if self.phase == 'enemy_effect':
            tick = self.frame % DOUBLE_HIT_CYCLE if self.enemy_action == 'double_attack' else self.frame
            if self.enemy_action == 'double_attack' and tick >= DOUBLE_EFFECT_FRAMES:
                return round(pixels * max(0, 1 - (tick - DOUBLE_EFFECT_FRAMES) / HIT_FRAMES))
            return round(pixels * min(1, (tick + 1) / DOUBLE_EFFECT_FRAMES))
        return 0

    def shake_offset(self):
        if self.legend.id:
            return self.legend.shake(self.phase, self.frame)
        if self.presentation_id == 'rare_impact' and self.phase == 'rare_feedback':
            return RARE_SHAKE_OFFSETS[min(self.frame, len(RARE_SHAKE_OFFSETS) - 1)]
        if self.enemy_action == 'heavy_attack' and self.phase == 'party_hit' and self.hit_targets:
            return HEAVY_SHAKE_OFFSETS[min(self.frame, len(HEAVY_SHAKE_OFFSETS) - 1)]
        return 0, 0

    def party_recoiling(self, index):
        return index in self.hit_targets and (self.phase == 'party_hit' or
            self.phase == 'enemy_effect' and self.enemy_action == 'double_attack' and
            DOUBLE_EFFECT_FRAMES <= self.frame % DOUBLE_HIT_CYCLE < DOUBLE_EFFECT_FRAMES + HIT_FRAMES)

    def holds_party_sprite(self, index):
        return index in self.hit_targets and self.phase in ('enemy_effect', 'status_effect', 'party_hit')

    def displayed_hp(self, index):
        # Rules have already resolved; only the displayed number waits for impact.
        if self.phase in ('enemy_effect', 'status_effect') and index in self.hit_targets and index < len(self.hp_before):
            return self.hp_before[index]
        return self.battle.party[index].hp

    def enemy_visual(self, index):
        if self.phase != 'enemy_death' or index not in self.deaths:
            if self.active and index in self.deaths:
                return True, 0  # Counter KO waits for attack FX/recoil before defeat FX.
            return self.battle.enemies[index].alive, 0
        if self.frame < DEATH_FLASH_FRAMES:
            return self.frame // DEATH_BLINK_FRAMES % 2 == 0, 0
        progress = (self.frame - DEATH_FLASH_FRAMES) / (DEATH_FRAMES - DEATH_FLASH_FRAMES)
        return True, round(DEATH_SINK_PIXELS * progress)

    def target_flashing(self, side, index):
        """A short target-only palette flash, with no screen fill."""
        return self.legend.flashing(self.phase, self.frame, side, index) or (
                self.presentation_id in ('rare_impact', 'rare_slash', 'rare_magic')
                and self.phase == 'rare_effect' and 3 <= self.frame < 5
                and (side, index) in self.skill_effect_targets)

    def effect_position(self, side, index):
        if side == 'party':
            return 98 + self.actor_offset(index), 13 + index * 16
        if self.battle.is_elysion_battle:
            return 40, 40
        return enemy_position(index, len(self.battle.enemies))

    def draw_rare_effect(self, pyxel):
        """At most four target blits. Sprites live in the Editor resource."""
        from .text import text
        if self.phase == 'rare_feedback':
            # One precomputed HP number per affected target; never recalculate damage.
            for side, index, delta in self.rare_hp_changes:
                x, y = self.effect_position(side, index)
                label = str(delta) if delta < 0 else '+' + str(delta)
                # Keep party feedback left of the name/HP columns and in its row.
                text(80 if side == 'party' else max(1, x - 1),
                     y + 4 if side == 'party' else max(11, y - 3), label, 3, 8)
            if self.rare_drain and self.actor is not None and self.target is not None:
                x, y = self.effect_position(*self.target)
                ax, ay = self.effect_position('party', self.actor)
                u, v = RARE_SPRITES['rare_heal']
                t = (self.frame + 1) / RARE_FEEDBACK_FRAMES
                pyxel.blt(round(x + (ax - x) * t), round(y + (ay - y) * t),
                          RARE_ASSET_BANK, u + 13, v + 2, 5, 5, 0)
            return
        frame = (0 if self.phase == 'rare_cast' else
                 min(RARE_FRAME_COUNT - 1, self.frame // EFFECT_FRAME_TICKS))
        u, v = RARE_SPRITES[self.presentation_id]
        # MAGIC gathers at the caster; the same rune then expands at all targets.
        targets = ([('party', self.actor)] if self.phase == 'rare_cast'
                   and self.presentation_id == 'rare_magic' else self.skill_effect_targets)
        for side, index in targets:
            x, y = self.effect_position(side, index)
            # Preserve the title, message panel and the party's HP/name columns.
            pyxel.clip(0 if side == 'enemy' else 80, 11, 96 if side == 'enemy' else 35, 66)
            movement = frame if self.presentation_id in ('rare_heal', 'rare_support') else 0
            movement *= 1 if self.rare_debuff else -1
            height = -RARE_FRAME_SIZE if self.rare_debuff else RARE_FRAME_SIZE
            pyxel.blt(x - 8, y - 8 + movement, RARE_ASSET_BANK,
                      u + frame * RARE_FRAME_SIZE, v, RARE_FRAME_SIZE, height, 0)
            if self.presentation_id == 'rare_magic' and self.phase == 'rare_effect':
                eu, ev = EFFECT_SPRITES[self.effect]
                pyxel.blt(x, y, ASSET_BANK, eu + frame * 16, ev, 16, 16, 0)
                # Small reflected tongues/arcs keep FIRE and LIGHTNING recognizable.
                pyxel.blt(x - 5, y - 3, ASSET_BANK, eu + frame * 16, ev, -16, 16, 0)
            pyxel.clip()

    def draw_effect(self, pyxel):
        if self.legend.id and self.phase in LEGEND_PHASES:
            self.legend.draw(pyxel, self)
            return
        if self.presentation_id and self.phase in ('rare_cast', 'rare_effect', 'rare_feedback'):
            self.draw_rare_effect(pyxel)
            return
        if self.phase == 'status_effect':
            for event in self.status_events:
                side, index = event['target']
                if side == 'party':
                    x, y = 98, 13 + index * 16
                elif self.battle.is_elysion_battle:
                    x, y = 40, 40
                else:
                    x, y = enemy_position(index, len(self.battle.enemies))
                icon = self.battle.status_definitions[event['status_id']].icon_id
                pyxel.circb(x + 8, y + 8, 3 + self.frame // 2, 2)
                pyxel.blt(x + 4, y + 4, ASSET_BANK, *STATUS_SPRITES[icon], 8, 8, 0)
            return
        if self.phase == 'enemy_effect':
            u, v = EFFECT_SPRITES[self.effect]
            if self.enemy_action == 'double_attack':
                tick = self.frame % DOUBLE_HIT_CYCLE
                if tick >= DOUBLE_EFFECT_FRAMES:
                    return  # Clear gap and per-hit recoil separate the two impacts.
                frame = tick
            elif self.enemy_action == 'heavy_attack':
                frame = min(2, self.frame * 3 // HEAVY_EFFECT_FRAMES)
            else:
                frame = (self.frame // EFFECT_FRAME_TICKS) % EFFECT_FRAMES
            for side, index in self.enemy_effect_targets:
                if side == 'party':
                    x, y = 98 + self.actor_offset(index), 13 + index * 16
                elif self.battle.is_elysion_battle:
                    x, y = 40, 40
                else:
                    x, y = enemy_position(index, len(self.battle.enemies))
                pyxel.blt(x, y, ASSET_BANK, u + frame * 16, v, 16, 16, 0)
            return
        if self.phase != 'skill_effect':
            return
        u, v = EFFECT_SPRITES[self.effect]
        frame = min(EFFECT_FRAMES - 1, self.frame // EFFECT_FRAME_TICKS)
        for side, index in self.skill_effect_targets or ([self.target] if self.target is not None else []):
            if side == 'party':
                x, y = 98 + self.actor_offset(index), 13 + index * 16
            elif self.battle.is_elysion_battle:
                x, y = 40, 40
            else:
                x, y = enemy_position(index, len(self.battle.enemies))
            pyxel.blt(x, y, ASSET_BANK, u + frame * 16, v, 16, 16, 0)
