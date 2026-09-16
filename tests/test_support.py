"""Tactical effects, stock/mastery, depth probabilities and alternative counters."""
from collections import Counter
import random
import unittest

from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon import load_dungeon_settings
from rpg.growth import grow_and_spark, spark_probability
from rpg.labels import EFFECTS
from rpg.models import Action, Enemy


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.settings, self.skills, self.party, self.rows = load_content()
        self.actor = self.party[0]

    def enemy(self, sid):
        r = next(r for r in self.rows if r['id'] == sid)
        return Enemy(r['name'], r['max_hp'], r['str'], r['agi'], r['int'],
                     tuple(r['sprite']), r['magic_chance'],
                     defense=r.get('defense', 0), magic_defense=r.get('magic_defense', 0))

    def battle(self, sid='iron_golem', max_rounds=60):
        return Battle(self.party, [self.enemy(sid)], self.skills, max_rounds, random.Random(12))

    def use(self, b, sid, target=0):
        if sid not in self.actor.skills:
            self.actor.learn(self.skills[sid])
        self.actor.cooldowns.clear()
        return b._party_action(Action(0, 'SKILL', target, sid))

    def resolve(self, b, actions=None):
        b.begin_round(actions or [Action(i, 'DEFEND') for i, c in enumerate(self.party) if c.alive])
        while b.queue:
            b.step()

    def test_all_six_supports_consume_last_use_and_master(self):
        for sid in EFFECTS:
            with self.subTest(skill=sid):
                self.setUp()
                b = self.battle()
                self.actor.learn(self.skills[sid])
                self.actor.skill_uses[sid] = 1
                self.use(b, sid, 1 if self.skills[sid].target == 'ally' else 0)
                self.assertNotIn(sid, self.actor.skills)
                self.assertIn(sid, b.discovered_skills)
                self.assertIn(sid, b.mastered_skills)
                target = self.party[1] if self.skills[sid].target == 'ally' else b.enemies[0]
                self.assertEqual(target.effects[sid][1], 3)
                self.assertEqual(self.actor.used_skills[sid], 1)
                self.assertGreater(self.actor.growth_points['INT'], 0)

    def test_refresh_does_not_stack_and_different_effects_coexist(self):
        b = self.battle()
        self.use(b, 'armor_break')
        self.resolve(b)
        self.assertEqual(b.enemies[0].effects['armor_break'], (.7, 2))
        self.use(b, 'armor_break')
        self.use(b, 'weaken')
        self.assertEqual(b.enemies[0].effects, {'armor_break': (.7, 3), 'weaken': (.8, 3)})
        self.assertEqual(b.enemies[0].defense, 16)  # Base stats are never changed.
        for _ in range(3):
            self.resolve(b)
        self.assertEqual(b.enemies[0].effects, {})

    def test_power_and_focus_boost_real_damage_without_permanent_growth(self):
        b = self.battle()
        self.actor.intellect = 12
        base_physical = self.skills['power_strike'].power(self.actor)
        base_magic = self.skills['meteor'].power(self.actor)
        self.use(b, 'power_up')
        self.use(b, 'focus')
        self.assertGreater(self.skills['power_strike'].power(self.actor), base_physical)
        self.assertEqual(self.skills['meteor'].power(self.actor), round(base_magic * 1.5))
        self.assertEqual(self.actor.strength, 8)
        b.clear_effects()
        self.assertEqual(self.skills['power_strike'].power(self.actor), base_physical)
        self.assertEqual(self.skills['meteor'].power(self.actor), base_magic)

    def test_weaken_and_guard_up_reduce_actual_enemy_damage(self):
        for magic in (False, True):
            for effect in ('weaken', 'guard_up'):
                with self.subTest(effect=effect, magic=magic):
                    self.setUp()
                    for c in self.party[1:]:
                        c.hp = 0
                    b = self.battle('berserker')
                    b.enemies[0].intellect = 29
                    b.enemies[0].magic_chance = float(magic)
                    state, hp = b.rng.getstate(), self.actor.hp
                    b._enemy_action(0)
                    original = hp - self.actor.hp
                    self.actor.hp = hp
                    self.use(b, effect)
                    b.rng.setstate(state)
                    b._enemy_action(0)
                    self.assertLess(hp - self.actor.hp, original)

    def test_slow_reverses_order_from_next_round(self):
        b = self.battle('assassin')
        self.actor.agility = 20
        self.actor.learn(self.skills['slow'])
        actions = [Action(0, 'SKILL', 0, 'slow')] + [Action(i, 'DEFEND') for i in range(1, 4)]
        b.begin_round(actions)
        attacks = [side for side, action in b.queue if side == 'enemy' or action.kind == 'SKILL']
        self.assertEqual(attacks, ['enemy', 'party'])
        while b.queue:
            b.step()
        actions[0] = Action(0, 'SKILL', 0, 'punch')
        b.begin_round(actions)
        attacks = [side for side, action in b.queue if side == 'enemy' or action.kind == 'SKILL']
        self.assertEqual(attacks, ['party', 'enemy'])
        self.assertEqual(b.enemies[0].agility, 28)

    def test_all_outcomes_clear_effects_including_dead_characters(self):
        for outcome in ('VICTORY', 'DEFEAT', 'DRAW'):
            self.setUp()
            b = self.battle(max_rounds=1)
            self.use(b, 'weaken')
            self.use(b, 'power_up')
            if outcome == 'VICTORY':
                b.enemies[0].hp = 1
                b.enemies[0].defense = 0
            elif outcome == 'DEFEAT':
                for c in self.party[1:]:
                    c.hp = 0
                self.actor.hp = 1
                b.enemies[0].agility = 999
            self.resolve(b, b.auto_actions() if outcome != 'DRAW' else None)
            self.assertEqual(b.outcome, outcome)
            self.assertTrue(all(not c.effects for c in self.party + b.enemies))

    def test_all_bosses_accept_debuffs(self):
        for sid in ('guardian', 'skill_keeper', 'depth_lord'):
            b = self.battle(sid)
            for effect in ('armor_break', 'weaken', 'slow'):
                self.use(b, effect)
                self.assertIn(effect, b.enemies[0].effects)

    def tactical_fight(self, enemy_id='iron_golem', attack='punch', armor=False):
        self.setUp()
        for c in self.party:
            c.strength, c.intellect, c.agility = 19, 12, 20
            c.hp = c.max_hp = 200
            for sid in list(c.skills):
                c.forget(sid)
            for sid in ('punch', 'armor_break', 'fire', 'power_strike'):
                c.learn(self.skills[sid])
        self.actor.agility = 30
        b = self.battle(enemy_id)
        while not b.outcome:
            actions = []
            for i, c in enumerate(self.party):
                if c.alive:
                    sid = 'punch' if c.cooldowns.get(attack) else attack
                    if armor and i == 0 and not b.enemies[0].effects.get('armor_break'):
                        sid = 'armor_break'
                    actions.append(Action(i, 'SKILL', 0, sid))
            self.resolve(b, actions)
        self.assertEqual(b.outcome, 'VICTORY')
        return b.round

    def test_armor_break_golem_has_clear_turn_advantage_and_alternatives(self):
        ordinary = self.tactical_fight()
        armor = self.tactical_fight(armor=True)
        magic = self.tactical_fight(attack='fire')
        heavy = self.tactical_fight(attack='power_strike')
        self.assertTrue(5 <= ordinary <= 7, ordinary)
        self.assertTrue(2 <= armor <= 4, armor)
        self.assertLess(magic, ordinary)
        self.assertLess(heavy, ordinary)

    def test_every_special_enemy_can_be_beaten_without_support(self):
        for sid in ('iron_golem', 'berserker', 'assassin', 'stone_beast'):
            with self.subTest(enemy=sid):
                self.assertLess(self.tactical_fight(sid), 60)

    def test_depth_sampling_includes_rare_legend_and_support_on_b1(self):
        counts = []
        for multiplier in (1, 2):
            rng = random.Random(628)
            rarities, supports = Counter(), Counter()
            for i in range(20000):
                c = type(self.actor)('TEST', 'POWER', 10, 1, 1, 1, (0, 0))
                grow_and_spark(c, self.skills, self.settings, rng, i, spark_multiplier=multiplier)
                for sid in c.skills:
                    rarities[self.skills[sid].rarity] += 1
                    if sid in EFFECTS:
                        supports[sid] += 1
            self.assertGreater(rarities['LEGEND'], 0)
            self.assertGreater(rarities['RARE'], 0)
            self.assertEqual(set(supports), set(EFFECTS))
            counts.append(sum(rarities.values()))
        self.assertTrue(2700 <= counts[0] <= 3300, counts)
        self.assertTrue(5600 <= counts[1] <= 6400, counts)
        self.assertGreater(counts[1], counts[0] * 1.7)

    def test_session_passes_depth_and_debug_overrides_rate(self):
        class FixedRng(random.Random):
            def random(self):
                return .2
        for multiplier, expected in ((1, False), (2, True)):
            s = Session(*load_content())
            s.rng = FixedRng(1)
            s.next_battle([self.enemy('iron_golem')], spark_multiplier=multiplier).outcome = 'VICTORY'
            s.settle()
            self.assertEqual(any('閃き!' in line for line in s.results), expected)
        rates = [spark_probability(self.settings, m) for m in load_dungeon_settings()['spark_multipliers']]
        self.assertEqual(rates, sorted(rates))
        self.assertEqual((rates[0], rates[-1]), (.15, .30))
        self.assertEqual(spark_probability(self.settings, 2, True), .95)
        self.assertEqual(spark_probability(self.settings, 100), 1)


if __name__ == '__main__':
    unittest.main()
