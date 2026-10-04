"""Image Bank 1 tile coordinates, in 8px tile units (not pixel coordinates)."""
from .content import ROOT

DUNGEON_RESOURCE = ROOT / "game.pyxres"
MAP_IMAGE_BANK = 1
FLOOR_TILEMAPS = (0, 1, 2, 3, 4)
AREA_RESOURCES = (DUNGEON_RESOURCE, ROOT / "area2.pyxres", ROOT / "area3.pyxres")
BOSS_FLOORS = (4, 9, 14)
TILE_SIZE = 8
TILE_FLOOR = (0, 0)
# Nine 8x8 corridor tiles at image pixels x=0..71, y=64..71.
FLOOR_TILES = {TILE_FLOOR} | {(u, 8) for u in range(9)}
TILE_WALL = (1, 0)
TILE_STAIRS_UP = (2, 0)
TILE_STAIRS_DOWN = (3, 0)
TILE_CHEST = (4, 0)
TILE_ENTRANCE = (5, 0)
TILE_CHEST_OPEN = (6, 0)
TILE_BOSS = (7, 0)
TILE_BOSS_CLEAR = (8, 0)
TILE_RARE_CHEST = (9, 0)  # Image Bank 1 (72, 0): potion appearance, rare-chest reward.
TILE_POISON = (10, 0)
TILE_PIT = (11, 0)
TILE_PIT_AREA2 = (19, 0)
TILE_PIT_AREA3 = (20, 0)
PIT_TILES = {TILE_PIT, TILE_PIT_AREA2, TILE_PIT_AREA3}
TILE_HEAL_POINT = (12, 0)  # Image Bank 1 (96, 0): healing spring.
TILE_QUEST = (13, 0)  # Editor-visible quest candidate; drawn as floor until selected.
TILE_SWITCH = (15, 0)  # A operates a floor-wide switch group.
TILE_DOOR = (16, 0)
TILE_DOOR_OPEN = (17, 0)
TILE_SWITCH_ON = (18, 0)  # Runtime overlay, not an initial switch placement.
LORE_TILES = {(u, 0) for u in range(21, 27)}  # Six independently editable inscription IDs.
TILE_GUARDIAN = (27, 0)
TILE_WARNING = (28, 0)
PASSABLE = {TILE_FLOOR, TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_CHEST,
            TILE_ENTRANCE, TILE_CHEST_OPEN, TILE_BOSS, TILE_BOSS_CLEAR,
            TILE_RARE_CHEST, TILE_POISON, TILE_PIT, TILE_HEAL_POINT, TILE_QUEST,
            TILE_SWITCH, TILE_SWITCH_ON, TILE_DOOR_OPEN, TILE_GUARDIAN,
            TILE_WARNING} | FLOOR_TILES | PIT_TILES | LORE_TILES
