"""Editable enemy actions; no graphics, audio, floor rules or condition AI."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
from .statuses import STATUS_IDS, percentage


ACTION_TARGETS = {"physical_single": "random_player", "magic_single": "random_player",
                  "physical_all": "all_players", "magic_all": "all_players",
                  "guard": "self", "buff": "self", "debuff": "random_player", "status": "random_player"}


@dataclass(frozen=True)
class EnemyAction:
    name: str
    type: str
    target: str
    power: float = 1.0
    hits: int = 1
    effect: str = ""
    modifier: float = 1.0
    duration: int = 0
    effect_id: str = "blunt"
    status_id: str = ""
    status_chance: float = 100


def positive(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def usable(action):
    if (not isinstance(action, EnemyAction) or not isinstance(action.type, str)
            or ACTION_TARGETS.get(action.type) != action.target
            or not isinstance(action.effect_id, str)):
        return False
    if not positive(action.power) or type(action.hits) is not int or not 1 <= action.hits <= 8:
        return False
    if (action.status_id and action.status_id not in STATUS_IDS or not percentage(action.status_chance)
            or action.type == 'status' and not action.status_id):
        return False
    if action.type == 'guard':
        return positive(action.modifier) and action.modifier <= 1
    if action.type in ('buff', 'debuff'):
        effects = ('power_up',) if action.type == 'buff' else ('weaken', 'armor_break', 'slow')
        return (action.effect in effects and positive(action.modifier)
                and (1 < action.modifier <= 2 if action.type == 'buff' else action.modifier < 1)
                and type(action.duration) is int and 1 <= action.duration <= 9)
    return True


def load_enemy_actions(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / 'data/enemy_actions.json'
    rows = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(rows, dict):
        raise ValueError('enemy_actions.json: object required')
    actions = {}
    for ident, row in rows.items():
        try:
            action = EnemyAction(**row)
        except (TypeError, ValueError) as error:
            raise ValueError(f'enemy_actions.json: invalid action {ident}') from error
        if (not isinstance(ident, str) or not ident or not ident.isascii()
                or not isinstance(action.name, str) or not action.name.strip() or not action.name.isprintable()
                or not usable(action)):
            raise ValueError(f'enemy_actions.json: invalid action {ident}')
        actions[ident] = action
    if any(ident not in actions or actions[ident].type != kind for ident, kind in
           (('attack', 'physical_single'), ('magic', 'magic_single'))):
        raise ValueError('enemy_actions.json: attack and magic required for fallback')
    return actions


def action_categories(action):
    """Only tags needed for the two-action safety limits; no skill changes."""
    tags = set()
    if action.target == 'all_players' and action.type.startswith(('physical', 'magic')):
        tags.add('major_aoe')
    if action.status_id in ('sleep', 'paralyze', 'confusion'):
        tags.add('control')
    if action.type in ('physical_single', 'magic_single'):
        tags.add('single_attack')
    return tags or {'utility'}


def enemy_action_rows(enemy):
    rows = enemy.actions
    for phase in sorted(enemy.ai.get('phases', ()), key=lambda row: row['hp_at_most']):
        if enemy.hp <= enemy.max_hp * phase['hp_at_most']:
            return phase['actions']
    return rows


def choose_enemy_action(enemy, definitions, rng, history=(), recent=()):
    """Skip unavailable entries; no retries or unbounded action selection."""
    rows = enemy_action_rows(enemy)
    rows = rows if isinstance(rows, (list, tuple)) else ()
    available = [(row['id'], row['weight']) for row in rows
                 if isinstance(row, dict) and isinstance(row.get('id'), str)
                 and usable(definitions.get(row['id'])) and positive(row.get('weight'))]
    ai = enemy.ai
    if ai:
        used_tags = set().union(*(action_categories(definitions[k]) for k in history))
        last_tags = action_categories(definitions[recent[-1]]) if recent else set()
        aoe_limit = ai.get('max_consecutive_aoe', 0)
        aoe_limited = aoe_limit and len(recent) >= aoe_limit and all(
            'major_aoe' in action_categories(definitions[k]) for k in recent[-aoe_limit:])
        available = [(ident, weight) for ident, weight in available
            if not (ai.get('avoid_active_buffs') and definitions[ident].type == 'buff'
                    and definitions[ident].effect in enemy.effects)
            and not (ai.get('avoid_repeat_control') and 'control' in last_tags
                     and 'control' in action_categories(definitions[ident]))
            and not (aoe_limited and 'major_aoe' in action_categories(definitions[ident]))
            and not (ai.get('actions_per_round', 1) > 1 and
                (ident in history or bool(used_tags & action_categories(definitions[ident]) & {'major_aoe', 'control'})))]
    if not available:
        return None
    ids, weights = zip(*available)
    largest = max(weights)
    return rng.choices(ids, [weight / largest for weight in weights])[0]


def validate_enemy_action_lists(enemies, definitions):
    for row in enemies:
        actions = row.get('actions')
        if actions is not None and (not isinstance(actions, list) or any(
                not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or item['id'] not in definitions or not positive(item.get('weight')) for item in actions)):
            raise ValueError(f"enemies.json: invalid actions for {row['id']}")
        ai = row.get('ai', {})
        allowed = {'actions_per_round', 'avoid_active_buffs', 'avoid_repeat_control', 'max_consecutive_aoe', 'phases'}
        if not isinstance(ai, dict) or set(ai)-allowed or ai and not row.get('boss'):
            raise ValueError(f"enemies.json: invalid boss ai for {row['id']}")
        if (type(ai.get('actions_per_round', 1)) is not int or ai.get('actions_per_round', 1) not in (1, 2)
                or any(type(ai[k]) is not bool for k in ('avoid_active_buffs', 'avoid_repeat_control') if k in ai)
                or type(ai.get('max_consecutive_aoe', 2)) is not int
                or not 1 <= ai.get('max_consecutive_aoe', 2) <= 3):
            raise ValueError(f"enemies.json: invalid boss ai options for {row['id']}")
        phases = ai.get('phases', [])
        if not isinstance(phases, list) or len(phases) > 3:
            raise ValueError(f"enemies.json: invalid phases for {row['id']}")
        thresholds = set()
        for phase in phases:
            if (not isinstance(phase, dict) or set(phase) != {'hp_at_most', 'actions'}
                    or not positive(phase['hp_at_most']) or phase['hp_at_most'] > 1
                    or phase['hp_at_most'] in thresholds):
                raise ValueError(f"enemies.json: invalid phase for {row['id']}")
            thresholds.add(phase['hp_at_most'])
            entries = phase['actions']
            if not isinstance(entries, list) or not entries or any(
                    not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] not in definitions
                    or not positive(item.get('weight')) for item in entries):
                raise ValueError(f"enemies.json: invalid phase actions for {row['id']}")
