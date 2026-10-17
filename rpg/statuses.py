"""Shared ailments; only poison may persist within a dungeon expedition."""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import random

STATUS_IDS = ('poison', 'paralyze', 'sleep', 'confusion')
CONTROL_STATUSES = ('paralyze', 'sleep', 'confusion')


@dataclass(frozen=True)
class StatusDefinition:
    name: str
    duration: int
    icon_id: str
    damage_fraction: float = .05
    skip_chance: float = .35
    power: float = .75
    enemy_weight: float = 40
    ally_weight: float = 40
    idle_weight: float = 20


def percentage(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 100)


def load_statuses(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / 'data/statuses.json'
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(raw, dict) or set(raw) != set(STATUS_IDS):
        raise ValueError('statuses.json: exactly poison/paralyze/sleep/confusion required')
    definitions = {}
    for ident, row in raw.items():
        try:
            definition = StatusDefinition(**row)
        except (TypeError, ValueError) as error:
            raise ValueError(f'statuses.json: invalid {ident}') from error
        if (not isinstance(definition.name, str) or not definition.name.strip()
                or not definition.name.isprintable() or type(definition.duration) is not int
                or not 1 <= definition.duration <= 9 or definition.icon_id not in STATUS_IDS
                or not percentage(definition.damage_fraction) or not 0 < definition.damage_fraction <= 1
                or not percentage(definition.skip_chance) or not 0 <= definition.skip_chance <= 1
                or not percentage(definition.power) or not 0 < definition.power <= 2
                or any(not percentage(n) for n in (definition.enemy_weight, definition.ally_weight, definition.idle_weight))
                or definition.enemy_weight + definition.ally_weight + definition.idle_weight <= 0):
            raise ValueError(f'statuses.json: invalid {ident}')
        definitions[ident] = definition
    return definitions


@lru_cache(maxsize=1)
def default_statuses():
    return load_statuses()


def active_statuses(target):
    values = getattr(target, 'statuses', {})
    return {key: turns for key, turns in values.items()
            if key in STATUS_IDS and type(turns) is int and turns > 0} if isinstance(values, dict) else {}


def clear_statuses(target, preserve_poison=False):
    """Keep only a living character's exact remaining poison ticks if requested."""
    poison = active_statuses(target).get('poison') if preserve_poison and target.alive else None
    target.statuses = {'poison': poison} if poison is not None else {}


def cure_statuses(target, status_ids):
    """Remove selected ailments from a living unit; return removed IDs.

    HP and the separate buff/debuff effects are untouched. Empty tuple means
    there was nothing to cure. IDs come from the existing status definitions.
    """
    if not target.alive:
        return ()
    states = active_statuses(target)
    removed = tuple(key for key in states if key in status_ids)
    for key in removed:
        states.pop(key)
    target.statuses = states
    return removed


def apply_status(target, status_id, chance=100, rng=None, definitions=None):
    """Percentage chance, optional 0..100 resistance, optional immunity IDs.

    Reject dead/invalid targets and another control ailment before drawing RNG.
    A reapplication refreshes duration; it never stacks potency.
    """
    if status_id not in STATUS_IDS or not target.alive or not percentage(chance):
        return False
    states = active_statuses(target)
    if status_id in CONTROL_STATUSES and any(key in states and key != status_id for key in CONTROL_STATUSES):
        return False
    if status_id in (getattr(target, 'status_immunities', ()) or ()):
        return False
    resistances = getattr(target, 'status_resistances', {}) or {}
    resistance = resistances.get(status_id, 0) if isinstance(resistances, dict) else 0
    resistance = resistance if percentage(resistance) else 0
    chance *= 1 - resistance / 100
    if chance <= 0 or chance < 100 and (rng or random).random() * 100 >= chance:
        return False
    definitions = definitions if definitions is not None else default_statuses()
    states[status_id] = definitions[status_id].duration
    target.statuses = states
    return True


def damage_hp(target, amount):
    """One HP loss path for regular damage and poison; wake on actual HP loss."""
    removed = min(max(0, target.hp), max(0, int(amount)))
    target.hp -= removed
    states = active_statuses(target)
    woke = removed > 0 and 'sleep' in states
    if woke:
        states.pop('sleep')
    target.statuses = states if target.alive else {}
    return removed, woke


def control_decision(target, definitions, rng):
    states = active_statuses(target)
    if 'sleep' in states:
        return 'sleep'
    if 'paralyze' in states and rng.random() < definitions['paralyze'].skip_chance:
        return 'paralyze'
    return 'confusion' if 'confusion' in states else None


def confusion_target(actor, allies, foes, definition, rng):
    choice = rng.choices(('enemy', 'ally', 'idle'),
                         (definition.enemy_weight, definition.ally_weight, definition.idle_weight))[0]
    candidates = [unit for unit in (foes if choice == 'enemy' else allies if choice == 'ally' else ())
                  if unit.alive and unit is not actor]
    return rng.choice(candidates) if candidates else None
