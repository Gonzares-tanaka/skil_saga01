"""Predrawn intervals, actual grid moves, event priority and exact resume."""
from copy import deepcopy
import json
import random
import statistics
from unittest.mock import patch
import pyxel

from tests.encounter_fixture import EncounterFixture
from tests.encounter_preservation import assert_encounter_preserved
from rpg.dungeon import Dungeon
from rpg.elevator import arrival_point
from rpg.save import make_save_data, prepare_saved_game, SaveError
from rpg.suspend import job_result
from rpg.final_battle import FinalBattleCheckpoint
from rpg.tiles import (FLOOR_TILES,TILE_STAIRS_DOWN,TILE_BOSS,TILE_POISON,
                       TILE_PIT,TILE_CHEST,TILE_HEAL_POINT,TILE_SWITCH)


class Encounter04Tests(EncounterFixture):
    def test_both_endpoints_and_exact_nth_move_all_areas_and_debug(self):
        for floor in (0,4,5,9,10,13):
            low,high = self.d.settings['encounter_step_ranges'][floor//5]
            for debug in (False,True):
                for n in (low,high,12):
                    with self.subTest(floor=floor,debug=debug,n=n):
                        start,delta = self.pair(floor)
                        with patch.object(self.d.rng,'randint',return_value=n) as draw:
                            self.d.reset_encounter()
                            draw.assert_called_once_with(low,high)
                        with patch.object(self.d.rng,'random',side_effect=AssertionError('per-step roll')):
                            for i in range(1,n+1):
                                self.assertEqual(self.walk(start,delta,debug),'battle' if i==n else '')
                                self.assertEqual(self.d.encounter_remaining,n-i)

    def test_invalid_wall_and_facing_only_preserve_count_and_rng(self):
        d = self.d
        x,y,dx,dy = next((x,y,dx,dy) for x,y in sorted(d.reachable(0))
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))
            if d.tile(0,x,y) in FLOOR_TILES and not d.can_enter(0,x+dx,y+dy))
        d.x,d.y,d.encounter_remaining = x,y,12
        before = d.steps,d.encounter_remaining,d.rng.getstate()
        for delta in ((dx,dy),(0,0),(1,1),(2,0)):
            d.move(*delta)
            self.assertEqual((d.steps,d.encounter_remaining,d.rng.getstate()),before)
        button = {(1,0):pyxel.KEY_RIGHT,(-1,0):pyxel.KEY_LEFT,(0,1):pyxel.KEY_DOWN,(0,-1):pyxel.KEY_UP}[dx,dy]
        self.tick(button)
        self.assertEqual((d.steps,d.encounter_remaining,d.rng.getstate()),before)

    def test_wait_menu_status_and_item_do_not_consume(self):
        self.pair()
        a,d = self.a,self.d
        before = d.steps,d.encounter_remaining,d.rng.getstate()
        for _ in range(120): self.tick()
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        for _ in range(20): self.tick()
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((d.steps,d.encounter_remaining,d.rng.getstate()),before)

    def test_held_pad_counts_cells_not_frames(self):
        d,a = self.d,self.a
        for floor in range(14):
            w,h = d.map_bounds(floor)
            chosen = next(((x,y) for y in range(h) for x in range(w-8)
                if all(d.tile(floor,x+i,y) in FLOOR_TILES for i in range(9))),None)
            if chosen:
                d.floor,d.x,d.y = floor,*chosen
                break
        self.assertIsNotNone(chosen)
        d.encounter_remaining = 16
        steps = d.steps
        for frame in range(30):
            def held(key,hold=0,repeat=0):
                return key==pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT and (frame==0 or
                    bool(repeat) and frame>=hold and (frame-hold)%repeat==0)
            with patch.object(pyxel,'btn',return_value=False),patch.object(pyxel,'btnp',side_effect=held):
                a.update()
        self.assertEqual(d.steps-steps,8)
        self.assertEqual((d.x,d.y),(chosen[0]+8,chosen[1]))
        self.assertEqual(d.encounter_remaining,8)

    def test_moved_event_tiles_count_once_no_double_event_battle(self):
        d = self.d
        start,delta = self.pair()
        destination = start[0]+delta[0],start[1]+delta[1]
        for tile in (TILE_POISON,TILE_CHEST,TILE_HEAL_POINT,TILE_SWITCH,TILE_PIT):
            with self.subTest(tile=tile):
                d.maps[0].pset(*destination,tile)
                d.x,d.y,d.encounter_remaining = *start,1
                steps = d.steps
                self.assertNotEqual(d.move(*delta)[0],'battle')
                self.assertEqual(d.steps,steps+1)
                self.assertEqual(d.encounter_remaining,0)

    def test_stair_confirm_loops_do_not_reset_or_consume(self):
        d = self.d
        for budget in (0,3,12):
            d.floor,d.encounter_remaining = 0,budget
            d.x,d.y = d.find(0,TILE_STAIRS_DOWN)
            before = d.steps,d.rng.getstate()
            for _ in range(20):
                self.assertEqual(d.interact()[0],'stairs')
                self.assertEqual(d.encounter_remaining,budget)
                self.assertEqual((d.steps,d.rng.getstate()),before)
            self.assertEqual(d.floor,0)

    def test_step_onto_stair_counts_once_and_arrival_no_encounter(self):
        d = self.d
        stairs = d.find(0,TILE_STAIRS_DOWN)
        start = next((stairs[0]+dx,stairs[1]+dy) for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))
            if d.tile(0,stairs[0]+dx,stairs[1]+dy) in FLOOR_TILES)
        d.x,d.y,d.encounter_remaining = *start,1
        before = d.steps,d.rng.getstate()
        self.assertEqual(d.move(stairs[0]-start[0],stairs[1]-start[1])[0],'stairs')
        self.assertEqual((d.floor,d.encounter_remaining,d.steps),(1,0,before[0]+1))
        self.assertEqual(d.rng.getstate(),before[1])
        start,delta = self.pair(1)
        self.assertEqual(self.walk(start,delta),'battle')

    def test_area_crossing_preserves_remainder_then_draws_destination_area(self):
        d = self.d
        d.defeated_bosses.update((4,9))
        for source,destination in ((4,5),(5,4),(9,10),(10,9)):
            d.floor,d.encounter_remaining = source,5
            rng = d.rng.getstate()
            self.assertEqual(d.change_floor(destination)[0],'stairs')
            self.assertEqual(d.encounter_remaining,5)
            self.assertEqual(d.rng.getstate(),rng)
            start,delta = self.pair(destination)
            for i in range(5):
                self.assertEqual(self.walk(start,delta),'battle' if i==4 else '')
            low,high = d.settings['encounter_step_ranges'][destination//5]
            with patch.object(d.rng,'randint',return_value=high) as draw:
                d.reset_encounter()
                draw.assert_called_once_with(low,high)

    def test_normal_escape_draw_hunt_finish_redraw_once_without_audio(self):
        for outcome,kind in (('VICTORY','normal'),('ESCAPE','normal'),('DRAW','normal'),('VICTORY','quest_hunt')):
            with self.subTest(outcome=outcome,kind=kind):
                with patch.object(self.d,'reset_encounter',wraps=self.d.reset_encounter) as draw:
                    self.finish(outcome=outcome,kind=kind)
                    draw.assert_called_once_with()
                self.assertTrue(7 <= self.d.encounter_remaining <=16)

    def test_b5_b10_boss_exit_redraw_story_does_not_redraw(self):
        for floor in (4,9):
            self.finish(floor,boss=True)
            self.assertEqual(self.a.state,'boss_after')
            low,high = self.d.settings['encounter_step_ranges'][floor//5]
            remaining,rng = self.d.encounter_remaining,self.d.rng.getstate()
            self.assertTrue(low <= remaining <= high)
            for _ in range(10):
                if self.a.state=='explore': break
                self.tick(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(self.a.state,'explore')
            self.assertEqual((self.d.encounter_remaining,self.d.rng.getstate()),(remaining,rng))

    def test_b15_never_random_but_guardians_and_demon_work(self):
        a,d = self.a,self.d
        start,delta = self.pair(14)
        d.encounter_remaining = 1
        for _ in range(100): self.assertEqual(self.walk(start,delta),'')
        self.assertEqual(d.encounter_remaining,0)
        d.finale.guardians_defeated = True
        a.state,a.message_lines,a.message_page = 'guardian_after',['道が開いた。'],0
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state,'explore')
        d.x,d.y = d.find(14,TILE_BOSS)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state,'boss_message')

    def test_hunt_contact_owns_due_random_step_only_one_encounter(self):
        a,d = self.a,self.d
        a.exploration.accept(1,quest_type='hunt')
        q = a.exploration.active
        floor = q['target_floor']-1
        start,delta = self.pair(floor)
        target = start[0]+delta[0],start[1]+delta[1]
        q['points'] = [list(target)]
        d.encounter_remaining = 1
        with patch.object(a,'begin_encounter',wraps=a.begin_encounter) as start_battle:
            event = d.move(*delta)
            a.quest_or_field_event(lambda:event,contact=True)
            start_battle.assert_called_once_with(quest_hunt=True,animate=True)
        self.assertEqual(a.battle_kind,'quest_hunt')

    def test_boss_trigger_not_limited_by_remainder(self):
        for floor in (4,9):
            self.d.debug_floor(floor)
            self.d.x,self.d.y = self.d.find(floor,TILE_BOSS)
            self.d.encounter_remaining = 22
            self.a.state,self.a.overlay = 'explore',None
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(self.a.state,'boss_message')
            self.assertEqual(self.d.encounter_remaining,22)

    def test_elevator_one_destination_area_draw_no_steps_or_battle(self):
        self.unlock()
        for floor in (5,10,14):
            self.a.state = 'elevator'
            self.d.encounter_remaining = 1
            steps,battles = self.d.steps,self.a.session.total_battles
            with patch.object(self.d.rng,'randint',return_value=22) as draw:
                self.a.travel_elevator(floor)
                draw.assert_called_once_with(9,22)
            self.tick()
            self.assertEqual((self.d.x,self.d.y),arrival_point(self.d,floor))
            self.assertEqual(self.d.steps,steps)
            self.assertEqual(self.a.session.total_battles,battles)
            self.assertEqual(self.d.encounter_remaining,22)

    def save_resume(self,transform=None):
        job_result(self.a.suspend_manager.save(self.a))
        raw = job_result(self.backend.start('read'))
        if transform:
            data = json.loads(raw); transform(data)
            raw = json.dumps(data,ensure_ascii=False)
            job_result(self.backend.start('write',raw))
            raw = job_result(self.backend.start('read'))
        prepared = self.a.suspend_manager.prepare(self.a,raw)
        job_result(self.backend.start('consume',raw))
        self.a.activate_suspended_game(prepared)
        self.d = self.a.dungeon
        self.assertTrue(self.backend.start('consume',raw).error)
        return json.loads(raw)

    def test_suspend17_walk5_resume12_then_exact12th_move(self):
        start,delta = self.pair(8)
        self.d.encounter_remaining = 17
        for _ in range(5): self.assertEqual(self.walk(start,delta),'')
        self.assertEqual(self.d.encounter_remaining,12)
        rng = self.d.rng.getstate()
        raw = self.save_resume()
        self.assertEqual(raw['dungeon']['encounter_remaining'],12)
        self.assertEqual(self.d.encounter_remaining,12)
        self.assertEqual(self.d.rng.getstate(),rng)
        for i in range(12): self.assertEqual(self.walk(start,delta),'battle' if i==11 else '')

    def test_repeated_suspend_never_refills_even_zero(self):
        start,delta = self.pair()
        self.d.encounter_remaining = 3
        for remaining in (3,2,1,0):
            rng = self.d.rng.getstate()
            self.save_resume()
            self.assertEqual((self.d.encounter_remaining,self.d.rng.getstate()),(remaining,rng))
            if remaining: self.walk(start,delta)

    def test_old_checkpoint_migration_without_rng_and_only_once(self):
        for floor,old_grace,expected in ((0,2,7),(8,0,9),(13,6,9)):
            self.pair(floor)
            self.d.grace = old_grace
            rng = self.d.rng.getstate()
            self.save_resume(lambda data:data['dungeon'].pop('encounter_remaining'))
            self.assertEqual(self.d.encounter_remaining,expected)
            self.assertEqual(self.d.rng.getstate(),rng)
            self.d.encounter_remaining -= 1
            self.save_resume()
            self.assertEqual(self.d.encounter_remaining,expected-1)

    def test_invalid_checkpoint_remaining_rejected_without_consuming(self):
        job_result(self.a.suspend_manager.save(self.a))
        raw = job_result(self.backend.start('read'))
        for bad in (-1,True,1.5,None,'12'):
            data = json.loads(raw); data['dungeon']['encounter_remaining'] = bad
            with self.assertRaises(SaveError): self.a.suspend_manager.prepare(self.a,json.dumps(data))
        self.assertEqual(job_result(self.backend.start('read')),raw)

    def test_normal_save_still_hub_only_and_new_trip_draws(self):
        self.a.enter_camp()
        data = make_save_data(self.a)
        self.assertNotIn('encounter_remaining',json.dumps(data))
        s,d,e,shown = prepare_saved_game(self.a,data)
        self.assertEqual(s.treasure.banked,self.a.session.treasure.banked)
        with patch.object(d.rng,'randint',return_value=16) as draw:
            d.enter(); draw.assert_called_once_with(7,16)
        self.assertEqual(d.encounter_remaining,16)

    def test_final_checkpoint_restores_remaining_and_rng_three_times(self):
        a,d = self.a,self.d
        self.unlock(); d.encounter_remaining = 12
        cp = FinalBattleCheckpoint.capture(a.session,d,a.exploration)
        rng = d.rng.getstate()
        for _ in range(3):
            d.encounter_remaining = 0; d.rng.random()
            cp.restore(a.session,d,a.exploration)
            self.assertEqual((d.encounter_remaining,d.rng.getstate()),(12,rng))

    def test_thousand_intervals_each_area_uniform_bounds_and_mean(self):
        for floor in (3,8,13):
            start,delta = self.pair(floor)
            self.d.rng.seed(40400+floor)
            self.d.reset_encounter()
            intervals = []
            for _ in range(2000):
                drawn = self.d.encounter_remaining
                for i in range(drawn):
                    self.assertEqual(self.walk(start,delta),'battle' if i==drawn-1 else '')
                intervals.append(drawn)
                self.d.reset_encounter()
            low,high = self.d.settings['encounter_step_ranges'][floor//5]
            self.assertEqual(set(intervals),set(range(low,high+1)))
            self.assertAlmostEqual(statistics.mean(intervals),(low+high)/2,delta=.3)
            for value in range(low,high+1):
                self.assertAlmostEqual(intervals.count(value)/len(intervals),1/(high-low+1),delta=.025)

    def test_only_authorized_changes_and_settings_validation(self):
        assert_encounter_preserved(self)
        for bad in ([[7,16],[9,22]],[[7,True],[9,22],[9,22]],
                    [[16,7],[9,22],[9,22]],[[0,16],[9,22],[9,22]],
                    [[7,16.0],[9,22],[9,22]],[[7,1000],[9,22],[9,22]]):
            settings = deepcopy(self.d.settings); settings['encounter_step_ranges'] = bad
            with self.assertRaisesRegex(ValueError,'encounter_step_ranges'):
                Dungeon(self.d.maps,self.a.session.enemy_data,settings,random.Random(1))
