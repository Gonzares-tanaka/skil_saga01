import unittest

from rpg.battle import Session
from rpg.content import load_content
from rpg.models import Action
from rpg.treasure import Treasure


class TreasureTests(unittest.TestCase):
    def setUp(self):
        self.s = Session(*load_content(), seed=7)
        self.c = self.s.party[0]
        self.s.treasure.banked = 20
        self.s.discovered_skills.update(("fire", "return"))

    def fill(self):
        for skill in self.s.skills.values():
            if skill.id not in ("fire", "return") and skill.id not in self.c.skills:
                self.c.learn(skill)
            if len(self.c.skills) == 6:
                break

    def test_bank_and_loss_are_idempotent(self):
        t = Treasure(5, 7)
        self.assertEqual(t.secure(), 5)
        self.assertEqual(t.secure(), 0)
        t.unbanked = 3
        self.assertEqual(t.lose(), 3)
        self.assertEqual(t.lose(), 0)
        self.assertEqual(t.banked, 12)

    def test_only_discovered_basic_common(self):
        for skill in self.s.skills.values():
            if skill.rarity not in ("BASIC", "COMMON"):
                self.s.discovered_skills.add(skill.id)
                with self.assertRaises(ValueError):
                    self.s.relearn(0, skill.id)
        self.s.discovered_skills.remove("fire")
        with self.assertRaises(ValueError):
            self.s.relearn(0, "fire")
        self.assertEqual(self.s.treasure.banked, 20)

    def test_partial_stock_and_no_owned_refill(self):
        self.s.relearn(0, "fire")
        skill = self.s.skills["fire"]
        self.assertEqual(self.c.skill_uses["fire"], skill.relearn_uses)
        self.assertEqual(self.s.treasure.banked, 20 - skill.relearn_cost)
        with self.assertRaises(ValueError):
            self.s.relearn(0, "fire")
        self.assertEqual(self.s.treasure.banked, 20 - skill.relearn_cost)

    def test_unbanked_cannot_pay(self):
        self.s.treasure.banked = 0
        self.s.treasure.unbanked = 999
        with self.assertRaises(ValueError):
            self.s.relearn(0, "fire")
        self.assertNotIn("fire", self.c.skills)

    def test_full_cancel_is_free(self):
        self.fill()
        before = dict(self.c.skill_uses)
        self.s.relearn(0, "fire")
        self.assertEqual(self.s.treasure.banked, 20)
        self.s.resolve_replacement(0)
        self.assertEqual(self.c.skill_uses, before)
        self.assertEqual(self.s.treasure.banked, 20)
        self.assertIsNone(self.s.pending_relearn)

    def test_full_commit_once_and_not_mastered(self):
        self.fill()
        old = self.c.skills[0]
        self.s.relearn(0, "fire")
        self.s.resolve_replacement(0, 0)
        self.assertEqual(len(self.c.skills), 6)
        self.assertEqual(self.c.skill_uses["fire"], self.s.skills["fire"].relearn_uses)
        self.assertNotIn(old, self.s.mastered_skills)
        with self.assertRaises(ValueError):
            self.s.resolve_replacement(0, 0)
        self.assertEqual(self.s.treasure.banked, 20 - self.s.skills["fire"].relearn_cost)

    def test_funds_rechecked_before_replacement(self):
        self.fill()
        before = dict(self.c.skill_uses)
        self.s.relearn(0, "fire")
        self.s.treasure.banked = 0
        with self.assertRaises(ValueError):
            self.s.resolve_replacement(0, 0)
        self.assertEqual(self.c.skill_uses, before)
        self.assertEqual(self.c.pending_skill, "fire")
        self.s.resolve_replacement(0)

    def test_paid_support_cannot_replace_last_attack(self):
        for skill in self.s.skills.values():
            if skill.effect not in ("damage", "drain", "return"):
                self.c.learn(skill)
            if len(self.c.skills) == 6:
                break
        self.assertEqual(len(self.c.skills), 6)
        before = dict(self.c.skill_uses)
        self.s.relearn(0, "return")
        with self.assertRaises(ValueError):
            self.s.resolve_replacement(0, 0)
        self.assertEqual(before, self.c.skill_uses)
        self.assertEqual(self.s.treasure.banked, 20)
        self.s.resolve_replacement(0, 1)
        self.assertEqual(self.c.skill_uses["return"], 1)

    def test_basic_relearn_preserves_growth_and_archive(self):
        sid = self.c.skills[0]
        self.c.forget(sid)
        before = (self.c.max_hp, self.c.strength, self.c.agility, self.c.intellect)
        self.s.relearn(0, sid)
        self.assertEqual(self.c.skill_uses[sid], self.s.skills[sid].relearn_uses)
        self.assertEqual(before, (self.c.max_hp, self.c.strength, self.c.agility, self.c.intellect))
        self.assertNotIn(sid, self.s.mastered_skills)

    def test_return_last_use_disappears_and_masters(self):
        self.s.relearn(0, "return")
        self.assertEqual(self.c.skill_uses["return"], 1)
        self.s.field_return(0)
        self.assertNotIn("return", self.c.skills)
        self.assertIn("return", self.s.mastered_skills)
        self.s.relearn(1, "return")
        self.assertEqual(self.s.party[1].skill_uses["return"], 1)

    def test_return_rejects_dead_or_missing_caster(self):
        with self.assertRaises(ValueError):
            self.s.field_return(0)
        self.c.learn(self.s.skills["return"])
        self.c.hp = 0
        with self.assertRaises(ValueError):
            self.s.field_return(0)
        self.assertEqual(self.c.skill_uses["return"], 3)

    def test_return_forbidden_in_battle_without_consumption(self):
        self.c.learn(self.s.skills["return"])
        battle = self.s.next_battle()
        with self.assertRaises(ValueError):
            self.s.field_return(0)
        actions = [Action(i, "DEFEND") for i in range(4)]
        actions[0] = Action(0, "SKILL", 0, "return")
        with self.assertRaises(ValueError):
            battle.begin_round(actions)
        self.assertFalse(battle.queue)
        self.assertEqual(self.c.skill_uses["return"], 3)

    def test_defeat_loses_only_unbanked_once(self):
        self.s.treasure.unbanked = 7
        battle = self.s.next_battle()
        before = [(c.strength, c.agility, c.intellect, dict(c.skill_uses)) for c in self.s.party]
        archive = set(self.s.discovered_skills)
        for c in self.s.party:
            c.hp = 0
        battle.outcome = "DEFEAT"
        self.s.settle()
        self.s.settle()
        self.assertEqual((self.s.treasure.unbanked, self.s.treasure.banked), (0, 20))
        self.assertEqual(self.s.completed, 1)
        self.assertEqual(before, [(c.strength, c.agility, c.intellect, dict(c.skill_uses)) for c in self.s.party])
        self.assertEqual(archive, self.s.discovered_skills)
