import random
import unittest

from rpg.battle import Session
from rpg.content import load_content
from rpg.growth import growth_bonus, grow_and_spark
from rpg.models import Action, Enemy
from rpg.skill_resources import ensure_attack


class FiniteSkillTests(unittest.TestCase):
    def setUp(self):
        self.s = Session(*load_content(), seed=8)
        self.c = self.s.party[0]

    def begin(self):
        return self.s.next_battle([Enemy("試験", 999, 1, 1, 1, (0, 0))], recover=False)

    def give(self, actor, ids):
        for sid in list(actor.skills):
            actor.forget(sid)
        for sid in ids:
            actor.learn(self.s.skills[sid])

    def turn(self, battle, sid):
        actions = [Action(i, "DEFEND") for i, c in enumerate(self.s.party) if c.alive]
        actions[0] = Action(0, "SKILL", 0, sid)
        battle.begin_round(actions)
        lines = []
        while battle.queue:
            lines.extend(battle.step())
        return lines

    def test_attack_rejected_and_initial_skills_are_personal(self):
        self.assertEqual(self.s.skills["punch"].name, "パンチ")
        b = self.begin()
        with self.assertRaises(ValueError):
            b.begin_round([Action(i, "ATTACK") for i in range(4)])
        self.turn(b, "punch")
        self.assertEqual(self.c.skill_uses["punch"], 29)
        self.assertEqual(self.s.party[3].skill_uses["punch"], 30)

    def test_last_use_removed_and_no_growth_information_lost(self):
        self.c.learn(self.s.skills["meteor"])
        self.c.skill_uses["meteor"] = 1
        b = self.begin()
        lines = self.turn(b, "meteor")
        self.assertNotIn("meteor", self.c.skills)
        self.assertNotIn("meteor", self.c.skill_uses)
        self.assertNotIn("meteor", self.c.cooldowns)
        self.assertEqual(self.c.growth_points["INT"], 5)
        self.assertEqual(self.c.used_skills["meteor"], 1)
        self.assertTrue(any("消滅" in line for line in lines))
        self.assertTrue(any("消滅" in line for line in b.resource_events))
        self.assertIn("meteor", self.s.discovered_skills)
        self.assertIn("meteor", self.s.mastered_skills)
        self.assertTrue(any("MASTERED" in line for line in lines))
        with self.assertRaises(ValueError):
            self.turn(b, "meteor")
        self.c.learn(self.s.skills["meteor"])
        self.assertIn("meteor", self.s.mastered_skills)

    def test_zero_rejected_without_spending_or_training(self):
        b = self.begin()
        self.c.learn(self.s.skills["fire"])
        self.c.skill_uses["fire"] = 0
        with self.assertRaises(ValueError):
            self.turn(b, "fire")
        b._party_action(Action(0, "SKILL", 0, "fire"))
        self.assertEqual(self.c.skill_uses["fire"], 0)
        self.assertFalse(self.c.used_skills)

    def test_dead_and_cancelled_actions_do_not_consume(self):
        b = self.begin()
        self.c.hp = 0
        b._party_action(Action(0, "SKILL", 0, "punch"))
        self.assertEqual(self.c.skill_uses["punch"], 30)
        self.assertFalse(self.c.growth_points)
        self.c.hp = 20
        b.enemies[0].hp = 0
        b._party_action(Action(0, "SKILL", 0, "punch"))
        self.assertEqual(self.c.skill_uses["punch"], 30)

    def test_recover_and_new_battle_keep_remaining_uses(self):
        self.c.skill_uses["punch"] = 32
        self.c.hp = 1
        self.c.recover()
        self.assertEqual((self.c.hp, self.c.skill_uses["punch"]), (48, 32))
        b = self.begin()
        self.turn(b, "punch")
        b.outcome = "DEFEAT"
        self.s.settle()
        self.s.next_battle()
        self.assertEqual(self.c.skill_uses["punch"], 31)

    def test_heal_is_consumed_and_exhausted(self):
        self.c.learn(self.s.skills["heal"])
        self.c.skill_uses["heal"] = 1
        self.c.hp = 10
        b = self.begin()
        self.turn(b, "heal")
        self.assertGreater(self.c.hp, 10)
        self.assertNotIn("heal", self.c.skills)
        self.assertEqual(self.c.growth_points["HP"], .5)

    def test_multiple_hits_and_counter_each_consume_one(self):
        b = self.begin()
        for sid in ("seven_slash", "counter"):
            self.c.learn(self.s.skills[sid])
            before = self.c.skill_uses[sid]
            self.turn(b, sid)
            self.assertEqual(self.c.skill_uses[sid], before - 1)

    def test_growth_counts_actual_uses_and_has_cap(self):
        b = self.begin()
        self.turn(b, "punch")
        one = growth_bonus(self.c, "STR", self.s.settings)
        self.turn(b, "punch")
        self.assertGreater(growth_bonus(self.c, "STR", self.s.settings), one)
        self.assertEqual(growth_bonus(self.c, "INT", self.s.settings), 0)
        self.c.growth_points["INT"] = 999
        self.assertEqual(growth_bonus(self.c, "INT", self.s.settings), .35)
        b.outcome = "DRAW"
        self.s.settle()
        self.s.next_battle()
        self.assertEqual(self.c.growth_points, {})

    def test_meteor_changes_power_type_growth_at_fixed_roll(self):
        class Fixed(random.Random):
            def random(self):
                return .25
        self.s.settings["spark_chance"] = 0
        b = self.begin()
        before = self.c.intellect
        self.c.learn(self.s.skills["meteor"])
        self.turn(b, "meteor")
        grow_and_spark(self.c, self.s.skills, self.s.settings, Fixed(1), 1)
        self.assertEqual(self.c.intellect, before + 1)
        other = self.s.party[3]
        before = other.intellect
        grow_and_spark(other, self.s.skills, self.s.settings, Fixed(1), 1)
        self.assertEqual(other.intellect, before)

    def test_entire_party_exhaustion_has_finite_fallback(self):
        for c in self.s.party:
            c.skill_uses[c.skills[0]] = 1
        b = self.begin()
        b.begin_round(b.auto_actions())
        while b.queue:
            b.step()
        for c in self.s.party:
            self.assertEqual(c.skills, ["punch"])
            self.assertEqual(c.skill_uses, {"punch": 30})
        b.begin_round(b.auto_actions())
        while b.queue:
            b.step()
        self.assertTrue(all(c.skill_uses['punch'] == 29 for c in self.s.party))

    def test_full_support_loadout_still_respects_slot_limit(self):
        self.give(self.c, ["heal", "renew", "first_aid", "full_heal", "counter", "berserk"])
        messages = ensure_attack(self.c, self.s.skills, 6)
        self.assertEqual(len(self.c.skills), 6)
        self.assertIn("punch", self.c.skills)
        self.assertNotIn("berserk", self.c.skills)
        self.assertTrue(any("放棄" in line for line in messages))

    def test_debug_gates_refills_and_full_slot_choices(self):
        with self.assertRaises(ValueError):
            self.s.debug_skills("restore")
        self.s.debug = True
        self.s.debug_skills("one")
        self.assertTrue(all(set(c.skill_uses.values()) == {1} for c in self.s.party))
        self.s.debug_skills("restore")
        self.assertEqual(self.c.skill_uses["punch"], 30)
        self.s.debug_skills("fill", 2)
        c = self.s.party[2]
        self.assertEqual(len(c.skills), 6)
        # Keep a LEGEND candidate available for a deterministic menu test.
        if all(sid in c.skills for sid in ("meteor", "seven_slash", "full_heal")):
            c.forget("meteor")
            c.learn(self.s.skills["punch"])
        before = dict(c.skill_uses)
        self.s.debug_skills("legend", 2)
        pending = c.pending_skill
        self.assertEqual(self.s.skills[pending].rarity, "LEGEND")
        old = c.skills[5]
        self.s.resolve_replacement(2, 5)
        self.assertIn("DEBUG", c.history[-1])
        self.assertNotIn(old, c.skill_uses)
        self.assertEqual(c.skill_uses[pending], self.s.skills[pending].max_uses)
        for sid in c.skills:
            if sid in before:
                self.assertEqual(c.skill_uses[sid], before[sid])
        before = dict(c.skill_uses)
        self.s.debug_skills("random", 2)
        self.s.resolve_replacement(2)
        self.assertEqual(c.skill_uses, before)

    def test_debug_spark_with_room_is_full_and_battle_mutation_blocked(self):
        self.s.debug = True
        self.s.debug_skills("rare", 0)
        new = self.c.skills[-1]
        self.assertIn(self.s.skills[new].rarity, ("RARE", "LEGEND"))
        self.assertEqual(self.c.skill_uses[new], self.s.skills[new].max_uses)
        self.begin()
        with self.assertRaises(ValueError):
            self.s.debug_skills("one")

    def test_exploration_healing_uses_same_stock_and_disappears(self):
        self.c.learn(self.s.skills["heal"])
        self.c.skill_uses["heal"] = 1
        used, _ = self.s.field_heal(0, "heal", 0)
        self.assertFalse(used)
        self.assertEqual(self.c.skill_uses["heal"], 1)
        self.s.party[1].hp = 0
        self.assertFalse(self.s.field_heal(0, "heal", 1)[0])
        self.c.hp = 10
        self.assertTrue(self.s.field_heal(0, "heal", 0)[0])
        self.assertEqual(self.c.hp, 15)
        self.assertNotIn("heal", self.c.skills)
        self.assertIn("heal", self.s.mastered_skills)
        self.assertFalse(self.c.growth_points)
        self.assertFalse(self.s.field_heal(0, "heal", 0)[0])
        self.assertEqual(self.c.hp, 15)

    def test_field_heal_blocked_in_battle_and_dead_caster(self):
        self.c.learn(self.s.skills["heal"])
        self.c.hp = 0
        self.s.party[1].hp = 1
        self.assertFalse(self.s.field_heal(0, "heal", 1)[0])
        self.assertEqual(self.c.skill_uses["heal"], 6)
        self.c.recover()
        self.begin()
        with self.assertRaises(ValueError):
            self.s.field_heal(0, "heal", 1)

    def test_archive_starts_with_initial_skills_and_dynamic_totals(self):
        self.assertEqual(self.s.discovered_skills, {"punch", "quick_hit", "spark"})
        self.assertEqual(self.s.mastered_skills, set())
        summary = self.s.archive_summary()
        self.assertEqual(summary["total"], len(self.s.skills))
        self.assertEqual(summary["discovered"], 3)
        self.assertEqual(summary["mastered"], 0)
        self.assertEqual(sum(row["total"] for row in summary["rarities"].values()),
                         len(self.s.skills))

    def test_declined_or_replaced_skill_is_discovered_but_not_mastered(self):
        self.s.debug = True
        self.s.debug_skills("fill", 0)
        candidate = next(sid for sid in self.s.skills if sid not in self.c.skills)
        old = self.c.skills[0]
        self.s.debug_acquire(candidate, 0)
        self.assertIn(candidate, self.s.discovered_skills)
        self.assertNotIn(candidate, self.s.mastered_skills)
        self.s.resolve_replacement(0, None)
        self.assertNotIn(candidate, self.c.skills)
        self.assertNotIn(candidate, self.s.mastered_skills)
        candidate = next(sid for sid in self.s.skills if sid not in self.c.skills)
        self.s.debug_acquire(candidate, 0)
        self.s.resolve_replacement(0, 0)
        self.assertNotIn(old, self.s.mastered_skills)

    def test_debug_exact_acquire_and_one_do_not_master(self):
        self.s.debug = True
        self.s.debug_acquire("meteor", 0)
        self.assertIn("meteor", self.c.skills)
        self.assertIn("meteor", self.s.discovered_skills)
        self.s.debug_set_one("meteor", 0)
        self.assertEqual(self.c.skill_uses["meteor"], 1)
        self.assertNotIn("meteor", self.s.mastered_skills)


if __name__ == "__main__":
    unittest.main()
