from dataclasses import dataclass, field
from copy import deepcopy
from .labels import EFFECTS
from .statuses import clear_statuses


MASTERED_POWER_MULTIPLIER = 1.2


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    rarity: str
    effect: str
    target: str
    str_scale: float
    agi_scale: float
    int_scale: float
    hits: int
    cooldown: int
    description: str
    max_uses: int
    skill_type: str
    growth: dict[str, float]
    duration: int = 0
    modifier: float = 1.0
    relearn_cost: int = 0
    relearn_uses: int = 0
    effect_id: str = 'blunt'  # Optional presentation data; never used in damage rules.
    status_id: str | None = None
    status_chance: float = 0  # Percentage, matching EnemyAction (0..100).
    cure_statuses: tuple[str, ...] = ()
    field_usable: bool | None = None
    presentation_id: str | None = None  # Static RARE visuals; never saved or used by rules.

    def __post_init__(self):
        # Preserve the five existing field skills without changing their JSON.
        if self.field_usable is None:
            object.__setattr__(self, 'field_usable', self.effect in ('heal', 'return'))

    @property
    def can_relearn(self):
        # Validation rejects incomplete/nonpositive pairs; no rarity/effect gate.
        return bool(self.relearn_cost or self.relearn_uses)

    @property
    def mastery_label(self):
        return f"再取得POWER x{MASTERED_POWER_MULTIPLIER:g}" if self.effect in ("damage", "drain") else "習熟記録"

    def power(self, actor, apply_mastery=True):
        strength = actor.strength * effect_factor(actor, "power_up") * (1.5 if actor.berserk else 1)
        base = (strength * self.str_scale + actor.agility * self.agi_scale
                + actor.intellect * effect_factor(actor, "focus") * self.int_scale) * self.hits
        factor = actor.power_multiplier(self) if apply_mastery else 1.0
        return max(1, round(base * factor))

    def formula(self):
        if self.effect == 'status':
            return f"状態異常付与 {self.status_chance:g}%"
        if self.effect == 'cure':
            return "指定の状態異常を治療"
        if self.effect == "return":
            return "探索専用 / 拠点へ帰還"
        if self.effect == "revive":
            return "戦闘不能をHP25%で蘇生"
        if self.duration:
            return f"倍率 {self.modifier:g} / {self.duration}ターン"
        parts = [f"{stat}*{scale:g}" for stat, scale in
                 (("STR", self.str_scale), ("AGI", self.agi_scale),
                  ("INT", self.int_scale)) if scale]
        formula = "+".join(parts) or "能力強化"
        return f"({formula})*{self.hits}" if self.hits > 1 else formula


@dataclass
class FieldSkillResult:
    used: bool
    messages: list[str]
    cured_count: int = 0
    returned: bool = False


@dataclass
class Character:
    name: str
    growth_type: str
    max_hp: int
    strength: int
    agility: int
    intellect: int
    sprite: tuple
    hp: int = field(init=False)
    skills: list[str] = field(default_factory=list)
    skill_uses: dict[str, int] = field(default_factory=dict)
    mastered_skills: set[str] = field(default_factory=set, repr=False)
    mastered_copies: set[str] = field(default_factory=set, repr=False)
    growth_points: dict[str, float] = field(default_factory=dict)
    used_skills: dict[str, int] = field(default_factory=dict)
    category_uses: dict[str, int] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    pending_skill: str | None = None
    cooldowns: dict[str, int] = field(default_factory=dict)
    guarding: bool = False
    counter: Skill | None = None
    berserk: int = 0
    effects: dict[str, tuple[float, int]] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict, repr=False)
    status_resistances: dict[str, float] = field(default_factory=dict, repr=False)
    status_immunities: tuple[str, ...] = field(default_factory=tuple, repr=False)

    def __post_init__(self):
        self.hp = self.max_hp

    @property
    def alive(self):
        return self.hp > 0

    def recover(self):
        self.hp = self.max_hp
        self.reset_battle_state()

    def learn(self, skill):
        if skill.id in self.skills:
            raise ValueError("既に習得している技です。")
        self.skills.append(skill.id)
        self.skill_uses[skill.id] = skill.max_uses
        if self.next_power_multiplier(skill) > 1:
            self.mastered_copies.add(skill.id)

    def next_max_uses(self, skill):
        return skill.max_uses

    def max_uses(self, skill):
        return skill.max_uses

    def relearn_uses(self, skill):
        return skill.relearn_uses

    def next_power_multiplier(self, skill):
        return MASTERED_POWER_MULTIPLIER if skill.id in self.mastered_skills and skill.effect in ("damage", "drain") else 1.0

    def power_multiplier(self, skill):
        return MASTERED_POWER_MULTIPLIER if skill.id in self.mastered_copies and skill.effect in ("damage", "drain") else 1.0

    def forget(self, skill_id):
        self.skills.remove(skill_id)
        self.skill_uses.pop(skill_id, None)
        self.mastered_copies.discard(skill_id)
        self.cooldowns.pop(skill_id, None)

    def reset_battle_state(self, preserve_poison=False):
        """Reset per-battle effects without healing wounds or reviving allies."""
        self.growth_points.clear()
        self.used_skills.clear()
        self.category_uses.clear()
        self.cooldowns.clear()
        self.guarding = False
        self.counter = None
        self.berserk = 0
        self.effects.clear()
        clear_statuses(self, preserve_poison)


@dataclass
class Enemy:
    name: str
    max_hp: int
    strength: int
    agility: int
    intellect: int
    sprite: tuple
    magic_chance: float = 0
    hp: int = field(init=False)
    guarding: bool = False
    berserk: int = 0
    defense: float = 0
    magic_defense: float = 0
    effects: dict[str, tuple[float, int]] = field(default_factory=dict)
    id: str = ""
    actions: list[dict] = field(default_factory=list, repr=False)
    ai: dict = field(default_factory=dict, repr=False)  # Static boss rules, never saved.
    guard_multiplier: float = 0.5
    statuses: dict[str, int] = field(default_factory=dict, repr=False)
    status_resistances: dict[str, float] = field(default_factory=dict, repr=False)
    status_immunities: tuple[str, ...] = field(default_factory=tuple, repr=False)

    @classmethod
    def from_definition(cls, row, **overrides):
        """Keep the fixed data ID separate from names and encounter scaling."""
        values = dict(name=row["name"], max_hp=row["max_hp"], strength=row["str"],
                      agility=row["agi"], intellect=row["int"], sprite=tuple(row["sprite"]),
                      magic_chance=row["magic_chance"], defense=row.get("defense", 0),
                      magic_defense=row.get("magic_defense", 0),
                      actions=deepcopy(row.get("actions") or []))
        values['status_resistances'] = deepcopy(row.get('status_resistances') or {})
        values['status_immunities'] = tuple(row.get('status_immunities') or ())
        values['ai'] = deepcopy(row.get('ai') or {})
        values.update(overrides)
        values["id"] = row["id"]
        return cls(**values)

    def __post_init__(self):
        self.hp = self.max_hp

    @property
    def alive(self):
        return self.hp > 0


@dataclass(frozen=True)
class Action:
    actor: int
    kind: str = "GUARD"
    target: int = 0
    skill_id: str | None = None
    item_id: str | None = None


def effect_factor(actor, effect):
    return actor.effects.get(effect, (1.0, 0))[0]


def battle_agility(actor):
    return actor.agility * effect_factor(actor, "slow")
