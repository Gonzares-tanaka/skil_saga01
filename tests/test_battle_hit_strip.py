"""Real damage -> recoil -> KO; strip bounds and adjusted editable sound."""
from collections import deque
import time
import unittest
from unittest.mock import patch
import pyxel
import test_battle_extra as fixtures
from rpg.battle_presentation import (HIT_PIXELS,HIT_FRAMES,STEP_PIXELS,STEP_FRAMES,BATTLE_FLOOR_STRIPS,
                                     BATTLE_STRIP_Y,draw_battle_background)
from rpg.sound import SOUND_ENEMY_DEFEAT,ATTACK_SOUND,init_sound


class HitStripTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.BattleExtraTests()
        fixture.setUp()
        self.app=fixture.app
        self.app.state,self.app.delay='resolve',0
        self.app.battle.queue=deque([('enemy',0)])
        self.app.pending.clear()

    def hit(self,index=0):
        with patch.object(self.app.battle.rng,'choice',return_value=self.app.session.party[index]):
            self.app.apply_visual_action()

    def test_actual_damage_moves_only_target_four_pixels_and_returns_in_three_frames(self):
        self.assertLess(HIT_PIXELS,STEP_PIXELS)
        self.assertLess(HIT_FRAMES,STEP_FRAMES)
        a=self.app
        for index in (0,1,0,1):
            a.battle.queue=deque([('enemy',0)])
            a.session.party[index].hp=a.session.party[index].max_hp
            self.hit(index)
            v=a.battle_visual()
            self.assertEqual(v.phase,'party_hit')
            self.assertEqual([v.actor_offset(i) for i in range(4)],
                             [HIT_PIXELS if i==index else 0 for i in range(4)])
            for _ in range(HIT_FRAMES):a.update_battle_visual()
            self.assertFalse(v.active)
            self.assertEqual([v.actor_offset(i) for i in range(4)],[0]*4)

    def test_damage_to_zero_shows_normal_sprite_during_recoil_then_ko(self):
        a=self.app
        a.session.party[0].hp=1
        self.hit()
        self.assertEqual(a.session.party[0].hp,0)
        with patch.object(pyxel,'blt',wraps=pyxel.blt) as blit:
            a.draw()
        self.assertIn((102,13,0,*a.session.party[0].sprite,16,16,0),[c.args for c in blit.call_args_list])
        self.assertFalse(any(c.args[:5]==(98,13,2,240,0) for c in blit.call_args_list))
        for _ in range(HIT_FRAMES):a.update_battle_visual()
        with patch.object(pyxel,'blt',wraps=pyxel.blt) as blit:
            a.draw()
        self.assertIn((98,13,2,240,0,16,16,0),[c.args for c in blit.call_args_list])

    def test_multiple_hp_changes_move_only_those_targets_simultaneously(self):
        a=self.app
        hp=[c.hp for c in a.session.party]
        a.session.party[0].hp-=1
        a.session.party[2].hp-=1
        v=a.battle_visual()
        v.after_action([e.alive for e in a.battle.enemies],hp)
        self.assertEqual(v.hit_targets,[0,2])
        self.assertEqual([v.actor_offset(i) for i in range(4)],[4,0,4,0])

    def test_heal_buff_and_zero_damage_do_not_trigger_knockback(self):
        a=self.app
        hp=[c.hp for c in a.session.party]
        a.session.party[0].hp-=1
        hp[0]=a.session.party[0].hp
        a.session.party[0].hp+=1
        v=a.battle_visual()
        v.after_action([True]*len(a.battle.enemies),hp)
        self.assertFalse(v.hit_targets)
        self.assertFalse(v.active)
        v.after_action([True]*len(a.battle.enemies),[c.hp for c in a.session.party])
        self.assertFalse(v.active)

    def test_guard_hit_still_recoils_without_changing_damage_rules(self):
        self.app.session.party[0].guarding=True
        self.hit()
        self.assertEqual(self.app.battle_visual().hit_targets,[0])
        self.assertEqual(self.app.battle_visual().actor_offset(0),4)

    def test_recoil_locks_inputs_and_defers_next_enemy_and_result(self):
        a=self.app
        self.hit()
        a.battle.queue=deque([('enemy',0)])
        with patch.object(a.battle,'step',side_effect=AssertionError('next action ran early')):
            for _ in range(HIT_FRAMES):
                a.update()
                self.assertEqual(a.state,'resolve')
        self.assertEqual(len(a.battle.queue),1)
        self.assertFalse(a.session.settled)

    def test_silent_recoil_and_resume_timeout_always_finish(self):
        with patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
             patch.object(pyxel,'play_pos',side_effect=RuntimeError('closed')):
            self.hit()
            self.app.battle_visual().started_at=time.monotonic()-1
            self.app.update()
        self.assertFalse(self.app.battle_visual().active)

    def test_counter_death_cue_waits_until_actual_death_phase_and_runs_once(self):
        a=self.app
        def counter_hit():
            a.session.party[0].hp-=1
            a.battle.enemies[0].hp=0
            return []
        with patch.object(a.battle,'step',side_effect=counter_hit),patch('rpg.app.play_cue') as cue:
            a.apply_visual_action()
            self.assertEqual(a.battle_visual().phase,'party_hit')
            self.assertNotIn(('enemy_defeat',),[c.args for c in cue.call_args_list])
            for _ in range(HIT_FRAMES):a.update_battle_visual()
            self.assertEqual(a.battle_visual().phase,'enemy_death')
            self.assertEqual(sum(c.args==('enemy_defeat',) for c in cue.call_args_list),1)
            for _ in range(18):a.update_battle_visual()
            self.assertEqual(sum(c.args==('enemy_defeat',) for c in cue.call_args_list),1)

    def test_strip_is_one_96_by_16_image_and_does_not_touch_upper_field_or_ui(self):
        for area,(bank,u,v,w,h) in BATTLE_FLOOR_STRIPS.items():
            self.assertEqual((w,h),(96,16))
            pyxel.images[bank].pset(u+95,v+15,3)
            pyxel.cls(0)
            with patch.object(pyxel,'blt',wraps=pyxel.blt) as blit:
                draw_battle_background(pyxel,area)
            blit.assert_called_once_with(0,BATTLE_STRIP_Y,bank,u,v,96,16)
            self.assertEqual(pyxel.pget(95,79),3)
            self.assertTrue(all(pyxel.pget(x,y)==0 for y in range(11,64) for x in range(96)))
            self.assertTrue(all(pyxel.pget(x,y)==0 for y in range(64,80) for x in range(96,160)))
            self.assertEqual(pyxel.pget(0,80),0)

    def test_editing_one_strip_does_not_modify_the_other_areas(self):
        bank,u,v,_,_=BATTLE_FLOOR_STRIPS[1]
        others=[pyxel.images[2].pget(95,sy+15) for _,_,sy,_,_ in list(BATTLE_FLOOR_STRIPS.values())[1:]]
        pyxel.images[bank].pset(u+95,v+15,3)
        self.assertEqual(others,[pyxel.images[2].pget(95,sy+15) for _,_,sy,_,_ in list(BATTLE_FLOOR_STRIPS.values())[1:]])

    def test_defeat_sound_is_longer_lower_and_not_overwritten_at_startup(self):
        s=pyxel.sounds[SOUND_ENEMY_DEFEAT]
        snapshot=(list(s.notes),list(s.tones),list(s.volumes),list(s.effects),s.speed)
        self.assertTrue(0.2<=s.total_sec()<=0.4)
        self.assertGreater(s.total_sec(),pyxel.sounds[ATTACK_SOUND].total_sec()*3)
        self.assertLess(sum(s.notes)/len(s.notes),sum(pyxel.sounds[ATTACK_SOUND].notes)/len(pyxel.sounds[ATTACK_SOUND].notes))
        init_sound()
        self.assertEqual(snapshot,(list(s.notes),list(s.tones),list(s.volumes),list(s.effects),s.speed))


if __name__=='__main__':unittest.main()
