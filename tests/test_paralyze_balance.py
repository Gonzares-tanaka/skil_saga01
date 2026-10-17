"""PARALYZE BALANCE PASS 01: shared 50% checks through real Battle turns."""
from collections import deque
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from rpg.battle import Battle
from rpg.content import load_content
from rpg.models import Action, Enemy
from rpg.statuses import apply_status, damage_hp


def battle_fixture(seed=501):
    _, skills, party, rows = load_content()
    for actor in party:
        actor.hp = actor.max_hp = 1000
    enemy = Enemy.from_definition(next(row for row in rows if row['id'] == 'slime'),
                                  max_hp=10000)
    enemy.actions = [dict(id='guard', weight=1)]
    return Battle(party, [enemy], skills, rng=random.Random(seed))


def sample_turns(side, count=10000, seed=501):
    """Reapply the real duration each trial; prepare/step share one cached roll."""
    battle = battle_fixture(seed)
    unit = battle.party[0] if side == 'party' else battle.enemies[0]
    entry = Action(0, 'GUARD') if side == 'party' else 0
    failed = 0
    for _ in range(count):
        apply_status(unit, 'paralyze')
        unit.guarding = False
        # Keep a second actor queued to observe guard before round-end reset.
        battle.queue = deque([(side, entry), ('party', Action(1, 'GUARD'))])
        decision = battle.prepare_turn()[2]
        failed += decision == 'paralyze'
        battle.step()
        assert len(battle.queue) == 1
        assert unit.statuses == {'paralyze': 2}
        assert unit.guarding == (decision is None)
    return dict(trials=count, failed=failed, rate=failed / count, seed=seed)


class ParalyzeBalanceTests(unittest.TestCase):
    def setUp(self):
        self.b = battle_fixture()
        self.actor, self.enemy = self.b.party[0], self.b.enemies[0]

    def turn(self, side='party', action=None):
        entry = (action or Action(0, 'GUARD')) if side == 'party' else 0
        self.b.queue = deque([(side, entry), ('party', Action(1, 'GUARD'))])
        return self.b.step()

    def test_definition_has_fifty_percent_and_original_three_actor_turns(self):
        self.assertEqual(self.b.status_definitions['paralyze'].skip_chance, .5)
        self.assertEqual(self.b.status_definitions['paralyze'].duration, 3)

    def test_fixed_seed_player_rate_through_prepare_and_step(self):
        result = sample_turns('party')
        self.assertTrue(.48 <= result['rate'] <= .52, result)

    def test_fixed_seed_enemy_rate_through_prepare_and_step(self):
        result = sample_turns('enemy')
        self.assertTrue(.48 <= result['rate'] <= .52, result)

    def test_shared_boundary_and_one_roll_for_preview_and_execution(self):
        for side, unit in (('party', self.actor), ('enemy', self.enemy)):
            for roll, expected in ((0, 'paralyze'), (.35, 'paralyze'),
                                   (.499999, 'paralyze'), (.5, None), (.999999, None)):
                with self.subTest(side=side, roll=roll):
                    apply_status(unit, 'paralyze')
                    entry = Action(0, 'GUARD') if side == 'party' else 0
                    self.b.queue = deque([(side, entry), ('party', Action(1, 'GUARD'))])
                    with patch.object(self.b.rng, 'random', return_value=roll) as rng, \
                         patch('rpg.battle.choose_enemy_action', return_value='guard'):
                        for _ in range(5):
                            self.assertEqual(self.b.prepare_turn()[2], expected)
                        self.b.step()
                    rng.assert_called_once()
                    self.assertEqual(len(self.b.queue), 1)
                    self.assertEqual(unit.statuses, {'paralyze': 2})

    def test_failed_skill_spends_turn_without_uses_cooldown_or_effect(self):
        skill = self.b.skills['shock_stab']
        self.actor.learn(skill)
        before = deepcopy((self.actor.skill_uses, self.actor.used_skills,
                           self.actor.category_uses, self.actor.growth_points))
        apply_status(self.actor, 'paralyze')
        with patch.object(self.b.rng, 'random', return_value=.49):
            self.turn(action=Action(0, 'SKILL', 0, skill.id))
        self.assertEqual(len(self.b.queue), 1)
        self.assertEqual(self.actor.statuses, {'paralyze': 2})
        self.assertEqual((self.actor.skill_uses, self.actor.used_skills,
                          self.actor.category_uses, self.actor.growth_points), before)
        self.assertFalse(self.actor.cooldowns)
        self.assertEqual(self.enemy.hp, 10000)
        self.assertFalse(self.enemy.statuses)
        self.assertIsNone(self.b.player_skill_visual)

    def test_successful_skill_has_normal_damage_uses_and_cooldown(self):
        skill = self.b.skills['shock_stab']
        self.actor.learn(skill)
        apply_status(self.actor, 'paralyze')
        with patch.object(self.b.rng, 'random', return_value=.99):
            self.turn(action=Action(0, 'SKILL', 0, skill.id))
        self.assertLess(self.enemy.hp, 10000)
        self.assertEqual(self.actor.skill_uses[skill.id], skill.max_uses - 1)
        self.assertEqual(self.actor.cooldowns[skill.id], skill.cooldown + 1)
        self.assertEqual(self.actor.statuses, {'paralyze': 2})

    def test_failed_item_does_not_consume_or_heal(self):
        self.b.inventory.counts['POTION'] = 1
        self.b.party[1].hp = 1
        apply_status(self.actor, 'paralyze')
        with patch.object(self.b.rng, 'random', return_value=.49):
            self.turn(action=Action(0, 'ITEM', 1, item_id='POTION'))
        self.assertEqual(self.b.inventory.counts['POTION'], 1)
        self.assertEqual(self.b.party[1].hp, 1)
        self.assertEqual(len(self.b.queue), 1)

    def test_enemy_failed_attack_has_no_effect_then_success_attacks_normally(self):
        self.enemy.actions = [dict(id='paralyze_grab', weight=1)]
        hp = [actor.hp for actor in self.b.party]
        apply_status(self.enemy, 'paralyze')
        with patch.object(self.b.rng, 'random', return_value=.49):
            self.turn('enemy')
        self.assertEqual([actor.hp for actor in self.b.party], hp)
        self.assertFalse(any(actor.statuses for actor in self.b.party))
        self.assertIsNone(self.b.enemy_action_visual)
        with patch.object(self.b.rng, 'random', return_value=.99):
            self.turn('enemy')
        self.assertLess(sum(actor.hp for actor in self.b.party), sum(hp))
        self.assertEqual(self.b.enemy_action_visual['action_id'], 'paralyze_grab')
        self.assertEqual(self.enemy.statuses, {'paralyze': 1})

    def test_both_outcomes_tick_duration_and_expire_for_both_sides(self):
        for side, unit in (('party', self.actor), ('enemy', self.enemy)):
            for roll in (.49, .5):
                apply_status(unit, 'paralyze')
                with patch.object(self.b.rng, 'random', return_value=roll):
                    for remaining in (2, 1, 0):
                        self.turn(side)
                        self.assertEqual(unit.statuses.get('paralyze', 0), remaining)
                self.assertNotIn('paralyze', unit.statuses)

    def test_damage_preserves_paralyze_and_application_chances_are_unchanged(self):
        for unit in (self.actor, self.enemy):
            apply_status(unit, 'paralyze')
            damage_hp(unit, 1)
            self.assertEqual(unit.statuses, {'paralyze': 3})
        self.assertEqual(self.b.skills['shock_stab'].status_chance, 30)
        self.assertEqual(self.b.skills['thunder_bind'].status_chance, 45)
        self.assertEqual(self.b.enemy_actions['paralyze_grab'].status_chance, 35)


if __name__ == '__main__':
    unittest.main()
