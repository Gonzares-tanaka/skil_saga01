"""Repeatable multi-seed balance checks; writes a development report, not a save."""
from collections import Counter
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import simulate
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.growth import grow_and_spark


def report():
    sessions = []
    for debug in (False, True):
        for seed in range(20):
            session = Session(*load_content(), seed=seed)
            session.debug = debug
            result = simulate(session, 50)
            assert result["wins"] + result["losses"] + result["draws"] == 50
            assert all(len(c.skills) <= session.settings["skill_slots"] and len(c.skills) == len(set(c.skills)) for c in session.party)
            assert all(0 <= c.hp <= c.max_hp for c in session.party)
            sessions.append({k: result[k] for k in ("debug", "wins", "losses", "draws")} | {"seed": seed})
    settings, skills, party, _ = load_content()
    actor = party[0]
    depths = []
    # Independent initial-state trials at both depths, no forced rarity or DEBUG.
    for floor, multiplier in ((1, 1), (15, 2)):
        rng = random.Random(2026)
        rarities, supports = Counter(), Counter()
        for _ in range(100000):
            actor.skills.clear()
            actor.skill_uses.clear()
            actor.history.clear()
            actor.max_hp, actor.strength, actor.agility, actor.intellect = 48, 8, 5, 2
            grow_and_spark(actor, skills, settings, rng, 1, spark_multiplier=multiplier)
            if actor.skills:
                skill = skills[actor.skills[0]]
                rarities[skill.rarity] += 1
                if skill.duration:
                    supports[skill.id] += 1
        assert rarities["LEGEND"] > 0
        assert len(supports) == 6
        assert rarities["COMMON"] > rarities["UNCOMMON"] > rarities["RARE"] > rarities["LEGEND"]
        depths.append({"floor": floor, "multiplier": multiplier, "trials": 100000,
                       "sparks": sum(rarities.values()), "rarities": dict(rarities), "support_skills": dict(supports)})
    assert depths[1]['sparks'] > depths[0]['sparks'] * 1.8
    example = simulate(Session(*load_content(), seed=42), 50)
    for character in example["party"]:
        character.pop("history")
    result = {"simulation_battles": 2000, "sessions": sessions,
              "fresh_first_win_trials": 100000,
              "spark_rarities": depths[0]['rarities'], "depth_trials": depths,
              "seed_42_example": example}
    output = ROOT / "verification" / "balance.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for debug in (False, True):
        rows = [s for s in sessions if s["debug"] == debug]
        print(f"debug={debug}: {sum(s['wins'] for s in rows)} wins / "
              f"{sum(s['losses'] for s in rows)} losses / {sum(s['draws'] for s in rows)} draws")
    for row in depths:
        print(f"B{row['floor']}F: {row['sparks']}/100000 sparks; {row['rarities']}")
    print(json.dumps(example, indent=2))
    print(f"Report: {output}")


if __name__ == "__main__":
    report()
