"""Small field rewards and one active survey quest; no new inventory system."""
import json
from .content import ROOT
from .growth import spark
from .tiles import FLOOR_TILES, TILE_QUEST


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
        self.quest_data = json.loads((ROOT / "data/quests.json").read_text(encoding="utf-8-sig"))
        self.active = None
        self.target = None
        self.surveyed = False
        self.completed = set()
        self.springs = set()

    def unlocked(self, quest):
        return quest["gate"] is None or quest["gate"] - 1 in self.dungeon.defeated_bosses

    def accept(self, quest_id, debug=False):
        quest = next(q for q in self.quest_data["quests"] if q["id"] == quest_id)
        if self.active or quest_id in self.completed:
            raise ValueError("受注中・達成済みのクエストです")
        if not self.unlocked(quest) and not debug:
            raise ValueError("先のエリアのボス撃破が必要です")
        candidates = {}
        for floor in range(quest["floors"][0] - 1, quest["floors"][1]):
            reachable = self.dungeon.reachable(floor)
            marked = sorted(p for p in reachable if self.dungeon.tile(floor, *p) == TILE_QUEST)
            points = marked or sorted(p for p in reachable
                                      if self.dungeon.tile(floor, *p) in FLOOR_TILES)
            if points:
                candidates[floor] = points
        if not candidates:
            raise ValueError("調査地点に使える到達可能な床がありません")
        floor = self.session.rng.choice(list(candidates))
        self.target = (floor, *self.session.rng.choice(candidates[floor]))
        self.active, self.surveyed = quest, False
        return quest["name"] + "を受注。気配を頼りに調査しよう。"

    def hint(self):
        return self.quest_data["hint"] if self.active and not self.surveyed and self.target[0] == self.dungeon.floor else ""

    def investigate(self):
        if not self.active or self.surveyed or self.target != (self.dungeon.floor, self.dungeon.x, self.dungeon.y):
            return []
        self.surveyed = True
        return [self.active["dialogue"], self.quest_data["objective"]]

    def return_to_camp(self, survived):
        if not survived:
            was_surveyed = self.surveyed
            self.surveyed = False
            return [self.quest_data["death"]] if was_surveyed else []
        if not self.active or not self.surveyed:
            return []
        reward = self.active["reward"]
        self.session.treasure.banked += reward
        self.completed.add(self.active["id"])
        self.active, self.target, self.surveyed = None, None, False
        return [self.quest_data["complete"].format(reward=reward)]

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
