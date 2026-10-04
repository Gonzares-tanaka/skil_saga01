"""One-time, backed-up addition of field tiles to existing Editor resources.

Does not run at game startup. Existing drawings in these slots are preserved.
"""
from collections import deque
from datetime import datetime
from pathlib import Path
import random
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT, load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.tiles import (AREA_RESOURCES, PASSABLE, TILE_FLOOR, TILE_PIT, PIT_TILES,
                       TILE_POISON, TILE_HEAL_POINT, TILE_RARE_CHEST)


ART = {
    9: ["00030000", "00333000", "03333330", "03222330", "03333330", "03232330", "03333330", "00000000"],
    10: ["11111111", "12211221", "11221111", "11112311", "12311121", "11122111", "12111121", "11111111"],
    11: ["11111111", "11222211", "12000021", "12000021", "12000021", "12000021", "11222211", "11111111"],
    12: ["00030000", "00333000", "00232000", "02222200", "02323220", "02232220", "00222200", "00000000"],
    13: ["00033000", "00333300", "00233200", "00333300", "00033000", "00000000", "00033000", "00000000"],
}


def reachable(tilemap, width, height):
    # The entry can be edited freely; detect its tile instead of assuming its position.
    start = next((x, y) for y in range(height) for x in range(width)
                 if tuple(tilemap.pget(x, y)) in {(2, 0), (5, 0)})
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = x + dx, y + dy
            if (0 <= point[0] < width and 0 <= point[1] < height and point not in seen
                    and tuple(tilemap.pget(*point)) in PASSABLE - PIT_TILES):
                seen.add(point)
                queue.append(point)
    return start, seen


def main():
    pyxel.init(160, 120, headless=True)
    settings = load_dungeon_settings()
    width, height = settings['width'], settings['height']
    backup = ROOT / 'verification/backups' / datetime.now().strftime('%Y%m%d_%H%M%S')
    backup.mkdir(parents=True)
    for path in AREA_RESOURCES:
        shutil.copy2(path, backup / path.name)
    rng = random.Random(923)
    for area, path in enumerate(AREA_RESOURCES):
        pyxel.load(str(path))
        for u, rows in ART.items():
            if all(pyxel.images[1].pget(u * 8 + x, y) == 0 for y in range(8) for x in range(8)):
                pyxel.images[1].set(u * 8, 0, rows)
        for local in range(5):
            tilemap = pyxel.tilemaps[local]
            start, seen = reachable(tilemap, width, height)
            additions = [(TILE_POISON, 2), (TILE_PIT, 1), (TILE_HEAL_POINT, 1)]
            if local == 2:
                additions.append((TILE_RARE_CHEST, 1))
            for tile, count in additions:
                if any(tuple(tilemap.pget(x, y)) == tile for y in range(height) for x in range(width)):
                    continue
                candidates = sorted(p for p in seen if tuple(tilemap.pget(*p)) == TILE_FLOOR
                                    and p[0] > 3 and p[1] > 3
                                    and abs(p[0] - start[0]) + abs(p[1] - start[1]) >= 6)
                rng.shuffle(candidates)
                placed = 0
                for point in candidates:
                    tilemap.pset(*point, tile)
                    if tile == TILE_PIT and not (seen - {point}) <= reachable(tilemap, width, height)[1]:
                        tilemap.pset(*point, TILE_FLOOR)
                        continue
                    placed += 1
                    if placed == count:
                        break
                if placed != count:
                    raise ValueError(f'{path.name} map{local}: no safe tile space; originals in {backup}')
                start, seen = reachable(tilemap, width, height)
        pyxel.save(str(path))
    Dungeon(load_maps(), load_content()[3], settings, rng)
    print(f'Added editable tiles; all 15 floors reachable. Backup: {backup}')


if __name__ == '__main__':
    main()
