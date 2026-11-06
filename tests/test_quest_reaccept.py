"""Reaccept through real UI after a real hunt victory, without clearing history."""
from copy import deepcopy
import json
import unittest
import pyxel
from tests.quest_reaccept_flow import QuestFlow,A,B,DOWN
from rpg.save import make_save_data,prepare_saved_game
from rpg.suspend import make_suspend_data,job_result


class QuestReacceptTests(unittest.TestCase):
    def setUp(self):
        self.flow=QuestFlow();self.addCleanup(self.flow.close)
        self.flow.new_game();self.a=self.flow.a

    def test_new_game_hunt_report_reaccept_and_clear_again(self):
        f=self.flow;a=self.a
        first=f.accept('hunt');f.complete()
        self.assertEqual(a.exploration.quest_clear_counts['hunt'],1)
        self.assertEqual(a.session.treasure.banked,3+first['reward'])
        self.assertIsNone(a.exploration.active)
        self.assertEqual(a.battle_kind,'quest_hunt')
        self.assertEqual(a.battle.outcome,'VICTORY')
        self.assertTrue(a.session.settled)
        q=f.accept('hunt')
        self.assertFalse(a.exploration.active['completed'])
        self.assertEqual(a.exploration.active['progress'],0)
        f.complete()
        self.assertEqual(a.exploration.quest_clear_counts['hunt'],2)
        self.assertEqual(a.session.treasure.banked,3+first['reward']+q['reward'])

    def test_all_required_type_switches_preserve_records(self):
        pairs=(('hunt','hunt'),('hunt','explore'),('hunt','investigate'),
               ('explore','hunt'),('explore','explore'),('investigate','hunt'),('investigate','investigate'))
        for source,target in pairs:
            with self.subTest(source=source,target=target):
                # A fresh NEW GAME, not a manually-cleared active contract.
                self.a.start_new_game()
                for _ in range(300):
                    if self.a.state=='camp':break
                    self.flow.tick(None if self.a.opening_input_blocked else A)
                old=self.flow.accept(source);self.flow.complete()
                count=dict(self.a.exploration.quest_clear_counts)
                ids=list(self.a.exploration.completed_quest_ids)
                bank=self.a.session.treasure.banked
                q=self.flow.accept(target)
                self.assertEqual(self.a.exploration.active,q)
                self.assertEqual(self.a.exploration.quest_clear_counts,count)
                self.assertEqual(self.a.exploration.completed_quest_ids,ids)
                self.assertIn(old['flavor_id'],ids)
                self.assertEqual(self.a.session.treasure.banked,bank)

    def test_all_three_unique_hunts_then_repeat_then_explore(self):
        f=self.flow;a=self.a;e=a.exploration
        ids=set();expected=3
        for _ in range(5):
            q=f.accept('hunt');ids.add(q['flavor_id']);f.complete()
            expected+=q['reward'];self.assertEqual(a.session.treasure.banked,expected)
            for _ in range(4):f.tick()
            self.assertEqual(a.session.treasure.banked,expected)
        self.assertEqual(len(ids),3)
        self.assertEqual(e.quest_clear_counts['hunt'],5)
        self.assertEqual(len(e.completed_quest_ids),3)
        q=f.accept('explore');self.assertEqual(e.active,q)
        f.complete();self.assertEqual(e.quest_clear_counts['explore'],1)
        self.assertEqual(a.session.treasure.banked,expected+q['reward'])

    def test_stale_victory_never_autocompletes_new_contract_at_same_point(self):
        f=self.flow;a=self.a
        f.accept('hunt');f.complete();f.accept('hunt')
        q=a.exploration.active
        a.dungeon.floor=q['target_floor']-1;a.dungeon.x,a.dungeon.y=q['points'][0]
        a.state='explore'
        before=deepcopy(q)
        for _ in range(3):f.tick()
        self.assertEqual(q,before)
        self.assertFalse(q['completed'])

    def test_save_load_reaccept_switch_suspend_and_reclear(self):
        f=self.flow;a=self.a;f.accept('hunt');f.complete()
        # Use the actual GUILD save screen and isolated file backend.
        while a.camp_cursor!=0:f.tick(DOWN)
        f.tick(A);f.tick(DOWN);f.tick(DOWN);f.tick(A);f.tick(A)
        self.assertEqual(a.state,'save_result')
        old=a.save_manager.backend.read()
        a.continue_game();f.tick()
        self.assertEqual(a.exploration.quest_clear_counts['hunt'],1)
        self.assertEqual(a.session.treasure.banked,old['banked_trz'])
        f.accept('hunt');f.complete();f.accept('explore')
        a.enter_dungeon();f.settle_screens()
        saved=json.loads(json.dumps(make_suspend_data(a)))
        job_result(a.suspend_manager.save(a));raw=job_result(a.suspend_manager.backend.start('read'))
        prepared=a.suspend_manager.prepare(a,raw)
        job_result(a.suspend_manager.backend.start('consume',raw))
        a.activate_suspended_game(prepared);f.tick()
        self.assertEqual(json.loads(json.dumps(make_suspend_data(a))),saved)
        a.state,a.menu_cursor='menu',6;f.tick(A)
        self.assertEqual(a.overlay,'field_quest');a.draw();f.tick(B);f.tick(B)
        a.enter_camp() # Travel fixture; no completed objective/reward to bypass.
        f.complete()
        a.state,a.facility_index,a.facility_cursor='facility',0,2
        f.tick(A);f.tick(A)
        restored=prepare_saved_game(a,a.save_manager.backend.read())
        self.assertEqual(restored[2].quest_clear_counts,{'explore':1,'investigate':0,'hunt':2})

    def test_unaccepted_and_preview_summary_never_completes_old_battle(self):
        f=self.flow;a=self.a;f.accept('hunt');f.complete()
        a.state,a.menu_cursor='menu',6;f.tick(A)
        self.assertIsNone(a.exploration.active);a.draw();f.tick(B);f.tick(B)
        a.enter_camp();f.accept('investigate')
        a.state,a.menu_cursor='menu',6;f.tick(A);a.draw()
        self.assertEqual(a.exploration.active['progress'],0)
