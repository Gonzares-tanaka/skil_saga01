"""Shared helpers for finite learned skills; no automatic refills."""
MAX_SKILLS = 6  # Default; data/settings.json skill_slots overrides this.
FALLBACK_SKILL = "punch"


def ensure_attack(actor, skills, slots=MAX_SKILLS, discovered=None):
    """Prototype safety net, also covering a full loadout of support skills."""
    if any(skills[s].effect in ("damage", "drain") and actor.skill_uses.get(s, 0) > 0
           for s in actor.skills):
        return []
    messages = []
    for sid in list(actor.skills):
        if actor.skill_uses.get(sid, 0) <= 0:
            actor.forget(sid)
    if len(actor.skills) >= slots:
        sid = actor.skills[-1]
        messages.append(f"救済: {actor.name} {skills[sid].name}を放棄")
        actor.forget(sid)
    actor.learn(skills[FALLBACK_SKILL])
    if discovered is not None:
        discovered.add(FALLBACK_SKILL)
    messages.append(f"救済: {actor.name} パンチ {skills[FALLBACK_SKILL].max_uses}回")
    return messages
