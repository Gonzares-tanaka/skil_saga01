"""Playtest the resource maps with ordinary movement, battles, potions and returns."""
from collections import deque
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.tiles import (DUNGEON_RESOURCE, PASSABLE, TILE_ENTRANCE, TILE_STAIRS_UP,
                       TILE_STAIRS_DOWN, TILE_CHEST, TILE_BOSS)


def path_to(d, goal):
    start = d.x, d.y
    queue, previous = deque([start]), {start: None}
    while queue:
        point = queue.popleft()
        if point == goal:
            path = []
            while previous[point] is not None:
                path.append(point)
                point = previous[point]
            return list(reversed(path))
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nxt = point[0] + dx, point[1] + dy
            tile = d.tile(d.floor, *nxt)
            if nxt in previous or tile not in PASSABLE:
                continue
            if nxt != goal and tile in (TILE_ENTRANCE, TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_BOSS):
                continue
            previous[nxt] = point
            queue.append(nxt)
    raise AssertionError("No route to event in authored resource")


def play(seed):
    pyxel.load(str(DUNGEON_RESOURCE))
    s = Session(*load_content(), seed=seed)
    d = Dungeon(load_maps(), s.enemy_data, load_dungeon_settings(), s.rng, s.treasure)
    retreats = potions_used = trips = 0
    for trips in range(1, 11):
        for actor in s.party:
            actor.recover()
        d.enter()
        retreat = False
        for _ in range(5000):
            injured = [c for c in s.party if c.alive and c.hp < c.max_hp * 0.55]
            while d.potions and injured:
                d.use_potion(min(injured, key=lambda c: c.hp / c.max_hp))
                potions_used += 1
                injured = [c for c in s.party if c.alive and c.hp < c.max_hp * 0.55]
            if not retreat and (sum(c.alive for c in s.party) < 3 or
                                sum(c.hp for c in s.party) < sum(c.max_hp for c in s.party) * 0.38):
                retreat = True
                retreats += 1
            if retreat:
                goal = d.find(d.floor, TILE_ENTRANCE if d.floor == 0 else TILE_STAIRS_UP)
            else:
                chests = [p for p in d.positions(d.floor, TILE_CHEST) if (d.floor, *p) not in d.opened]
                if chests and d.potions < d.settings["items"]["max_potions"]:
                    goal = min(chests, key=lambda p: len(path_to(d, p)))
                else:
                    boss = d.floor in (4, 9, 14) and d.floor not in d.defeated_bosses
                    goal = d.find(d.floor, TILE_BOSS if boss else TILE_STAIRS_DOWN)
            path = path_to(d, goal)
            if path:
                nx, ny = path[0]
                event, _ = d.move(nx - d.x, ny - d.y)
            else:
                event, _ = d.interact()
            if event == "base":
                s.treasure.secure()
                break
            if event in ("battle", "boss"):
                before = d.floor, d.x, d.y
                battle = s.next_battle(d.make_enemies(event == "boss"), recover=False, spark_multiplier=d.spark_multiplier)
                while not battle.outcome:
                    battle.begin_round(battle.auto_actions())
                    while battle.queue:
                        battle.step()
                hp = [c.hp for c in s.party]
                s.settle()
                for index in s.pending_replacements:
                    s.resolve_replacement(index)
                assert hp == [c.hp for c in s.party]
                assert before == (d.floor, d.x, d.y)
                d.grace = d.settings["safe_steps"]
                if battle.outcome == "DEFEAT":
                    break
                if event == "boss" and battle.outcome == "VICTORY":
                    d.defeat_boss()
                    if d.cleared:
                        break
        else:
            raise AssertionError("Exploration failed to terminate")
        if d.cleared:
            break
    return {"seed": seed, "clear": d.cleared, "trips": trips, "battles": s.completed,
            "wins": s.wins, "defeats": s.losses, "retreats": retreats, "steps": d.steps,
            "potions_used": potions_used, "unbanked_treasure": d.treasure.unbanked,
            "banked_treasure": d.treasure.banked,
            "party": [{"name": c.name, "HP": c.max_hp, "STR": c.strength, "AGI": c.agility,
                       "INT": c.intellect, "skills": c.skills,
                       "remaining_uses": dict(c.skill_uses),
                       "exhaustions": sum("使い切り消滅" in line for line in c.history),
                       "rescues": sum("救済:" in line for line in c.history)} for c in s.party]}


if __name__ == "__main__":
    pyxel.init(160, 120, headless=True)
    results = [play(seed) for seed in range(10)]
    (ROOT / "verification" / "expeditions.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        print({k: v for k, v in r.items() if k != "party"})
    assert all(r["clear"] for r in results), "Some test parties could not clear within ten trips"
