"""Quest definitions and safe spawn candidates; terrain is never rewritten."""
from collections import deque
import json
import logging

from .content import ROOT
from .tiles import (PASSABLE, PIT_TILES, TILE_ENTRANCE, TILE_STAIRS_UP,
                    TILE_STAIRS_DOWN, TILE_BOSS, TILE_GUARDIAN, TILE_WARNING,
                    TILE_DOOR, TILE_SWITCH, TILE_QUEST, FLOOR_TILES)

QUEST_TYPES = ('explore', 'investigate', 'hunt')
QUEST_NAMES = dict(zip(QUEST_TYPES, ('探索', '調査', '討伐')))
# Save-compatible fixed catalog: defaults and future incidental rows are excluded.
QUEST_COMPLETION_IDS = {
    kind: tuple(f'{kind}_l{level}_{index:02d}'
                for level in (1, 2, 3) for index in (1, 2, 3))
    for kind in QUEST_TYPES
}
QUEST_COMPLETION_TOTAL = 27
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
                complete = row.get('complete_lines')
                if (not isinstance(complete, list) or not complete or
                    any(not isinstance(line, str) for line in complete) or
                    not any(line.strip() for line in complete)):
                    raise ValueError('quest_flavors.json: complete_linesのお礼文が必要です。')
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


def quest_spawn_report(dungeon, floor):
    """Filter editor markers and data-only points against the same safe route.

    Supplemental points must be ordinary floor; they never rewrite a Tilemap.
    Quest reachability excludes story gates even after the guardian is defeated.
    """
    markers = dungeon.positions(floor, TILE_QUEST)
    extra = [tuple(point) for point in dungeon.settings['floors'][floor].get('quest_spawn_points', [])]
    registered = markers + extra
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
            break
    valid, rejected = [], []
    for point in sorted(set(registered)):
        tile = dungeon.tile(floor, *point)
        reason = ('outside_map' if tile is None else
                  'not_empty_floor' if tile not in FLOOR_TILES | {TILE_QUEST} else
                  'unreachable_before_story_gates' if point not in seen else None)
        if reason:
            rejected.append(dict(point=point, reason=reason))
        else:
            valid.append(point)
    return dict(floor=floor + 1, marker_count=len(markers), extra_count=len(extra),
                registered_count=len(registered), pre_filter_count=len(set(registered)),
                valid_count=len(valid), valid_points=valid, rejected=rejected)


def spawn_candidates(dungeon, floor):
    return quest_spawn_report(dungeon, floor)['valid_points']


def log_spawn_failure(kind, level, floor, required, valid_count):
    logging.getLogger(__name__).warning(
        'QUEST SPAWN FAILED type=%s level=%s target_floor=B%sF required_count=%s valid_candidate_count=%s',
        kind, level, floor + 1, required, valid_count)
