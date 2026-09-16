"""One-time migration: preserve existing art/maps; write two fixed 24x24 areas.

Run manually, never on game startup. Refuses to overwrite an existing area.
The created maps are ordinary Pyxel Editor tilemaps, not runtime generation.
"""
from collections import deque
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.tiles import *


def main():
    if any(path.exists() for path in AREA_RESOURCES[1:]):
        raise SystemExit("Area files already exist. Edit them with Pyxel Editor.")
    backup = ROOT / "verification/backups/game_before_15f.pyxres"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists() and "--resume" not in sys.argv:
        raise SystemExit("Backup exists; refusing to replace it.")
    if not backup.exists():
        shutil.copy2(DUNGEON_RESOURCE, backup)
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(DUNGEON_RESOURCE))
    # Add the first area's exit on a reachable floor, preferably next to the boss.
    tm = pyxel.tilemaps[4]
    events = [(x, y) for y in range(256) for x in range(256) if tuple(tm.pget(x, y)) == TILE_BOSS]
    if len(events) != 1:
        raise ValueError("B5F needs one boss tile.")
    has_exit = any(tuple(tm.pget(x, y)) == TILE_STAIRS_DOWN for y in range(256) for x in range(256))
    seen, queue = {events[0]}, deque([] if has_exit else events)
    while queue:
        x, y = queue.popleft()
        if tuple(tm.pget(x, y)) == TILE_FLOOR:
            tm.pset(x, y, TILE_STAIRS_DOWN)
            break
        for dx, dy in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            p = x + dx, y + dy
            if p not in seen and 0 <= p[0] < 256 and 0 <= p[1] < 256 and tuple(tm.pget(*p)) in PASSABLE:
                seen.add(p)
                queue.append(p)
    else:
        if not has_exit:
            raise ValueError("B5F has no floor space for the exit.")
    pyxel.save(str(DUNGEON_RESOURCE))
    # Authored wall/door positions for four fixed maps, reused with a mirror in area 3.
    walls = (((7, 5), (15, 18)), ((9, 19), (17, 4)),
             ((6, 14), (16, 7)), ((8, 4), (14, 19)))
    for area, path in enumerate(AREA_RESOURCES[1:], 1):
        pyxel.load(str(DUNGEON_RESOURCE))  # Include terrain art for Editor previews.
        for slot in range(5):
            tm = pyxel.tilemaps[slot]
            tm.cls(TILE_WALL)
            tm.imgsrc = MAP_IMAGE_BANK
            def put(x, y, tile):
                tm.pset(23 - x if area == 2 else x, y, tile)
            for y in range(1, 23):
                for x in range(1, 23):
                    put(x, y, TILE_FLOOR)
            if slot < 4:
                for x, door in walls[slot]:
                    for y in range(1, 23):
                        if y not in (door, door + 1):
                            put(x, y, TILE_WALL)
            else:
                for x in (6, 15):
                    for y in (6, 15):
                        for dx in range(3):
                            for dy in range(3):
                                put(x + dx, y + dy, TILE_WALL)
            put(1, 1, TILE_STAIRS_UP)
            put(4, 19, TILE_CHEST)
            put(20, 3, TILE_CHEST)
            if slot == 4:
                put(21, 21, TILE_BOSS)
            if not (area == 2 and slot == 4):
                put(22, 22, TILE_STAIRS_DOWN)
        pyxel.save(str(path))
    print("Created B6F-B15F; B1F-B4F preserved. Original backup:", backup)


if __name__ == "__main__":
    main()
