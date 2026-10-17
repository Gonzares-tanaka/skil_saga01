"""Enemy action targeting, weighted data, modifiers and bounded presentation."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from rpg.battle import Battle
from rpg.battle_presentation import BattlePresentation, MAX_PRESENTATION_SECONDS
from rpg.content import load_content, ROOT
from rpg.enemy_actions import (choose_enemy_action, load_enemy_actions,
                               validate_enemy_action_lists)
from rpg.models import Action, Enemy, battle_agility


class EnemyActionTests(unittest.TestCase):
    def setUp(self):
        self.settings, self.skills, self.party, self.rows = load_content()
        for actor in self.party:
            actor.hp = actor.max_hp = 1000
        row = deepcopy(next(row for row in self.rows if row['id'] == 'berserker'))
        row.update(max_hp=10000, str=100, int=80, defense=0)
        self.enemy = Enemy.from_definition(row)
        self.b = Battle(self.party, [self.enemy], self.skills, rng=random.Random(7))
        self.b.rng.uniform = Mock(return_value=1.0)
        self.b.rng.choice = Mock(side_effect=lambda choices: choices[0])

    def use(self, ident):
        self.enemy.actions = [dict(id=ident, weight=100)]
        return self.b._enemy_action(0)

    def test_normal_attack_and_magic_use_existing_damage_formula(self):
        for ident, amount in (('attack', 100), ('magic', 80), ('heavy_attack', 135)):
            self.party[0].hp = 1000
            self.use(ident)
            self.assertEqual(self.party[0].hp, 1000 - amount)

    def test_unconfigured_fallback_preserves_legacy_rng_target_and_damage(self):
        for chance in (0, .4, .8, 1):
            for seed in range(20):
                self.enemy.actions = []
                self.enemy.magic_chance = chance
                self.b.rng = random.Random(seed)
                oracle = random.Random(seed)
                index = oracle.choice(list(range(4)))
                magic = oracle.random() < chance
                amount = round((80 if magic else 100) * oracle.uniform(.9, 1.1))
                for actor in self.party:
                    actor.hp = 1000
                lines = self.b._enemy_action(0)
                self.assertEqual(self.party[index].hp, 1000 - amount)
                self.assertEqual(self.b.rng.getstate(), oracle.getstate())
                self.assertIn(self.party[index].name, lines[1])

    def test_double_attack_hits_one_target_twice_in_one_queued_action(self):
        self.enemy.actions = [dict(id='double_attack', weight=1)]
        self.b.queue.append(('enemy', 0))
        lines = self.b.step()
        self.assertEqual([actor.hp for actor in self.party], [880, 1000, 1000, 1000])
        self.assertEqual(sum('-60' in line for line in lines), 2)
        self.assertFalse(self.b.queue)

    def test_double_attack_stops_on_ko_without_retarget(self):
        self.party[0].hp = 30
        self.use('double_attack')
        self.assertEqual([actor.hp for actor in self.party], [0, 1000, 1000, 1000])
        self.assertEqual(self.b.enemy_action_visual['repeats'], 1)

    def test_area_actions_hit_only_living_party_and_remain_weaker_per_person(self):
        for ident, damage in (('area_attack', 55), ('area_magic', 40)):
            self.party[0].hp = 0
            for actor in self.party[1:]:
                actor.hp = 1000
            self.use(ident)
            self.assertEqual([actor.hp for actor in self.party], [0] + [1000-damage]*3)
            self.assertEqual(self.b.enemy_action_visual['targets'], [('party', 1), ('party', 2), ('party', 3)])

    def test_dead_enemy_and_absent_living_targets_do_not_select_or_act(self):
        for enemy_hp, party_hp in ((0, 1000), (10000, 0)):
            self.enemy.hp = enemy_hp
            for actor in self.party:
                actor.hp = party_hp
            with patch('rpg.battle.choose_enemy_action', side_effect=AssertionError('dead actor selected')):
                self.assertEqual(self.b._enemy_action(0), [])

    def test_single_actions_never_select_ko_party(self):
        self.party[0].hp = 0
        self.use('heavy_attack')
        self.assertEqual([actor.hp for actor in self.party], [0, 865, 1000, 1000])

    def test_enemy_guard_survives_round_and_expires_at_next_own_action(self):
        self.enemy.actions = [dict(id='guard', weight=1)]
        self.b.queue.append(('enemy', 0))
        self.b.step()
        self.assertTrue(self.enemy.guarding)
        self.assertEqual(self.b._damage(self.enemy, 100), 50)
        self.b.begin_round([Action(i, 'GUARD') for i in range(4)])
        self.assertTrue(self.enemy.guarding)
        self.enemy.actions = [dict(id='attack', weight=1)]
        while self.b.queue:
            self.b.step()
        self.assertFalse(self.enemy.guarding)
        self.assertEqual(self.b._damage(self.enemy, 100), 100)

    def test_enemy_guard_does_not_change_player_guard(self):
        self.use('guard')
        self.party[0].guarding = True
        self.assertEqual(self.b._damage(self.party[0], 100), 50)
        self.b.clear_effects()
        self.assertFalse(self.enemy.guarding)

    def test_power_up_boosts_physical_only_without_stacking_or_stat_mutation(self):
        for _ in range(8):
            self.use('power_up')
        self.assertEqual(self.enemy.effects['power_up'], (1.2, 3))
        self.use('attack')
        self.assertEqual(self.party[0].hp, 880)
        self.party[0].hp = 1000
        self.use('magic')
        self.assertEqual(self.party[0].hp, 920)
        self.assertEqual(self.enemy.strength, 100)

    def test_weaken_reduces_actual_player_damage_but_not_healing(self):
        actor = self.party[0]
        actor.learn(self.skills['fire'])
        before = self.enemy.hp
        self.b._skill_effect(actor, self.skills['fire'], 0)
        original = before - self.enemy.hp
        for _ in range(5):
            self.use('weaken')
        self.assertEqual(actor.effects['weaken'], (.85, 3))
        before = self.enemy.hp
        self.b._skill_effect(actor, self.skills['fire'], 0)
        self.assertLess(before - self.enemy.hp, original)
        healed = self.skills['heal'].power(actor)
        actor.hp = 1
        self.b._skill_effect(actor, self.skills['heal'], 0)
        self.assertEqual(actor.hp, 1 + healed)

    def test_armor_break_increases_player_physical_damage_only(self):
        self.use('armor_break')
        self.assertEqual(self.party[0].effects['armor_break'], (.85, 3))
        self.assertEqual(self.b._damage(self.party[0], 100), 118)
        self.assertEqual(self.b._damage(self.party[0], 100, magic=True), 100)
        self.party[0].guarding = True
        self.assertEqual(self.b._damage(self.party[0], 100), 59)
        self.b.clear_effects()
        self.assertEqual(self.b._damage(self.party[0], 100), 100)

    def test_slow_changes_next_round_order_without_mutating_agi(self):
        actor = self.party[0]
        actor.agility = 20
        self.enemy.agility = 18
        self.use('slow')
        self.assertEqual(battle_agility(actor), 16)
        for member in self.party:
            if 'punch' not in member.skills:
                member.learn(self.skills['punch'])
        self.b.begin_round([Action(i, 'SKILL', 0, 'punch') for i in range(4)])
        order = list(self.b.queue)
        self.assertLess(order.index(('enemy', 0)), next(i for i, entry in enumerate(order)
                                                    if entry[0] == 'party' and entry[1].actor == 0))
        self.assertEqual(actor.agility, 20)

    def test_modifiers_refresh_coexist_expire_and_clear_on_battle_end(self):
        for ident in ('power_up', 'weaken', 'armor_break', 'slow'):
            self.use(ident)
        self.assertEqual(set(self.party[0].effects), {'weaken', 'armor_break', 'slow'})
        self.enemy.actions = [dict(id='attack', weight=1)]
        for remaining in (2, 1, 0):
            self.b.queue.append(('enemy', 0))
            self.b.step()
            self.assertEqual(self.enemy.effects.get('power_up', (1, 0))[1], remaining)
            self.assertTrue(all(turns == remaining for _, turns in self.party[0].effects.values()))
        self.assertFalse(self.party[0].effects or self.enemy.effects)
        self.use('guard'); self.use('slow')
        self.b.run_override = True
        self.b.attempt_run()
        self.assertFalse(self.enemy.guarding or self.party[0].effects)

    def test_unknown_disabled_and_unusable_actions_fallback_without_retry(self):
        for actions in (None, [], 7, [dict(id='missing', weight=2)],
                        [dict(id='attack', weight=0)], [dict(id='attack', weight=float('nan'))],
                        [dict(id='broken', weight=1)]):
            self.enemy.actions = actions
            self.b.enemy_actions['broken'] = replace(self.b.enemy_actions['attack'], type='not_implemented')
            self.party[0].hp = 1000
            self.enemy.magic_chance = 0
            self.b._enemy_action(0)
            self.assertEqual(self.party[0].hp, 900)

    def test_weight_selection_matches_ratio_and_json_edits_need_no_code_change(self):
        self.enemy.actions = [dict(id='attack', weight=65), dict(id='heavy_attack', weight=35)]
        rng = random.Random(22)
        counts = Counter(choose_enemy_action(self.enemy, self.b.enemy_actions, rng) for _ in range(10000))
        self.assertTrue(.33 < counts['heavy_attack']/10000 < .37)
        data = deepcopy(self.rows)
        row = next(row for row in data if row['id'] == 'goblin')
        row['actions'] = [dict(id='heavy_attack', weight=100)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'enemies.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            edited = json.loads(path.read_text())
        validate_enemy_action_lists(edited, self.b.enemy_actions)
        enemy = Enemy.from_definition(next(row for row in edited if row['id'] == 'goblin'))
        self.assertEqual(choose_enemy_action(enemy, self.b.enemy_actions, rng), 'heavy_attack')

    def test_action_definition_damage_multiplier_is_editable_json(self):
        raw = json.loads((ROOT/'data/enemy_actions.json').read_text(encoding='utf-8'))
        raw['heavy_attack']['power'] = 1.3
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'enemy_actions.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            self.b.enemy_actions = load_enemy_actions(path)
        self.use('heavy_attack')
        self.assertEqual(self.party[0].hp, 870)

    def test_requested_initial_assignments_and_boss_fallback(self):
        expected = {'slime': {'attack':100}, 'bat': {'attack':100},
                    'goblin': {'attack':90,'heavy_attack':10}, 'wisp': {'attack':30,'magic':70},
                    'golem': {'attack':85,'heavy_attack':15}, 'skeleton': {'attack':100},
                    'mage': {'attack':20,'magic':80}, 'iron_golem': {'attack':75,'guard':25},
                    'berserker': {'attack':65,'heavy_attack':35},
                    'assassin': {'attack':70,'double_attack':30},
                    'stone_beast': {'attack':65,'guard':20,'area_attack':15}}
        for row in self.rows:
            if row.get('boss'):
                continue  # Boss weights are covered by ENEMY & BOSS BALANCE PASS 01.
            if row['id'] not in expected and not row.get('boss'):
                continue  # Expansion assignments are checked in test_enemy_roster.
            actual = {a['id']: a['weight'] for a in row.get('actions', [])}
            self.assertEqual(actual, expected.get(row['id'], {}))
        self.assertEqual(len(self.rows), 25)

    def test_action_identity_is_independent_of_display_name(self):
        self.enemy.name = 'renamed for test'
        lines = self.use('heavy_attack')
        self.assertEqual(self.b.enemy_action_visual['enemy_id'], 'berserker')
        self.assertIn(self.enemy.name, lines[0])
        self.assertNotIn('berserker', lines[0])

    def test_dead_enemy_from_counter_does_not_continue_double_or_area_attack(self):
        self.party[0].counter = self.skills['counter']
        self.party[0].strength = 100
        self.enemy.hp = 1
        self.use('area_attack')
        self.assertEqual(self.enemy.hp, 0)
        self.assertEqual([actor.hp for actor in self.party[1:]], [1000, 1000, 1000])

    def test_special_action_effect_repeats_without_reapplying_damage_or_audio_wait(self):
        visual = BattlePresentation(self.b)
        before = [actor.hp for actor in self.party]
        self.use('double_attack')
        visual.after_action([True], before)
        self.assertEqual(visual.phase, 'enemy_effect')
        self.assertEqual(visual.enemy_effect_repeats, 2)
        after = [actor.hp for actor in self.party]
        surface = Mock()
        for _ in range(visual.enemy_effect_frames()):
            visual.draw_effect(surface)
            visual.advance()
        self.assertFalse(visual.active)  # Recoil now occurs once per hit, within enemy_effect.
        self.assertEqual([actor.hp for actor in self.party], after)
        self.assertEqual(surface.blt.call_count, 6)
        visual.started_at = time.monotonic() - MAX_PRESENTATION_SECONDS - 1
        visual.advance()
        self.assertFalse(visual.active)

    def test_area_effect_uses_all_living_positions_and_has_wall_timeout(self):
        visual = BattlePresentation(self.b)
        before = [actor.hp for actor in self.party]
        self.use('area_magic')
        visual.after_action([True], before)
        surface = Mock()
        visual.draw_effect(surface)
        self.assertEqual(surface.blt.call_count, 4)
        visual.started_at = time.monotonic() - MAX_PRESENTATION_SECONDS - 1
        visual.advance()
        self.assertEqual(visual.phase, 'party_hit')

    def test_special_lethal_hit_keeps_normal_sprite_until_recoil_finishes(self):
        import pyxel
        import test_battle_extra as fixtures
        fixture = fixtures.BattleExtraTests()
        fixture.setUp()
        app = fixture.app
        b = app.battle
        b.enemies[0].actions = [dict(id='heavy_attack', weight=100)]
        b.party[0].hp = 1
        b.queue.clear(); b.queue.append(('enemy', 0))
        app.state = 'resolve'
        with patch.object(b.rng, 'choice', return_value=b.party[0]):
            app.apply_visual_action()
        self.assertEqual(b.party[0].hp, 0)
        self.assertEqual(app.battle_visual().phase, 'enemy_effect')
        with patch.object(pyxel, 'blt', wraps=pyxel.blt) as blt:
            app.draw()
        self.assertIn((98,13,0,*b.party[0].sprite,16,16,0), [call.args for call in blt.call_args_list])
        self.assertNotIn((98,13,2,240,0,16,16,0), [call.args for call in blt.call_args_list])
        for _ in range(12):
            app.update_battle_visual()
        with patch.object(pyxel, 'blt', wraps=pyxel.blt) as blt:
            app.draw()
        self.assertIn((98,13,2,240,0,16,16,0), [call.args for call in blt.call_args_list])

    def test_invalid_json_is_rejected_with_clear_error(self):
        raw = json.loads((ROOT/'data/enemy_actions.json').read_text(encoding='utf-8'))
        for field, value in (('power',0),('hits',0),('type','sleep')):
            bad = deepcopy(raw)
            bad['attack'][field] = value
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'enemy_actions.json'
                path.write_text(json.dumps(bad), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_enemy_actions(path)
