"""Shared helpers for finite learned skills; no automatic refills."""
MAX_SKILLS = 6  # Default; data/settings.json skill_slots overrides this.
FALLBACK_SKILL = "punch"
FALLBACK_SKILLS = ("punch", "spark")
RESCUE_SKILLS = {
    "rou": ("spark", "ミオ"),
    "kai": ("spark", "ミオ"),
    "mio": ("punch", "ロウ"),
    "sen": ("spark", "ミオ"),
}


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
    # Real party identity comes from stable party slots, never display names,
    # stats, growth type or editable sprites. Keep legacy synthetic actors safe.
    skill_id, companion = RESCUE_SKILLS.get(actor.party_id, (FALLBACK_SKILL, "ロウ"))
    actor.learn(skills[skill_id])
    if discovered is not None:
        discovered.add(skill_id)
    messages.extend((f"{actor.name} こうげきのてだてが", "なくなった！",
                     "ピンチの中で", f"{companion}の「{skills[skill_id].name}」を", "おもいだした！"))
    return messages
