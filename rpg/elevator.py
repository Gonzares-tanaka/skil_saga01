"""Boss-gated shortcuts, derived from durable progress; no terrain mutation."""
from .quests import spawn_candidates
from .tiles import FLOOR_TILES, PASSABLE, TILE_DOOR, TILE_STAIRS_UP

B15_ELEVATOR_SPRITE = (1, 120, 8, 8, 8)  # Bank, pixel u/v, width/height.

# Zero-based destination floor, required boss floor, visible label.
ELEVATOR_DESTINATIONS = ((5, 4, 'B6   AREA 2'),
                         (10, 9, 'B11  AREA 3'),
                         (14, 14, 'B15  DEEPEST'))


def unlocked_destinations(dungeon):
    return [(floor, label) for floor, gate, label in ELEVATOR_DESTINATIONS
            if gate in dungeon.defeated_bosses and
            (floor != 14 or dungeon.finale.demon_defeated)]


def b15_elevator_point(dungeon):
    """One tile directly right of the authored, one-tile demon marker.

    After the demon is defeated, the lift overlays this existing floor cell;
    the stored Tilemap is never changed.
    """
    boss_x, y = dungeon.boss_positions[14]
    x = boss_x + 1
    if getattr(dungeon, '_b15_elevator_point', None) == (x, y):
        return x, y
    tile = dungeon.tile(14, x, y)
    if (tile is None or tile in (PASSABLE - FLOOR_TILES) | {TILE_DOOR}
            or (x, y) in spawn_candidates(dungeon, 14)):
        raise ValueError('B15のデーモン右隣にエレベータを配置できません')
    dungeon._b15_elevator_point = (x, y)
    return x, y


def arrival_point(dungeon, floor):
    if floor not in {f for f, _ in unlocked_destinations(dungeon)}:
        raise ValueError('その行き先は未解放です')
    point = b15_elevator_point(dungeon) if floor == 14 else dungeon.find(floor, TILE_STAIRS_UP)
    if not dungeon.can_enter(floor, *point):
        raise ValueError('安全な入口へ移動できません')
    return point


def b15_elevator_open(dungeon, floor, x, y):
    if (floor != 14 or not dungeon.finale.demon_defeated or
            14 not in dungeon.defeated_bosses):
        return False
    boss_x, boss_y = dungeon.boss_positions[14]
    if (x, y) != (boss_x + 1, boss_y):
        return False
    return (x, y) == b15_elevator_point(dungeon)


def at_b15_elevator(dungeon):
    return b15_elevator_open(dungeon, dungeon.floor, dungeon.x, dungeon.y)


def unlock_notice(floor):
    return {4: ['LV2のクエストが受注可能になった！',
                'エレベーターのB6行きが解放された！', '城下町のパブへ行ってみよう。'],
            9: ['LV3のクエストが受注可能になった！',
                'エレベーターのB11行きが解放された！'],
            14: ['エレベーターのB15行きが解放された！',
                 'デーモンの亡骸の横から拠点へ帰還できる。']}.get(floor, [])
