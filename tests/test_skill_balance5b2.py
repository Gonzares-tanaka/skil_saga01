"""5B-2 durations, advisory cure UI, execution-time checks and old saves."""
from copy import deepcopy
from dataclasses import replace
import json
import random
from unittest.mock import patch
import pyxel

from tests.encounter_fixture import EncounterFixture
from tests.skill_balance5b2_preservation import baseline, assert_preserved, adjusted_rows
from tests.rescue5c_preservation import adopted_skill_rows
from rpg.battle import Battle
from rpg.models import Action, Enemy, Skill, battle_agility
from rpg.save import make_save_data, prepare_saved_game
from rpg.statuses import active_statuses, damage_hp
from rpg.suspend import make_suspend_data, job_result
from rpg.text import text_width, fit
from tools.audit_skill_balance5b2 import ready, resolve, offense

SUPPORT = ('power_up','focus','sanctuary','cure','purify_wind')

class SkillBalance5B2Tests(EncounterFixture):
    def battle(self, ids=SUPPORT, count=4):
        s=self.a.session
        party=ready(s.party[:count],s.skills,ids)
        party[0].agility=100
        enemy=Enemy('PROBE',100000,1,1,1,(0,0))
        return Battle(party,[enemy],s.skills,rng=random.Random(5110))

    def test_only_authorized_received_tree_changes_including_audio_and_sleep_text(self):
        assert_preserved(self)
        old={r['id']:Skill(**r) for r in adopted_skill_rows(baseline()['skills'])}
        self.assertEqual(len(old),62)
        for sid in ('sleep_spell','nightmare','time_stop','return','battle_cry','focus_field','iron_wall',
                    'double_slash','triple_slash','rapid_edge','seven_slash'):
            self.assertEqual(self.a.session.skills[sid],old[sid])

    def test_exact_durations_modifiers_uses_cd_and_shared_descriptions(self):
        expected={r['id']:r for r in adjusted_rows(baseline()['skills'])}
        for sid,modifier,duration,uses,cd in (('power_up',1.4,4,8,0),('focus',1.5,4,6,0),('sanctuary',.55,3,2,4)):
            s=self.a.session.skills[sid]
            self.assertEqual((s.modifier,s.duration,s.max_uses,s.cooldown),(modifier,duration,uses,cd))
            self.assertIn(f'{duration}ターン',s.formula())
            self.assertEqual(s.description,expected[sid]['description'])
            self.assertLessEqual(text_width(fit(s.description,148)),148)
            with patch('rpg.app.text') as text:
                self.a.skill_details(self.a.session.party[0],s)
            self.assertTrue(any(f'{duration}ターン' in c.args[2] for c in text.call_args_list))

    def test_self_buff_round_end_expiry_and_added_attack_opportunity(self):
        for sid,attack,expected in (('power_up','punch',[0,28,28,28,20]),('focus','spark',[0,36,36,36,24])):
            b=self.battle((sid,attack),1)
            per_round=[]
            with patch.object(b,'_enemy_action',return_value=[]):
                for t in range(5):
                    hp=b.enemies[0].hp
                    resolve(b,[Action(0,'SKILL',0,sid if t==0 else attack)])
                    per_round.append(hp-b.enemies[0].hp)
                    self.assertEqual(b.party[0].effects.get(sid),(b.skills[sid].modifier,3-t) if t<3 else None)
            self.assertEqual(per_round,expected)

    def test_ally_order_and_defense_offense_totals_independent_expectations(self):
        for sid,base,boost in (('power_up',20,28),('focus',24,36)):
            for df in (0,16):
                for timing in ('self','ally_early','ally_late'):
                    for turns in (2,3,4,5):
                        for variant,duration in (('none',0),('old',3),('new',4)):
                            n=1 if timing=='self' else 2
                            buff_attacks=0 if variant=='none' else min(turns-1,duration-1)+(timing=='ally_early')
                            expected=(n*turns-(variant!='none'))*(base-df)+buff_attacks*(boost-base)
                            self.assertEqual(offense(sid,variant,df,turns,timing)[0],expected,
                                             (sid,df,timing,turns,variant))

    def test_focus_fire_meteor_and_three_heals_at_new_final_round(self):
        for sid,expected in (('fire',60),('meteor',210),('first_aid',45),('renew',135),('miracle',150)):
            b=self.battle(('focus',sid),4)
            c=b.party[0]
            with patch.object(b,'_enemy_action',return_value=[]):
                for t in range(3):
                    resolve(b,[Action(0,'SKILL',0,'focus') if t==0 else Action(0,'GUARD'),
                               *[Action(i,'GUARD') for i in range(1,4)]])
            self.assertEqual(c.effects['focus'],(1.5,1))
            for target in b.party: target.hp=1000
            old_hp=[x.hp for x in b.party]; enemy_hp=b.enemies[0].hp
            with patch.object(b,'_enemy_action',return_value=[]):
                resolve(b,[Action(0,'SKILL',0,sid),*[Action(i,'GUARD') for i in range(1,4)]])
            if sid in ('fire','meteor'):
                self.assertEqual(enemy_hp-b.enemies[0].hp,expected)
            else:
                affected=4 if sid=='miracle' else 1
                self.assertEqual([c.hp-hp for c,hp in zip(b.party,old_hp)], [expected]*affected+[0]*(4-affected))
            self.assertNotIn('focus',c.effects)

    def test_sanctuary_all_targets_physical_magic_guard_expiry_and_refresh(self):
        for magic in (False,True):
            for guarding in (False,True):
                b=self.battle()
                b._skill_effect(b.party[0],b.skills['sanctuary'],0)
                for c in b.party:
                    c.guarding=guarding
                    self.assertEqual(b._damage(c,100,magic=magic),28 if guarding else 55)
                b.party[0].effects['guard_up']=(.55,1)
                b._skill_effect(b.party[0],b.skills['sanctuary'],0)
                self.assertTrue(all(c.effects['guard_up']==(.55,3) for c in b.party))
                b._skill_effect(b.party[0],b.skills['iron_wall'],0)
                self.assertTrue(all(c.effects['guard_up']==(.7,3) for c in b.party))
                b._skill_effect(b.party[0],b.skills['sanctuary'],0)
                with patch.object(b,'_enemy_action',return_value=[]):
                    for t in range(3):
                        resolve(b,[Action(i,'GUARD') for i in range(4)])
                        self.assertTrue(all(c.effects.get('guard_up')==((.55,2-t) if t<2 else None) for c in b.party))

    def test_cure_reservation_gains_ailment_or_loses_it_before_execution(self):
        for sid in ('cure','purify_wind'):
            for moment in ('healthy','gained','cleared'):
                b=self.battle()
                c,target=b.party[:2]
                if moment=='cleared': target.statuses={'poison':3}
                b.begin_round([Action(0,'SKILL',1,sid),*[Action(i,'GUARD') for i in range(1,4)]])
                # No restriction at reservation. Re-evaluate actual execution state.
                if moment=='gained': target.statuses={'poison':3,'sleep':2}
                if moment=='cleared': target.statuses.clear()
                uses=c.skill_uses[sid]
                while b.queue[0] != ('party',Action(0,'SKILL',1,sid)): b.step()
                b.step()
                self.assertEqual(c.skill_uses[sid],uses-(moment=='gained'))
                self.assertFalse(target.statuses)
                self.assertEqual(c.used_skills.get(sid,0),int(moment=='gained'))
                self.assertEqual(bool(c.growth_points),moment=='gained')
                self.assertEqual(c.cooldowns.get(sid,0),b.skills[sid].cooldown+1 if moment=='gained' else 0)
                self.assertNotIn(('party',Action(0,'SKILL',1,sid)),b.queue)

    def test_cure_each_ailment_and_group_all_living_targets_only(self):
        for status in ('poison','paralyze','sleep','confusion'):
            b=self.battle(); b.party[1].statuses={status:3}
            b._party_action(Action(0,'SKILL',1,'cure'))
            self.assertFalse(active_statuses(b.party[1]))
            self.assertEqual(b.party[0].skill_uses['cure'],2)
        b=self.battle()
        for c in b.party: c.statuses={'poison':3,'paralyze':3}
        b._party_action(Action(0,'SKILL',0,'purify_wind'))
        self.assertTrue(all(not active_statuses(c) for c in b.party))
        self.assertEqual(b.party[0].skill_uses['purify_wind'],1)

    def test_healthy_cure_ui_allows_target_queue_keyboard_and_gamepad(self):
        a=self.a
        for key in (pyxel.KEY_Z,pyxel.GAMEPAD1_BUTTON_A):
            if 'cure' not in a.session.party[0].skills: a.session.party[0].learn(a.session.skills['cure'])
            a.begin_encounter(); a.begin_input()
            a.selected_skill=a.session.skills['cure']; a.state='target'; a.target_cursor=1
            a.battle_input_blocked=False
            self.assertEqual(len(a.targets()),4)
            with patch('rpg.app.text') as text: a.draw_battle()
            self.assertIn('治療対象なし / 予約可',[c.args[2] for c in text.call_args_list])
            self.tick(key)
            self.assertEqual(a.actions[0],Action(0,'SKILL',1,'cure'))
            self.assertEqual(a.session.party[0].skill_uses['cure'],3)
            a.session.settled=True

    def test_group_cure_hint_updates_from_live_states_and_keeps_queue(self):
        a=self.a
        a.begin_encounter(); a.begin_input()
        c=a.actor; c.learn(a.session.skills['purify_wind'])
        skill=a.session.skills['purify_wind']; a.state='skill'; a.skill_cursor=c.skills.index(skill.id)
        with patch('rpg.app.text') as text: a.draw_skills()
        self.assertIn('治療対象なし / 予約可',[c.args[2] for c in text.call_args_list])
        a.session.party[2].statuses={'poison':2}
        with patch('rpg.app.text') as text: a.draw_skills()
        self.assertNotIn('治療対象なし / 予約可',[c.args[2] for c in text.call_args_list])
        a.session.party[2].statuses.clear(); a.battle_input_blocked=False
        self.tick(pyxel.KEY_Z)
        self.assertEqual(a.actions[0].skill_id,'purify_wind')

    def test_field_hint_no_target_no_stock_loss_and_successful_treatment(self):
        a=self.a; s=a.session; c=s.party[0]
        for sid in ('cure','purify_wind'):
            c.learn(s.skills[sid]); a.field_skill=sid; a.field_actor=0; a.item_cursor=1
            a.field_return='explore'; a.state='field_heal'
            if sid=='cure':
                with patch('rpg.dungeon_app.text') as text: a.draw_field_heal()
                self.assertIn('治療対象なし / 消費なし',[c.args[2] for c in text.call_args_list])
            result=s.field_use(0,sid,1)
            self.assertFalse(result.used); self.assertIn('治療対象なし',result.messages)
            self.assertEqual(c.skill_uses[sid],s.skills[sid].max_uses)
            s.party[1].statuses={'poison':3}
            result=s.field_use(0,sid,1)
            self.assertTrue(result.used); self.assertFalse(s.party[1].statuses)
            self.assertEqual(c.skill_uses[sid],s.skills[sid].max_uses-1)
            self.assertFalse(c.growth_points or c.cooldowns)

    def test_sleep_boss_immunity_existing_visual_damage_and_wake(self):
        b=self.battle(('nightmare','sleep_spell','time_stop'))
        b.boss=True
        enemy=b.enemies[0]
        for sid in ('nightmare','sleep_spell','time_stop'):
            hp=enemy.hp
            b._party_action(Action(0,'SKILL',0,sid))
            self.assertNotIn('sleep',enemy.statuses)
            self.assertTrue(any('睡眠は無効' in m for m in b.status_messages))
            self.assertEqual(hp-enemy.hp,40 if sid=='nightmare' else 0)
        b.boss=False; self.assertTrue(b.apply_status(enemy,'sleep',100))
        damage_hp(enemy,1); self.assertNotIn('sleep',enemy.statuses)

    def test_slow_order_two_future_rounds_all_targets_no_power_change(self):
        for sid in ('slow','slow_field'):
            b=self.battle((sid,'punch'),1)
            b.party[0].agility=20; b.enemies[0].agility=30
            if sid=='slow_field': b.enemies.append(deepcopy(b.enemies[0]))
            orders=[]
            with patch.object(b,'_enemy_action',return_value=[]):
                for t in range(4):
                    orders.append(resolve(b,[Action(0,'SKILL',0,sid if t==0 else 'punch')])[0][0])
                    for e in b.enemies:
                        self.assertEqual(e.effects.get('slow'),(.5,2-t) if t<2 else None)
                        self.assertEqual(e.strength,1)
            self.assertEqual(orders,['enemy','party','party','enemy'])

    def old_save_setup(self):
        s=self.a.session
        for c in s.party:
            for sid in list(c.skills): c.forget(sid)
            for sid in (*SUPPORT,'double_slash'): c.learn(s.skills[sid]); c.skill_uses[sid]-=1
            s.discovered_skills.update(c.skills)
        s.mastered_skills.update(('focus','double_slash'))
        for c in s.party: c.mastered_skills=s.mastered_skills

    def assert_loaded_skills(self, session):
        for c in session.party:
            self.assertEqual(c.skills,[*SUPPORT,'double_slash'])
            for sid in SUPPORT: self.assertEqual(c.skill_uses[sid],session.skills[sid].max_uses-1)
        self.assertTrue({'focus','double_slash'}<=session.mastered_skills)
        b=Battle(session.party,[Enemy('PROBE',10000,1,1,1,(0,0))],session.skills,rng=random.Random(1))
        for sid,duration in (('power_up',4),('focus',4),('sanctuary',3)):
            b._party_action(Action(0,'SKILL',0,sid))
            self.assertEqual(b.party[0].effects[b.skills[sid].effect][1],duration)

    def test_old_normal_save_ids_uses_mastery_and_new_definitions(self):
        self.old_save_setup(); s=self.a.session; current=s.skills
        s.skills={r['id']:Skill(**r) for r in baseline()['skills']}
        try: raw=json.loads(json.dumps(make_save_data(self.a)))
        finally: s.skills=current
        restored=prepare_saved_game(self.a,raw)[0]
        self.assertEqual(raw['save_version'],1)
        self.assert_loaded_skills(restored)

    def test_old_suspend_state_exact_and_one_time_consume(self):
        self.old_save_setup(); s=self.a.session; current=s.skills
        s.skills={r['id']:Skill(**r) for r in baseline()['skills']}
        try: job_result(self.a.suspend_manager.save(self.a))
        finally: s.skills=current
        raw=job_result(self.backend.start('read'))
        prepared=self.a.suspend_manager.prepare(self.a,raw)
        job_result(self.backend.start('consume',raw))
        self.a.activate_suspended_game(prepared)
        self.assertTrue(self.backend.start('consume',raw).error)
        self.assert_loaded_skills(self.a.session)
