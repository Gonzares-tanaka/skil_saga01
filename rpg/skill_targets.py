"""Small shared target resolver. Only battle execution may draw random targets."""

SKILL_TARGETS = ('enemy', 'ally', 'self', 'all_enemies', 'all_allies', 'random_enemy')
AUTO_TARGETS = ('self', 'all_enemies', 'all_allies', 'random_enemy')


def target_refs(skill, actor_index, party, enemies, selected=0, rng=None):
    """Return (side, index) pairs; a random preview returns no targets/no RNG draw.

    Keep legacy single-target fallback to the first living member. REVIVE alone
    selects a dead ally. All-target healing/buffs/cures never include KO members.
    """
    if skill.target == 'self':
        return [('party', actor_index)] if party[actor_index].alive else []
    side, group = ('party', party) if skill.target in ('ally', 'all_allies') else ('enemy', enemies)
    if skill.effect == 'revive':
        return [(side, selected)] if 0 <= selected < len(group) and not group[selected].alive else []
    living = [(side, i) for i, unit in enumerate(group) if unit.alive]
    if skill.target in ('all_enemies', 'all_allies'):
        return living
    if skill.target == 'random_enemy':
        return [rng.choice(living)] if living and rng is not None else []
    if 0 <= selected < len(group) and group[selected].alive:
        return [(side, selected)]
    return living[:1]
