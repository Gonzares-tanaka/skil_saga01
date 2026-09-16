"""Run the game or a reproducible headless growth simulation."""
# title: Pyxel Dungeon RPG Prototype
# desc: 4人パーティのスキル消耗・閃き・帰還を検証する開発中プロトタイプ
# license: TBD
import argparse
import json

from rpg.battle import Session
from rpg.content import load_content


def simulate(session, count):
    for _ in range(count):
        battle = session.next_battle()
        while not battle.outcome:
            battle.begin_round(battle.auto_actions())
            while battle.queue:
                battle.step()
        session.settle()
        # Headless runs have no selection UI; explicitly keep existing skills.
        for actor_index in session.pending_replacements:
            session.resolve_replacement(actor_index)
    return {
        "battles": session.completed, "wins": session.wins,
        "losses": session.losses, "draws": session.draws, "debug": session.debug,
        "party": [{"name": c.name, "type": c.growth_type, "HP": c.max_hp,
                   "STR": c.strength, "AGI": c.agility, "INT": c.intellect,
                   "skills": [session.skills[s].name for s in c.skills],
                   "skill_uses": {s: {"current": c.skill_uses[s], "max": session.skills[s].max_uses} for s in c.skills},
                   "history": c.history} for c in session.party],
    }


def main():
    parser = argparse.ArgumentParser(description="SPARK / a tiny growth laboratory")
    parser.add_argument("--seed", type=int, help="Reproducible random seed")
    parser.add_argument("--simulate", type=int, metavar="N", help="Play N battles without a window")
    parser.add_argument("--debug", action="store_true", help="Start with boosted spark chance")
    parser.add_argument("--battle-lab", action="store_true", help="Original endless battle lab (full recovery between battles)")
    args = parser.parse_args()
    if args.simulate is not None and args.simulate < 1:
        parser.error("--simulate must be positive")
    try:
        session = Session(*load_content(), seed=args.seed)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Data error: {error}\nCheck data/*.json (see README.md).\n")
    session.debug = args.debug
    if args.simulate:
        print(json.dumps(simulate(session, args.simulate), indent=2, ensure_ascii=False))
    else:
        if args.battle_lab:
            from rpg.app import App
        else:
            from rpg.dungeon_app import DungeonApp as App
        try:
            App(session)
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.exit(1, f"Resource/data error: {error}\nCheck game.pyxres, area2.pyxres, area3.pyxres and data/dungeon.json.\n")


if __name__ == "__main__":
    main()
