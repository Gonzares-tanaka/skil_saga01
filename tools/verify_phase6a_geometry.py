"""Validate B11-B15 topology and preserved map rectangles without launching Pyxel.

Checks actual resource data, not the one-off authoring definitions, so Editor
changes can be evaluated. Fixed event totals reflect the Phase 6A draft contract.
"""
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rpg.tiles import (FLOOR_TILES, PASSABLE, PIT_TILES, TILE_BOSS, TILE_CHEST,
                       TILE_DOOR, TILE_ENTRANCE, TILE_HEAL_POINT, TILE_POISON,
                       TILE_QUEST, TILE_RARE_CHEST, TILE_STAIRS_DOWN,
                       TILE_STAIRS_UP, TILE_SWITCH)

GUARDIAN, WARNING = (27, 0), (28, 0)
LORE = {(u, 0) for u in range(21, 27)}
TRAVERSABLE = PASSABLE | LORE | {TILE_DOOR, GUARDIAN, WARNING}
SIZE = 24


def resource(path):
    with zipfile.ZipFile(path) as archive:
        return tomllib.loads(archive.read("pyxel_resource.toml").decode("utf8"))


def grid(tilemap):
    rows = tilemap["data"]
    return [[tuple(rows[y][x*2:x*2+2]) if y < len(rows) and x*2+1 < len(rows[y]) else (0, 0)
             for x in range(SIZE)] for y in range(SIZE)]


def positions(rows, tiles):
    if isinstance(tiles, tuple):
        tiles = {tiles}
    return [(x, y) for y, row in enumerate(rows) for x, tile in enumerate(row) if tile in tiles]


def only(rows, tile):
    found = positions(rows, tile)
    assert len(found) == 1, (tile, found)
    return found[0]


def route(rows, start, goal, blocked=frozenset(), open_doors=True):
    queue, previous = deque([start]), {start: None}
    while queue:
        point = queue.popleft()
        if point == goal:
            steps = []
            while previous[point] is not None:
                steps.append(point)
                point = previous[point]
            return list(reversed(steps))
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nxt = point[0]+dx, point[1]+dy
            if nxt in previous or not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE):
                continue
            tile = rows[nxt[1]][nxt[0]]
            if tile not in TRAVERSABLE or tile in PIT_TILES | set(blocked):
                continue
            if tile == TILE_DOOR and not open_doors:
                continue
            if nxt != goal and tile in (TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_ENTRANCE):
                continue
            previous[nxt] = point
            queue.append(nxt)
    return None


def verify_preservation():
    baseline = ROOT / "verification" / "backups" / "phase6a"
    if not (baseline / "area3.pyxres").exists():
        return {"baseline_available": False}
    old_game = resource(baseline / "game.pyxres")
    now_game = resource(ROOT / "game.pyxres")
    assert old_game["tilemaps"] == now_game["tilemaps"], "B1-B5 Tilemaps changed"
    assert old_game['images'][0] == now_game['images'][0] and old_game['images'][2] == now_game['images'][2]
    assert old_game['sounds'] == now_game['sounds'] and old_game['musics'] == now_game['musics']
    def pixel(image, x, y):
        rows = image['data']
        return rows[y][x] if y < len(rows) and x < len(rows[y]) else 0
    for y in range(256):
        for x in range(256):
            if y < 8 and 168 <= x < 232:
                assert pixel(old_game['images'][1], x, y) == 0, 'New glyph overwrote existing artwork'
            else:
                assert pixel(old_game['images'][1], x, y) == pixel(now_game['images'][1], x, y), 'B1-B10 graphic changed'
    assert (baseline / "area2.pyxres").read_bytes() == (ROOT / "area2.pyxres").read_bytes(), "B6-B10 resource changed"
    old, new = resource(baseline / "area3.pyxres"), resource(ROOT / "area3.pyxres")
    assert old["tilemaps"][5:] == new["tilemaps"][5:], "Unused Tilemaps changed"
    assert old["sounds"] == new["sounds"] and old["musics"] == new["musics"]
    for index in range(5):
        a, b = old["tilemaps"][index]["data"], new["tilemaps"][index]["data"]
        assert a[24:] == b[24:], "Rows beyond draft changed"
        for y in range(24):
            assert (a[y][48:] if y < len(a) else []) == (b[y][48:] if y < len(b) else []), "Columns beyond draft changed"
    return {"baseline_available": True, "B1_B5_tilemaps_unchanged": True,
            "B6_B10_resource_byte_identical": True,
            'B1_B10_existing_images_sounds_music_unchanged': True,
            "B11_B15_changes_within_24x24": True,
            "area3_unused_tilemaps_sounds_music_unchanged": True,
            "B1_B5_tilemap_sha256": hashlib.sha256(json.dumps(old_game["tilemaps"][:5], sort_keys=True).encode()).hexdigest()}


def main():
    area2, area3 = resource(ROOT / "area2.pyxres"), resource(ROOT / "area3.pyxres")
    baseline_area = sum(sum(tile in TRAVERSABLE for row in grid(tm) for tile in row)
                        for tm in area2["tilemaps"][:5]) / 5
    reports = []
    event_names = (("normal_chests", TILE_CHEST), ("rare_chests", TILE_RARE_CHEST),
                   ("poison", TILE_POISON), ("pits", PIT_TILES), ("springs", TILE_HEAL_POINT),
                   ("switches", TILE_SWITCH), ("doors", TILE_DOOR), ("quests", TILE_QUEST),
                   ("lore", LORE), ("guardians", GUARDIAN), ("warnings", WARNING), ("bosses", TILE_BOSS))
    for index, tilemap in enumerate(area3["tilemaps"][:5]):
        assert tilemap["imgsrc"] == 1
        rows = grid(tilemap)
        start = only(rows, TILE_STAIRS_UP)
        goal = only(rows, TILE_STAIRS_DOWN if index < 4 else TILE_BOSS)
        events = {name: positions(rows, tiles) for name, tiles in event_names}
        chest_count = len(events["normal_chests"]) + len(events["rare_chests"])
        assert chest_count == [3, 4, 5, 3, 1][index]
        assert len(events["quests"]) == 3
        assert len(events["lore"]) == [1, 2, 1, 2, 0][index]
        assert len(events["springs"]) == (index == 4)
        walkable = sum(tile in TRAVERSABLE for row in rows for tile in row)
        if index < 4:
            assert 1.2 <= walkable / baseline_area <= 1.4
            assert not events["guardians"] and not events["warnings"] and not events["bosses"]
        else:
            assert not positions(rows, TILE_STAIRS_DOWN)
        for y, row in enumerate(rows):
            for x, tile in enumerate(row):
                if tile in TRAVERSABLE - PIT_TILES:
                    assert route(rows, start, (x, y)) is not None, (index+11, x, y)
        tour, point = 0, start
        remaining = events["normal_chests"] + events["rare_chests"]
        while remaining:
            target = min(remaining, key=lambda p: len(route(rows, point, p)))
            tour += len(route(rows, point, target))
            point = target
            remaining.remove(target)
        tour += len(route(rows, point, goal))
        reports.append({"floor": index+11, "resource": "area3.pyxres", "tilemap": index,
                        "bounds": [0, 0, 24, 24], "walkable": walkable,
                        "ratio_to_B6_B10_average": round(walkable/baseline_area, 3),
                        "stairs_up": start, "stairs_down": goal if index < 4 else None,
                        "shortest_exit_or_boss_steps": len(route(rows, start, goal)),
                        "chest_tour_steps": tour, "events": events})
    rows = grid(area3["tilemaps"][1])
    start = only(rows, TILE_STAIRS_UP)
    assert route(rows, start, only(rows, TILE_SWITCH), open_doors=False) is not None
    assert route(rows, start, only(rows, TILE_STAIRS_DOWN), open_doors=False) is not None
    assert route(rows, start, only(rows, (23, 0)), open_doors=False) is None
    shortcut = (7, 12), (10, 12)
    assert len(route(rows, *shortcut)) < len(route(rows, *shortcut, blocked={TILE_POISON}))
    # The first lore events and the final-area route can all be reached safely.
    for index in range(4):
        rows = grid(area3["tilemaps"][index])
        assert route(rows, only(rows, TILE_STAIRS_UP), only(rows, TILE_STAIRS_DOWN), blocked={TILE_POISON}) is not None
    assert reports[2]["chest_tour_steps"] > reports[2]["shortest_exit_or_boss_steps"] * 3
    rows = grid(area3["tilemaps"][4])
    start, guardian = only(rows, TILE_STAIRS_UP), only(rows, GUARDIAN)
    warning, spring, boss = only(rows, WARNING), only(rows, TILE_HEAL_POINT), only(rows, TILE_BOSS)
    assert route(rows, start, warning, blocked={GUARDIAN}) is not None
    assert route(rows, start, spring, blocked={GUARDIAN}) is None
    assert route(rows, start, boss, blocked={GUARDIAN}) is None
    approach = route(rows, start, boss)
    assert [approach.index(p) for p in (warning, guardian, spring, boss)] == sorted(approach.index(p) for p in (warning, guardian, spring, boss))
    for mark in (WARNING, GUARDIAN, TILE_HEAL_POINT):
        assert route(rows, start, boss, blocked={mark}) is None
    assert any(route(rows, start, point, blocked={GUARDIAN}) is not None
               for point in reports[4]["events"]["quests"])
    report = {"preservation": verify_preservation(), "baseline_B6_B10_walkable_average": baseline_area,
              "floors": reports, "lore_total": 6, "quest_total": 15,
              "B12_switch_archive_and_poison_shortcut": "PASS",
              "B13_safe_shortest_vs_long_treasure_tour": "PASS",
              "B15_warning_guardians_spring_demon_chokepoints": "PASS",
              "physical_PC_browser_smartphone_test": "NOT_RUN: resource topology only"}
    path = ROOT / "verification" / "phase6a_maps.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    for row in reports:
        print({key: value for key, value in row.items() if key != "events"})
    print("Preservation:", report["preservation"])
    print("B12 gates / B13 detours / B15 sequence: PASS")


if __name__ == "__main__":
    main()
