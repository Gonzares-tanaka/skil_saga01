import random
import unittest

from main import simulate
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.growth import grow_and_spark
from rpg.models import Action, Enemy


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.settings, self.skills, self.party, self.enemies = load_content()

    def give(self, actor, ids):
        for sid in list(actor.skills):
            actor.forget(sid)
        for sid in ids:
            actor.learn(self.skills[sid])

    def enemy(self, hp=500, strength=1, agility=1):
        return Enemy("DUMMY", hp, strength, agility, 1, (0, 16))

    def battle(self, enemies=None, rounds=60):
        return Battle(self.party, enemies or [self.enemy()], self.skills, rounds, random.Random(1))

    def resolve(self, battle, actions):
        battle.begin_round(actions)
        lines = []
        while battle.queue:
            lines.extend(battle.step())
        return lines

    def defend(self):
        return [Action(i, "DEFEND") for i, c in enumerate(self.party) if c.alive]

    def use(self, battle, skill_id, target=0):
        actor = self.party[0]
        if skill_id not in actor.skills:
            actor.learn(self.skills[skill_id])
        actions = self.defend()
        actions[0] = Action(0, "SKILL", target, skill_id)
        return self.resolve(battle, actions)

    def test_no_level_or_experience_and_basic_skills(self):
        self.assertEqual(len(self.skills), 30)
        for c in self.party:
            self.assertTrue(c.skills)
            self.assertGreaterEqual(c.skill_uses[c.skills[0]], 25)
            self.assertFalse(hasattr(c, "level") or hasattr(c, "experience"))

    def test_dead_actor_skipped_and_no_negative_hp(self):
        self.party[0].hp = 0
        b = self.battle([self.enemy(hp=1)])
        lines = self.resolve(b, b.auto_actions())
        self.assertFalse(any(f"{self.party[0].name} の攻撃" in line for line in lines))
        self.assertEqual(b.enemies[0].hp, 0)
        self.assertEqual(b.outcome, "VICTORY")

    def test_lethal_hit_cancels_queued_action(self):
        for c in self.party:
            c.hp = 0
        self.party[0].hp = 1
        b = self.battle([self.enemy(strength=100, agility=100)])
        lines = self.resolve(b, [Action(0, "SKILL", 0, self.party[0].skills[0])])
        self.assertEqual(b.outcome, "DEFEAT")
        self.assertFalse(any(f"{self.party[0].name} の攻撃" in line for line in lines))

    def test_dead_target_retargeted(self):
        b = self.battle([self.enemy(hp=1), self.enemy(hp=1)])
        self.resolve(b, [Action(i, "SKILL", 0, self.party[i].skills[0]) for i in range(4)])
        self.assertEqual(b.outcome, "VICTORY")

    def test_defend_works_before_fast_enemy(self):
        for c in self.party[1:]:
            c.hp = 0
        b = self.battle([self.enemy(strength=20, agility=100)])
        before = self.party[0].hp
        self.resolve(b, [Action(0, "DEFEND")])
        self.assertLessEqual(before - self.party[0].hp, 11)

    def test_counter_physical_only(self):
        for c in self.party[1:]:
            c.hp = 0
        b = self.battle([self.enemy(agility=100)])
        self.use(b, "counter")
        self.assertLess(b.enemies[0].hp, 500)
        self.party[0].cooldowns.clear()
        b.enemies[0].magic_chance = 1
        before = b.enemies[0].hp
        self.use(b, "counter")
        self.assertEqual(b.enemies[0].hp, before)

    def test_heal_clamps_and_does_not_revive(self):
        self.party[1].hp = 0
        self.party[2].hp = 35
        b = self.battle()
        self.use(b, "heal", 2)
        self.assertLessEqual(self.party[2].hp, self.party[2].max_hp)
        self.assertEqual(self.party[1].hp, 0)

    def test_drain_uses_actual_damage(self):
        self.party[0].hp = 10
        b = self.battle([self.enemy(hp=2)])
        self.use(b, "drain")
        self.assertEqual(self.party[0].hp, 11)

    def test_legend_scales_with_stats_not_rarity_bonus(self):
        actor = self.party[0]
        self.assertEqual(self.skills["meteor"].power(actor), 14)
        actor.intellect = 20
        self.assertEqual(self.skills["meteor"].power(actor), 140)
        actor.strength = 20
        self.assertEqual(self.skills["seven_slash"].power(actor), 77)

    def test_cooldown_blocks_exact_number_of_rounds(self):
        b = self.battle()
        self.use(b, "meteor")
        self.assertEqual(self.party[0].cooldowns["meteor"], 4)
        with self.assertRaises(ValueError):
            b.begin_round([Action(0, "SKILL", 0, "meteor")] + self.defend()[1:])
        for _ in range(4):
            self.resolve(b, self.defend())
        self.assertNotIn("meteor", self.party[0].cooldowns)
        self.use(b, "meteor")

    def test_berserk_expires(self):
        b = self.battle()
        self.use(b, "berserk")
        self.assertEqual(self.party[0].berserk, 3)
        self.assertEqual(self.skills["power_strike"].power(self.party[0]), 24)
        for _ in range(3):
            self.resolve(b, self.defend())
        self.assertEqual(self.party[0].berserk, 0)

    def test_draw_prevents_endless_defending(self):
        b = self.battle(rounds=3)
        for _ in range(3):
            self.resolve(b, self.defend())
        self.assertEqual(b.outcome, "DRAW")

    def test_every_effect_executes(self):
        for skill_id in self.skills:
            with self.subTest(skill=skill_id):
                self.setUp()
                b = self.battle()
                if skill_id == 'return':
                    with self.assertRaises(ValueError):
                        self.use(b, skill_id)
                    continue
                self.use(b, skill_id)
                self.assertTrue(all(0 <= c.hp <= c.max_hp for c in self.party))

    def test_legend_can_spark_at_first_win_on_power_type(self):
        class LegendRng(random.Random):
            def random(self):
                return 0
            def choices(self, population, weights=None, **kwargs):
                return ["LEGEND"]
            def choice(self, population):
                return next(s for s in population if s.id == "meteor")
        c = self.party[0]
        grow_and_spark(c, self.skills, self.settings, LegendRng(), 1)
        self.assertIn("meteor", c.skills)

    def test_skill_slots_full_waits_for_choice(self):
        c = self.party[0]
        self.give(c, list(self.skills)[:6])
        before = list(c.skills)
        self.settings["spark_chance"] = 1
        lines = grow_and_spark(c, self.skills, self.settings, random.Random(2), 1)
        self.assertEqual(c.skills, before)
        self.assertTrue(any("入替待ち" in line for line in lines))
        self.assertIsNotNone(c.pending_skill)
        self.assertNotIn(c.pending_skill, c.skills)

    def full_session(self):
        s = Session(*load_content(), seed=2)
        for actor in s.party:
            self.give(actor, list(s.skills)[:6])
        s.settings["spark_chance"] = 1
        s.next_battle().outcome = "VICTORY"
        s.settle()
        return s

    def test_replace_last_slot_and_decline_remaining(self):
        s = self.full_session()
        self.assertEqual(s.pending_replacements, [0, 1, 2, 3])
        actor = s.party[0]
        new_id, old = actor.pending_skill, list(actor.skills)
        s.resolve_replacement(0, 5)
        self.assertEqual(actor.skills, old[:5] + [new_id])
        self.assertIsNone(actor.pending_skill)
        self.assertIn(s.skills[new_id].name, actor.history[-1])
        with self.assertRaises(ValueError):
            s.resolve_replacement(0, 5)
        for i in s.pending_replacements:
            before = list(s.party[i].skills)
            s.resolve_replacement(i)
            self.assertEqual(s.party[i].skills, before)
            self.assertIn("見送った", s.party[i].history[-1])
        stats = [(c.max_hp, c.strength, c.agility, c.intellect) for c in s.party]
        s.settle()
        self.assertEqual(s.completed, 1)
        self.assertEqual(stats, [(c.max_hp, c.strength, c.agility, c.intellect) for c in s.party])
        s.next_battle()
        self.assertIn(new_id, actor.skills)

    def test_pending_choice_blocks_next_battle_and_invalid_slots(self):
        s = self.full_session()
        before = list(s.party[0].skills)
        with self.assertRaises(ValueError):
            s.next_battle()
        for slot in (-1, 8, "1", True):
            with self.assertRaises(ValueError):
                s.resolve_replacement(0, slot)
        self.assertEqual(before, s.party[0].skills)
        self.assertIsNotNone(s.party[0].pending_skill)
        history = list(s.party[0].history)
        s.settle()
        self.assertEqual(history, s.party[0].history)

    def test_sound_cues_for_actions_and_skipped_actors(self):
        b = self.battle()
        b._party_action(Action(0, "SKILL", 0, "punch"))
        self.assertEqual(b.sound_cue, "attack")

    def test_player_hit_cue_only_for_enemy_damage(self):
        b = self.battle()
        b._party_action(Action(0, "SKILL", 0, "punch"))
        self.assertFalse(b.player_hit)
        b._enemy_action(0)
        self.assertTrue(b.player_hit)
        b.player_hit = True
        b.queue.append(("party", Action(0, "DEFEND")))
        b.step()
        self.assertFalse(b.player_hit)
        self.give(self.party[0], ["fire"])
        b._party_action(Action(0, "SKILL", 0, "fire"))
        self.assertEqual(b.sound_cue, "skill")
        b.queue.append(("party", Action(1, "DEFEND")))
        b.step()
        self.assertIsNone(b.sound_cue)
        self.party[0].hp = 0
        b.queue.append(("party", Action(0)))
        b.step()
        self.assertIsNone(b.sound_cue)
        b.enemies[0].magic_chance = 1
        b._enemy_action(0)
        self.assertEqual(b.sound_cue, "skill")
        b.enemies[0].magic_chance = 0
        b._enemy_action(0)
        self.assertEqual(b.sound_cue, "attack")

    def test_debug_fifty_battles_handles_full_slots_without_ui(self):
        s = Session(*load_content(), seed=42)
        s.debug = True
        result = simulate(s, 50)
        self.assertEqual(result["battles"], 50)
        self.assertFalse(s.pending_replacements)
        self.assertTrue(all(1 <= len(c.skills) <= 6 for c in s.party))

    def test_learning_all_candidates_does_not_loop(self):
        self.give(self.party[0], list(self.skills))
        self.settings["spark_chance"] = 1
        grow_and_spark(self.party[0], self.skills, self.settings, random.Random(1), 1)

    def test_hp_and_type_growth_plus_practice(self):
        class ThresholdRng(random.Random):
            def random(self):
                return 0.2
        self.settings["spark_chance"] = 0
        self.party[0].growth_points["INT"] = 5
        before = self.party[0].intellect
        hp = self.party[0].max_hp
        grow_and_spark(self.party[0], self.skills, self.settings, ThresholdRng(1), 1)
        self.assertEqual(self.party[0].intellect, before + 1)
        self.assertGreater(self.party[0].max_hp, hp)

    def test_settle_once_and_recovery(self):
        s = Session(self.settings, self.skills, self.party, self.enemies, seed=1)
        b = s.next_battle()
        b.outcome = "VICTORY"
        self.party[0].hp = 0
        s.settle()
        history = list(self.party[0].history)
        s.settle()
        self.assertEqual(s.completed, 1)
        self.assertEqual(self.party[0].history, history)
        self.assertTrue(history)
        s.next_battle()
        self.assertEqual(self.party[0].hp, self.party[0].max_hp)

    def test_defeat_and_draw_have_no_growth(self):
        for outcome in ("DEFEAT", "DRAW"):
            s = Session(*load_content(), seed=1)
            before = [(c.max_hp, c.strength, c.agility, c.intellect) for c in s.party]
            s.next_battle().outcome = outcome
            s.settle()
            self.assertEqual(before, [(c.max_hp, c.strength, c.agility, c.intellect) for c in s.party])
            s.next_battle()

    def test_fifty_battles_reproducible_and_personalities_diverge(self):
        a = simulate(Session(*load_content(), seed=42), 50)
        b = simulate(Session(*load_content(), seed=42), 50)
        self.assertEqual(a, b)
        self.assertEqual(a["battles"], 50)
        self.assertGreater(a["wins"], 30)
        self.assertNotEqual(a["party"][0]["skills"], a["party"][3]["skills"])
        for c in a["party"]:
            self.assertLessEqual(len(c["skills"]), 6)


if __name__ == "__main__":
    unittest.main()
