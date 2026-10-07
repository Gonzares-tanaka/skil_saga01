"""Quest definitions and safe spawn candidates; terrain is never rewritten."""
from collections import deque
import json

from .content import ROOT
from .tiles import (PASSABLE, PIT_TILES, TILE_ENTRANCE, TILE_STAIRS_UP,
                    TILE_STAIRS_DOWN, TILE_BOSS, TILE_GUARDIAN, TILE_WARNING,
                    TILE_DOOR, TILE_SWITCH, TILE_QUEST)

QUEST_TYPES = ('explore', 'investigate', 'hunt')
QUEST_NAMES = dict(zip(QUEST_TYPES, ('探索', '調査', '討伐')))
# Image Bank, pixel X, pixel Y. All sprites are 8x8, color 0 transparent.
QUEST_SYMBOL_EXPLORE = (1, 232, 0)
QUEST_SYMBOL_INVESTIGATE = (1, 240, 0)
QUEST_SYMBOL_HUNT = (1, 248, 0)
QUEST_SYMBOLS = dict(zip(QUEST_TYPES, (QUEST_SYMBOL_EXPLORE,
                                     QUEST_SYMBOL_INVESTIGATE, QUEST_SYMBOL_HUNT)))
# Text widths use the existing UI's 4px units (36 = 144px).
QUEST_FLAVOR_MAX_CHARS = 36
QUEST_FLAVOR_LINE_HEIGHT = 9
QUEST_FLAVOR_LINES_PER_PAGE = 3


def load_quest_flavors(path=None):
    data = json.loads((path or ROOT / 'data/quest_flavors.json').read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ('texts', 'fallbacks')):
        raise ValueError('quest_flavors.json: textsとfallbacksが必要です。')
    ids = set()
    for kind in QUEST_TYPES:
        pools, defaults = data['texts'].get(kind, {}), data['fallbacks'].get(kind, {})
        if not isinstance(pools, dict) or not isinstance(defaults, dict):
            raise ValueError('quest_flavors.json: 種別ごとにLvの辞書が必要です。')
        for level in ('1', '2', '3'):
            pool = pools.get(level, [])
            if not isinstance(pool, list):
                raise ValueError('quest_flavors.json: 文章候補は配列にしてください。')
            for row in pool + [defaults.get(level)]:
                if (not isinstance(row, dict) or
                    any(not isinstance(row.get(k), str) or not row[k].strip() for k in ('id', 'requester')) or
                    not isinstance(row.get('lines'), list) or not row['lines'] or
                    any(not isinstance(line, str) for line in row['lines']) or
                    not any(line.strip() for line in row['lines'])):
                    raise ValueError('quest_flavors.json: id・requester・linesと各Lvの汎用文が必要です。')
                if row['id'] in ids:
                    raise ValueError('quest_flavors.json: idは重複させないでください。')
                ids.add(row['id'])
    return data


def load_quest_settings():
    data = json.loads((ROOT / 'data/quests.json').read_text(encoding='utf-8-sig'))
    levels = data['levels']
    if [row['level'] for row in levels] != [1, 2, 3]:
        raise ValueError('quests.json: Lv1～3が必要です。')
    for row in levels:
        lv = row['level']
        if row['floors'] != [(lv - 1) * 5 + 1, lv * 5] or row['gate'] != (None if lv == 1 else (lv - 1) * 5):
            raise ValueError('quests.json: Lvの対象階・解放ボスが不正です。')
        count = data['investigate_points'][str(lv)]
        if type(count) is not int or count < 2:
            raise ValueError('quests.json: 調査は2地点以上にしてください。')
    for kind in QUEST_TYPES:
        rewards = [data['rewards'][kind][str(lv)] for lv in (1, 2, 3)]
        if any(type(v) is not int or v < 1 for v in rewards) or not rewards[0] < rewards[1] < rewards[2]:
            raise ValueError('quests.json: 報酬は正の整数・Lv順に増加させてください。')
    hunt = data['hunt']
    if not 1 <= hunt['hp_multiplier'] <= 3 or any(type(hunt[k]) is not int or hunt[k] < 0 for k in ('str_bonus', 'def_bonus')):
        raise ValueError('quests.json: 討伐補正が不正です。')
    return data


def spawn_candidates(dungeon, floor):
    """Use authored markers without crossing bosses, guardians or story gates."""
    start = dungeon.find(floor, TILE_ENTRANCE if floor == 0 else TILE_STAIRS_UP)
    forbidden = PIT_TILES | {TILE_ENTRANCE, TILE_STAIRS_UP, TILE_STAIRS_DOWN,
                             TILE_BOSS, TILE_GUARDIAN, TILE_WARNING}
    allowed = PASSABLE - forbidden
    for doors_open in (False, True):
        seen, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                point = x + dx, y + dy
                tile = dungeon.tile(floor, *point)
                if point not in seen and (tile in allowed or doors_open and tile == TILE_DOOR):
                    seen.add(point)
                    queue.append(point)
        if doors_open or not any(dungeon.tile(floor, *p) == TILE_SWITCH for p in seen):
            return sorted(p for p in seen if dungeon.tile(floor, *p) == TILE_QUEST)
