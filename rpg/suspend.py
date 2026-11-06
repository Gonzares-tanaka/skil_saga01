"""Explicit, single-use expedition checkpoints, separate from normal SAVE v1.

Restore/validate detached objects before consuming storage. Only publish those
objects after consumption succeeds. No timers or lifecycle hooks save a game.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import uuid
from types import SimpleNamespace

from .map_resources import load_maps
from .save import (FileSaveBackend, SaveError, NoSaveError, make_save_data,
                   prepare_saved_game, require, integer, strings)
from .statuses import STATUS_IDS
from .labels import EFFECTS
from .quests import spawn_candidates

SUSPEND_VERSION = 1
SUSPEND_PATH = Path('save/suspend.json')
RUNTIME_FIELDS = ('growth_points', 'used_skills', 'category_uses', 'cooldowns',
                  'guarding', 'berserk', 'effects', 'statuses',
                  'status_resistances', 'status_immunities', 'last_skill_id',
                  'last_skill_index')


class StorageJob:
    def __init__(self, result=None, error=None):
        self.done, self.result, self.error = True, result, error


class FileSuspendBackend:
    def __init__(self, path=SUSPEND_PATH):
        self.path = Path(path)
        self.claim = self.path.with_name(self.path.stem + '.consuming.json')

    def _source(self):
        if self.path.exists() and self.claim.exists():
            raise SaveError('中断データを別のゲームが使用中です')
        # A crash before deletion has not published a restored game. Preserve
        # that unconsumed file rather than silently losing the checkpoint.
        return self.path if self.path.exists() else self.claim

    def _consume(self, expected):
        source = self._source()
        if source.read_text(encoding='utf-8-sig') != expected:
            raise SaveError('中断データが変更されました')
        if source == self.path:
            os.replace(self.path, self.claim)
        try:
            if self.claim.read_text(encoding='utf-8-sig') != expected:
                raise SaveError('中断データが変更されました')
            # Unlink is the consumption commit. Only one caller can succeed.
            self.claim.unlink()
        except Exception:
            if self.claim.exists() and not self.path.exists():
                try:
                    os.replace(self.claim, self.path)
                except OSError:
                    pass  # Retain claim; _source can recover it next time.
            raise

    def start(self, operation, payload=None):
        try:
            if operation == 'exists':
                value = self._source().exists()
            elif operation == 'read':
                value = self._source().read_text(encoding='utf-8-sig')
            elif operation == 'write':
                if self.claim.exists():
                    raise SaveError('中断データを使用中です')
                FileSaveBackend(self.path).write(json.loads(payload))
                value = True
            elif operation == 'consume':
                self._consume(payload)
                value = True
            else:
                raise SaveError('不明な中断操作です')
            return StorageJob(value)
        except FileNotFoundError:
            return StorageJob(error=NoSaveError('中断データがありません'))
        except Exception as error:
            return StorageJob(error=error)


class BrowserSuspendBackend:
    """IndexedDB transactions run asynchronously; Pyxel polls a small JS job."""
    def start(self, operation, payload=None):
        try:
            from js import window
            return window.sparkSuspendStore.start(operation, payload or '')
        except Exception:
            return StorageJob(error=SaveError('中断用の保存領域を使用できません'))


def job_result(job):
    if job.error:
        raise SaveError(str(job.error))
    return job.result


def _authored_maps(app):
    maps = load_maps()
    settings = app.dungeon.settings
    cells = []
    for floor, tilemap in enumerate(maps):
        row = settings['floors'][floor]
        w, h = row.get('width', settings['width']), row.get('height', settings['height'])
        cells.append([w, h, [list(tilemap.pget(x, y)) for y in range(h) for x in range(w)]])
    digest = hashlib.sha256(json.dumps(cells, separators=(',', ':')).encode()).hexdigest()
    return maps, cells, digest


def make_suspend_data(app):
    if not app.can_suspend_game():
        raise SaveError('中断は安定した探索メニューでのみ可能です')
    s, d, e = app.session, app.dungeon, app.exploration
    _, cells, signature = _authored_maps(app)
    patches = []
    for floor, (w, h, tiles) in enumerate(cells):
        for index, tile in enumerate(tiles):
            x, y = index % w, index // w
            actual = list(d.maps[floor].pget(x, y))
            if actual != tile:
                patches.append([floor, x, y, *actual])
    party = []
    for actor in s.party:
        runtime = {key: deepcopy(getattr(actor, key)) for key in RUNTIME_FIELDS}
        runtime['counter'] = actor.counter.id if actor.counter else None
        party.append(runtime)
    return dict(suspend_version=SUSPEND_VERSION, game=make_save_data(app),
        party_runtime=party, rng_state=s.rng.getstate(),
        session=dict(unbanked_trz=s.treasure.unbanked, settled=s.settled,
            debug=s.debug, debug_pending=s.debug_pending, field_pending=s.field_pending,
            results=list(s.results), auto_recover=getattr(s, 'auto_recover', None),
            spark_multiplier=getattr(s, 'spark_multiplier', None)),
        dungeon=dict(floor=d.floor, x=d.x, y=d.y, steps=d.steps, grace=d.grace,
                     encounter_remaining=d.encounter_remaining,
            opened=[list(p) for p in sorted(d.opened)],
            activated_switches=sorted(d.activated_switches),
            chest_loot=[dict(point=list(p), reward=deepcopy(r)) for p, r in sorted(d.chest_loot.items())],
            last_reward=deepcopy(d.last_reward)),
        exploration=dict(active=deepcopy(e.active), springs=[list(p) for p in sorted(e.springs)],
            flavor_rng_state=e.flavor_rng.getstate()),
        ui=dict(player_facing=app.player_facing, last_rumor=app.last_rumor,
                explore_message=app.explore_message),
        map_signature=signature, map_patches=patches)


def _set_rng(rng, state):
    require(isinstance(state, list) and len(state) == 3 and state[0] == 3, '乱数形式')
    inner, gauss = state[1:]
    require(isinstance(inner, list) and len(inner) == 625 and
            all(integer(v, 0, 2**32 - 1) for v in inner[:-1]) and integer(inner[-1], 0, 624), '乱数状態')
    require(gauss is None or type(gauss) in (int, float) and math.isfinite(gauss), '乱数キャッシュ')
    rng.setstate((3, tuple(inner), gauss))


def prepare_suspend_game(app, data):
    """Reject malformed data without touching the running party or storage."""
    require(isinstance(data, dict) and type(data.get('suspend_version')) is int
            and data['suspend_version'] == SUSPEND_VERSION, '中断バージョン')
    required = {'game', 'party_runtime', 'rng_state', 'session', 'dungeon',
                'exploration', 'ui', 'map_signature', 'map_patches'}
    require(required <= data.keys(), '中断項目')
    maps, cells, signature = _authored_maps(app)
    require(data['map_signature'] == signature, 'マップの版が異なります')
    patches = data['map_patches']
    require(isinstance(patches, list) and len(patches) <= sum(w*h for w, h, _ in cells), 'マップ差分')
    seen = set()
    for patch in patches:
        require(isinstance(patch, list) and len(patch) == 5 and all(type(v) is int for v in patch), 'マップ差分座標')
        floor, x, y, u, v = patch
        require(integer(floor, 0, 14) and integer(x, 0, cells[floor][0]-1)
                and integer(y, 0, cells[floor][1]-1) and integer(u, 0, 31) and integer(v, 0, 31), 'マップ差分範囲')
        require((floor, x, y) not in seen, 'マップ差分重複')
        seen.add((floor, x, y)); maps[floor].pset(x, y, (u, v))
    proxy = SimpleNamespace(initial_content=app.initial_content, dungeon=SimpleNamespace(maps=maps))
    s, d, e, shown = prepare_saved_game(proxy, data['game'])
    require(not d.finale.final_event_started and d.finale.guardian_index is None, 'イベント途中')
    runtime = data['party_runtime']
    require(isinstance(runtime, list) and len(runtime) == 4, '中断パーティ')
    for actor, row in zip(s.party, runtime):
        require(isinstance(row, dict) and {*RUNTIME_FIELDS, 'counter'} <= row.keys(), '継続状態')
        for key in ('used_skills', 'cooldowns', 'category_uses', 'growth_points'):
            value = row[key]
            require(isinstance(value, dict) and all(isinstance(k, str) and type(v) in (int, float)
                    and math.isfinite(v) and v >= 0 for k, v in value.items()), key)
            if key in ('used_skills', 'cooldowns'):
                require(set(value) <= s.skills.keys() and all(type(v) is int for v in value.values()), key)
            if key == 'growth_points':
                require(set(value) <= {'HP', 'STR', 'AGI', 'INT'}, key)
            setattr(actor, key, dict(value))
        require(type(row['guarding']) is bool and integer(row['berserk']), '防御継続')
        actor.guarding, actor.berserk = row['guarding'], row['berserk']
        effects = row['effects']
        require(isinstance(effects, dict) and effects.keys() <= EFFECTS.keys(), '効果')
        for value in effects.values():
            require(isinstance(value, list) and len(value) == 2 and type(value[0]) in (int, float)
                    and math.isfinite(value[0]) and value[0] > 0 and integer(value[1], 1), '効果持続')
        actor.effects = {k: tuple(v) for k, v in effects.items()}
        for key in ('statuses', 'status_resistances'):
            value = row[key]
            require(isinstance(value, dict) and set(value) <= set(STATUS_IDS), key)
            require(all(integer(v, 1, 9) for v in value.values()) if key == 'statuses' else
                    all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 100 for v in value.values()), key)
            setattr(actor, key, dict(value))
        require(strings(row['status_immunities']) and set(row['status_immunities']) <= set(STATUS_IDS), '耐性')
        actor.status_immunities = tuple(row['status_immunities'])
        require(row['counter'] is None or isinstance(row['counter'], str) and row['counter'] in s.skills, '反撃')
        actor.counter = s.skills.get(row['counter'])
        sid = row['last_skill_id']
        require(sid is None or isinstance(sid, str) and sid in s.skills, 'カーソル技ID')
        require(integer(row['last_skill_index'], 0, 5), 'カーソル位置')
        actor.last_skill_id, actor.last_skill_index = sid, row['last_skill_index']
    extra = data['session']
    require(isinstance(extra, dict) and {'unbanked_trz', 'settled', 'debug', 'debug_pending',
            'field_pending', 'results', 'auto_recover', 'spark_multiplier'} <= extra.keys(), '冒険状態')
    require(integer(extra['unbanked_trz']), '未確定TRZ')
    s.treasure.unbanked = extra['unbanked_trz']
    for key in ('settled', 'debug', 'debug_pending', 'field_pending'):
        require(type(extra[key]) is bool, key); setattr(s, key, extra[key])
    require(strings(extra['results']), '結果履歴'); s.results = list(extra['results'])
    require(extra['auto_recover'] is None or type(extra['auto_recover']) is bool, '回復方式')
    require(extra['spark_multiplier'] is None or type(extra['spark_multiplier']) in (int, float)
            and math.isfinite(extra['spark_multiplier']) and extra['spark_multiplier'] > 0, '閃き倍率')
    for key in ('auto_recover', 'spark_multiplier'):
        if extra[key] is not None: setattr(s, key, extra[key])
    field = data['dungeon']
    require(isinstance(field, dict) and {'floor', 'x', 'y', 'steps', 'grace', 'opened',
            'activated_switches', 'chest_loot', 'last_reward'} <= field.keys(), '探索状態')
    require(integer(field['floor'], 0, 14), '階層')
    d.floor = field['floor']; w, h = d.map_bounds(d.floor)
    require(integer(field['x'], 0, w-1) and integer(field['y'], 0, h-1), '現在座標')
    d.x, d.y = field['x'], field['y']
    for key in ('steps', 'grace'):
        require(integer(field[key]), key); setattr(d, key, field[key])
    # PASS03 checkpoints have no pre-drawn countdown. Migrate once to the
    # current AREA minimum, preserving any larger old safe budget, without RNG.
    # New checkpoints restore the exact remainder (including a deferred zero).
    remaining = field.get('encounter_remaining', max(
        d.settings['encounter_step_ranges'][d.floor // 5][0], d.grace + 1))
    require(integer(remaining), '残り遭遇歩数')
    d.encounter_remaining = remaining

    def point(value):
        require(isinstance(value, list) and len(value) == 3 and all(type(v) is int for v in value), '探索地点')
        f, x, y = value
        require(integer(f, 0, 14), '地点階層')
        w, h = d.map_bounds(f)
        require(integer(x, 0, w-1) and integer(y, 0, h-1), '地点座標')
        return f, x, y

    def reward(value):
        if value is None: return
        kinds = {'TREASURE', 'POTION', 'PHOENIX ASH', 'REMEDY', 'SKILL_CHANCE', 'TRAP', 'EMPTY'}
        require(isinstance(value, dict) and value.get('kind') in kinds and
                integer(value.get('amount', 1)) and type(value.get('chance', 1)) in (int, float)
                and 0 <= value.get('chance', 1) <= 1, '宝箱報酬')

    require(isinstance(field['opened'], list) and isinstance(field['chest_loot'], list), '宝箱')
    d.opened = {point(p) for p in field['opened']}
    require(len(d.opened) == len(field['opened']), '宝箱重複')
    switches = field['activated_switches']
    require(isinstance(switches, list) and all(integer(f, 0, 14) for f in switches), 'スイッチ')
    d.activated_switches = set(switches)
    require(d.can_enter(d.floor, d.x, d.y), '再開地点')
    d.chest_loot = {}
    for row in field['chest_loot']:
        require(isinstance(row, dict) and {'point', 'reward'} <= row.keys(), '宝箱抽選')
        p = point(row['point']); reward(row['reward'])
        require(p not in d.chest_loot and row['reward'] is not None, '宝箱抽選重複')
        d.chest_loot[p] = deepcopy(row['reward'])
    reward(field['last_reward']); d.last_reward = deepcopy(field['last_reward'])
    exploration = data['exploration']
    require(isinstance(exploration, dict) and {'active', 'springs', 'flavor_rng_state'} <= exploration.keys(), '探索進行')
    q = exploration['active']
    require((q is None) == (e.active is None), '依頼の有無')
    if q is not None:
        require(isinstance(q, dict) and {'points', 'investigated_points'} <= q.keys(), '依頼地点')
        for key in e.active:
            if key not in ('points', 'investigated_points'):
                require(q.get(key) == e.active[key], '依頼状態:' + key)
        points, done = q['points'], q['investigated_points']
        valid = spawn_candidates(d, q['target_floor']-1)
        require(isinstance(points, list) and len(points) == q['required_count'] and
                all(isinstance(p, list) and len(p) == 2 and all(type(v) is int for v in p) for p in points), '依頼地点数')
        require(len({tuple(p) for p in points}) == len(points) and all(tuple(p) in valid for p in points), '依頼地点範囲')
        require(isinstance(done, list) and all(p in points for p in done) and len({tuple(p) for p in done}) == len(done), '調査地点')
        require(len(done) == q['progress'], '調査進捗')
        e.active = deepcopy(q)
    require(isinstance(exploration['springs'], list), '泉')
    e.springs = {point(p) for p in exploration['springs']}
    _set_rng(s.rng, data['rng_state']); _set_rng(e.flavor_rng, exploration['flavor_rng_state'])
    ui = data['ui']
    require(isinstance(ui, dict) and ui.get('player_facing') in ('up', 'down', 'left', 'right')
            and isinstance(ui.get('explore_message'), str)
            and (ui.get('last_rumor') is None or isinstance(ui['last_rumor'], str)), '探索表示')
    return s, d, e, shown, deepcopy(ui)


class SuspendManager:
    def __init__(self, backend=None):
        self.backend = backend if backend is not None else (
            BrowserSuspendBackend() if sys.platform == 'emscripten' else FileSuspendBackend())

    def save(self, app):
        # Validate the exact JSON representation before any storage is touched.
        data = make_suspend_data(app)
        # Separate identity prevents an old reader from consuming a newer save
        # even when the expedition happens to have byte-identical state (ABA).
        data['suspend_id'] = uuid.uuid4().hex
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False)
        prepare_suspend_game(app, json.loads(raw))
        return self.backend.start('write', raw)

    def prepare(self, app, raw):
        try:
            data = json.loads(raw)
            ident = data.get('suspend_id') if isinstance(data, dict) else None
            require(isinstance(ident, str) and len(ident) == 32 and
                    all(c in '0123456789abcdef' for c in ident), '中断ID')
            return prepare_suspend_game(app, data)
        except SaveError:
            raise
        except Exception as error:
            raise SaveError('中断データを復元できません') from error
