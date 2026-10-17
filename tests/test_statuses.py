"""Shared ailments, resource-safe control actions, remedy, timing and visual safety."""
from collections import deque
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from rpg.battle import Battle, Session
from rpg.content import load_content, ROOT
from rpg.enemy_actions import EnemyAction, usable
from rpg.models import Action, Enemy
from rpg.statuses import (apply_status, load_statuses, active_statuses, confusion_target,
                         damage_hp, clear_statuses, STATUS_IDS)


class StatusTests(unittest.TestCase):
    def setUp(self):
        settings, self.skills, self.party, self.rows = load_content()
        for c in self.party:
            c.hp = c.max_hp = 1000
        self.enemy = Enemy.from_definition(next(r for r in self.rows if r['id'] == 'slime'), max_hp=10000)
        self.b = Battle(self.party, [self.enemy], self.skills, rng=random.Random(44))
        self.defs = self.b.status_definitions
        self.actor = self.party[0]
        self.skill_id = self.actor.skills[0]

    def turn(self, side='party', action=None):
        entry = action or Action(0, 'GUARD')
        self.b.queue = deque([(side, entry if side == 'party' else 0)])
        return self.b.step()

    def use_skill(self):
        return self.turn(action=Action(0, 'SKILL', 0, self.skill_id))

    def test_shared_application_fixed_ids_refresh_and_no_stacking(self):
        for target in (self.actor, self.enemy):
            for key in STATUS_IDS:
                clear_statuses(target)
                self.assertTrue(apply_status(target, key))
                target.statuses[key] = 1
                self.assertTrue(apply_status(target, key))
                self.assertEqual(target.statuses, {key: self.defs[key].duration})
        self.assertFalse(apply_status(self.actor, 'curse'))
        self.assertFalse(apply_status(self.actor, 'instant_death'))

    def test_all_control_status_pairs_exclude_but_poison_coexists(self):
        for existing in ('sleep', 'paralyze', 'confusion'):
            clear_statuses(self.actor)
            apply_status(self.actor, 'poison'); apply_status(self.actor, existing)
            for other in ('sleep', 'paralyze', 'confusion'):
                self.assertEqual(apply_status(self.actor, other), other == existing)
            self.assertEqual(set(self.actor.statuses), {'poison', existing})

    def test_chance_boundaries_and_resistance_immunity_without_boss_defaults(self):
        rng = Mock(); rng.random.return_value = .4
        self.assertFalse(apply_status(self.actor, 'poison', 40, rng))
        rng.random.return_value = .399
        self.assertTrue(apply_status(self.actor, 'poison', 40, rng))
        self.actor.status_resistances = {'poison': 50}
        rng.random.return_value = .21
        self.assertFalse(apply_status(self.actor, 'poison', 40, rng))
        rng.random.return_value = .19
        self.assertTrue(apply_status(self.actor, 'poison', 40, rng))
        self.actor.status_immunities = ('poison',)
        self.assertFalse(apply_status(self.actor, 'poison', 100))
        for value in (0, -1, 101, float('nan'), True):
            self.assertFalse(apply_status(self.enemy, 'poison', value))
        self.actor.hp = 0
        self.assertFalse(apply_status(self.actor, 'sleep'))
        for row in self.rows:
            self.assertFalse(row.get('status_resistances') or row.get('status_immunities'))

    def test_invalid_resistance_falls_back_and_no_rng_draw_at_zero_or_hundred(self):
        rng = Mock(); rng.random.side_effect = AssertionError('unnecessary RNG')
        self.actor.status_resistances = {'poison': 'bad'}
        self.assertTrue(apply_status(self.actor, 'poison', 100, rng))
        self.assertFalse(apply_status(self.actor, 'poison', 0, rng))

    def test_poison_three_own_turn_ticks_ignores_guard_and_minimum_one(self):
        apply_status(self.actor, 'poison')
        for hp, remaining in ((950, 2), (900, 1), (850, 0)):
            self.turn()
            self.assertEqual(self.actor.hp, hp)
            self.assertEqual(self.actor.statuses.get('poison', 0), remaining)
        self.actor.hp = self.actor.max_hp = 9
        apply_status(self.actor, 'poison')
        self.turn()
        self.assertEqual(self.actor.hp, 8)

    def test_poison_not_ticked_by_other_actor_and_enemy_armor_does_not_reduce_it(self):
        apply_status(self.actor, 'poison')
        self.turn(action=Action(1, 'GUARD'))
        self.assertEqual(self.actor.hp, 1000)
        self.assertEqual(self.actor.statuses['poison'], 3)
        self.enemy.defense = self.enemy.magic_defense = 9999
        self.enemy.actions = [dict(id='guard', weight=1)]
        apply_status(self.enemy, 'poison')
        self.turn('enemy')
        self.assertEqual(self.enemy.hp, 9500)

    def test_poison_ko_clears_all_states_and_uses_normal_defeat(self):
        for actor in self.party:
            actor.hp = 0
        self.actor.hp = 1
        apply_status(self.actor, 'poison'); apply_status(self.actor, 'sleep')
        lines = self.turn()
        self.assertEqual(self.b.outcome, 'DEFEAT')
        self.assertEqual(self.actor.hp, 0)
        self.assertFalse(self.actor.statuses)
        self.assertTrue(any('戦闘不能' in line for line in lines))

    def test_enemy_poison_ko_clears_and_uses_normal_victory(self):
        self.enemy.hp = 1
        apply_status(self.actor, 'paralyze')
        apply_status(self.enemy, 'poison')
        self.turn('enemy')
        self.assertEqual(self.b.outcome, 'VICTORY')
        self.assertFalse(self.enemy.statuses)
        self.assertFalse(self.actor.statuses)

    def test_enemy_sleep_and_paralyze_skip_and_expire_on_own_turns(self):
        for ident, turns in (('sleep', 2), ('paralyze', 3)):
            apply_status(self.enemy, ident)
            hp = [c.hp for c in self.party]
            with patch.object(self.b.rng, 'random', return_value=0):
                for remaining in reversed(range(turns)):
                    self.turn('enemy')
                    self.assertEqual(self.enemy.statuses.get(ident, 0), remaining)
            self.assertEqual([c.hp for c in self.party], hp)

    def test_paralyze_skip_preserves_skill_and_item_but_permitted_turn_uses_skill(self):
        apply_status(self.actor, 'paralyze')
        before = deepcopy(self.actor.skill_uses)
        with patch.object(self.b.rng, 'random', return_value=0):
            self.use_skill()
            self.b.inventory.counts['POTION'] = 1
            self.party[1].hp = 1
            self.turn(action=Action(0, 'ITEM', 1, item_id='POTION'))
        self.assertEqual(self.actor.skill_uses, before)
        self.assertEqual(self.b.inventory.counts['POTION'], 1)
        self.assertFalse(self.actor.used_skills or self.actor.category_uses or self.actor.growth_points)
        with patch.object(self.b.rng, 'random', return_value=.99):
            self.use_skill()
        self.assertNotIn('paralyze', self.actor.statuses)
        self.assertEqual(self.actor.skill_uses.get(self.skill_id, 0), before[self.skill_id] - 1)

    def test_prepare_turn_checks_paralyze_once_without_consuming_queue(self):
        apply_status(self.actor, 'paralyze')
        self.b.queue.append(('party', Action(0, 'SKILL', 0, self.skill_id)))
        with patch.object(self.b.rng, 'random', return_value=0) as roll:
            for _ in range(10):
                self.assertEqual(self.b.prepare_turn()[2], 'paralyze')
            self.assertEqual(len(self.b.queue), 1)
            self.b.step()
        self.assertEqual(roll.call_count, 1)

    def test_sleep_skips_two_own_turns_without_resources(self):
        apply_status(self.actor, 'sleep')
        uses = deepcopy(self.actor.skill_uses)
        self.use_skill(); self.use_skill()
        self.assertFalse(self.actor.statuses)
        self.assertEqual(self.actor.skill_uses, uses)
        self.assertFalse(self.actor.used_skills)

    def test_all_real_hp_losses_wake_and_zero_does_not(self):
        for magic in (False, True):
            for target in (self.actor, self.enemy):
                apply_status(target, 'sleep')
                self.b._damage(target, 10, magic=magic)
                self.assertNotIn('sleep', target.statuses)
        apply_status(self.actor, 'sleep')
        damage_hp(self.actor, 0)
        self.assertIn('sleep', self.actor.statuses)
        self.assertTrue(any('目を覚ました' in line for line in self.b.status_messages))

    def test_waking_before_queued_turn_allows_original_selected_action(self):
        apply_status(self.actor, 'sleep')
        before = self.actor.skill_uses[self.skill_id]
        self.b.queue = deque([('enemy', 0), ('party', Action(0, 'SKILL', 0, self.skill_id))])
        with patch.object(self.b.rng, 'choice', return_value=self.actor):
            self.b.step()
        self.assertNotIn('sleep', self.actor.statuses)
        self.b.step()
        self.assertEqual(self.actor.skill_uses.get(self.skill_id, 0), before - 1)

    def test_sleep_poison_skips_then_wakes_after_own_turn(self):
        apply_status(self.actor, 'poison'); apply_status(self.actor, 'sleep')
        uses = deepcopy(self.actor.skill_uses)
        self.use_skill()
        self.assertNotIn('sleep', self.actor.statuses)
        self.assertEqual(self.actor.statuses['poison'], 2)
        self.assertEqual(self.actor.hp, 950)
        self.assertEqual(self.actor.skill_uses, uses)
        self.use_skill()
        self.assertEqual(self.actor.skill_uses.get(self.skill_id, 0), uses[self.skill_id] - 1)

    def confusion(self, side, branch):
        actor = self.actor if side == 'party' else self.enemy
        apply_status(actor, 'confusion')
        with patch.object(self.b.rng, 'choices', return_value=[branch]), \
             patch.object(self.b.rng, 'choice', side_effect=lambda choices: choices[0]):
            return self.turn(side, Action(0, 'SKILL', 0, self.skill_id))

    def test_player_confusion_enemy_ally_idle_never_spends_records(self):
        self.actor.strength = 100
        original = deepcopy((self.actor.skill_uses, self.actor.used_skills, self.actor.category_uses, self.actor.growth_points))
        self.confusion('party', 'enemy')
        self.assertEqual(self.enemy.hp, 9925)
        self.confusion('party', 'ally')
        self.assertEqual(self.party[1].hp, 925)
        self.assertEqual(self.actor.hp, 1000)
        self.confusion('party', 'idle')
        self.assertEqual((self.actor.skill_uses, self.actor.used_skills, self.actor.category_uses, self.actor.growth_points), original)

    def test_confusion_replaces_item_without_consuming_and_expires_in_two_turns(self):
        self.b.inventory.counts['POTION'] = 1
        self.party[1].hp = 1
        apply_status(self.actor, 'confusion')
        with patch.object(self.b.rng, 'choices', return_value=['idle']):
            for _ in range(2):
                self.turn(action=Action(0, 'ITEM', 1, item_id='POTION'))
        self.assertFalse(self.actor.statuses)
        self.assertEqual(self.party[1].hp, 1)
        self.assertEqual(self.b.inventory.counts['POTION'], 1)

    def test_enemy_confusion_player_ally_idle_and_lone_enemy_fallback(self):
        self.enemy.strength = 100
        self.confusion('enemy', 'enemy')
        self.assertEqual(self.actor.hp, 925)
        self.confusion('enemy', 'ally')
        self.assertEqual(self.enemy.hp, 10000)
        other = Enemy.from_definition(self.rows[0], max_hp=1000)
        self.b.enemies.append(other)
        self.confusion('enemy', 'ally')
        self.assertEqual(other.hp, 925)
        self.confusion('enemy', 'idle')
        self.assertEqual(other.hp, 925)

    def test_confusion_target_rates_dead_exclusion_and_no_self(self):
        rng = random.Random(345)
        counts = {'enemy': 0, 'ally': 0, 'idle': 0}
        self.party[1].hp = 0
        for _ in range(10000):
            target = confusion_target(self.actor, self.party, [self.enemy], self.defs['confusion'], rng)
            self.assertIsNot(target, self.actor)
            self.assertIsNot(target, self.party[1])
            counts['idle' if target is None else 'enemy' if target is self.enemy else 'ally'] += 1
        self.assertTrue(3800 < counts['enemy'] < 4200 and 3800 < counts['ally'] < 4200 and 1800 < counts['idle'] < 2200)

    def test_remedy_all_ailments_and_poison_control_does_not_clear_effects(self):
        self.actor.effects = {'weaken': (.85, 3), 'armor_break': (.85, 3), 'slow': (.8, 3), 'focus': (1.2, 3)}
        for key in STATUS_IDS:
            self.b.inventory.counts['REMEDY'] = 1
            apply_status(self.actor, key)
            if key != 'poison':
                apply_status(self.actor, 'poison')
            expected = deepcopy(self.actor.effects)
            used, _ = self.b.inventory.use('REMEDY', self.actor)
            self.assertTrue(used)
            self.assertFalse(self.actor.statuses)
            self.assertEqual(self.actor.effects, expected)
            self.assertEqual(self.b.inventory.counts['REMEDY'], 0)

    def test_remedy_rejects_ko_and_healthy_target_without_spending(self):
        self.b.inventory.counts['REMEDY'] = 2
        for hp in (1000, 0):
            self.actor.hp = hp
            self.assertFalse(self.b.inventory.use('REMEDY', self.actor)[0])
        self.assertEqual(self.b.inventory.counts['REMEDY'], 2)

    def test_teammate_remedy_restores_sleeping_actors_original_turn(self):
        apply_status(self.party[1], 'poison'); apply_status(self.party[1], 'sleep')
        self.b.inventory.counts['REMEDY'] = 1
        skill = self.party[1].skills[0]; uses = self.party[1].skill_uses[skill]
        self.b.queue = deque([('party', Action(0, 'ITEM', 1, item_id='REMEDY')),
                              ('party', Action(1, 'SKILL', 0, skill))])
        self.b.step()
        self.assertEqual(self.b.inventory.counts['REMEDY'], 0)
        self.assertFalse(self.party[1].statuses)
        self.b.step()
        self.assertEqual(self.party[1].skill_uses.get(skill, 0), uses - 1)

    def test_ko_revive_and_escape_clear_without_touching_growth_or_inventory(self):
        apply_status(self.actor, 'poison'); apply_status(self.actor, 'sleep')
        self.b._damage(self.actor, 10000)
        self.assertFalse(self.actor.statuses)
        self.b.inventory.counts['PHOENIX ASH'] = 1
        self.b.inventory.use('PHOENIX ASH', self.actor)
        self.assertTrue(self.actor.alive)
        self.assertFalse(self.actor.statuses)
        apply_status(self.actor, 'sleep'); apply_status(self.enemy, 'poison')
        self.b.run_override = True
        self.b.attempt_run()
        self.assertFalse(self.actor.statuses or self.enemy.statuses)

    def test_damage_and_status_only_actions_connect_without_roster_edits(self):
        for key in STATUS_IDS:
            clear_statuses(self.actor)
            self.b.enemy_actions['test'] = EnemyAction('test', 'status', 'random_player', status_id=key)
            self.assertTrue(usable(self.b.enemy_actions['test']))
            self.enemy.actions = [dict(id='test', weight=1)]
            with patch.object(self.b.rng, 'choice', return_value=self.actor):
                self.turn('enemy')
            self.assertEqual(self.actor.statuses[key], self.defs[key].duration)
        clear_statuses(self.actor)
        self.b.enemy_actions['test'] = replace(self.b.enemy_actions['attack'], status_id='poison', status_chance=100)
        self.actor.hp = 1000
        with patch.object(self.b.rng, 'choice', return_value=self.actor):
            self.turn('enemy')
        self.assertLess(self.actor.hp, 1000)
        self.assertEqual(self.actor.statuses['poison'], 3)
        self.assertEqual(len(self.b.status_visual_events), 1)

    def test_status_json_editing_and_invalid_data(self):
        raw = json.loads((ROOT / 'data/statuses.json').read_text(encoding='utf8'))
        raw['poison']['name'] = 'renamed'
        raw['poison']['duration'] = 4
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'statuses.json'
            path.write_text(json.dumps(raw), encoding='utf8')
            defs = load_statuses(path)
            self.assertTrue(apply_status(self.actor, 'poison', definitions=defs))
            self.assertEqual(self.actor.statuses['poison'], 4)
            raw['poison']['duration'] = 0
            path.write_text(json.dumps(raw), encoding='utf8')
            with self.assertRaises(ValueError):
                load_statuses(path)


class StatusUITests(unittest.TestCase):
    def setUp(self):
        import test_battle_extra as fixtures
        fixture = fixtures.BattleExtraTests(); fixture.setUp()
        self.app = fixture.app
        self.b = self.app.battle

    def test_confused_command_skips_selection_and_all_confused_resolves(self):
        apply_status(self.b.party[0], 'confusion')
        self.app.begin_input()
        self.assertEqual(self.app.actor_index, 1)
        self.assertEqual(self.app.actions, [Action(0, 'STATUS')])
        for c in self.b.party:
            apply_status(c, 'confusion')
        self.app.begin_input()
        self.assertEqual(self.app.state, 'resolve')
        self.assertEqual(len(self.app.actions), 4)

    def test_remedy_targets_only_affected_living_and_reserves_inventory(self):
        self.b.inventory.counts['REMEDY'] = 1
        self.assertNotIn('REMEDY', self.app.battle_items())
        apply_status(self.b.party[2], 'sleep')
        self.assertIn('REMEDY', self.app.battle_items())
        self.app.selected_item = 'REMEDY'
        self.assertEqual([i for i, _ in self.app.targets()], [2])
        self.app.actions = [Action(0, 'ITEM', 2, item_id='REMEDY')]
        self.assertNotIn('REMEDY', self.app.battle_items())

    def test_icons_player_enemy_two_statuses_and_ko_priority(self):
        import pyxel
        from rpg.battle_presentation import STATUS_SPRITES
        for unit in (self.b.party[0], self.b.enemies[0]):
            apply_status(unit, 'poison'); apply_status(unit, 'confusion')
        with patch.object(pyxel, 'blt', wraps=pyxel.blt) as blt:
            self.app.draw()
        icons = [call.args for call in blt.call_args_list if call.args[2] == 2 and call.args[5:7] == (8, 8)]
        self.assertEqual(len(icons), 4)
        self.assertTrue(all(0 <= a[0] <= 152 and 11 <= a[1] <= 72 for a in icons))
        self.b._damage(self.b.party[0], 99999)
        self.assertFalse(self.b.party[0].statuses)
        self.app.draw()

    def test_poison_sleep_feedback_blocks_spam_and_has_audio_free_timeout(self):
        import pyxel
        self.app.state = 'resolve'
        apply_status(self.b.party[0], 'poison'); apply_status(self.b.party[0], 'sleep')
        self.b.queue = deque([('party', Action(0, 'SKILL', 0, self.b.party[0].skills[0]))])
        before = deepcopy(self.b.party[0].skill_uses)
        with patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')):
            self.app.apply_visual_action()
        v = self.app.battle_visual()
        self.assertEqual(v.phase, 'status_effect')
        self.b.queue.append(('enemy', 0))
        with patch.object(self.b, 'step', side_effect=AssertionError('double application')):
            while v.active:
                self.app.update(); self.app.draw()
        self.assertEqual(self.b.party[0].skill_uses, before)
        self.assertEqual(len(self.b.queue), 1)
        self.assertNotIn('sleep', self.b.party[0].statuses)

    def test_save_schema_has_no_statuses_and_debug_preview_draws(self):
        from rpg.save import make_save_data
        for c in self.b.party:
            apply_status(c, 'poison')
        self.app.state = 'camp'
        data = make_save_data(self.app)
        self.assertEqual(data['save_version'], 1)
        self.assertNotIn('statuses', json.dumps(data))
        self.app.state = 'command'; self.app.overlay = 'status_debug'
        self.app.status_debug_target = self.app.status_debug_cursor = 0
        self.app.draw()

    def test_sleep_ko_status_effect_displays_before_normal_recoil_and_ko(self):
        import pyxel
        self.app.state = 'resolve'
        actor = self.b.party[0]
        actor.hp = 1
        apply_status(actor, 'poison'); apply_status(actor, 'sleep')
        self.b.queue = deque([('party', Action(0, 'GUARD'))])
        self.app.apply_visual_action()
        v = self.app.battle_visual()
        self.assertEqual(actor.hp, 0)
        self.assertEqual(v.phase, 'status_effect')
        self.assertFalse(actor.statuses)
        self.assertTrue(v.holds_party_sprite(0))
        for _ in range(6): self.app.update_battle_visual()
        self.assertEqual(v.phase, 'party_hit')
        for _ in range(3): self.app.update_battle_visual()
        self.assertFalse(v.holds_party_sprite(0))
        with patch.object(pyxel, 'blt', wraps=pyxel.blt) as blt:
            self.app.draw()
        self.assertIn((98, 13, 2, 240, 0, 16, 16, 0), [c.args for c in blt.call_args_list])

    def test_three_final_retries_restore_no_statuses_and_amrita_barrier(self):
        import pyxel
        import test_final_battle as fixtures
        fixture = fixtures.FinalBattleTests(); fixture.setUp()
        fixture.launch()
        for _ in range(3):
            for c in fixture.s.party:
                apply_status(c, 'poison'); apply_status(c, 'confusion')
            apply_status(fixture.a.battle.enemies[0], 'sleep')
            fixture.a.battle.elysion_barrier_active = False
            fixture.fail()
            self.assertFalse(any(c.statuses for c in fixture.s.party))
            fixture.press(pyxel.GAMEPAD1_BUTTON_A)
            self.assertTrue(fixture.a.battle.elysion_barrier_active)
            self.assertTrue(fixture.d.finale.has_amrita)
            self.assertFalse(any(c.statuses for c in fixture.s.party + fixture.a.battle.enemies))

    def test_debug_f2_can_apply_clear_and_return_without_uses(self):
        self.app.overlay = 'status_debug'
        self.app.status_debug_target = self.app.status_debug_cursor = 0
        self.app.direction = lambda horizontal=False: 0
        self.app.update_status_debug(True, False)
        self.assertIn('poison', self.b.party[0].statuses)
        self.app.status_debug_cursor = 4
        self.app.update_status_debug(True, False)
        self.assertFalse(self.b.party[0].statuses)
        self.app.update_status_debug(False, True)
        self.assertIsNone(self.app.overlay)
        self.assertEqual(self.app.state, 'command')

    def test_resume_wall_timeout_releases_all_status_phases(self):
        apply_status(self.b.party[0], 'poison'); apply_status(self.b.party[0], 'sleep')
        self.app.state = 'resolve'
        self.b.queue = deque([('party', Action(0, 'GUARD'))])
        self.app.apply_visual_action()
        v = self.app.battle_visual()
        phases = []
        while v.active:
            phases.append(v.phase)
            v.started_at = time.monotonic() - 3
            self.app.update_battle_visual()
            self.assertLess(len(phases), 4)
        self.assertEqual(phases, ['status_effect', 'party_hit'])

    def test_each_status_visual_survives_normal_and_fast_spam_without_double_step(self):
        for fast in (False, True):
            for key in STATUS_IDS:
                self.b.clear_effects()
                self.b.outcome = None
                self.b.party[0].hp = self.b.party[0].max_hp
                apply_status(self.b.party[0], key)
                self.b.queue = deque([('party', Action(0, 'GUARD'))])
                self.app.state = 'resolve'; self.app.battle_visual().reset()
                with patch.object(self.b.rng, 'random', return_value=0), \
                     patch.object(self.b.rng, 'choices', return_value=['idle']):
                    self.app.apply_visual_action()
                v = self.app.battle_visual()
                hp, statuses = self.b.party[0].hp, deepcopy(self.b.party[0].statuses)
                self.b.queue.append(('enemy', 0))
                self.app.confirm = self.app.confirm_held = lambda: fast
                ticks = 0
                with patch.object(self.b, 'step', side_effect=AssertionError('double status turn')):
                    while v.active:
                        self.app.update(); self.app.draw()
                        ticks += 1
                        self.assertLess(ticks, 50)
                self.assertGreaterEqual(ticks, 6)
                self.assertEqual((self.b.party[0].hp, self.b.party[0].statuses), (hp, statuses))
                self.assertEqual(len(self.b.queue), 1)


if __name__ == '__main__':
    unittest.main()
