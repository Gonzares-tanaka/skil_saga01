"""Presentation duration/faults/input, real key action and drawing boundaries."""
from collections import deque
import time
import unittest
from unittest.mock import patch

import pyxel
import test_final_battle as fixtures
from rpg.final_presentation import (FinalPresentation, AMRITA_EFFECT_FRAMES,
                                   AMRITA_EFFECT_MAX_SECONDS, AMRITA_FLASH_FRAMES)
from rpg.models import Action
from rpg.text import font


class FinalPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.FinalBattleTests.setUpClass()
        font()

    def setUp(self):
        self.f = fixtures.FinalBattleTests()
        self.f.setUp()
        self.b = self.f.launch()
        self.a = self.f.a

    def release(self):
        self.b.begin_round(self.f.actions(Action(0, 'ITEM', item_id='AMRITA')))
        self.a.state, self.a.delay, self.a.log = 'resolve', 0, []
        self.a.pending = deque()
        for _ in range(60):
            self.f.press(pyxel.KEY_Z)
            if self.a.state == 'amrita_effect':
                return
        self.fail('Actual key action did not start presentation')

    def test_actual_key_releases_model_before_visual_wait_and_freezes_other_actions(self):
        self.release()
        self.assertFalse(self.b.elysion_barrier_active)
        self.assertTrue(self.f.d.finale.has_amrita)
        queue = list(self.b.queue)
        round_number = self.b.round
        # Includes overlay hotkeys; neither held A nor repeated inputs can skip it.
        for key in (pyxel.KEY_Z, pyxel.KEY_X, pyxel.KEY_UP, pyxel.KEY_DOWN,
                    pyxel.KEY_D, pyxel.KEY_H, pyxel.KEY_F9, pyxel.KEY_F3):
            self.f.press(key)
            self.assertEqual(self.a.state, 'amrita_effect')
            self.assertIsNone(self.a.overlay)
            self.assertEqual(list(self.b.queue), queue)
            self.assertEqual(self.b.round, round_number)

    def test_effect_completes_at_fixed_frame_count_and_requires_release_afterwards(self):
        self.release()
        for _ in range(AMRITA_EFFECT_FRAMES - 1):
            self.f.press(pyxel.KEY_Z)
            self.assertEqual(self.a.state, 'amrita_effect')
        self.f.press(pyxel.KEY_X)
        self.assertEqual(self.a.state, 'resolve')
        self.assertFalse(self.a.final_visual().active)
        self.assertTrue(self.a.battle_input_blocked)
        with patch.object(pyxel, 'btn', return_value=True):
            self.a.update()
        self.assertTrue(self.a.battle_input_blocked)
        self.f.press()
        self.assertFalse(self.a.battle_input_blocked)
        self.f.press(pyxel.KEY_Z)
        self.assertEqual(self.a.state, 'resolve')

    def test_background_time_deadline_releases_without_audio_or_render(self):
        self.release()
        self.a.final_visual().started_at = time.monotonic() - AMRITA_EFFECT_MAX_SECONDS - 1
        with patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
             patch.object(pyxel, 'playm', side_effect=RuntimeError('interrupted')), \
             patch.object(pyxel, 'stop', side_effect=RuntimeError('closed')):
            self.f.press()
        self.assertEqual(self.a.state, 'resolve')
        self.assertFalse(self.b.elysion_barrier_active)

    def test_draw_fault_releases_effect_and_palette_camera_cleanup(self):
        self.release()
        with patch.object(self.a.final_visual(), 'draw_light', side_effect=RuntimeError('draw failure')), \
             patch.object(pyxel, 'pal') as pal, patch.object(pyxel, 'camera') as camera:
            self.a.draw()
        self.assertEqual(self.a.state, 'resolve')
        self.assertFalse(self.b.elysion_barrier_active)
        pal.assert_called_with()
        camera.assert_called_with()

    def test_effect_update_fault_also_releases_without_losing_amrita(self):
        self.release()
        with patch.object(self.a.final_visual(), 'advance', side_effect=RuntimeError('timer fault')):
            self.f.press()
        self.assertEqual(self.a.state, 'resolve')
        self.assertFalse(self.b.elysion_barrier_active)
        self.assertTrue(self.f.d.finale.has_amrita)

    def test_effect_initialization_fault_keeps_resolved_key_and_queue(self):
        with patch.object(self.a, 'final_visual', side_effect=RuntimeError('missing presentation')):
            self.b.elysion_barrier_active = False  # Already-applied model action.
            self.a.start_amrita_effect()
        self.assertEqual(self.a.state, 'resolve')
        self.assertFalse(self.b.elysion_barrier_active)

    def test_retry_discards_animation_and_restores_barrier_visual(self):
        self.release()
        old = self.a.final_visual()
        old.frame = 32
        self.f.fail()
        self.f.press(pyxel.KEY_Z)
        self.assertTrue(self.a.battle.elysion_barrier_active)
        self.assertTrue(self.f.d.finale.has_amrita)
        self.assertIsNone(self.a.final_presentation)
        new = self.a.final_visual()
        self.assertIsNot(new, old)
        self.assertFalse(new.active)
        self.assertEqual(new.frame, 0)
        with patch.object(pyxel, 'pset') as dots:
            new.draw_boss(pyxel, self.a.battle.enemies[0], True)
        self.assertGreater(dots.call_count, 0)

    def test_sprite_barrier_and_fragments_fit_left_field_and_palette_is_four_colors(self):
        v = self.a.final_visual()
        self.assertEqual(v.bounds(), (24, 24, 48, 48))
        v.start()
        for frame in range(AMRITA_EFFECT_FRAMES):
            v.frame = frame
            with patch.object(pyxel, 'blt') as blt, patch.object(pyxel, 'pset') as pset:
                v.draw_boss(pyxel, self.b.enemies[0], False)
            x, y, bank, u, w_y, width, height, colkey = blt.call_args.args
            self.assertTrue(0 <= x and x + width < 97 and 21 <= y and y + height < 80)
            self.assertEqual((bank, u, w_y, width, height), (0, 144, 64, 48, 48))
            for call in pset.call_args_list:
                x, y, color = call.args
                self.assertTrue(2 <= x <= 93 and 21 <= y <= 77)
                self.assertIn(color, (1, 2, 3))

    def test_inactive_released_barrier_draws_no_shell_and_flash_uses_brightest_color(self):
        v = self.a.final_visual()
        with patch.object(pyxel, 'pset') as pset:
            v.draw_boss(pyxel, self.b.enemies[0], False)
        pset.assert_not_called()
        v.start()
        for frame in AMRITA_FLASH_FRAMES:
            v.frame = frame
            with patch.object(pyxel, 'rect') as rect:
                v.draw_light(pyxel)
            rect.assert_called_once_with(0, 0, 160, 120, 3)

    def test_normal_item_never_starts_amrita_effect_and_normal_sprites_stay_16px(self):
        self.b.elysion_barrier_active = False
        self.f.s.party[0].hp = 1
        self.b.begin_round(self.f.actions(Action(0, 'ITEM', 0, item_id='POTION')))
        self.a.state, self.a.delay, self.a.log = 'resolve', 0, []
        for _ in range(80):
            self.f.press(pyxel.KEY_Z)
            self.assertNotEqual(self.a.state, 'amrita_effect')
            if self.a.state == 'command':
                break
        self.b.outcome = 'ESCAPE'
        self.f.s.settle()
        self.a.begin_encounter()
        with patch.object(pyxel, 'blt') as blt:
            self.a.draw_battle()
        for call in blt.call_args_list:
            self.assertEqual(call.args[5:7], (16, 16))

    def test_sprite_metadata_rejects_size_that_would_cover_ui(self):
        data = dict(self.a.final_battle_data)
        data['boss_sprite'] = dict(data['boss_sprite'], width=64)
        with self.assertRaises(ValueError):
            FinalPresentation(data)


if __name__ == '__main__':
    unittest.main()
