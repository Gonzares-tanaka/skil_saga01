"""UI-only changes, read-only contracts, legacy saves and next-copy previews."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pyxel

from tests.encounter_fixture import EncounterFixture
from tests.ui_phase6b1_preservation import assert_preserved, baseline
from rpg import app as base_ui, dungeon_app as ui
from rpg.hub import HUB_FACILITIES, HUB_FACILITY_LABELS, HUB_MENUS, HUB_MENU_LABELS
from rpg.items import ITEMS
from rpg.save import make_save_data, prepare_saved_game, SaveError
from rpg.content import ROOT
from rpg.suspend import make_suspend_data, job_result
from rpg.text import text_width, font, DescriptionScroll
from rpg.elevator import b15_elevator_point, B15_ELEVATOR_SPRITE


class UIPhase6B1Tests(EncounterFixture):
    def capture(self, draw=None):
        lines=[]
        actual=base_ui.text
        def capture(x,y,value,*args,**kwargs):
            lines.append((x,y,str(value),args,kwargs))
            return actual(x,y,value,*args,**kwargs)
        with patch.object(base_ui,'text',side_effect=capture), patch.object(ui,'text',side_effect=capture):
            (draw or self.a.draw)()
        return lines

    def words(self, draw=None):
        return [row[2] for row in self.capture(draw)]

    def open_quest(self):
        self.a.state,self.a.overlay,self.a.menu_cursor='menu',None,6
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((self.a.state,self.a.overlay),('menu','field_quest'))

    def test_only_authorized_ui_and_two_names_changed(self):
        assert_preserved(self)
        self.assertEqual(len(self.a.session.skills),62)
        self.assertEqual((self.a.session.skills['return'].name,self.a.session.skills['revive'].name),('リターン','リバイブ'))

    def test_each_item_selection_changes_hint_without_effects_or_rng(self):
        a=self.a;a.state='items'
        expected=('味方1人のHPを回復する','戦闘不能の味方1人を蘇生する',
                  '味方の状態異常を治療する','ダンジョンから帰還 / 1個消費')
        before=deepcopy(make_suspend_data(a) if a.can_suspend_game() else make_save_data(a))
        rng=a.session.rng.getstate()
        for i,hint in enumerate(expected):
            self.assertEqual(a.item_kind_cursor,i)
            self.assertIn(hint,self.words())
            self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.assertEqual(a.item_kind_cursor,0)
        self.assertEqual(make_save_data(a),before)
        self.assertEqual(a.session.rng.getstate(),rng)

    def test_item_effects_prices_and_invalid_targets_unchanged(self):
        a=self.a;inv=a.session.inventory;c=a.session.party[0]
        for sid in ITEMS:inv.counts[sid]=2
        for item in ('POTION','REMEDY','PHOENIX ASH'):
            c.recover();before=inv.counts[item]
            self.assertFalse(inv.use(item,c)[0]);self.assertEqual(inv.counts[item],before)
        c.hp=1
        self.assertTrue(inv.use('POTION',c)[0])
        self.assertEqual(c.hp,min(c.max_hp,1+inv.data['items']['POTION']['heal']))
        c.hp=0;self.assertTrue(inv.use('PHOENIX ASH',c)[0])
        self.assertEqual(c.hp,max(1,int(c.max_hp*inv.data['revive_fraction'])))

    def test_b_instructions_follow_unchanged_facility_routes(self):
        a=self.a
        for state in ('shop','pub','archive','relearn_character'):
            a.state,a.overlay,a.facility_back,a.notice_timer=state,None,'facility',0
            self.assertTrue(any('B:戻る' in line for line in self.words()),state)
            self.tick(pyxel.GAMEPAD1_BUTTON_B);self.assertEqual(a.state,'facility')
        self.assertTrue(any('B:拠点へ' in line for line in self.words()))
        self.tick(pyxel.GAMEPAD1_BUTTON_B);self.assertEqual(a.state,'camp')
        self.assertFalse(any('B:' in line for line in self.words()))
        self.tick(pyxel.GAMEPAD1_BUTTON_B);self.assertEqual(a.state,'camp')

    def test_unaccepted_quest_read_only_and_ab_routes(self):
        a=self.a;rng=a.session.rng.getstate();before=deepcopy(a.exploration.active_quest)
        self.open_quest()
        self.assertIn('受注中のクエストはありません',self.words())
        self.tick(pyxel.GAMEPAD1_BUTTON_A);self.assertEqual(a.overlay,'field_quest')
        self.tick(pyxel.GAMEPAD1_BUTTON_B);self.assertEqual((a.state,a.overlay),('menu',None))
        self.tick(pyxel.GAMEPAD1_BUTTON_B);self.assertEqual(a.state,'explore')
        self.assertEqual(a.exploration.active_quest,before)
        self.assertEqual(a.session.rng.getstate(),rng)

    def test_all_quest_types_levels_partial_complete_and_no_coordinates(self):
        a=self.a;self.unlock()
        for kind in ('explore','investigate','hunt'):
            for level in (1,2,3):
                e=a.exploration;e.active_quest=None;e.accept(level,quest_type=kind)
                q=e.active_quest;q['progress']=max(0,q['required_count']-1)
                before=deepcopy(q);rng=a.session.rng.getstate();flavor_rng=e.flavor_rng.getstate()
                self.open_quest();lines=self.words()
                self.assertIn(e.quest_name(),lines)
                self.assertIn(f"対象：B{q['target_floor']}F",lines)
                self.assertIn(f"進捗：{q['progress']}/{q['required_count']}",lines)
                self.assertFalse(any('拠点に戻って報告' in line for line in lines))
                self.assertEqual(q,before)
                self.assertEqual(a.session.rng.getstate(),rng)
                self.assertEqual(e.flavor_rng.getstate(),flavor_rng)
                # Only fields explicitly known to the player are shown.
                self.assertEqual(lines,['クエスト',e.quest_name(),f"対象：B{q['target_floor']}F",
                    f"進捗：{q['progress']}/{q['required_count']}",'B:戻る'])
                q.update(progress=q['required_count'],completed=True)
                self.assertIn('拠点に戻って報告',self.words())
                self.tick(pyxel.GAMEPAD1_BUTTON_B)

    def test_quest_progress_reflects_real_investigation_and_death(self):
        a=self.a;e=a.exploration;e.accept(1,quest_type='investigate')
        q=e.active_quest;self.d.floor=q['target_floor']-1;self.d.x,self.d.y=q['points'][0]
        e.investigate();self.open_quest();self.assertIn('進捗：1/2',self.words())
        e.return_to_camp(False)
        self.assertIn('進捗：0/2',self.words())

    def test_quest_suspend_exact_once_then_reopen_summary(self):
        a=self.a;self.unlock();e=a.exploration;e.accept(3,quest_type='investigate')
        q=e.active_quest;q['target_floor']=14
        from rpg.quests import spawn_candidates
        q['points']=[list(p) for p in spawn_candidates(self.d,13)[:3]]
        q['investigated_points']=[q['points'][0]];q['progress']=1
        self.d.floor=13;self.d.x,self.d.y=q['points'][1]
        a.session.treasure.banked,a.session.treasure.unbanked=37,9
        a.state,a.overlay='explore',None
        snapshot=json.loads(json.dumps(make_suspend_data(a)))
        job_result(a.suspend_manager.save(a));raw=job_result(self.backend.start('read'))
        prepared=a.suspend_manager.prepare(a,raw);job_result(self.backend.start('consume',raw))
        a.activate_suspended_game(prepared);self.tick()
        self.assertEqual(json.loads(json.dumps(make_suspend_data(a))),snapshot)
        self.open_quest();self.assertIn('進捗：1/3',self.words());self.assertIn('対象：B14F',self.words())
        with self.assertRaises(SaveError):job_result(self.backend.start('consume',raw))

    def test_pub_heading_fee_ratio_text_and_return_preserved(self):
        a=self.a;s=a.session;s.treasure.banked=20
        self.assertEqual(s.inventory.data['pub_gameplay_weight'],.7)
        self.assertEqual([len(a.rumors[k]) for k in ('gameplay','flavor')],[11,7])
        previous=None
        for _ in range(8):
            a.state,a.pub_cursor='pub',0;funds=s.treasure.banked
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(s.treasure.banked,funds-1)
            self.assertEqual(a.state,'field_event');self.assertIn('酒場の噂',self.words())
            self.assertNotEqual(a.last_rumor,previous);previous=a.last_rumor
            while a.state=='field_event':self.tick(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(a.state,'pub')
        a.show_field_event(['通常イベント'])
        self.assertIn('探索 / 調査と発見',self.words())

    def test_training_next_copy_preview_normal_mastered_cancel_and_no_promotion(self):
        a=self.a;s=a.session;c=s.party[0];skill=s.skills['punch']
        a.info_character=0;a.relearn_skill='punch';a.state='relearn_confirm'
        s.treasure.banked=30;s.discovered_skills.add('punch')
        held_power=skill.power(c)
        for mastered in (False,True):
            if mastered:s.mastered_skills.add('punch')
            lines=self.words();expected=skill.power(c,next_copy=True)
            self.assertTrue(any(f'予定威力 {expected}' in line for line in lines))
            self.assertEqual(skill.power(c),held_power)
        before=make_save_data(a);self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(a.state,'relearn_list');self.assertEqual(make_save_data(a),before)
        c.forget('punch');a.state='relearn_confirm'
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(s.treasure.banked,30-skill.relearn_cost)
        self.assertEqual(skill.power(c),skill.power(c,next_copy=True))

    def test_training_nonattacks_have_no_damage_preview_and_full_slots_still_compare(self):
        a=self.a;c=a.session.party[0]
        for sid in ('heal','cure','return','power_up','revive'):
            a.state,a.relearn_skill='relearn_confirm',sid
            self.assertFalse(any('予定威力' in line for line in self.words()),sid)
        for sid in list(c.skills):c.forget(sid)
        for sid in ('punch','fire','ice','quick_stab','heal','return'):c.learn(a.session.skills[sid])
        c.pending_skill='power_strike';a.session.pending_relearn=(0,'power_strike')
        a.state='replace';a.replacement_confirm=False;a.replacement_cursor=0
        self.assertTrue(any('威力' in line for line in self.words()))

    def test_localized_facilities_menus_and_lift_full_glyphs_fit(self):
        a=self.a
        self.assertEqual(HUB_FACILITIES,('GUILD','TRAINING','PUB','SHOP','DUNGEON','ELEVATOR'))
        self.assertEqual(HUB_FACILITY_LABELS,('ギルド','訓練場','パブ','ショップ','ダンジョン','エレベーター'))
        a.state='camp'
        for index in range(6):
            a.camp_cursor=index;lines=self.capture()
            for x,y,value,args,kwargs in lines:
                self.assertLessEqual(x+text_width(value),160,(x,y,value))
            self.assertIn('エレベーター',[row[2] for row in lines])
        for index,menu in enumerate(HUB_MENUS):
            a.state,a.facility_index='facility',index
            lines=self.words()
            for key in menu:self.assertTrue(any(HUB_MENU_LABELS[key] in line for line in lines),key)
        a.state='menu'
        for x,y,value,args,kwargs in self.capture():
            self.assertLessEqual(x+text_width(value),160);self.assertLessEqual(y+8,120)

    def test_skill_names_across_skill_info_archive_training_and_replacement(self):
        a=self.a;c=a.session.party[0]
        for sid in list(c.skills):c.forget(sid)
        for sid in ('return','revive'):c.learn(a.session.skills[sid])
        a.begin_encounter();a.begin_input()
        for sid in ('return','revive'):
            name=a.session.skills[sid].name
            a.state,a.overlay,a.skill_cursor='skill',None,c.skills.index(sid)
            self.assertTrue(any(name in line for line in self.words()))
            a.state,a.overlay,a.info_tab,a.scroll='menu','info',1,c.skills.index(sid)
            self.assertTrue(any(name in line for line in self.words()))
            a.state,a.overlay='relearn_confirm',None;a.relearn_skill=sid
            self.assertTrue(any(name in line for line in self.words()))
            a.state,a.archive_page,a.archive_cursor='archive',1,list(a.session.skills).index(sid)
            a.session.discovered_skills.add(sid)
            self.assertTrue(any(name in line for line in self.words()))
            c.pending_skill=sid
            a.state,a.overlay,a.replacement_confirm='replace',None,False
            self.assertIn('新: '+name,self.words())
            c.pending_skill=None

    def test_legacy_normal_save_load_uses_mastery_contract_and_trz(self):
        path=ROOT/'tests/fixtures/ui_phase6b1_legacy_save.json'
        self.assertTrue(path.exists(),'Generate the actual pre-change save with verify_ui6b1.py --legacy first')
        old=json.loads(path.read_text(encoding='utf8'))
        s,d,e,shown=prepare_saved_game(self.a,old)
        self.assertEqual(s.treasure.banked,37)
        self.assertEqual((e.active['type'],e.active['target_floor'],e.active['progress']),('investigate',14,1))
        for sid,uses in (('return',2),('revive',1)):
            self.assertEqual(s.party[0].skill_uses[sid],uses)
            self.assertEqual(s.skills[sid].name,{'return':'リターン','revive':'リバイブ'}[sid])
        self.assertIn('revive',s.mastered_skills)
        self.assertEqual(b15_elevator_point(d),(12,0));self.assertTrue(d.finale.has_amrita)

    def test_prechange_suspend_restores_without_schema_changes(self):
        old=json.loads((ROOT/'tests/fixtures/ui_phase6b1_legacy_suspend.json').read_text(encoding='utf8'))
        prepared=self.a.suspend_manager.prepare(self.a,json.dumps({**old,'suspend_id':'1'*32}))
        self.a.activate_suspended_game(prepared);self.tick()
        self.assertEqual(json.loads(json.dumps(make_suspend_data(self.a))),old)
        self.open_quest();self.assertIn('進捗：1/3',self.words())
