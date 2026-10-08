"""Versioned JSON game state, with a small replaceable storage boundary.

No pickle, device identifiers or battle/checkpoint objects.
Version migrations belong in migrate_save_data before validation/application.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from .battle import Session
from .dungeon import Dungeon, load_dungeon_settings
from .exploration import Exploration
from .models import Character
from .quests import QUEST_TYPES, QUEST_COMPLETION_IDS, spawn_candidates

SAVE_VERSION = 1
DEFAULT_SAVE_PATH = Path('save') / 'save.json'
BROWSER_SAVE_KEY = 'skill_seekers_save_v1'
STORY_FLAGS = ('guardians_defeated', 'demon_defeated', 'has_amrita',
               'final_event_started', 'lord_of_elysion_defeated', 'amrita_power_spent')
COUNTERS = ('completed', 'wins', 'losses', 'draws', 'total_battles')


class SaveError(ValueError):
    pass


class NoSaveError(SaveError):
    pass


class FileSaveBackend:
    available = True

    def __init__(self, path=DEFAULT_SAVE_PATH):
        self.path = Path(path)

    def read(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8-sig'))
        except FileNotFoundError as error:
            raise NoSaveError('セーブデータがありません') from error
        except (OSError, ValueError, UnicodeError) as error:
            raise SaveError('セーブデータを読み込めません') from error

    def write(self, data):
        temporary = self.path.with_suffix('.tmp')
        try:
            encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        except (OSError, ValueError, TypeError) as error:
            raise SaveError('セーブできませんでした') from error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


class BrowserSaveBackend:
    """Same JSON data in localStorage; no virtual-file fallback or audio waits."""
    available = True

    def __init__(self, storage=None):
        self.storage = storage  # Optional injection for storage failure tests.

    def _storage(self):
        if self.storage is not None:
            return self.storage
        # Pyxel Web uses Pyodide's documented js bridge. Access lazily: even
        # obtaining window.localStorage can raise SecurityError.
        from js import window
        return window.localStorage

    def _read_text(self):
        try:
            value = self._storage().getItem(BROWSER_SAVE_KEY)
        except Exception as error:
            raise SaveError('セーブデータを読み込めません') from error
        # getItem returns a string or null. Pyodide 314 maps null to jsnull,
        # older versions to None; neither is a Python string.
        return value if isinstance(value, str) else None

    def exists(self):
        return self._read_text() is not None

    def read(self):
        value = self._read_text()
        if value is None:
            raise NoSaveError('セーブデータがありません')
        try:
            return json.loads(value)
        except (ValueError, TypeError) as error:
            raise SaveError('セーブデータを読み込めません') from error

    def write(self, data):
        try:
            encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
            self._storage().setItem(BROWSER_SAVE_KEY, encoded)
        except Exception as error:
            raise SaveError('セーブできませんでした') from error


def default_backend():
    return BrowserSaveBackend() if sys.platform == 'emscripten' else FileSaveBackend()


def migrate_save_data(data):
    if not isinstance(data, dict) or type(data.get('save_version')) is not int or data['save_version'] != SAVE_VERSION:
        raise SaveError('未対応または不正なsave_versionです')
    return deepcopy(data)


def require(condition, label):
    if not condition:
        raise SaveError('セーブデータが不正です: ' + label)


def integer(value, low=0, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def strings(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def make_save_data(app):
    s, d, e = app.session, app.dungeon, app.exploration
    party = []
    for actor in s.party:
        party.append(dict(name=actor.name, growth_type=actor.growth_type,
            hp=actor.hp, max_hp=actor.max_hp, strength=actor.strength,
            agility=actor.agility, intellect=actor.intellect, sprite=list(actor.sprite),
            skills=[dict(skill_id=sid, uses=actor.skill_uses[sid],
                         max_uses=actor.max_uses(s.skills[sid]),
                         mastered_copy=sid in actor.mastered_copies) for sid in actor.skills],
            history=list(actor.history)))
    active = None
    if e.active:
        keys = ('type', 'level', 'target_floor', 'progress', 'required_count',
                'completed', 'reward', 'flavor_id')
        active = {key: e.active[key] for key in keys}
        if e.active['type'] == 'hunt':
            active.update({key: e.active[key] for key in ('hunt_enemy_id', 'hunt_source_floor')})
    return dict(save_version=SAVE_VERSION, party=party,
        discovered_skills=sorted(s.discovered_skills), mastered_skills=sorted(s.mastered_skills),
        items=dict(s.inventory.counts), banked_trz=s.treasure.banked,
        **{key: getattr(s, key) for key in COUNTERS},
        quest_clear_counts=dict(e.quest_clear_counts), completed_quest_ids=list(e.completed_quest_ids),
        quest_completed_levels=sorted(e.completed), active_quest=deepcopy(active),
        last_flavor_id=e.last_flavor_id,
        dungeon_progress=dict(defeated_bosses=sorted(d.defeated_bosses)),
        story={**{key: getattr(d.finale, key) for key in STORY_FLAGS},
               'read_lore': sorted(d.finale.read_lore)}, hub_intro_shown=app.hub_intro_shown)


def prepare_saved_game(app, raw_data):
    """Validate and build detached objects; an invalid save cannot alter play."""
    data = migrate_save_data(raw_data)
    required = {'party', 'discovered_skills', 'mastered_skills', 'items', 'banked_trz',
                *COUNTERS, 'quest_clear_counts', 'completed_quest_ids', 'quest_completed_levels',
                'active_quest', 'last_flavor_id', 'dungeon_progress', 'story', 'hub_intro_shown'}
    require(required <= data.keys(), '必要キー欠損')
    s = Session(*deepcopy(app.initial_content))
    d = Dungeon(app.dungeon.maps, s.enemy_data, load_dungeon_settings(), s.rng, s.treasure, s.inventory)
    e = Exploration(s, d)
    for key in COUNTERS:
        require(integer(data[key]), key)
        setattr(s, key, data[key])
    require(integer(data['banked_trz']), 'banked_trz')
    s.treasure.banked, s.treasure.unbanked = data['banked_trz'], 0
    for key in ('discovered_skills', 'mastered_skills'):
        value = data[key]
        require(strings(value) and len(value) == len(set(value)) and set(value) <= s.skills.keys(), key)
        setattr(s, key, set(value))
    require(s.mastered_skills <= s.discovered_skills, 'MASTERED/DISCOVERED')
    items = data['items']
    require(isinstance(items, dict) and items.keys() == s.inventory.counts.keys(), 'items')
    require(all(integer(v, 0, 9) for v in items.values()), 'ITEM個数')
    s.inventory.counts = dict(items)
    require(isinstance(data['party'], list) and len(data['party']) == 4, 'party')
    restored_party = []
    for row in data['party']:
        keys = {'name', 'growth_type', 'hp', 'max_hp', 'strength', 'agility', 'intellect', 'sprite', 'skills', 'history'}
        require(isinstance(row, dict) and keys <= row.keys(), 'キャラクター項目')
        require(isinstance(row['name'], str) and bool(row['name'].strip()) and row['name'].isprintable(), 'name')
        require(row['growth_type'] in ('POWER', 'SPEED', 'MIND'), 'growth_type')
        require(all(integer(row[k], 1) for k in ('max_hp', 'strength', 'agility', 'intellect')), '能力値')
        require(integer(row['hp'], 0, row['max_hp']), 'HP')
        require(isinstance(row['sprite'], list) and len(row['sprite']) == 2 and
                all(integer(v, 0, 240) for v in row['sprite']), 'sprite')
        require(strings(row['history']), 'history')
        require(isinstance(row['skills'], list) and len(row['skills']) <= s.settings['skill_slots'], 'skill slots')
        actor = Character(row['name'], row['growth_type'], row['max_hp'], row['strength'],
                          row['agility'], row['intellect'], tuple(row['sprite']))
        actor.hp, actor.history = row['hp'], list(row['history'])
        actor.mastered_skills = s.mastered_skills
        for learned in row['skills']:
            require(isinstance(learned, dict) and {'skill_id', 'uses', 'max_uses', 'mastered_copy'} <= learned.keys(), '所持技')
            sid = learned['skill_id']
            require(isinstance(sid, str) and sid in s.skills and sid not in actor.skills, 'skill_id')
            skill = s.skills[sid]
            require(integer(learned['max_uses'], 1) and learned['max_uses'] == skill.max_uses, 'max_uses/技データ不一致')
            require(integer(learned['uses'], 1, learned['max_uses']), 'Uses')
            require(type(learned['mastered_copy']) is bool and sid in s.discovered_skills, '所持技記録')
            require(not learned['mastered_copy'] or (sid in s.mastered_skills and skill.effect in ('damage', 'drain')), 'MASTEREDコピー')
            actor.skills.append(sid)
            actor.skill_uses[sid] = learned['uses']
            if learned['mastered_copy']:
                actor.mastered_copies.add(sid)
        restored_party.append(actor)
    require(any(actor.alive for actor in restored_party), '生存者')
    s.party, s.settled = restored_party, True
    counts = data['quest_clear_counts']
    require(isinstance(counts, dict) and counts.keys() == set(QUEST_TYPES) and all(integer(v) for v in counts.values()), 'QUEST CLEAR')
    e.quest_clear_counts = dict(counts)
    ids = data['completed_quest_ids']
    fixed_ids = {sid for values in QUEST_COMPLETION_IDS.values() for sid in values}
    require(strings(ids) and len(ids) == len(set(ids)) and set(ids) <= fixed_ids, 'QUEST固有ID')
    e.completed_quest_ids = list(ids)
    for kind in QUEST_TYPES:
        require(len(set(ids).intersection(QUEST_COMPLETION_IDS[kind])) <= counts[kind], 'QUEST達成数/CLEAR')
    levels = data['quest_completed_levels']
    require(isinstance(levels, list) and all(integer(v, 1, 3) for v in levels), 'QUEST旧Lv記録')
    e.completed = set(levels)
    require(data['last_flavor_id'] is None or isinstance(data['last_flavor_id'], str), 'last_flavor_id')
    e.last_flavor_id = data['last_flavor_id']
    progress = data['dungeon_progress']
    require(isinstance(progress, dict) and isinstance(progress.get('defeated_bosses'), list), 'ダンジョン進行')
    bosses = progress['defeated_bosses']
    require(all(type(v) is int and v in (4, 9, 14) for v in bosses), '撃破階層')
    d.defeated_bosses = set(bosses)
    story = data['story']
    require(isinstance(story, dict) and set(STORY_FLAGS) | {'read_lore'} <= story.keys(), 'ストーリー')
    require(all(type(story[k]) is bool for k in STORY_FLAGS), 'ストーリーフラグ型')
    require(strings(story['read_lore']) and set(story['read_lore']) <= d.finale.data['lore'].keys(), '石碑記録')
    require(story['demon_defeated'] == (14 in d.defeated_bosses), 'デーモン撃破')
    require(not story['demon_defeated'] or story['guardians_defeated'], '守護者撃破')
    require(not story['has_amrita'] or (story['demon_defeated'] and not story['amrita_power_spent']), 'アムリタ')
    require(story['lord_of_elysion_defeated'] == story['amrita_power_spent'], '最終撃破/消費')
    require(not story['final_event_started'] or story['demon_defeated'], '最終イベント')
    require(not story['amrita_power_spent'] or story['final_event_started'], '最終撃破')
    # In-flight final events cannot originate from GUILD. Without a checkpoint
    # such a manually altered save would strand a loaded party in the HUB.
    require(not story['final_event_started'] or story['lord_of_elysion_defeated'], '決戦途中の通常SAVE')
    require(not story['demon_defeated'] or story['has_amrita'] or story['amrita_power_spent'], 'KEY ITEM欠損')
    d.finale.restore({key: story[key] for key in (*STORY_FLAGS, 'read_lore')})
    require(type(data['hub_intro_shown']) is bool, 'hub_intro_shown')
    q = data['active_quest']
    if q is not None:
        keys = {'type', 'level', 'target_floor', 'progress', 'required_count', 'completed', 'reward', 'flavor_id'}
        require(isinstance(q, dict) and keys <= q.keys(), 'active_quest')
        require(isinstance(q['type'], str) and q['type'] in QUEST_TYPES and integer(q['level'], 1, 3), 'QUEST種別/Lv')
        kind, level = q['type'], q['level']
        require(integer(q['target_floor'], (level - 1) * 5 + 1, level * 5), 'QUEST対象階')
        require(e.unlocked(e.quest_data['levels'][level - 1]), 'QUEST未解放Lv')
        expected = e.quest_data['investigate_points'][str(level)] if kind == 'investigate' else 1
        require(type(q['required_count']) is int and q['required_count'] == expected, 'QUEST必要数')
        require(integer(q['progress'], 0, expected) and type(q['completed']) is bool and q['completed'] == (q['progress'] == expected), 'QUEST進捗')
        require(type(q['reward']) is int and q['reward'] == e.quest_data['rewards'][kind][str(level)], 'QUEST報酬')
        require(q['flavor_id'] is None or isinstance(q['flavor_id'], str), 'flavor_id')
        points = spawn_candidates(d, q['target_floor'] - 1)
        require(len(points) >= expected, 'QUEST安全地点')
        q = {key: deepcopy(q[key]) for key in keys}
        q.update(id=level, points=[list(p) for p in points[:expected]],
                 investigated_points=[list(p) for p in points[:q['progress']]])
        if kind == 'hunt':
            source = q['target_floor'] - 1
            if 'enemy_ids' not in d.settings['floors'][source]:
                source -= 1
            saved = data['active_quest']
            require(saved.get('hunt_source_floor') == source + 1 and type(saved.get('hunt_source_floor')) is int,
                    '討伐元階')
            require(isinstance(saved.get('hunt_enemy_id'), str) and saved['hunt_enemy_id'] in d.settings['floors'][source]['enemy_ids'], '討伐敵')
            q.update(hunt_source_floor=source + 1, hunt_enemy_id=saved['hunt_enemy_id'])
        e.active = q
    return s, d, e, data['hub_intro_shown']


def apply_save_data(app, data):
    prepared = prepare_saved_game(app, data)
    app.session, app.dungeon, app.exploration, app.hub_intro_shown = prepared


class SaveManager:
    def __init__(self, backend=None):
        self.backend = backend if backend is not None else default_backend()

    def save(self, app):
        if not app.can_save_game():
            raise SaveError('SAVEはGUILDでのみ可能です')
        data = make_save_data(app)
        prepare_saved_game(app, data)  # Refuse writing unrecoverable state.
        self.backend.write(data)

    def load(self, app):
        apply_save_data(app, self.backend.read())
