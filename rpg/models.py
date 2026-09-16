from dataclasses import dataclass, field


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

    def power(self, actor):
        strength = actor.strength * effect_factor(actor, "power_up") * (1.5 if actor.berserk else 1)
        return max(1, round((strength * self.str_scale
                            + actor.agility * self.agi_scale
                            + actor.intellect * effect_factor(actor, "focus") * self.int_scale) * self.hits))

    def formula(self):
        if self.effect == "return":
            return "探索専用 / 拠点へ帰還"
        if self.duration:
            return f"倍率 {self.modifier:g} / {self.duration}ターン"
        parts = [f"{stat}*{scale:g}" for stat, scale in
                 (("STR", self.str_scale), ("AGI", self.agi_scale),
                  ("INT", self.int_scale)) if scale]
        formula = "+".join(parts) or "能力強化"
        return f"({formula})*{self.hits}" if self.hits > 1 else formula


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
    growth_points: dict[str, float] = field(default_factory=dict)
    used_skills: dict[str, int] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    pending_skill: str | None = None
    cooldowns: dict[str, int] = field(default_factory=dict)
    guarding: bool = False
    counter: Skill | None = None
    berserk: int = 0
    effects: dict[str, tuple[float, int]] = field(default_factory=dict)

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

    def forget(self, skill_id):
        self.skills.remove(skill_id)
        self.skill_uses.pop(skill_id, None)
        self.cooldowns.pop(skill_id, None)

    def reset_battle_state(self):
        """Reset per-battle effects without healing wounds or reviving allies."""
        self.growth_points.clear()
        self.used_skills.clear()
        self.cooldowns.clear()
        self.guarding = False
        self.counter = None
        self.berserk = 0
        self.effects.clear()


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

    def __post_init__(self):
        self.hp = self.max_hp

    @property
    def alive(self):
        return self.hp > 0


@dataclass(frozen=True)
class Action:
    actor: int
    kind: str = "DEFEND"
    target: int = 0
    skill_id: str | None = None


def effect_factor(actor, effect):
    return actor.effects.get(effect, (1.0, 0))[0]


def battle_agility(actor):
    return actor.agility * effect_factor(actor, "slow")
