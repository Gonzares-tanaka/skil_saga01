"""Visual-only differences, input-spam safety, per-hit recoil and bounded waits."""
from collections import deque
from dataclasses import replace
import time
import unittest
from unittest.mock import Mock, patch

import pyxel
import test_battle_extra as fixtures
from rpg.battle_presentation import (BattlePresentation, EFFECT_SPRITES, HIT_PIXELS,
    ENEMY_STEP_PIXELS, HEAVY_STEP_PIXELS, HEAVY_EFFECT_FRAMES, DOUBLE_HIT_CYCLE,
    DOUBLE_EFFECT_FRAMES, MAX_PRESENTATION_SECONDS)


class EnemyVisualTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.BattleExtraTests()
        fixture.setUp()
        self.app = fixture.app
        self.b = self.app.battle
        for actor in self.b.party:
            actor.hp = actor.max_hp = 1000
        self.enemy = self.b.enemies[0]
        self.enemy.hp = self.enemy.max_hp = 10000
        self.enemy.strength, self.enemy.intellect = 100, 80
        self.b.rng.choice = Mock(side_effect=lambda choices: choices[0])
        self.b.rng.uniform = Mock(return_value=1)
        self.app.state = 'resolve'

    def use(self, ident):
        self.app.battle_visual().reset()
        self.enemy.actions = [dict(id=ident, weight=1)]
        self.b.queue = deque([('enemy', 0)])
        self.app.apply_visual_action()
        return self.app.battle_visual()

    def test_attack_is_legacy_hit_with_small_lunge(self):
        v = self.use('attack')
        self.assertEqual(v.phase, 'party_hit')
        self.assertEqual(v.enemy_offset(0), ENEMY_STEP_PIXELS)
        self.assertEqual(v.actor_offset(0), HIT_PIXELS)
        surface = Mock()
        v.draw_effect(surface)
        surface.blt.assert_not_called()

    def test_heavy_lunge_is_larger_and_shake_is_three_short_frames(self):
        v = self.use('heavy_attack')
        self.assertEqual(v.effect, 'heavy_hit')
        self.assertEqual(self.app.shake_timer, 0)
        self.assertEqual(v.displayed_hp(0), 1000)
        for _ in range(3):
            self.assertEqual(v.shake_offset(), (0, 0))
            v.advance()
        self.assertEqual(v.enemy_offset(0), HEAVY_STEP_PIXELS)
        for _ in range(HEAVY_EFFECT_FRAMES - 3):
            v.advance()
        self.assertEqual(v.phase, 'party_hit')
        self.assertEqual(v.displayed_hp(0), 865)
        self.assertEqual(v.actor_offset(0), HIT_PIXELS)
        shakes = []
        for _ in range(3):
            shakes.append(v.shake_offset())
            v.advance()
        self.assertEqual(shakes, [(3, 0), (-2, 1), (1, -1)])
        self.assertEqual(v.shake_offset(), (0, 0))
        self.assertFalse(v.active)

    def test_double_hit_effects_and_reactions_are_separated_by_two_blank_frames(self):
        v = self.use('double_attack')
        effects, recoil = [], []
        hp = [c.hp for c in self.b.party]
        for tick in range(v.enemy_effect_frames()):
            surface = Mock()
            v.draw_effect(surface)
            if surface.blt.called:
                effects.append(tick)
            if v.actor_offset(0) == HIT_PIXELS:
                recoil.append(tick)
            v.advance()
        self.assertEqual(effects, [0, 1, 2, 8, 9, 10])
        self.assertEqual(recoil, [3, 11])
        self.assertEqual(hp, [880, 1000, 1000, 1000])
        self.assertEqual([c.hp for c in self.b.party], hp)
        self.assertFalse(v.active)

    def test_first_hit_ko_has_one_effect_one_reaction_and_no_retarget(self):
        self.b.party[0].hp = 1
        v = self.use('double_attack')
        self.assertEqual(v.enemy_effect_repeats, 1)
        self.assertEqual(v.enemy_effect_frames(), 6)
        self.assertEqual([c.hp for c in self.b.party], [0, 1000, 1000, 1000])
        for _ in range(3):
            self.assertTrue(v.holds_party_sprite(0))
            v.advance()
        self.assertTrue(v.party_recoiling(0))
        for _ in range(3):
            v.advance()
        self.assertFalse(v.holds_party_sprite(0))

    def test_magic_casts_in_place_and_uses_existing_target_effect(self):
        v = self.use('magic')
        self.assertEqual(v.phase, 'enemy_effect')
        self.assertEqual(v.effect, 'magic')
        surface = Mock()
        v.draw_effect(surface)
        surface.blt.assert_called_once_with(98, 13, 2, *EFFECT_SPRITES['magic'], 16, 16, 0)
        for _ in range(9):
            self.assertEqual(v.enemy_offset(0), 0)
            v.advance()
        self.assertEqual(v.phase, 'party_hit')

    def test_all_target_magic_and_physical_use_only_living_positions(self):
        for ident, effect in (('area_attack', 'blunt'), ('area_magic', 'magic')):
            with self.subTest(ident=ident):
                self.b.party[1].hp = 0
                v = self.use(ident)
                self.assertEqual(v.hit_targets, [0, 2, 3])
                surface = Mock()
                v.draw_effect(surface)
                self.assertEqual([c.args[:2] for c in surface.blt.call_args_list], [(98, 13), (98, 45), (98, 61)])
                self.assertEqual(v.effect, effect)
                for _ in range(9):
                    v.advance()
                self.assertEqual([v.actor_offset(i) for i in range(4)], [4, 0, 4, 4])

    def test_support_icons_are_distinct_and_do_not_cause_damage_or_recoil(self):
        expected = {'guard': 'guard', 'power_up': 'buff', 'weaken': 'debuff',
                    'armor_break': 'armor_down', 'slow': 'slow'}
        for ident, effect in expected.items():
            v = self.use(ident)
            self.assertEqual(v.effect, effect)
            self.assertFalse(v.hit_targets)
            self.assertEqual(v.enemy_offset(0), 0)
            self.assertEqual([c.hp for c in self.b.party], [1000] * 4)
            self.assertEqual(v.enemy_effect_targets[0][0], 'enemy' if ident in ('guard', 'power_up') else 'party')
        self.assertEqual(self.b.party[0].effects, {'armor_break': (.85, 1), 'slow': (.8, 2)})

    def test_missing_unknown_effect_uses_safe_default(self):
        for effect in (None, '', 'missing'):
            self.b.enemy_actions['magic'] = replace(self.b.enemy_actions['magic'], effect_id=effect)
            v = self.use('magic')
            self.assertEqual(v.effect, 'blunt')
            v.draw_effect(Mock())

    def test_fast_slow_and_spam_inputs_do_not_skip_visual_or_reapply_damage(self):
        for fast in (False, True):
            for ident in self.b.enemy_actions:
                with self.subTest(fast=fast, action=ident):
                    for c in self.b.party:
                        c.hp = 1000; c.effects.clear()
                    v = self.use(ident)
                    hp = [c.hp for c in self.b.party]
                    self.b.queue.append(('enemy', 0))
                    self.app.confirm = lambda: fast
                    self.app.confirm_held = lambda: fast
                    self.app.cancel = lambda: True
                    self.app.direction = lambda horizontal=False: 1
                    ticks = 0
                    with patch.object(self.b, 'step', side_effect=AssertionError('resolved twice')):
                        while v.active:
                            self.app.update(); self.app.draw()
                            ticks += 1
                            self.assertLess(ticks, 50)
                    self.assertGreaterEqual(ticks, 3 if ident == 'attack' else 6)
                    self.assertEqual([c.hp for c in self.b.party], hp)
                    self.assertEqual(len(self.b.queue), 1)
                    self.assertEqual(self.app.state, 'resolve')

    def test_counter_death_is_deferred_until_effect_and_recoil_finish(self):
        self.b.party[0].counter = self.b.skills['counter']
        self.b.party[0].strength = 100
        self.enemy.hp = 1
        with patch('rpg.app.play_cue') as cue:
            v = self.use('double_attack')
            self.assertEqual(v.enemy_effect_repeats, 1)
            self.assertEqual(v.enemy_visual(0), (True, 0))
            self.assertNotIn(('enemy_defeat',), [c.args for c in cue.call_args_list])
            for _ in range(6):
                self.app.update_battle_visual()
            self.assertEqual(v.phase, 'enemy_death')
            self.assertEqual(sum(c.args == ('enemy_defeat',) for c in cue.call_args_list), 1)
            for _ in range(18):
                self.app.update_battle_visual()
            self.assertFalse(v.active)

    def test_damage_calls_are_exactly_once_or_twice_and_never_animation_driven(self):
        for ident, count in (('heavy_attack', 1), ('magic', 1), ('double_attack', 2),
                             ('area_attack', 3), ('area_magic', 3)):
            for c in self.b.party:
                c.hp = 1000
            self.b.party[3].hp = 0
            with patch.object(self.b, '_damage', wraps=self.b._damage) as damage:
                v = self.use(ident)
                while v.active:
                    self.app.update_battle_visual(); self.app.draw()
                self.assertEqual(damage.call_count, count)

    def test_all_visuals_have_wall_timeout_under_unavailable_audio(self):
        for ident in self.b.enemy_actions:
            with patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
                 patch.object(pyxel, 'play_pos', side_effect=RuntimeError('closed')):
                v = self.use(ident)
                ticks = 0
                while v.active:
                    v.started_at = time.monotonic() - MAX_PRESENTATION_SECONDS - 1
                    self.app.update_battle_visual()
                    ticks += 1
                    self.assertLess(ticks, 4)


if __name__ == '__main__':
    unittest.main()
