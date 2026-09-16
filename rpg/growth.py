"""One growth/spark roll per character after victory, with no stat gates."""
from .labels import RARITIES


def growth_bonus(actor, stat, settings):
    return min(settings["growth_bonus_cap"], actor.growth_points.get(stat, 0) * settings["growth_per_point"])


def spark(character, skills, settings, rng, allowed=None, discovered=None):
    if character.pending_skill is not None:
        raise ValueError("先に習得待ちの技を選択してください。")
    groups = {}
    for skill in skills.values():
        if skill.id not in character.skills and (allowed is None or skill.rarity in allowed):
            groups.setdefault(skill.rarity, []).append(skill)
    if not groups:
        return [f"{character.name} 閃き候補なし"]
    rarities = list(groups)
    rarity = rng.choices(rarities, [settings["rarity_weights"][r] for r in rarities])[0]
    skill = rng.choice(groups[rarity])
    if discovered is not None:
        discovered.add(skill.id)
    message = f"{character.name} 閃き! {skill.name} [{RARITIES[rarity]}] {skill.max_uses}/{skill.max_uses}回"
    if len(character.skills) < settings["skill_slots"]:
        character.learn(skill)
    else:
        character.pending_skill = skill.id
        message += " 入替待ち"
    return [message]


def grow_and_spark(character, skills, settings, rng, battle_number, debug=False,
                   discovered=None, spark_multiplier=1.0):
    if character.pending_skill is not None:
        raise ValueError("先に習得待ちの技を選択してください。")
    messages = []
    rates = settings["growth_rates"][character.growth_type]
    for stat, attribute in (("HP", "max_hp"), ("STR", "strength"),
                            ("AGI", "agility"), ("INT", "intellect")):
        bonus = growth_bonus(character, stat, settings)
        if rng.random() < min(1, rates[stat] + bonus):
            gain = rng.randint(*settings["hp_gain"]) if stat == "HP" else 1
            setattr(character, attribute, getattr(character, attribute) + gain)
            messages.append(f"{character.name} {stat} +{gain}")

    chance = spark_probability(settings, spark_multiplier, debug)
    if rng.random() < chance:
        messages.extend(spark(character, skills, settings, rng, discovered=discovered))
    if not messages:
        messages.append(f"{character.name} 変化なし")
    tag = " DEBUG" if debug else ""
    character.history.extend(f"B{battle_number}{tag} {line}" for line in messages)
    return messages


def spark_probability(settings, multiplier=1.0, debug=False):
    # Debug remains a fixed high rate so the depth multiplier can be compared normally.
    return min(1.0, settings["debug_spark_chance"] if debug else settings["spark_chance"] * multiplier)
