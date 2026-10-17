"""Escape/death presentation and one-way result flow, without changing rules."""
from collections import deque
from copy import deepcopy
import time
import unittest
from unittest.mock import patch
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Action
from rpg.battle_presentation import (RUN_FRAMES, RUN_PIXELS, BATTLE_FLOOR_STRIPS,
                                     battle_area, draw_battle_background, result_pages)
from rpg.sound import SOUND_RUN_SUCCESS, SOUND_ENEMY_DEFEAT
from rpg.save import make_save_data


class BattleExtraTests(unittest.TestCase):
    def setUp(self):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True)
            pyxel._tests_initialized=True
        with patch.object(pyxel,'init'):
            self.app=DungeonApp(Session(*load_content(),seed=74),run=False,headless=True,start_at_title=False)
        self.app.begin_encounter()
        self.app.confirm=lambda:True
        self.app.cancel=lambda:True
        self.app.confirm_held=lambda:True
        self.app.direction=lambda horizontal=False:0
        self.app.pressed=lambda *args:False

    def run_action(self,success=True):
        self.app.cursor=3
        self.app.battle.run_override=success
        self.app.update()

    def test_run_mirrors_all_four_and_moves_right_then_returns_directly_to_map(self):
        a=self.app
        a.session.party[1].hp=0
        before=deepcopy([(c.hp,c.skill_uses) for c in a.session.party])
        items=deepcopy(a.session.inventory.counts)
        with patch.object(pyxel,'play') as sound:
            self.run_action()
            self.assertEqual(a.battle_visual().phase,'run_success')
            sound.assert_called_once_with(0,SOUND_RUN_SUCCESS)
            for _ in range(7):a.update()
            offset=a.battle_visual().actor_offset(0)
            self.assertGreater(offset,0)
            self.assertLessEqual(offset,RUN_PIXELS)
            with patch.object(pyxel,'blt',wraps=pyxel.blt) as blit:
                a.draw()
            sprites=[c.args for c in blit.call_args_list if c.args[0]==98+offset and c.args[1] in (13,29,45,61)]
            self.assertEqual(len(sprites),4)
            self.assertTrue(all(args[5:7]==(-16,16) for args in sprites))
            for _ in range(RUN_FRAMES-7-1):
                a.update()
                self.assertEqual(a.state,'resolve')
                self.assertFalse(a.session.settled)
            a.update()
            self.assertEqual(a.state,'explore')
            self.assertEqual(a.session.completed,1)
            self.assertEqual(sum(c.args[0] == 0 for c in sound.call_args_list), 1)  # BGM resumes separately on 1-3.
        self.assertEqual([(c.hp,c.skill_uses) for c in a.session.party],before)
        self.assertEqual(a.session.inventory.counts,items)

    def test_failed_run_does_not_flip_move_or_play_success_sound(self):
        with patch.object(pyxel,'play') as sound:
            self.run_action(False)
            self.assertFalse(self.app.battle_visual().active)
            self.assertTrue(self.app.battle.queue)
            self.assertIsNone(self.app.battle.outcome)
            self.assertEqual([self.app.battle_visual().actor_offset(i) for i in range(4)],[0]*4)
            sound.assert_not_called()

    def test_silent_run_fixed_frames_and_resume_timeout_both_release_exploration(self):
        with patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
             patch.object(pyxel,'stop',side_effect=RuntimeError('closed')):
            self.run_action()
            for _ in range(RUN_FRAMES):self.app.update()
            self.assertEqual(self.app.state,'explore')
            self.assertEqual(self.app.session.completed,1)
            self.app.begin_encounter()
            self.run_action()
            self.app.battle_visual().started_at=time.monotonic()-1
            self.app.update()
            self.assertEqual(self.app.state,'explore')
            self.assertEqual(self.app.session.completed,2)

    def test_defeat_sound_occurs_once_when_death_phase_starts(self):
        a=self.app
        a.battle.enemies[0].hp=1
        a.session.party[0].strength=100
        a.battle.queue=deque([('party',Action(0,'SKILL',0,'punch'))])
        a.state,a.delay='resolve',0
        with patch.object(pyxel,'play') as sound:
            for _ in range(60):
                a.update()
                if not a.battle_visual().active and not a.battle.queue:break
            self.assertEqual(sum(c.args==(0,SOUND_ENEMY_DEFEAT) for c in sound.call_args_list),1)
        self.assertFalse(a.battle.enemies[0].alive)

    def test_simultaneous_deaths_have_one_cue_and_independent_enemy_visibility(self):
        a=self.app
        def hit():
            for enemy in a.battle.enemies:enemy.hp=0
            return []
        with patch.object(a.battle,'step',side_effect=hit),patch('rpg.app.play_cue') as cue:
            a.apply_visual_action()
        self.assertEqual(a.battle_visual().deaths,list(range(len(a.battle.enemies))))
        self.assertEqual(sum(c.args==('enemy_defeat',) for c in cue.call_args_list),1)

    def test_special_final_battle_does_not_receive_generic_death_sound(self):
        a=self.app
        a.battle.is_elysion_battle=True
        with patch.object(a.battle,'step',side_effect=lambda: setattr(a.battle.enemies[0],'hp',0) or []), \
             patch('rpg.app.play_cue') as cue:
            a.apply_visual_action()
        self.assertNotIn(('enemy_defeat',),[c.args for c in cue.call_args_list])
        self.assertFalse(a.battle_visual().deaths)

    def test_all_15_floors_choose_matching_background_including_boss_floors(self):
        self.assertEqual([battle_area(f) for f in range(15)],[1]*5+[2]*5+[3]*5)
        for floor in (4,9,14):
            self.app.session.settled=True
            self.app.dungeon.floor=floor
            self.app.begin_encounter()
            self.assertEqual(self.app.battle_background_area,floor//5+1)

    def test_editor_background_pixels_appear_and_outside_bounds_is_untouched(self):
        _,u,v,_,_=BATTLE_FLOOR_STRIPS[2]
        sample = pyxel.images[2].pget(u+32,v)
        marker = (sample+1)%4
        pyxel.images[2].pset(u,v,marker)
        pyxel.cls(0)
        draw_battle_background(pyxel,2)
        self.assertEqual(pyxel.pget(0,64),marker)
        self.assertEqual(pyxel.pget(32,64),sample)
        self.assertEqual(pyxel.pget(0,11),0)
        self.assertEqual(pyxel.pget(96,11),0)
        self.assertEqual(pyxel.pget(0,80),0)

    def test_growth_pages_precede_spark_summary_without_mutating_stats(self):
        party=self.app.session.party
        before=deepcopy(party)
        pages=result_pages([f'{party[0].name} HP +4',f'{party[0].name} INT +1',f'{party[1].name} STR +1','閃き! FIRE'],party)
        self.assertEqual([p['kind'] for p in pages],['growth','growth','summary'])
        self.assertEqual(party,before)

    def finish_replacement(self,decline=False,multiple=False):
        a=self.app
        a.battle.outcome='VICTORY'
        a.session.settings['spark_chance']=0
        original_settle=a.session.settle
        with patch.object(a.session,'settle',wraps=original_settle) as settle:
            a.set_result_pages(a.session.settle())
            for i in ((0,1) if multiple else (0,)):
                c=a.session.party[i]
                c.pending_skill='meteor'
                a.session.discovered_skills.add('meteor')
            stats=[(c.hp,c.max_hp,c.strength,c.agility,c.intellect) for c in a.session.party]
            a.state='replace'
            a.replacement_confirm=True
            a.replacement_cursor=len(a.session.party[0].skills) if decline else 0
            a.update_replacement(True,False)
            if multiple:
                self.assertEqual(a.state,'replace')
                a.replacement_confirm=True
                a.replacement_cursor=0
                a.update_replacement(True,False)
            self.assertEqual(a.state,'explore')
            self.assertEqual(settle.call_count,1)
            self.assertEqual(stats,[(c.hp,c.max_hp,c.strength,c.agility,c.intellect) for c in a.session.party])
            self.assertFalse(a.session.pending_replacements)
        return a

    def test_replacement_accept_finishes_without_rebuilding_growth_or_resettling(self):
        a=self.finish_replacement()
        self.assertIn('meteor',a.session.party[0].skills)

    def test_replacement_decline_also_finishes_without_replaying_growth(self):
        a=self.finish_replacement(decline=True)
        self.assertNotIn('meteor',a.session.party[0].skills)

    def test_multiple_replacements_complete_before_returning_to_exploration(self):
        self.finish_replacement(multiple=True)

    def test_replacement_after_boss_uses_existing_after_battle_dialogue(self):
        self.app.session.settled=True
        self.app.dungeon.floor=4
        self.app.begin_encounter(boss=True)
        a=self.app
        a.battle.outcome='VICTORY'
        a.session.settle()
        a.session.party[0].pending_skill='meteor'
        a.replacement_confirm=True
        a.replacement_cursor=0
        a.state='replace'
        a.update_replacement(True,False)
        self.assertEqual(a.state,'boss_after')

    def test_save_keeps_transient_presentation_out_of_schema(self):
        self.run_action()
        for _ in range(RUN_FRAMES):self.app.update()
        self.app.enter_camp()
        data=make_save_data(self.app)
        self.assertFalse(any(word in key for key in data for word in ('animation','growth_result','background','presentation')))


if __name__=='__main__':unittest.main()
