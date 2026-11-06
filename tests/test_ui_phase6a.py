"""Real map, clipped Japanese marquee, base labels and durable progress."""
from copy import deepcopy
import json
from unittest.mock import patch
import pyxel

from tests.encounter_fixture import EncounterFixture
from tests.ui_phase6a_preservation import assert_ui_preserved
from rpg.elevator import (B15_ELEVATOR_SPRITE, b15_elevator_point,
                         at_b15_elevator, arrival_point)
from rpg.save import make_save_data, prepare_saved_game
from rpg.suspend import job_result, make_suspend_data
from rpg.text import (DescriptionScroll, text, text_width, font,
                      DESCRIPTION_HOLD_FRAMES, DESCRIPTION_STEP_FRAMES)
from rpg.tiles import TILE_BOSS, TILE_STAIRS_UP
from rpg.items import RETURN_FEATHER


class UIPhase6ATests(EncounterFixture):
    def draw_frame(self, frame):
        with patch.object(pyxel, 'frame_count', frame):
            self.a.draw()

    def marquee(self, value, frame, context='skill'):
        with patch.object(pyxel, 'frame_count', frame):
            self.scroll.begin_frame()
            self.scroll.draw(5, 100, value, 2, 37, context)

    def test_all_user_data_rules_resources_audio_and_save_preserved(self):
        assert_ui_preserved(self)
        self.assertEqual(len(self.a.session.skills), 62)

    def test_demon_is_single_tile_lift_exact_right_existing_floor(self):
        d = self.d
        self.assertEqual(d.positions(14, TILE_BOSS), [(11, 0)])
        self.assertEqual(b15_elevator_point(d), (12, 0))
        d.finale.guardians_defeated = True
        before = {(x, y): d.can_enter(14, x, y) for y in range(32) for x in range(24)}
        self.assertTrue(before[12, 0])
        self.assertFalse(before[10, 0])
        self.unlock()
        after = {(x, y): d.can_enter(14, x, y) for y in range(32) for x in range(24)}
        self.assertEqual(before, after)
        for x, y in ((12, 0), (10, 0), (11, 0), (12, 1), (11, 1)):
            d.floor, d.x, d.y = 14, x, y
            self.assertEqual(at_b15_elevator(d), (x, y) == (12, 0))

    def test_lift_sprite_hidden_before_demon_new_bank_only_after(self):
        a, d = self.a, self.d
        d.floor, d.x, d.y = 14, 11, 0
        a.state = 'explore'
        for unlocked in (False, True):
            if unlocked: self.unlock()
            with patch.object(pyxel, 'blt', wraps=pyxel.blt) as blt:
                a.draw()
            sprites = [c.args[2:7] for c in blt.call_args_list]
            self.assertEqual(sprites.count(B15_ELEVATOR_SPRITE), int(unlocked))
            self.assertNotIn((2, 80, 0, 16, 16), sprites)

    def test_real_move_right_use_cancel_then_return_with_amrita_and_trz(self):
        a, d = self.a, self.d
        self.unlock()
        a.state, a.overlay, a.opening_input_blocked = 'explore', None, False
        d.floor, d.x, d.y = 14, 11, 0
        d.treasure.banked, d.treasure.unbanked = 15, 7
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
        self.assertEqual((d.x, d.y), (12, 0))
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state, 'elevator_return')
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.tick()
        self.assertEqual(a.state, 'explore')
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((d.treasure.banked, d.treasure.unbanked), (22, 0))
        self.assertTrue(d.finale.has_amrita)
        self.assertFalse(d.finale.final_event_started)
        self.assertIn(a.state, ('return_result', 'amrita_offer'))

    def test_demon_victory_claim_notice_and_destinations_unchanged(self):
        a, d = self.a, self.d
        d.floor = 14
        self.assertFalse(d.finale.has_amrita)
        d.finale.guardians_defeated = True
        lines = d.defeat_boss()
        self.assertTrue(d.finale.has_amrita and d.finale.demon_defeated)
        self.assertTrue(any('右隣' in v for v in lines))
        d.defeated_bosses.update((4, 9))
        for floor in (5, 10):
            self.assertEqual(arrival_point(d, floor), d.find(floor, TILE_STAIRS_UP))
        self.assertEqual(arrival_point(d, 14), (12, 0))
        self.assertNotIn('AMRITA', a.session.inventory.counts)

    def test_normal_load_and_suspend_at_new_or_old_landing_compatible(self):
        a = self.a
        self.unlock()
        s, d = prepare_saved_game(a, make_save_data(a))[:2]
        self.assertEqual(b15_elevator_point(d), (12, 0))
        self.assertTrue(d.can_enter(14, 12, 0))
        for point in ((12, 0), (10, 0), (4, 28)):
            d = a.dungeon
            d.floor, d.x, d.y = 14, *point
            a.state, a.overlay = 'explore', None
            before = json.loads(json.dumps(make_suspend_data(a)))
            job_result(a.suspend_manager.save(a))
            raw = job_result(self.backend.start('read'))
            prepared = a.suspend_manager.prepare(a, raw)
            job_result(self.backend.start('consume', raw))
            a.activate_suspended_game(prepared)
            self.assertEqual((a.dungeon.x, a.dungeon.y), point)
            self.assertEqual(json.loads(json.dumps(make_suspend_data(a))), before)
            self.assertTrue(a.dungeon.can_enter(14, 12, 0))

    def test_old_left_suspend_can_walk_out_but_lift_only_works_on_right(self):
        a,d=self.a,self.d
        self.unlock()
        a.state,a.overlay,a.opening_input_blocked='explore',None,False
        d.floor,d.x,d.y=14,10,0
        self.assertTrue(d.can_enter(14,10,0))
        self.assertFalse(at_b15_elevator(d))
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
        self.assertEqual((d.x,d.y),(11,0))
        self.assertFalse(d.can_enter(14,10,0))
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
        self.assertTrue(at_b15_elevator(d))

    def test_short_and_exact_width_stay_static_with_original_rendering(self):
        for value in ('短い説明 STR+1', 'A'*37):
            self.scroll = DescriptionScroll()
            self.assertLessEqual(text_width(value), 148)
            for frame in range(90): self.marquee(value, frame)
            self.assertEqual(self.scroll.offset, 0)
            self.assertIsNone(self.scroll.image)

    def test_long_japanese_all_glyphs_visible_start_end_pauses_and_repeat(self):
        value = '日本語とABC、STR+30%! ' * 4 + '最後の文章。'
        width = text_width(value)
        overflow = width - 148
        self.assertGreater(overflow, 0)
        hold, step = DESCRIPTION_HOLD_FRAMES, DESCRIPTION_STEP_FRAMES
        cycle = overflow*step + 2*hold
        self.scroll = DescriptionScroll()
        seen, offsets = set(), []
        for frame in range(cycle+1):
            self.marquee(value, frame)
            offset = self.scroll.offset
            offsets.append(offset)
            for i in range(len(value)):
                left, right = text_width(value[:i]), text_width(value[:i+1])
                if offset <= left and right <= offset+148: seen.add(i)
        self.assertEqual(seen, set(range(len(value))))
        self.assertTrue(all(o == 0 for o in offsets[:hold+1]))
        self.assertTrue(all(o == overflow for o in offsets[hold+overflow*step:cycle]))
        self.assertEqual(offsets[-1], 0)
        self.assertTrue(all(0 <= b-a <= 1 for a,b in zip(offsets[:-2],offsets[1:-1])))

    def test_transient_image_clips_edges_clears_old_pixels_and_preserves_adjacent_ui(self):
        value = '説明 ABC!? 日本語' * 12
        self.scroll = DescriptionScroll()
        for frame in range(80):
            pyxel.cls(1)
            self.marquee(value, frame)
            for y in (99, 108):
                self.assertTrue(all(pyxel.pget(x,y) == 1 for x in range(160)))
            for x in (4, 153):
                self.assertTrue(all(pyxel.pget(x,y) == 1 for y in range(100,108)))
        self.assertEqual((self.scroll.image.width,self.scroll.image.height), (148,8))
        # Compare with the independent crop of a full-width reference rendering.
        image = pyxel.Image(text_width(value), 8)
        image.cls(0); image.text(0,0,value,2,font())
        self.assertEqual([[self.scroll.image.pget(x,y) for x in range(148)] for y in range(8)],
            [[image.pget(x+self.scroll.offset,y) for x in range(148)] for y in range(8)])

    def test_selection_page_reopen_text_edit_and_frame_gap_reset(self):
        self.scroll = DescriptionScroll()
        value = '長い文章です。' * 12
        for frame in range(80): self.marquee(value,frame)
        self.assertGreater(self.scroll.offset,0)
        self.marquee(value,80,'other-skill'); self.assertEqual(self.scroll.offset,0)
        for frame in range(81,160): self.marquee(value,frame,'other-skill')
        self.assertGreater(self.scroll.offset,0)
        with patch.object(pyxel,'frame_count',160): self.scroll.begin_frame()
        self.marquee(value,162,'other-skill'); self.assertEqual(self.scroll.offset,0)
        for frame in range(163,242): self.marquee(value,frame,'other-skill')
        self.marquee(value+'編集',242,'other-skill'); self.assertEqual(self.scroll.offset,0)
        self.marquee(value,0,'other-skill'); self.assertEqual(self.scroll.offset,0)

    def test_dropped_render_frames_do_not_restart_a_visible_description(self):
        self.scroll=DescriptionScroll()
        value='描画が間引かれても全文が読めます。'*8
        for frame in range(0,100,3): self.marquee(value,frame)
        self.assertEqual(self.scroll.start_frame,0)
        self.assertGreater(self.scroll.offset,0)

    def test_real_battle_buttons_work_during_scroll_and_reopen_at_start(self):
        a, c = self.a, self.a.session.party[0]
        for sid in list(c.skills): c.forget(sid)
        for sid in ('power_up','punch'): c.learn(a.session.skills[sid])
        a.begin_encounter(); a.begin_input()
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        for frame in range(80): self.draw_frame(frame)
        self.assertGreater(a.description_scroll.offset,0)
        with patch.object(pyxel,'frame_count',80):
            self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN); a.draw()
        self.assertEqual(a.skill_cursor,1); self.assertEqual(a.description_scroll.offset,0)
        with patch.object(pyxel,'frame_count',81):
            self.tick(pyxel.GAMEPAD1_BUTTON_B); a.draw()
        self.assertEqual(a.state,'command')
        with patch.object(pyxel,'frame_count',82):
            self.tick(pyxel.GAMEPAD1_BUTTON_A); a.draw()
        self.assertEqual(a.state,'skill'); self.assertEqual(a.description_scroll.offset,0)

    def test_status_and_catalog_share_marquee_without_new_replacement_or_training_fields(self):
        a, c = self.a, self.a.session.party[0]
        for sid in list(c.skills): c.forget(sid)
        c.learn(a.session.skills['power_up'])
        a.overlay, a.info_tab, a.scroll = 'info',1,0
        for frame in range(80): self.draw_frame(frame)
        self.assertGreater(a.description_scroll.offset,0)
        a.overlay, a.catalog_cursor = 'catalog',list(a.session.skills).index('power_up')
        self.draw_frame(80)
        self.assertEqual(a.description_scroll.offset,0)
        for frame in range(81,160): self.draw_frame(frame)
        self.assertGreater(a.description_scroll.offset,0)
        a.state,a.overlay='relearn_list',None
        with patch.object(DescriptionScroll,'draw') as scrolling:
            a.draw()
            scrolling.assert_not_called()

    def test_base_labels_and_numbers_unified_without_mutating_treasure(self):
        a, s = self.a, self.a.session
        s.treasure.banked,s.treasure.unbanked=15,7
        for state in ('camp','shop','pub','relearn_character'):
            a.state,a.overlay=state,None
            with patch('rpg.dungeon_app.text') as draw:
                a.draw()
            lines=[str(c.args[2]) for c in draw.call_args_list]
            self.assertTrue(any('TRZ' in line and '15' in line for line in lines),state)
            self.assertFalse(any('確定' in line for line in lines),state)
        for facility in range(4):
            a.state,a.facility_index='facility',facility
            with patch('rpg.dungeon_app.text') as draw: a.draw()
            self.assertIn('TRZ 15',[c.args[2] for c in draw.call_args_list])
        self.assertEqual((s.treasure.banked,s.treasure.unbanked),(15,7))

    def test_insufficient_funds_labels_only_and_real_shop_pub_spending(self):
        a,s=self.a,self.a.session
        s.treasure.banked=0
        self.assertEqual(s.inventory.buy('POTION',s.treasure)[1],'TRZが足りません')
        a.state='pub'; self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.notice,'TRZが足りません')
        s.treasure.banked=15
        price=s.inventory.data['items'][RETURN_FEATHER]['price']
        before=s.inventory.counts[RETURN_FEATHER]
        self.assertTrue(s.inventory.buy(RETURN_FEATHER,s.treasure)[0])
        self.assertEqual((s.treasure.banked,s.inventory.counts[RETURN_FEATHER]),(15-price,before+1))
        a.state,a.pub_cursor='pub',0
        funds=s.treasure.banked
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(s.treasure.banked,funds-s.inventory.data['pub_cost'])
