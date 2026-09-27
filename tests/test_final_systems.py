import random
import unittest

from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.growth import growth_bonus
from rpg.exploration import Exploration
from rpg.items import Inventory
from rpg.models import Action, Enemy


class FinalSystemsTests(unittest.TestCase):
    def setUp(self):
        self.settings, self.skills, self.party, self.enemy_data = load_content()
        self.inventory = Inventory()
        self.enemy = Enemy("DUMMY", 999, 1, 1, 1, (0, 16))

    def battle(self, boss=False):
        return Battle(self.party, [self.enemy], self.skills, rng=random.Random(1),
                      inventory=self.inventory, boss=boss)

    def resolve(self, battle, actions):
        battle.begin_round(actions)
        while battle.queue:
            battle.step()

    def test_revive_is_only_for_ko_and_uses_finite_skill(self):
        actor = self.party[0]
        actor.learn(self.skills["revive"])
        self.party[1].hp = 0
        battle = self.battle()
        with self.assertRaises(ValueError):
            battle.begin_round([Action(0, "SKILL", 0, "revive"), Action(2), Action(3)])
        self.resolve(battle, [Action(0, "SKILL", 1, "revive"), Action(2), Action(3)])
        self.assertEqual(self.party[1].hp, max(1, self.party[1].max_hp // 4))
        self.assertEqual(actor.skill_uses["revive"], 2)
        self.assertEqual(actor.category_uses["healing"], 1)

    def test_revive_exhaustion_marks_mastered_without_power_bonus(self):
        actor = self.party[0]
        actor.learn(self.skills["revive"])
        battle = self.battle()
        for _ in range(3):
            self.party[1].hp = 0
            self.resolve(battle, [Action(0, "SKILL", 1, "revive"), Action(2), Action(3)])
        self.assertNotIn("revive", actor.skills)
        self.assertIn("revive", battle.discovered_skills)
        self.assertIn("revive", battle.mastered_skills)
        self.assertEqual(self.skills["revive"].mastery_label, "習熟記録")

    def test_items_cap_purchase_and_target_rules(self):
        session = Session(self.settings, self.skills, self.party, self.enemy_data)
        stock = session.inventory
        self.assertEqual(stock.counts["POTION"], 2)
        self.assertFalse(stock.use("PHOENIX ASH", self.party[0])[0])
        session.treasure.banked = 4
        self.assertTrue(stock.buy("PHOENIX ASH", session.treasure)[0])
        self.assertEqual(session.treasure.banked, 0)
        self.party[1].hp = 0
        self.inventory = stock
        battle = self.battle()
        with self.assertRaises(ValueError):
            battle.begin_round([Action(0, "ITEM", 0, item_id="PHOENIX ASH"), Action(2), Action(3)])
        self.resolve(battle, [Action(0, "ITEM", 1, item_id="PHOENIX ASH"), Action(2), Action(3)])
        self.assertTrue(self.party[1].alive)
        self.assertEqual(stock.counts["PHOENIX ASH"], 0)
        stock.counts["POTION"] = 9
        self.assertFalse(stock.add("POTION"))
        self.assertEqual(stock.counts["POTION"], 9)

    def test_run_failure_risks_damage_success_has_no_growth(self):
        session = Session(self.settings, self.skills, self.party, self.enemy_data)
        battle = session.next_battle([Enemy("DUMMY", 999, 10, 1, 1, (0, 16))], recover=False)
        battle.run_override = False
        self.assertIn("失敗", battle.attempt_run()[0])
        self.assertTrue(battle.queue)
        before = sum(c.hp for c in self.party)
        while battle.queue:
            battle.step()
        self.assertLess(sum(c.hp for c in self.party), before)
        battle.run_override = True
        self.assertIn("成功", battle.attempt_run()[0])
        self.assertEqual(battle.outcome, "ESCAPE")
        stats = [(c.max_hp, c.strength, c.agility, c.intellect) for c in self.party]
        session.settle()
        self.assertEqual(stats, [(c.max_hp, c.strength, c.agility, c.intellect) for c in self.party])
        self.assertEqual(session.wins, 0)

    def test_boss_cannot_run(self):
        battle = self.battle(boss=True)
        self.assertIn("CANNOT", battle.attempt_run()[0])
        self.assertIsNone(battle.outcome)
        self.assertFalse(battle.queue)

    def test_category_bonus_caps_after_three_uses(self):
        actor = self.party[0]
        actor.category_uses["magic"] = 3
        at_cap = growth_bonus(actor, "INT", self.settings)
        actor.category_uses["magic"] = 20
        self.assertEqual(growth_bonus(actor, "INT", self.settings), at_cap)
        self.assertGreater(at_cap, 0)

    def test_spring_only_heals_living_and_keeps_resources(self):
        session = Session(self.settings, self.skills, self.party, self.enemy_data)
        self.party[0].hp = 1
        self.party[1].hp = 0
        self.party[0].skill_uses[self.party[0].skills[0]] -= 2
        remaining = dict(self.party[0].skill_uses)
        stock = dict(session.inventory.counts)
        Exploration(session, None).heal(None)
        self.assertEqual(self.party[0].hp, self.party[0].max_hp)
        self.assertEqual(self.party[1].hp, 0)
        self.assertEqual(self.party[0].skill_uses, remaining)
        self.assertEqual(session.inventory.counts, stock)


if __name__ == "__main__":
    unittest.main()
