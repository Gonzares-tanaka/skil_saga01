"""Field rewards and one JSON-compatible quest, shared by all three types."""
import json
from random import Random
from .content import ROOT
from .growth import spark
from .quests import (QUEST_TYPES, QUEST_NAMES, load_quest_settings,
                     load_quest_flavors, spawn_candidates)
from .labels import CURRENCY_NAME
from .models import Enemy


def load_exploration_settings():
    data = json.loads((ROOT / "data/exploration.json").read_text(encoding="utf-8-sig"))
    kinds = {"TREASURE", "POTION", "PHOENIX ASH", "REMEDY", "SKILL_CHANCE", "TRAP", "EMPTY"}
    for rows in data["CHEST_REWARD_TABLE"].values():
        if not rows or sum(r["weight"] for r in rows) <= 0:
            raise ValueError("宝箱の重み合計は正の数が必要です")
        for row in rows:
            if row["kind"] not in kinds or row["weight"] < 0 or row.get("amount", 1) < 0 or not 0 <= row.get("chance", 1) <= 1:
                raise ValueError("宝箱テーブルの値が不正です")
    if data["poison_damage"] < 0:
        raise ValueError("探索ダメージは0以上です")
    return data


class Exploration:
    def __init__(self, session, dungeon):
        self.session, self.dungeon = session, dungeon
        self.quest_data = load_quest_settings()
        self.flavor_data = load_quest_flavors()
        # Flavor choices must not change target placement, combat or growth RNG.
        self.flavor_rng = Random()
        self.flavor_rng.setstate(session.rng.getstate())
        self.last_flavor_id = None
        self.active_quest = None
        self.pending_quest = None
        self.pending_quest_rng_state = None
        self.completed = set()
        self.springs = set()

    def unlocked(self, quest):
        return quest["gate"] is None or quest["gate"] - 1 in self.dungeon.defeated_bosses

    # Existing checkpoint/debug names are aliases; progress is stored only once.
    @property
    def active(self):
        return self.active_quest

    @active.setter
    def active(self, value):
        self.active_quest = value

    @property
    def target(self):
        q = self.active_quest
        return (q['target_floor'] - 1, *q['points'][0]) if q else None

    @target.setter
    def target(self, value):
        if self.active_quest and value is not None:
            self.active_quest['target_floor'] = value[0] + 1
            self.active_quest['points'][0] = list(value[1:])

    @property
    def surveyed(self):
        return bool(self.active_quest and self.active_quest['completed'])

    @surveyed.setter
    def surveyed(self, value):
        # Checkpoint restore writes the legacy False after restoring the full
        # quest dict. Preserve partial investigation progress on that no-op.
        if self.active_quest and bool(value) != self.surveyed:
            q = self.active_quest
            q['completed'] = bool(value)
            q['progress'] = q['required_count'] if value else 0
            q['investigated_points'] = [list(p) for p in q['points']] if value else []

    def reset_progress(self):
        if self.active_quest:
            self.active_quest.update(completed=False, progress=0, investigated_points=[])

    def quest_name(self, quest=None):
        q = self.active_quest if quest is None else quest
        return f"{QUEST_NAMES[q['type']]} Lv{q['level']}" if q else ''

    def message(self, key):
        q = self.active_quest or {}
        values = dict(q, name=self.quest_name(), floor=q.get('target_floor'), currency=CURRENCY_NAME)
        return self.quest_data['messages'][key].format(**values)

    def available(self):
        return [(kind, row['level']) for kind in QUEST_TYPES
                for row in self.quest_data['levels'] if self.unlocked(row)]

    def choose_flavor(self, kind, level):
        pool = self.flavor_data['texts'].get(kind, {}).get(str(level), [])
        choices = [row for row in pool if row['id'] != self.last_flavor_id] or pool
        row = (self.flavor_rng.choice(choices) if choices else
               self.flavor_data['fallbacks'][kind][str(level)])
        return row['id']

    def quest_flavor(self, quest=None):
        """Resolve only within this type/Lv; old or removed IDs use editable defaults."""
        q = self.active_quest if quest is None else quest
        if q is None:
            return None
        pool = self.flavor_data['texts'].get(q['type'], {}).get(str(q['level']), [])
        return next((row for row in pool if row['id'] == q.get('flavor_id')),
                    self.flavor_data['fallbacks'][q['type']][str(q['level'])])

    def make_quest(self, quest_id, debug=False, quest_type='explore', rng=None):
        """Generate a contract without activating it or recording acceptance."""
        if self.active_quest:
            raise ValueError(self.message('already_active'))
        if quest_type not in QUEST_TYPES or quest_id not in (1, 2, 3):
            raise ValueError('依頼の種別・Lvが不正です。')
        quest = next(q for q in self.quest_data['levels'] if q['level'] == quest_id)
        if not self.unlocked(quest) and not debug:
            raise ValueError("先のエリアのボス撃破が必要です")
        count = self.quest_data['investigate_points'][str(quest_id)] if quest_type == 'investigate' else 1
        candidates = {floor: spawn_candidates(self.dungeon, floor)
                      for floor in range(quest['floors'][0] - 1, quest['floors'][1])}
        candidates = {floor: points for floor, points in candidates.items() if len(points) >= count}
        if not candidates:
            raise ValueError('安全なQUEST候補地点が足りません。')
        rng = self.session.rng if rng is None else rng
        floor = rng.choice(list(candidates))
        points = rng.sample(candidates[floor], count)
        result = dict(type=quest_type, level=quest_id, id=quest_id,
            target_floor=floor + 1, points=[list(p) for p in points], investigated_points=[],
            progress=0, required_count=count, completed=False,
            reward=self.quest_data['rewards'][quest_type][str(quest_id)])
        if quest_type == 'hunt':
            source = floor if 'enemy_ids' in self.dungeon.settings['floors'][floor] else floor - 1
            profile = self.dungeon.settings['floors'][source]
            result['hunt_source_floor'] = source + 1
            result['hunt_enemy_id'] = rng.choices(profile['enemy_ids'], profile['weights'])[0]
        result['flavor_id'] = self.choose_flavor(quest_type, quest_id)
        return result

    def activate_quest(self, quest):
        if self.active_quest:
            raise ValueError(self.message('already_active'))
        self.active_quest = quest
        self.last_flavor_id = quest['flavor_id']
        self.decline_preview()
        return self.message('accepted')

    def accept(self, quest_id, debug=False, quest_type='explore'):
        # Direct acceptance remains available to existing debug/test callers.
        return self.activate_quest(self.make_quest(quest_id, debug, quest_type))

    def preview_quest(self, level, quest_type):
        # The modal UI cannot play while this offer is shown. Generate with a
        # copy, then commit its RNG state only when the player accepts the offer.
        rng = Random()
        rng.setstate(self.session.rng.getstate())
        quest = self.make_quest(level, quest_type=quest_type, rng=rng)
        self.pending_quest, self.pending_quest_rng_state = quest, rng.getstate()
        return quest

    def accept_preview(self):
        if self.active_quest:
            raise ValueError(self.message('already_active'))
        if self.pending_quest is None:
            raise ValueError('確認中の依頼がありません。')
        self.session.rng.setstate(self.pending_quest_rng_state)
        return self.activate_quest(self.pending_quest)

    def decline_preview(self):
        self.pending_quest = self.pending_quest_rng_state = None

    def hint(self):
        return self.message('hint') if self.active and not self.surveyed and self.target[0] == self.dungeon.floor else ''

    def visible_points(self):
        q = self.active_quest
        if not q or q['completed'] or q['target_floor'] != self.dungeon.floor + 1:
            return []
        return [p for p in q['points'] if p not in q['investigated_points']]

    def hunt_here(self):
        q = self.active_quest
        return bool(q and q['type'] == 'hunt' and [self.dungeon.x, self.dungeon.y] in self.visible_points())

    def investigate(self):
        q = self.active_quest
        point = [self.dungeon.x, self.dungeon.y]
        if not q or q['type'] == 'hunt' or point not in self.visible_points():
            return []
        q['investigated_points'].append(point)
        q['progress'] = len(q['investigated_points'])
        q['completed'] = q['progress'] == q['required_count']
        return [self.message(q['type'])] + ([self.message('objective')] if q['completed'] else [])

    def make_hunt_enemy(self):
        q = self.active_quest
        if not self.hunt_here():
            raise ValueError('討伐対象はいません。')
        profile = self.dungeon.settings['floors'][q['hunt_source_floor'] - 1]
        row = self.dungeon.enemies[q['hunt_enemy_id']]
        bonus = self.quest_data['hunt']
        return [Enemy(row['name'], max(1, round(row['max_hp'] * profile['hp_scale'] * bonus['hp_multiplier'])),
                      max(1, round(row['str'] * profile['power_scale']) + bonus['str_bonus']), row['agi'],
                      max(1, round(row['int'] * profile['power_scale'])), tuple(row['sprite']), row['magic_chance'],
                      defense=row.get('defense', 0) + bonus['def_bonus'],
                      magic_defense=row.get('magic_defense', 0), id=row['id'])]

    def hunt_victory(self):
        if not self.hunt_here():
            raise ValueError('討伐対象はいません。')
        self.surveyed = True
        return [self.message('hunt'), self.message('objective')]

    def return_to_camp(self, survived):
        if not survived:
            was_surveyed = bool(self.active and self.active['progress'])
            self.reset_progress()
            return [self.message('death')] if was_surveyed else []
        if not self.active or not self.surveyed:
            return []
        reward = self.active["reward"]
        self.session.treasure.banked += reward
        self.completed.add(self.active["id"])
        message = self.message('complete')
        self.active_quest = None
        return [message]

    def damage(self, amount):
        for actor in self.session.party:
            if actor.alive:
                actor.hp = max(1, actor.hp - amount)
        return [f"全員HP -{amount} (最低1)"]

    def heal(self, amount, everyone=True):
        living = [c for c in self.session.party if c.alive]
        if not everyone and living:
            living = [min(living, key=lambda c: c.hp / c.max_hp)]
        recovered = 0
        for c in living:
            gain = c.max_hp - c.hp if amount is None else min(amount, c.max_hp - c.hp)
            c.hp += gain
            recovered += gain
        return [f"{'全員' if everyone else living[0].name if living else '対象なし'} HP回復 合計{recovered}"]

    def chest_effect(self, reward):
        kind = reward["kind"]
        if kind == "TRAP":
            return ["宝箱の罠!"] + self.damage(reward["amount"])
        if kind == "SKILL_CHANCE":
            if self.session.rng.random() >= reward["chance"]:
                return ["古い技の記録……閃かなかった"]
            actor = self.session.rng.choice(self.session.party)
            messages = spark(actor, self.session.skills, self.session.settings, self.session.rng,
                             discovered=self.session.discovered_skills)
            actor.history.extend("宝箱: " + line for line in messages)
            self.session.field_pending = bool(self.session.pending_replacements)
            return messages
        return []
