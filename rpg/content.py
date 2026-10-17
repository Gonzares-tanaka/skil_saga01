"""UTF-8 JSON data. No expression evaluation or executable data files."""
import json
import math
from pathlib import Path

from .models import Character, Skill
from .skill_resources import MAX_SKILLS, FALLBACK_SKILL
from .labels import EFFECTS, BUFFS
from .enemy_actions import load_enemy_actions, validate_enemy_action_lists
from .statuses import load_statuses, percentage
from .skill_targets import SKILL_TARGETS
from .rare_skill_presentation import RARE_PRESENTATION_IDS
from .legend_skill_presentation import LEGEND_PRESENTATION_IDS

ROOT = Path(__file__).resolve().parent.parent
RARITIES = ("BASIC", "COMMON", "UNCOMMON", "RARE", "LEGEND")


def validate_skill(skill, status_definitions=None):
    """Validate the same model for JSON data and isolated test fixtures."""
    statuses = load_statuses() if status_definitions is None else status_definitions
    def require(ok, message):
        if not ok:
            raise ValueError(f'{skill.id}: {message}')
    def number(value, low, high):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and low <= value <= high)
    def integer(value, low, high):
        return type(value) is int and low <= value <= high
    effects = {'damage', 'heal', 'revive', 'counter', 'drain', 'berserk', 'return', 'status', 'cure'} | EFFECTS.keys()
    require(skill.effect in effects, 'Unknown effect')
    require(skill.target in SKILL_TARGETS, 'Invalid target')
    require(skill.presentation_id is None or (
            isinstance(skill.presentation_id, str) and (
                skill.rarity == 'RARE' and skill.presentation_id in RARE_PRESENTATION_IDS
                or skill.rarity == 'LEGEND' and skill.presentation_id in LEGEND_PRESENTATION_IDS)),
            'Invalid presentation_id')
    if skill.effect == 'revive':
        allowed = ('ally',)
    elif skill.effect in ('counter', 'berserk', 'return'):
        allowed = ('self',)
    elif skill.effect in ('heal', 'cure') or skill.effect in BUFFS:
        allowed = ('ally', 'self', 'all_allies')
    else:
        allowed = ('enemy', 'all_enemies', 'random_enemy')
    require(skill.target in allowed, 'Invalid effect/target combination')
    require(percentage(skill.status_chance), 'status_chance must be 0..100')
    require(skill.status_id is None or isinstance(skill.status_id, str) and skill.status_id in statuses,
            'Unknown status_id')
    require(skill.status_id is not None or skill.status_chance == 0, 'status_chance without status_id')
    require(skill.status_id is None or skill.effect in ('damage', 'drain', 'status'), 'Invalid status effect')
    require(skill.effect != 'status' or skill.status_id is not None, 'Pure status needs status_id')
    require(isinstance(skill.cure_statuses, (list, tuple))
            and all(isinstance(key, str) and key in statuses for key in skill.cure_statuses)
            and len(set(skill.cure_statuses)) == len(skill.cure_statuses), 'Invalid cure_statuses')
    require(bool(skill.cure_statuses) == (skill.effect == 'cure'), 'Cure needs its own nonempty status list')
    require(type(skill.field_usable) is bool, 'field_usable must be boolean')
    require(not skill.field_usable or skill.effect in ('heal', 'cure', 'return'), 'Invalid field use effect')
    require(skill.effect != 'return' or skill.field_usable, 'RETURN must be field usable')
    if skill.effect in EFFECTS:
        require(integer(skill.duration, 1, 9), 'duration must be 1..9')
        lo, hi = (1.01, 2) if skill.effect in ('power_up', 'focus') else (0.1, 0.99)
        require(number(skill.modifier, lo, hi), 'Invalid modifier')
    require(all(number(v, 0, 100) for v in (skill.str_scale, skill.agi_scale, skill.int_scale)), 'Invalid scales')
    require(integer(skill.hits, 1, 20) and integer(skill.cooldown, 0, 99), 'Invalid hits/cooldown')
    require(integer(skill.max_uses, 1, 99), 'max_uses must be 1..99')
    no_restore = type(skill.relearn_cost) is int and type(skill.relearn_uses) is int and skill.relearn_cost == skill.relearn_uses == 0
    require(no_restore or integer(skill.relearn_cost, 1, 999) and integer(skill.relearn_uses, 1, skill.max_uses),
            'Invalid relearn_cost/relearn_uses pair')
    require(skill.skill_type in ('physical', 'speed', 'magic', 'healing', 'support'), 'Invalid skill_type')
    require(set(skill.growth) == {'HP', 'STR', 'AGI', 'INT'}
            and all(number(v, 0, 10) for v in skill.growth.values()), 'Invalid growth contributions')


def load_content(directory=None):
    directory = Path(directory) if directory else ROOT / "data"
    def read(name):
        with (directory / f"{name}.json").open(encoding="utf-8-sig") as f:
            return json.load(f)
    settings, rows, enemies = read("settings"), read("party"), read("enemies")
    status_definitions = load_statuses(directory / 'statuses.json')
    validate_enemy_action_lists(enemies, load_enemy_actions())
    settings.setdefault("skill_slots", MAX_SKILLS)
    skills = {}
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    def number(value, low=0, high=float("inf")):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and low <= value <= high)
    def integer(value, low=0, high=9999):
        return type(value) is int and low <= value <= high
    def name_ok(value):
        return isinstance(value, str) and bool(value.strip()) and value.isprintable()
    for row in read("skills"):
        skill = Skill(**row)
        require(name_ok(skill.name) and name_ok(skill.id) and skill.id.isascii(), "技名は表示可能な文字、IDは半角英数字で指定してください。")
        require(skill.id not in skills, f"Duplicate skill: {skill.id}")
        require(skill.rarity in RARITIES, f"Unknown rarity: {skill.id}")
        validate_skill(skill, status_definitions)
        require(name_ok(skill.description), f"Invalid description: {skill.id}")
        skills[skill.id] = skill
    require(bool(skills), "skills.json must contain skills.")
    require(len(rows) == 4 and bool(enemies), "Exactly 4 party members and at least 1 enemy are required.")
    for row in rows + enemies:
        require(name_ok(row["name"]), "名前には改行や制御文字を使用できません。")
        require(integer(row['max_hp'], 1, 9999 if row.get('boss') else 999)
                and all(integer(row[k], 1, 999) for k in ("str", "agi", "int")), f"Invalid stats: {row['name']}")
        require(len(row["sprite"]) == 2 and all(integer(v, 0, 240) for v in row["sprite"]), "Sprite must fit a 16x16 area in bank 0.")
    require(len({r["name"] for r in rows}) == 4, "Party names must be unique.")
    for row in enemies:
        require(number(row["magic_chance"], 0, 1), "Invalid magic_chance.")
        require(all(number(row.get(k, 0), 0, 999) for k in ("defense", "magic_defense")), "Invalid enemy defense.")
    for row in rows:
        require(row["growth_type"] in settings["growth_rates"], "Unknown growth type.")
    for rates in settings["growth_rates"].values():
        require(all(number(rates[k], 0, 1) for k in ("HP", "STR", "AGI", "INT")), "Growth rates must be 0..1.")
    for key in ("spark_chance", "debug_spark_chance", "growth_per_point", "growth_bonus_cap"):
        require(number(settings[key], 0, 1), f"{key} must be 0..1.")
    for category in ("physical", "speed", "magic", "support", "healing"):
        rates = settings["category_growth"][category]
        require(all(stat in ("HP", "STR", "AGI", "INT") and number(rate, 0, 0.2)
                    for stat, rate in rates.items()), f"Invalid category_growth: {category}")
    weights = settings["rarity_weights"]
    require(all(number(weights[r], 0.000001) for r in RARITIES), "Every rarity must have a positive weight (including LEGEND).")
    require(integer(settings["skill_slots"], 1, 8), "skill_slots must be 1..8.")
    require(integer(settings["max_rounds"], 1, 999), "Invalid max_rounds.")
    gains = settings["hp_gain"]
    require(len(gains) == 2 and all(integer(x, 1) for x in gains) and gains[0] <= gains[1], "Invalid hp_gain.")
    for key in ("enemy_hp_per_win", "enemy_power_per_win", "enemy_scaling_cap"):
        require(number(settings[key], 0, 999), f"Invalid {key}.")
    party = [Character(r["name"], r["growth_type"], r["max_hp"], r["str"], r["agi"], r["int"], tuple(r["sprite"])) for r in rows]
    require(FALLBACK_SKILL in skills and skills[FALLBACK_SKILL].effect == "damage" and skills[FALLBACK_SKILL].cooldown == 0, "救済用punchは待ち時間0の攻撃技として必要です。")
    for actor, row in zip(party, rows):
        initial = row["initial_skills"]
        require(1 <= len(initial) <= settings["skill_slots"] and len(set(initial)) == len(initial), "Invalid initial skill slots.")
        require(all(s in skills for s in initial), "Unknown initial skill.")
        require(any(skills[s].effect == "damage" and skills[s].max_uses >= 25 and skills[s].cooldown == 0 for s in initial), "初期技に25回以上・待ち0の攻撃技が必要です。")
        for sid in initial:
            actor.learn(skills[sid])
    return settings, skills, party, enemies
