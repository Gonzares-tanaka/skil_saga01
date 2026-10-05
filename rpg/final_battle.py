"""Final-event data and a session-only snapshot; no ordinary save system."""
from copy import deepcopy
from dataclasses import dataclass
import json

from .content import ROOT
from .models import Enemy

LORD_OF_ELYSION_ID = "lord_of_elysion"
AMRITA_ITEM_ID = "AMRITA"


def load_final_battle_data():
    data = json.loads((ROOT / "data/final_battle.json").read_text(encoding="utf-8-sig"))
    def lines(value):
        return (isinstance(value, list) and bool(value) and
                all(isinstance(line, str) for line in value) and any(line.strip() for line in value))
    if not isinstance(data, dict):
        raise ValueError("final_battle.json: オブジェクト形式が必要です。")
    for key in ("offer_question", "battle_start", "barrier_hint", "amrita_release",
                "amrita_unavailable", "retry_question", "defeat", "victory", "ending_lines"):
        if not lines(data.get(key)):
            raise ValueError("final_battle.json: 文章の配列が必要です: " + key)
    pages = data.get("story_pages")
    if not isinstance(pages, list) or not pages or not all(lines(page) for page in pages):
        raise ValueError("final_battle.json: story_pagesは文章ページの配列です。")
    return data


def make_final_enemy(enemy_data):
    row = next((row for row in enemy_data if row["id"] == LORD_OF_ELYSION_ID), None)
    if row is None or not row.get("boss"):
        raise ValueError("enemies.json: lord_of_elysionのボスデータが必要です。")
    return Enemy(row["name"], row["max_hp"], row["str"], row["agi"], row["int"],
                 tuple(row["sprite"]), row["magic_chance"],
                 defense=row.get("defense", 0), magic_defense=row.get("magic_defense", 0),
                 id=LORD_OF_ELYSION_ID)


@dataclass(frozen=True)
class FinalBattleCheckpoint:
    """Restore copies of an unchanged pre-battle snapshot on every attempt.

    Durable field lists are explicit to make a later save-data mapping simple.
    Pyxel maps/art/audio and loaded rules are never copied or rewritten.
    """
    session_state: dict
    dungeon_state: dict
    exploration_state: dict
    finale_state: dict
    rng_state: tuple

    SESSION_FIELDS = ("party", "inventory", "treasure", "discovered_skills", "mastered_skills",
                      "completed", "wins", "losses", "draws", "debug", "debug_pending",
                      "field_pending", "pending_relearn")
    DUNGEON_FIELDS = ("floor", "x", "y", "steps", "grace", "opened", "activated_switches",
                      "chest_loot", "last_reward", "defeated_bosses")
    EXPLORATION_FIELDS = ("active", "target", "surveyed", "completed", "springs")

    @classmethod
    def capture(cls, session, dungeon, exploration):
        if not dungeon.finale.has_amrita or session.pending_replacements:
            raise ValueError("アムリタを保持し、技の入替を終えてから決戦へ進んでください。")
        if not any(actor.alive for actor in session.party):
            raise ValueError("決戦には生存する味方が必要です。")
        return cls(deepcopy({k: getattr(session, k) for k in cls.SESSION_FIELDS}),
                   deepcopy({k: getattr(dungeon, k) for k in cls.DUNGEON_FIELDS}),
                   deepcopy({k: getattr(exploration, k) for k in cls.EXPLORATION_FIELDS}),
                   dungeon.finale.snapshot(), session.rng.getstate())

    def restore(self, session, dungeon, exploration):
        for obj, state in ((session, self.session_state), (dungeon, self.dungeon_state),
                           (exploration, self.exploration_state)):
            for key, value in deepcopy(state).items():
                setattr(obj, key, value)
        dungeon.finale.restore(self.finale_state)
        session.rng.setstate(self.rng_state)
        session.battle, session.results, session.settled = None, [], True
        # Reconnect shared objects, including the party-wide mastery set.
        for actor in session.party:
            actor.mastered_skills = session.mastered_skills
        dungeon.inventory, dungeon.treasure, dungeon.rng = session.inventory, session.treasure, session.rng
        exploration.session, exploration.dungeon = session, dungeon
