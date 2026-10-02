"""Inspect B6-B10 routes, switch dependencies and resource preservation."""
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.tiles import (AREA_RESOURCES, PASSABLE, TILE_BOSS, TILE_CHEST, TILE_DOOR,
                       TILE_ENTRANCE, TILE_HEAL_POINT, TILE_PIT, TILE_POISON,
                       TILE_QUEST, TILE_RARE_CHEST, TILE_STAIRS_DOWN,
                       TILE_STAIRS_UP, TILE_SWITCH)


def route(d, floor, start, goal, blocked=frozenset(), open_doors=True):
    queue, previous = deque([start]), {start: None}
    while queue:
        point = queue.popleft()
        if point == goal:
            result = []
            while previous[point] is not None:
                result.append(point)
                point = previous[point]
            return list(reversed(result))
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nxt = point[0] + dx, point[1] + dy
            tile = d.tile(floor, *nxt)
            if nxt in previous or tile in blocked or tile == TILE_PIT:
                continue
            if tile not in PASSABLE and not (open_doors and tile == TILE_DOOR):
                continue
            if nxt != goal and tile in (TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_ENTRANCE):
                continue
            previous[nxt] = point
            queue.append(nxt)
    return None


def resource(path):
    return tomllib.loads(zipfile.ZipFile(path).read('pyxel_resource.toml').decode('utf8'))


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def verify_preservation():
    backup = ROOT / 'verification' / 'backups' / 'phase5'
    if not (backup / 'game.pyxres').exists():
        return {'baseline_available': False}
    old, new = resource(backup / 'game.pyxres'), resource(AREA_RESOURCES[0])
    assert old['tilemaps'] == new['tilemaps'], 'Human-edited B1-B5 maps changed'
    assert old['images'][0] == new['images'][0] and old['images'][2] == new['images'][2]
    assert old['sounds'] == new['sounds'] and old['musics'] == new['musics']
    def pixel(image, x, y):
        rows = image['data']
        return rows[y][x] if y < len(rows) and x < len(rows[y]) else 0
    for y in range(256):
        for x in range(256):
            if y < 8 and 120 <= x < 152:
                assert pixel(old['images'][1], x, y) == 0, 'Overwriting an existing graphic'
            else:
                assert pixel(old['images'][1], x, y) == pixel(new['images'][1], x, y)
    assert (backup / 'area3.pyxres').read_bytes() == AREA_RESOURCES[2].read_bytes()
    before, after = resource(backup / 'area2.pyxres'), resource(AREA_RESOURCES[1])
    assert before['tilemaps'][5:] == after['tilemaps'][5:]
    assert before['sounds'] == after['sounds'] and before['musics'] == after['musics']
    for index in range(5):
        b, a = before['tilemaps'][index]['data'], after['tilemaps'][index]['data']
        assert b[24:] == a[24:]
        assert all((b[y][48:] if y < len(b) else []) == a[y][48:] for y in range(24))
    return {'baseline_available': True, 'B1_B5_tilemaps_unchanged': True,
            'B1_B5_tilemaps_sha256': fingerprint(old['tilemaps'][:5]),
            'existing_graphics_sounds_music_unchanged': True, 'B11_B15_resource_unchanged': True,
            'B6_B10_changes_within_24x24': True}


def main():
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(AREA_RESOURCES[0]))
    s = Session(*load_content(), seed=17)
    d = Dungeon(load_maps(), s.enemy_data, load_dungeon_settings(), s.rng)
    baseline_area = sum(sum(d.tile(f, x, y) in PASSABLE for y in range(24) for x in range(24))
                        for f in range(5)) / 5
    rows = []
    for f in range(5, 10):
        start, exit_point = d.find(f, TILE_STAIRS_UP), d.find(f, TILE_STAIRS_DOWN)
        events = {name: d.positions(f, tile) for name, tile in (
            ('chests', TILE_CHEST), ('rare_chests', TILE_RARE_CHEST), ('poison', TILE_POISON),
            ('pits', TILE_PIT), ('springs', TILE_HEAL_POINT), ('switches', TILE_SWITCH),
            ('doors', TILE_DOOR), ('quests', TILE_QUEST), ('bosses', TILE_BOSS))}
        assert len(events['chests']) + len(events['rare_chests']) == [3, 3, 4, 4, 1][f-5]
        assert len(events['quests']) == [3, 3, 4, 3, 3][f-5]
        assert len(events['springs']) == (1 if f == 8 else 0)
        walkable = sum(d.tile(f, x, y) in PASSABLE | {TILE_DOOR} for y in range(24) for x in range(24))
        assert walkable / baseline_area <= (1.5 if f == 7 else 1.4)
        for y in range(24):
            for x in range(24):
                tile = d.tile(f, x, y)
                if tile in PASSABLE - {TILE_PIT} | {TILE_DOOR}:
                    assert route(d, f, start, (x, y)) is not None, (f, x, y)
        greedy = 0
        point = start
        remaining = events['chests'] + events['rare_chests']
        while remaining:
            goal = min(remaining, key=lambda p: len(route(d, f, point, p)))
            greedy += len(route(d, f, point, goal))
            point = goal
            remaining.remove(goal)
        greedy += len(route(d, f, point, exit_point))
        rows.append({'floor': f+1, 'resource': 'area2.pyxres', 'tilemap': f-5,
                     'bounds': [0, 0, 24, 24], 'walkable': walkable,
                     'ratio_to_B1_B5_average': round(walkable/baseline_area, 3),
                     'stairs_up': start, 'stairs_down': exit_point,
                     'shortest_exit_steps': len(route(d, f, start, exit_point)),
                     'chest_tour_steps': greedy, 'events': events})
    # Closed gate is visible two steps from arrival; both main path and switch are accessible.
    start = d.find(6, TILE_STAIRS_UP)
    switch = d.positions(6, TILE_SWITCH)[0]
    assert route(d, 6, start, switch, open_doors=False)
    assert route(d, 6, start, (18, 4), open_doors=False) is None
    assert route(d, 6, start, d.find(6, TILE_STAIRS_DOWN), open_doors=False)
    assert len(route(d, 6, start, (9, 4), open_doors=False)) == 2
    # B8 has the largest walkable area and rewards three true dead ends.
    # An omniscient greedy tour is not a measure of how hard a maze is to read.
    assert rows[2]['walkable'] == max(r['walkable'] for r in rows)
    dead_ends = sum(sum(d.tile(7, x+dx, y+dy) in PASSABLE for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))) == 1
                    for x,y in d.positions(7, TILE_CHEST) + d.positions(7, TILE_RARE_CHEST))
    assert dead_ends >= 3
    # B6 and B8 poison are optional shortcuts, not unavoidable tolls.
    for f, start, goal in ((5, (11, 10), (20, 3)), (7, (11, 19), (19, 19))):
        assert len(route(d, f, start, goal)) < len(route(d, f, start, goal, {TILE_POISON}))
    start, exit_point = d.find(8, TILE_STAIRS_UP), d.find(8, TILE_STAIRS_DOWN)
    spring = d.positions(8, TILE_HEAL_POINT)[0]
    assert route(d, 8, start, exit_point, {TILE_HEAL_POINT, TILE_POISON})
    spring_distance = len(route(d, 8, spring, exit_point))
    assert spring_distance >= 25
    assert rows[3]['chest_tour_steps'] > rows[3]['shortest_exit_steps'] * 2
    assert route(d, 9, d.find(9, TILE_STAIRS_UP), d.find(9, TILE_STAIRS_DOWN), {TILE_BOSS}) is None
    report = {'preservation': verify_preservation(), 'baseline_walkable_average': baseline_area,
              'floors': rows, 'B8_reward_dead_ends': dead_ends,
              'B9_spring_to_exit_steps': spring_distance,
              'switch_shortcuts_spring_boss_route_checks': 'PASS',
              'physical_PC_browser_smartphone_test': 'NOT_RUN: headless only'}
    (ROOT/'verification'/'phase5_maps.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    for row in rows:
        print({k:v for k,v in row.items() if k != 'events'})
    print('Preservation:', report['preservation'])
    print('Spring -> B10 stairs:', spring_distance, '/ B8 reward dead ends:', dead_ends)


if __name__ == '__main__':
    main()
