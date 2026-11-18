"""Beta regressions: public input, remembered commands, pages, growth and quests."""
from copy import deepcopy
import json
from unittest.mock import patch
import pyxel
from tests.encounter_fixture import EncounterFixture
from rpg.models import Action
from rpg.content import ROOT,load_content
from rpg.battle import Session
from rpg.dungeon_app import DungeonApp
from rpg.runtime import development_enabled
from rpg.text import font,text_width
from rpg.growth import growth_bonus

A=pyxel.GAMEPAD1_BUTTON_A
B=pyxel.GAMEPAD1_BUTTON_B
RIGHT=pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT
LEFT=pyxel.GAMEPAD1_BUTTON_DPAD_LEFT


class Phase8ATests(EncounterFixture):
    def test_received_rules_maps_resources_and_user_texts_preserved(self):
        from tests.phase8_preservation import assert_preserved
        assert_preserved(self)

    def test_public_q_f9_and_keyboard_auto_do_not_activate_but_pad_a_does(self):
        a=self.a
        with patch.object(pyxel,'quit') as quit:
            for state in ('explore','save_confirm','final_story'):
                a.state=state
                for key in (pyxel.KEY_Q,pyxel.KEY_F9):self.tick(key)
                self.assertFalse(a.session.debug)
            quit.assert_not_called()
        a.state='explore';a.begin_encounter();a.battle_input_blocked=False
        self.tick(pyxel.KEY_A);self.assertEqual(a.state,'command')
        self.tick(A);self.assertEqual(a.state,'skill')

    def test_developer_startup_and_release_lock(self):
        session=Session(*load_content(),seed=11);session.debug=True
        with patch.object(pyxel,'init'):
            app=DungeonApp(session,run=False,headless=True,start_at_title=False,
                save_backend=self.a.save_manager.backend,suspend_backend=self.backend)
        self.assertTrue(app.debug_allowed)
        with patch('rpg.runtime.DEVELOPMENT_BUILD',False):
            self.assertFalse(development_enabled(True))
            with patch.object(pyxel,'init'):
                locked=DungeonApp(session,run=False,headless=True,start_at_title=False,
                    save_backend=self.a.save_manager.backend,suspend_backend=self.backend)
            self.assertFalse(locked.debug_allowed);self.assertFalse(locked.session.debug)
        with patch('rpg.runtime.sys.platform','emscripten'):
            self.assertFalse(development_enabled(True))

    def test_dialogs_do_not_open_inspection_or_help_overlays(self):
        a=self.a
        for state in ('save_confirm','boss_message','field_event','replace','final_story'):
            a.state=state;a.overlay=None;a.field_lines=['test'];a.field_page=0;a.field_after='explore'
            if state=='replace':a.session.party[0].pending_skill='fire'
            for key in (pyxel.KEY_D,pyxel.KEY_TAB,pyxel.KEY_H):
                self.tick(key);self.assertIsNone(a.overlay,(state,key))
                self.assertEqual(a.state,state)
            a.session.party[0].pending_skill=None

    def test_pages_use_left_right_and_a_uses_field_skill_only_on_skill_page(self):
        a=self.a;c=a.session.party[0];c.learn(a.session.skills['heal']);c.hp-=10
        a.state='menu';a.overlay='info';a.info_tab=1;a.scroll=1
        before=dict(c.skill_uses)
        self.tick(RIGHT);self.assertEqual(a.info_tab,2)
        self.tick(A);self.assertEqual(a.info_tab,2);self.assertEqual(c.skill_uses,before)
        self.tick(LEFT);self.assertEqual(a.info_tab,1)
        a.scroll=1;self.tick(A);self.assertEqual(a.state,'field_heal')

    def test_selected_skill_is_remembered_when_actor_cannot_execute(self):
        a=self.a;c=a.session.party[0];c.learn(a.session.skills['fire'])
        a.begin_encounter();a.battle_input_blocked=False
        a.commit(Action(0,'SKILL',0,'fire'))
        self.assertEqual(c.last_skill_id,'fire')
        actions=[Action(0,'SKILL',0,'fire')]+[Action(i,'GUARD') for i in (1,2,3)]
        a.battle.begin_round(actions);c.hp=0;uses=c.skill_uses['fire']
        while a.battle.queue:a.battle.step()
        self.assertEqual(c.skill_uses['fire'],uses);self.assertEqual(c.last_skill_id,'fire')
        c.hp=c.max_hp;a.begin_input();self.tick(A)
        self.assertEqual(c.skills[a.skill_cursor],'fire')

    def test_memory_stays_on_same_id_after_removal_and_falls_back_safely(self):
        c=self.a.session.party[0]
        for sid in ('fire','ice','heal'):c.learn(self.a.session.skills[sid])
        c.remember_skill('ice');c.forget('punch')
        self.assertEqual(c.skills[c.remembered_skill_index()],'ice')
        c.forget('ice');self.assertLess(c.remembered_skill_index(),len(c.skills))
        self.assertEqual(c.skills[c.remembered_skill_index()],'heal')

    def test_mastered_stars_use_history_for_old_and_new_skills_and_font_has_glyph(self):
        a=self.a;c=a.session.party[0]
        a.session.mastered_skills.update(('punch','fire'))
        c.pending_skill='fire';a.state='replace'
        with patch('rpg.app.text') as render:a.draw_replacement()
        labels=[call.args[2] for call in render.call_args_list]
        self.assertTrue(any('パンチ★' in value for value in labels))
        self.assertTrue(any(a.session.skills['fire'].name+'★' in value for value in labels))
        self.assertFalse(a.mastered_label(a.session.skills['ice']).endswith('★'))
        pyxel.cls(0);pyxel.text(0,0,'★',3,font())
        self.assertTrue(any(pyxel.pget(x,y) for y in range(8) for x in range(8)))
        for skill in a.session.skills.values():
            self.assertLessEqual(text_width('>6.'+skill.name+'★'),92,skill.id)

    def test_only_requested_text_tokens_changed_and_guardian_names_match(self):
        before=json.loads((ROOT/'tests/fixtures/phase8_before.json').read_text(encoding='utf8'))['data']
        substitutions={'独義理':'毒霧','敵の走行':'敵の装甲','帰還にする':'帰還する',
                       '欲っする':'欲する','SKILL SEAKERS':'SKILL SEEKERS',
                       'イビルナイトが倒れた。':'デーモンガードが倒れた。',
                       'キュクロープスが崩れ落ちた。':'レッドドラゴンが崩れ落ちた。'}
        for name in ('skills.json','enemies.json','pub_messages.json','finale.json'):
            expected=json.dumps(before[name],ensure_ascii=False)
            for old,new in substitutions.items():expected=expected.replace(old,new)
            self.assertEqual(json.loads(expected),json.loads((ROOT/'data'/name).read_text(encoding='utf8')),name)


class Phase8BTests(EncounterFixture):
    def test_kai_magic_bonus_is_conditional_and_mio_remains_specialist(self):
        s=self.a.session;old=deepcopy(s.settings);old.pop('character_int_growth')
        for c in s.party:
            for mode in ('speed','magic','healing'):
                c.category_uses={mode:3};c.growth_points={'INT':6 if mode!='speed' else 0}
                expected=.09 if c.party_id=='kai' and mode!='speed' else 0
                self.assertAlmostEqual(growth_bonus(c,'INT',s.settings)-growth_bonus(c,'INT',old),expected)
                for stat in ('HP','STR','AGI'):
                    self.assertEqual(growth_bonus(c,stat,s.settings),growth_bonus(c,stat,old))
        kai,mio=s.party[1:3]
        self.assertLess(s.settings['growth_rates']['SPEED']['INT']+growth_bonus(kai,'INT',s.settings),
                        s.settings['growth_rates']['MIND']['INT']+growth_bonus(mio,'INT',s.settings))

    def test_save_load_does_not_rewrite_existing_stats(self):
        from rpg.save import make_save_data,prepare_saved_game
        a=self.a
        for i,c in enumerate(a.session.party):c.intellect=31+i;c.agility=81+i
        raw=make_save_data(a);prepared=prepare_saved_game(a,raw)
        self.assertEqual([(c.intellect,c.agility) for c in prepared[0].party],[(31+i,81+i) for i in range(4)])


class Phase8CTests(EncounterFixture):
    def test_all_nine_categories_reachable_and_hunt_not_boss_only(self):
        import random
        from rpg.quests import spawn_candidates
        self.unlock();e=self.a.exploration
        for level in (1,2,3):
            pools={}
            for kind in ('explore','investigate','hunt'):
                floors=set()
                for seed in range(30):
                    q=e.make_quest(level,quest_type=kind,rng=random.Random(seed))
                    low,high=e.quest_data['target_floors'][kind][str(level)]
                    self.assertTrue(low<=q['target_floor']<=high)
                    self.assertEqual(q['reward'],e.quest_data['rewards'][kind][str(level)])
                    self.assertTrue(set(map(tuple,q['points']))<=set(spawn_candidates(self.d,q['target_floor']-1)))
                    floors.add(q['target_floor'])
                pools[kind]=floors
            self.assertLess(min(pools['explore']),min(pools['hunt']))
            self.assertTrue(pools['hunt']-{5,10,15})

    def test_existing_b15_quest_roundtrip_and_progress_survive_new_ranges(self):
        from rpg.save import make_save_data,prepare_saved_game
        from rpg.quests import spawn_candidates
        self.unlock();a=self.a;e=a.exploration
        e.accept(3,quest_type='investigate')
        q=e.active;q['target_floor']=15;q['points']=[list(p) for p in spawn_candidates(self.d,14)[:3]]
        q['investigated_points']=[q['points'][0]];q['progress']=1
        raw=make_save_data(a);prepared=prepare_saved_game(a,raw)
        self.assertEqual(prepared[2].active['target_floor'],15)
        self.assertEqual(prepared[2].active['progress'],1)
        self.assertEqual(prepared[2].active['flavor_id'],q['flavor_id'])

    def test_repeated_same_kind_can_be_accepted_without_changing_history(self):
        self.unlock();e=self.a.exploration
        for i in range(3):
            e.accept(1,quest_type='hunt')
            self.assertEqual(e.active['progress'],0)
            self.assertFalse(e.active['completed'])
            e.active=None
        self.assertEqual(e.quest_clear_counts,dict.fromkeys(('explore','investigate','hunt'),0))


class Phase8DTests(EncounterFixture):
    def dragon(self):
        from rpg.postgame import dragon_location
        self.unlock();a=self.a;a.dungeon.completion.main_game_cleared=True
        floor,point=dragon_location(self.d);self.d.floor=floor;self.d.x,self.d.y=point
        a.begin_dragon_battle();return a.battle

    def test_stages_once_jump_to_deepest_no_stats_rng_or_turn_changes(self):
        b=self.dragon();e=b.enemies[0];before=deepcopy(vars(e));rng=b.rng.getstate()
        e.hp=int(e.max_hp*.74);self.assertEqual(len(b.hp_stage_feedback()),1)
        self.assertEqual(b.hp_stage_feedback(),[])
        e.hp=int(e.max_hp*.2);lines=b.hp_stage_feedback()
        self.assertEqual(lines,[b.hp_stage_messages[2]['message']])
        self.assertEqual(b.hp_stages_shown,{0,1,2})
        e.hp=e.max_hp;e.hp=int(e.max_hp*.1);self.assertEqual(b.hp_stage_feedback(),[])
        self.assertEqual(b.round,0);self.assertEqual(b.rng.getstate(),rng)
        self.assertEqual({k:v for k,v in vars(e).items() if k!='hp'},{k:v for k,v in before.items() if k!='hp'})

    def test_real_action_emits_stage_but_victory_does_not_and_rematch_resets(self):
        b=self.dragon();e=b.enemies[0]
        e.hp=int(e.max_hp*.75)+1
        b.queue.append(('party',Action(0,'SKILL',0,'punch')))
        lines=b.step();self.assertIn(b.hp_stage_messages[0]['message'],lines)
        e.hp=1;b.queue.append(('party',Action(0,'SKILL',0,'punch')))
        lines=b.step();self.assertEqual(b.outcome,'VICTORY')
        self.assertFalse(any(stage['message'] in lines for stage in b.hp_stage_messages))
        self.a.session.settle()
        for i in list(self.a.session.pending_replacements):self.a.session.resolve_replacement(i,None)
        self.a.begin_dragon_battle();self.assertFalse(self.a.battle.hp_stages_shown)
