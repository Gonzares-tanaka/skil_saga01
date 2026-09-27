"""GUARD consumes one turn, protects only its user and never changes rewards."""
import random
import unittest
from unittest.mock import patch

from rpg.battle import Battle, GUARD_DAMAGE_MULTIPLIER
from rpg.content import load_content
from rpg.models import Action, Enemy


class GuardTests(unittest.TestCase):
    def setUp(self):
        _, self.skills, self.party, _ = load_content()

    def battle(self, *, hp=500, strength=20, boss=False):
        enemy = Enemy("DUMMY", hp, strength, 100, 1, (0, 16))
        enemy.magic_chance = 0
        return Battle(self.party, [enemy], self.skills, rng=random.Random(2), boss=boss)

    def resolve(self, battle, actions):
        battle.begin_round(actions)
        messages = []
        while battle.queue:
            messages.extend(battle.step())
        return messages

    def guards(self):
        return [Action(i, "GUARD") for i, actor in enumerate(self.party) if actor.alive]

    def test_damage_multiplier_minimum_and_self_only(self):
        self.assertEqual(GUARD_DAMAGE_MULTIPLIER, 0.5)
        battle = self.battle()
        actor = self.party[0]
        actor.guarding = True
        self.assertEqual(battle._damage(actor, 20), 10)
        self.assertEqual(battle._damage(self.party[1], 20), 20)
        self.assertEqual(battle._damage(actor, 1), 1)
        with patch("rpg.battle.GUARD_DAMAGE_MULTIPLIER", 0.25):
            self.assertEqual(battle._damage(actor, 20), 5)
            actor.counter = object()
            self.assertEqual(battle._damage(actor, 20), 10)

    def test_one_guard_three_skills_and_no_guard_resources(self):
        battle = self.battle()
        actor = self.party[0]
        skill_id = actor.skills[0]
        before = (dict(actor.skill_uses), dict(actor.category_uses),
                  dict(actor.growth_points), dict(battle.inventory.counts))
        actions = [Action(0, "GUARD")] + [
            Action(i, "SKILL", 0, self.party[i].skills[0]) for i in range(1, 4)
        ]
        battle.begin_round(actions)
        self.assertEqual(battle.queue[0][1].kind, "GUARD")
        self.assertIn("まもる", " ".join(battle.step()))
        self.assertTrue(actor.guarding)
        self.assertEqual((actor.skill_uses, actor.category_uses, actor.growth_points,
                          battle.inventory.counts), before)
        while battle.queue:
            battle.step()
        self.assertFalse(actor.guarding)
        self.assertEqual(actor.skill_uses[skill_id], before[0][skill_id])
        self.assertEqual(actor.category_uses, before[1])
        self.assertEqual(actor.growth_points, before[2])

    def test_all_guard_returns_to_next_round(self):
        battle = self.battle(strength=1)
        self.resolve(battle, self.guards())
        self.assertIsNone(battle.outcome)
        self.assertFalse(any(actor.guarding for actor in self.party))
        self.resolve(battle, self.guards())
        self.assertEqual(battle.round, 2)

    def test_guard_then_run_and_item(self):
        battle = self.battle(strength=1)
        self.resolve(battle, self.guards())
        battle.run_override = True
        battle.attempt_run()
        self.assertEqual(battle.outcome, "ESCAPE")
        self.assertFalse(any(actor.guarding for actor in self.party))

        battle = self.battle(strength=1)
        self.resolve(battle, self.guards())
        self.party[0].hp = max(1, self.party[0].hp - 5)
        before = battle.inventory.counts["POTION"]
        actions = self.guards()
        actions[0] = Action(0, "ITEM", 0, item_id="POTION")
        self.resolve(battle, actions)
        self.assertEqual(battle.inventory.counts["POTION"], before - 1)

    def test_guard_then_victory_clears_state(self):
        battle = self.battle(hp=1, strength=1)
        actions = self.guards()
        actions[1] = Action(1, "SKILL", 0, self.party[1].skills[0])
        self.resolve(battle, actions)
        self.assertEqual(battle.outcome, "VICTORY")
        self.assertFalse(any(actor.guarding for actor in self.party))

    def test_boss_guard_allowed_but_run_blocked(self):
        battle = self.battle(strength=1, boss=True)
        self.resolve(battle, self.guards())
        self.assertIsNone(battle.outcome)
        self.assertIn("CANNOT ESCAPE", battle.attempt_run()[0])

    def test_defeat_clears_guard(self):
        for actor in self.party[:-1]:
            actor.hp = 0
        self.party[-1].hp = 1
        battle = self.battle(strength=100)
        self.resolve(battle, self.guards())
        self.assertEqual(battle.outcome, "DEFEAT")
        self.assertFalse(any(actor.guarding for actor in self.party))

    def test_ko_cannot_submit_guard(self):
        self.party[0].hp = 0
        battle = self.battle()
        with self.assertRaises(ValueError):
            battle.begin_round([Action(i, "GUARD") for i in range(4)])
        battle.begin_round(self.guards())
        self.assertNotIn(0, [action.actor for side, action in battle.queue if side == "party"])


if __name__ == "__main__":
    unittest.main()
