"""Check the editable B1-B5 draft and walk the ordinary staircase route."""
from collections import deque
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel

from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.exploration import Exploration
from rpg.map_resources import load_maps
from rpg.tiles import (DUNGEON_RESOURCE, PASSABLE, TILE_BOSS, TILE_CHEST,
                       TILE_ENTRANCE, TILE_HEAL_POINT, TILE_PIT, TILE_POISON,
                       TILE_QUEST, TILE_RARE_CHEST, TILE_STAIRS_DOWN,
                       TILE_STAIRS_UP)


def route(dungeon, floor, start, goal, blocked=frozenset()):
    queue, previous = deque([start]), {start: None}
    while queue:
        point = queue.popleft()
        if point == goal:
            path = []
            while previous[point] is not None:
                path.append(point)
                point = previous[point]
            return list(reversed(path))
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            next_point = point[0] + dx, point[1] + dy
            tile = dungeon.tile(floor, *next_point)
            if next_point in previous or tile not in PASSABLE - {TILE_PIT} - blocked:
                continue
            if next_point != goal and tile in (TILE_ENTRANCE, TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_BOSS):
                continue
            previous[next_point] = point
            queue.append(next_point)
    return None


pyxel.init(160, 120, headless=True)
pyxel.load(str(DUNGEON_RESOURCE))
session = Session(*load_content(), seed=42)
dungeon = Dungeon(load_maps(), session.enemy_data, load_dungeon_settings(),
                  session.rng, session.treasure, session.inventory)
exploration = Exploration(session, dungeon)
assert all(dungeon.maps[f].imgsrc == 1 for f in range(5))

counts = []
for floor in range(5):
    chests = len(dungeon.positions(floor, TILE_CHEST)) + len(dungeon.positions(floor, TILE_RARE_CHEST))
    springs = len(dungeon.positions(floor, TILE_HEAL_POINT))
    poison = len(dungeon.positions(floor, TILE_POISON))
    pits = len(dungeon.positions(floor, TILE_PIT))
    quests = len(dungeon.positions(floor, TILE_QUEST))
    counts.append((chests, springs, poison, pits, quests))
    assert quests == 3
    assert all(dungeon.tile(floor, x, y) == TILE_QUEST
               for x, y in dungeon.positions(floor, TILE_QUEST))
assert counts == [(0, 0, 0, 0, 3), (2, 0, 0, 0, 3), (2, 0, 1, 1, 3),
                  (2, 1, 1, 0, 3), (0, 0, 0, 0, 3)]

# A first B2 reward is only four steps from the arrival stair.
start_b2 = dungeon.find(1, TILE_STAIRS_UP)
first_chest = min(len(route(dungeon, 1, start_b2, point))
                  for point in dungeon.positions(1, TILE_CHEST))
assert first_chest == 4

# On B3, the poisonous route to the rare chest is shorter than the safe loop.
start_b3 = dungeon.find(2, TILE_STAIRS_UP)
rare = dungeon.positions(2, TILE_RARE_CHEST)[0]
risky = route(dungeon, 2, start_b3, rare)
safe = route(dungeon, 2, start_b3, rare, {TILE_POISON})
assert risky is not None and safe is not None and len(risky) < len(safe)
assert any(dungeon.tile(2, *point) == TILE_POISON for point in risky)

# B4's spring is an optional detour, followed by travel before B5.
start_b4 = dungeon.find(3, TILE_STAIRS_UP)
exit_b4 = dungeon.find(3, TILE_STAIRS_DOWN)
spring = dungeon.positions(3, TILE_HEAL_POINT)[0]
assert route(dungeon, 3, start_b4, exit_b4, {TILE_HEAL_POINT}) is not None
spring_to_exit = route(dungeon, 3, spring, exit_b4)
assert spring_to_exit is not None and len(spring_to_exit) >= 15

# B5's boss is the doorway to B6. The next stair remains boss-locked.
start_b5 = dungeon.find(4, TILE_STAIRS_UP)
boss = dungeon.find(4, TILE_BOSS)
exit_b5 = dungeon.find(4, TILE_STAIRS_DOWN)
assert route(dungeon, 4, start_b5, boss) is not None
assert route(dungeon, 4, start_b5, exit_b5, {TILE_BOSS}) is None
dungeon.debug_floor(4)
assert dungeon.change_floor(5)[0] == ""

# Quest targets come from the three Editor markers on the selected floor.
for _ in range(100):
    exploration.active = None
    exploration.accept(1)
    floor, x, y = exploration.target
    assert 0 <= floor < 5 and dungeon.tile(floor, x, y) == TILE_QUEST

# An unselected candidate behaves like ordinary floor for encounters.
dungeon.debug_floor(0)
dungeon.x, dungeon.y = 3, 4
dungeon.grace = 0
dungeon.settings["encounter_chance"] = 1
assert dungeon.move(0, 1)[0] == "battle"

# Walk real Tilemap steps from B1 to the B5 boss, without a debug warp.
dungeon.settings["encounter_chance"] = 0
dungeon.enter()
for floor in range(5):
    assert dungeon.floor == floor
    goal_tile = TILE_BOSS if floor == 4 else TILE_STAIRS_DOWN
    goal = dungeon.find(floor, goal_tile)
    # The planned main route avoids optional poison, pits and the B4 spring.
    path = route(dungeon, floor, (dungeon.x, dungeon.y), goal,
                 {TILE_POISON, TILE_HEAL_POINT})
    assert path is not None
    for x, y in path:
        event, _ = dungeon.move(x - dungeon.x, y - dungeon.y)
    assert event == ("boss" if floor == 4 else "stairs")
assert dungeon.boss_data["id"] == "guardian"
assert dungeon.floor == 4 and (dungeon.x, dungeon.y) == boss
dungeon.defeat_boss()
for x, y in route(dungeon, 4, boss, exit_b5):
    event, _ = dungeon.move(x - dungeon.x, y - dungeon.y)
assert event == "stairs" and dungeon.floor == 5
print("PASS B1-B5: editable 24x24 maps, counts", counts,
      "B2 first chest", first_chest, "B3 risk/safe", len(risky), len(safe),
      "B4 spring-to-exit", len(spring_to_exit), "normal stair walk and boss gate")
