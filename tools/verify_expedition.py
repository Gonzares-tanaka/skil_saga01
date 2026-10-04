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
from rpg.exploration import Exploration
from rpg.tiles import (DUNGEON_RESOURCE, PASSABLE, TILE_ENTRANCE, TILE_STAIRS_UP,
                       TILE_STAIRS_DOWN, TILE_CHEST, TILE_BOSS, TILE_RARE_CHEST, TILE_PIT,
                       PIT_TILES, TILE_SWITCH, TILE_WARNING, TILE_HEAL_POINT)


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
            if nxt in previous or tile in PIT_TILES or not d.can_enter(d.floor, *nxt):
                continue
            if nxt != goal and tile in (TILE_ENTRANCE, TILE_STAIRS_UP, TILE_STAIRS_DOWN):
                continue
            previous[nxt] = point
            queue.append(nxt)
    raise AssertionError(f"No route to event in authored resource: B{d.floor + 1}F {start} -> {goal}")


def reachable_path(d, goal):
    try:
        return path_to(d, goal)
    except AssertionError:
        return None


def play(seed):
    pyxel.load(str(DUNGEON_RESOURCE))
    s = Session(*load_content(), seed=seed)
    d = Dungeon(load_maps(), s.enemy_data, load_dungeon_settings(), s.rng, s.treasure, s.inventory)
    exploration = Exploration(s, d)
    retreats = potions_used = trips = 0
    progression = [1]
    bosses_won = []
    switches_operated = 0
    guardian_wins = []
    amrita_returned = False
    spring_uses_preserved = False
    for trips in range(1, 11):
        for actor in s.party:
            actor.recover()
        d.enter(allow_cleared=d.cleared)
        exploration.springs.clear()
        retreat = False
        unavailable_chests = set()
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
            if retreat or d.cleared:
                goal = d.find(d.floor, TILE_ENTRANCE if d.floor == 0 else TILE_STAIRS_UP)
            else:
                chests = [p for tile in (TILE_CHEST, TILE_RARE_CHEST) for p in d.positions(d.floor, tile)
                          if (d.floor, *p) not in d.opened | unavailable_chests]
                reachable = [(p, route) for p in chests if (route := reachable_path(d, p)) is not None]
                if reachable and d.potions < 9:
                    goal = min(reachable, key=lambda pair: len(pair[1]))[0]
                elif d.floor not in d.activated_switches and d.positions(d.floor, TILE_SWITCH):
                    goal = d.positions(d.floor, TILE_SWITCH)[0]
                elif d.floor == 14 and not d.finale.guardians_defeated:
                    goal = d.find(14, TILE_WARNING)
                elif d.floor == 14 and (14, *d.find(14, TILE_HEAL_POINT)) not in exploration.springs:
                    goal = d.find(14, TILE_HEAL_POINT)
                else:
                    boss = d.floor in (4, 9, 14) and d.floor not in d.defeated_bosses
                    goal = d.find(d.floor, TILE_BOSS if boss else TILE_STAIRS_DOWN)
            path = path_to(d, goal)
            if path:
                nx, ny = path[0]
                event, _ = d.move(nx - d.x, ny - d.y)
            else:
                event, _ = d.interact()
                if not event and d.tile(d.floor, *goal) in (TILE_CHEST, TILE_RARE_CHEST):
                    unavailable_chests.add((d.floor, *goal))
            if d.floor + 1 not in progression:
                progression.append(d.floor + 1)
            if event == 'switch':
                switches_operated += 1
            if event == "base":
                s.treasure.secure()
                amrita_returned = d.finale.has_amrita
                break
            if event == "chest":
                exploration.chest_effect(d.last_reward)
                for index in s.pending_replacements:
                    s.resolve_replacement(index)
            elif event == "poison":
                exploration.damage(d.exploration_settings['poison_damage'])
            elif event == "spring":
                point = d.floor, d.x, d.y
                if point not in exploration.springs:
                    exploration.springs.add(point)
                    uses = [dict(c.skill_uses) for c in s.party]
                    exploration.heal(None)
                    assert uses == [dict(c.skill_uses) for c in s.party]
                    if d.floor == 14:
                        spring_uses_preserved = True
            if event == 'guardian':
                d.finale.start_guardians()
                for index in range(3):
                    battle = s.next_battle(d.make_enemies(guardian_index=index), recover=False,
                                          spark_multiplier=d.spark_multiplier, boss=True)
                    while not battle.outcome:
                        battle.begin_round(battle.auto_actions())
                        while battle.queue:
                            battle.step()
                    hp = [c.hp for c in s.party]
                    s.settle()
                    for actor_index in s.pending_replacements:
                        s.resolve_replacement(actor_index)
                    assert hp == [c.hp for c in s.party]
                    if battle.outcome != 'VICTORY':
                        d.finale.abort_guardians()
                        break
                    guardian_wins.append(index+1)
                    assert d.finale.guardian_victory() == (index == 2)
                if battle.outcome == 'DEFEAT':
                    break
            if event in ("battle", "boss"):
                before = d.floor, d.x, d.y
                battle = s.next_battle(d.make_enemies(event == "boss"), recover=False,
                                      spark_multiplier=d.spark_multiplier, boss=event == 'boss')
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
                    bosses_won.append(d.floor + 1)
                    d.defeat_boss()
        else:
            raise AssertionError("Exploration failed to terminate")
        if amrita_returned:
            break
    return {"seed": seed, "clear": d.cleared, "trips": trips, "battles": s.completed,
            "progression": progression, "bosses_won": bosses_won, "switches_operated": switches_operated,
            'guardian_wins': guardian_wins, 'has_amrita': d.finale.has_amrita,
            'amrita_returned': amrita_returned, 'spring_uses_preserved': spring_uses_preserved,
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
    assert all(r['progression'] == list(range(1, 16)) and r['bosses_won'] == [5, 10, 15]
               and r['switches_operated'] > 0 for r in results), 'Ordinary staircase/switch/boss progression failed'
    assert all(r['guardian_wins'][-3:] == [1, 2, 3] and r['has_amrita'] and r['amrita_returned']
               and r['spring_uses_preserved'] for r in results), 'Guardians/spring/demon/Amrita/camp progression failed'
