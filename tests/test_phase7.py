"""Real ending/checkpoint/SAVE boundaries, optional old v1 data and extra boss."""
from copy import deepcopy
import json
from unittest.mock import patch
import pyxel
from tests.encounter_fixture import EncounterFixture
from rpg.postgame import CompletionRecords,dragon_here,dragon_location,dragon_image
from rpg.save import make_save_data,prepare_saved_game,SaveError,FileSaveBackend
from rpg.suspend import make_suspend_data,job_result
from rpg.text import text_width

A=pyxel.GAMEPAD1_BUTTON_A
B=pyxel.GAMEPAD1_BUTTON_B


class Phase7Tests(EncounterFixture):
    def final_ready(self):
        a=self.a;f=a.dungeon.finale
        a.enter_camp();f.guardians_defeated=f.demon_defeated=f.has_amrita=True
        a.dungeon.defeated_bosses.update((4,9,14))
        a.start_final_story();a.begin_final_battle();a.battle_input_blocked=False
        return a.battle

    def victory(self):
        a=self.a;a.battle.outcome='VICTORY';a.session.settle()
        for i in list(a.session.pending_replacements):a.session.resolve_replacement(i,None)
        with patch.object(a,'waiting_for_fanfare',return_value=False):a.finish_results()

    def clear(self):self.final_ready();self.victory()

    def advance(self):
        self.tick();self.tick(A)

    def credits_to_title(self):
        a=self.a
        for _ in range(5000):
            if a.state=='title':return
            self.tick(A)
        self.fail(('ending did not finish',a.state))

    def dragon_ready(self):
        a=self.a;self.clear();a.continue_game();self.tick()
        floor,point=dragon_location(a.dungeon)
        a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point;a.state='explore'
        a.begin_dragon_battle();a.battle_input_blocked=False
        return a.battle

    def test_clear_autosave_before_ending_has_prebattle_party_and_replayable_hub(self):
        a=self.a;b=self.final_ready()
        before=deepcopy(a.final_checkpoint.session_state)
        a.session.inventory.counts['POTION']=0
        a.session.party[0].strength+=99
        self.victory()
        self.assertEqual(a.state,'ending');self.assertTrue(a.dungeon.completion.main_game_cleared)
        self.assertTrue(a.dungeon.finale.amrita_power_spent)
        raw=a.save_manager.backend.read();self.assertTrue(raw['completion']['main_game_cleared'])
        self.assertTrue(raw['story']['has_amrita']);self.assertFalse(raw['story']['final_event_started'])
        self.assertEqual(raw['items'],before['inventory'].counts)
        self.assertEqual(raw['party'][0]['strength'],before['party'][0].strength)
        a.continue_game();self.assertEqual(a.state,'camp')
        self.assertTrue(a.dungeon.finale.has_amrita)
        self.assertTrue(a.dungeon.completion.main_game_cleared)
        a.start_final_story();a.begin_final_battle();self.assertTrue(a.battle.elysion_barrier_active)

    def test_first_credits_not_skippable_then_end_extra_and_title_without_audio(self):
        a=self.a;self.clear()
        for _ in range(len(a.final_ending_pages())):self.tick(A)
        self.assertEqual(a.state,'credits')
        self.tick(A);self.assertEqual(a.state,'credits')
        states=set()
        with patch.object(pyxel,'play',side_effect=RuntimeError('no audio')),patch.object(pyxel,'playm',side_effect=RuntimeError('no audio')):
            for _ in range(5000):
                states.add(a.state);self.tick(A)
                if a.state=='title':break
        self.assertEqual(a.state,'title')
        self.assertTrue({'ending_end','extra_quest_title','extra_quest_story'}<=states)
        self.assertEqual(a.credits_data['lines'].count('GONZARES TANAKA'),4)

    def test_reclear_preserves_postclear_growth_dragon_record_and_omits_extra_notice(self):
        a=self.a;self.clear();a.continue_game();self.tick()
        a.session.party[0].strength+=21
        a.dungeon.completion.dragon_victory(12)
        strength=a.session.party[0].strength
        self.final_ready();a.session.party[0].strength+=99;self.victory()
        self.assertFalse(a.ending_first)
        a.continue_game();self.tick()
        self.assertEqual(a.session.party[0].strength,strength)
        self.assertEqual(a.dungeon.completion.ancient_dragon_best_turns,12)
        self.final_ready();self.victory()
        for _ in range(len(a.final_ending_pages())):self.tick(A)
        self.tick(A);self.assertEqual(a.state,'ending_end')
        for _ in range(a.credits_data['end_frames']):self.tick()
        self.assertEqual(a.state,'title')

    def test_failed_clear_save_keeps_old_file_and_retry_is_idempotent(self):
        a=self.a;a.state='facility';a.facility_index=0;a.facility_cursor=2
        old=make_save_data(a);a.save_manager.backend.write(old)
        self.final_ready()
        with patch.object(a.save_manager.backend,'write',side_effect=SaveError('full disk')):self.victory()
        self.assertEqual(a.state,'clear_save_error')
        self.assertFalse(a.dungeon.completion.main_game_cleared)
        self.assertIsNotNone(a.final_checkpoint)
        self.assertEqual(a.save_manager.backend.read(),old)
        self.advance();self.assertEqual(a.state,'ending')
        self.assertTrue(a.save_manager.backend.read()['completion']['main_game_cleared'])

    def test_dragon_gated_location_cancel_no_map_mutation(self):
        a=self.a;floor,point=dragon_location(a.dungeon)
        a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point
        self.assertFalse(dragon_here(a.dungeon))
        with self.assertRaises(ValueError):a.begin_dragon_battle()
        self.clear();a.continue_game();self.tick()
        a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point;a.state='explore'
        self.assertTrue(dragon_here(a.dungeon))
        from rpg.quests import spawn_candidates
        self.assertNotIn(point,spawn_candidates(a.dungeon,floor))
        tile=a.dungeon.tile(floor,*point)
        a.quest_or_field_event(a.dungeon.interact,False)
        self.assertEqual(a.state,'dragon_warning')
        self.tick();self.tick(B);self.assertEqual(a.state,'explore')
        self.assertEqual(a.dungeon.tile(floor,*point),tile)

    def test_dragon_turn_best_record_repeat_and_no_final_boss_requirement(self):
        a=self.a;b=self.dragon_ready();b.round=17;self.victory()
        self.assertEqual(a.state,'dragon_victory_story')
        record=a.dungeon.completion
        self.assertEqual((record.ancient_dragon_best_turns,record.ancient_dragon_victories),(17,1))
        for _ in range(15):
            if a.state=='camp':break
            self.advance()
        self.assertEqual(a.state,'camp')
        a.continue_game();self.tick()
        for turns,best,count in ((22,17,2),(11,11,3)):
            floor,point=dragon_location(a.dungeon);a.dungeon.floor=floor;a.dungeon.x,a.dungeon.y=point
            a.state='explore';a.begin_dragon_battle();a.battle.round=turns;self.victory()
            self.assertEqual(a.state,'dragon_result')
            self.assertEqual((a.dungeon.completion.ancient_dragon_best_turns,a.dungeon.completion.ancient_dragon_victories),(best,count))
            self.advance();a.continue_game();self.tick()

    def test_dragon_defeat_does_not_record_and_returns_via_normal_loss(self):
        a=self.a;self.dragon_ready();a.battle.outcome='DEFEAT';a.session.settle()
        with patch.object(a,'waiting_for_fanfare',return_value=False):a.finish_results()
        self.assertFalse(a.dungeon.completion.ancient_dragon_defeated)
        self.assertEqual(a.dungeon.completion.ancient_dragon_victories,0)
        self.assertTrue(a.dungeon.completion.main_game_cleared)
        self.assertIsNone(a.final_checkpoint)

    def test_legacy_v1_without_records_loads_uncleared_and_new_game_resets(self):
        old=json.loads((__import__('rpg.content',fromlist=['ROOT']).ROOT/'tests/fixtures/ui_phase6b1_legacy_save.json').read_text(encoding='utf8'))
        _,d,_,_=prepare_saved_game(self.a,old)
        self.assertFalse(d.completion.main_game_cleared)
        self.clear();self.a.start_new_game()
        self.assertFalse(self.a.dungeon.completion.main_game_cleared)

    def test_clear_record_suspended_and_stale_same_run_cannot_rollback(self):
        a=self.a;self.clear();a.continue_game();self.tick();a.enter_dungeon()
        saved=json.loads(json.dumps(make_suspend_data(a)))
        newer=deepcopy(a.dungeon.completion);newer.dragon_victory(9)
        raw=a.save_manager.backend.read();raw['completion']=newer.snapshot();a.save_manager.backend.write(raw)
        prepared=a.suspend_manager.prepare(a,json.dumps({**saved,'suspend_id':'1'*32}))
        prepared=a.merge_saved_completion(prepared)
        self.assertEqual(prepared[1].completion.ancient_dragon_best_turns,9)
        self.assertEqual(prepared[1].completion.ancient_dragon_victories,1)

    def test_postgame_screens_and_every_credit_line_fit_existing_font(self):
        a=self.a;self.clear();self.assertIsNotNone(dragon_image())
        actual=pyxel.text
        def bounded(x,y,value,color,font=None):
            width=font.text_width(value) if font else len(value)*4
            self.assertTrue(0<=x and x+width<=160,(x,y,value,width))
            self.assertTrue(0<=y and y+8<=120,(x,y,value))
            return actual(x,y,value,color,font) if font else actual(x,y,value,color)
        with patch.object(pyxel,'text',side_effect=bounded):
            for state in ('credits','ending_end','extra_quest_title','extra_quest_story','clear_save_error','dragon_warning','dragon_victory_story','dragon_title','dragon_result','completion_record'):
                a.state=state;a.postgame_frame=360;a.draw()
        from rpg.text import wrap_lines
        self.assertTrue(all(text_width(s)<=152 for s in wrap_lines(a.credits_data['lines'],38)))

    def test_stale_preclear_suspend_is_preserved_and_cannot_undo_clear(self):
        a=self.a;a.state='explore'
        saved=json.loads(json.dumps(make_suspend_data(a)))
        self.clear()
        raw=json.dumps({**saved,'suspend_id':'1'*32})
        prepared=a.suspend_manager.prepare(a,raw)
        with self.assertRaises(SaveError):a.merge_saved_completion(prepared)
        self.assertTrue(a.save_manager.backend.read()['completion']['main_game_cleared'])

    def test_malformed_new_records_rejected_but_other_adventure_not_merged(self):
        a=self.a;original=make_save_data(a)
        for row in (None,{},dict(original['completion'],main_game_cleared=1),
                    dict(original['completion'],ancient_dragon_best_turns=0),
                    dict(original['completion'],ancient_dragon_victories=1)):
            with self.assertRaises(SaveError):prepare_saved_game(a,{**original,'completion':row})
        self.clear();a.start_new_game();a.state='explore'
        saved=json.loads(json.dumps(make_suspend_data(a)))
        prepared=a.suspend_manager.prepare(a,json.dumps({**saved,'suspend_id':'1'*32}))
        self.assertFalse(a.merge_saved_completion(prepared)[1].completion.main_game_cleared)
