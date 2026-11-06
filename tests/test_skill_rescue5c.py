"""Character-specific rescue, unchanged trigger paths, presentation and SaveData v1."""
from collections import deque
from copy import deepcopy
import json
import random
from unittest.mock import patch
import pyxel

from tests.encounter_fixture import EncounterFixture
from tests.rescue5c_preservation import assert_preserved, baseline, adopted_skill_rows
from rpg.battle import Battle, Session
from rpg.content import ROOT, load_content
from rpg.models import Action, Enemy, PARTY_IDS
from rpg.save import make_save_data, prepare_saved_game
from rpg.skill_resources import ensure_attack, RESCUE_SKILLS
from rpg.suspend import make_suspend_data, job_result
from rpg.text import wrap_lines, text_width

EXPECTED=('spark','spark','punch','spark')
SUPPORT=('heal','renew','first_aid','full_heal','counter','berserk')


class SkillRescue5CTests(EncounterFixture):
    def clear(self,c):
        for sid in list(c.skills): c.forget(sid)

    def ready(self,index=0,sid='punch'):
        s=self.a.session
        c=s.party[index]
        self.clear(c);c.learn(s.skills[sid]);c.skill_uses[sid]=1
        e=Enemy('PROBE',100000,1,1,1,(0,0))
        b=Battle(s.party,[e],s.skills,rng=s.rng,discovered_skills=s.discovered_skills,
                 mastered_skills=s.mastered_skills,inventory=s.inventory,max_rounds=999)
        return c,b

    def cast(self,b,index,sid):
        b.queue=deque([('party',Action(index,'SKILL',0,sid))])
        return b.step()

    def test_only_rescue_changes_all_skill_data_and_resources_exact(self):
        assert_preserved(self)
        self.assertEqual(len(self.a.session.skills),62)
        self.assertEqual(json.loads((ROOT/'data/skills.json').read_text(encoding='utf8')),
                         adopted_skill_rows(baseline()['skills']))

    def test_stable_identity_all_four_independent_of_names_growth_sprites_and_order(self):
        s=self.a.session
        self.assertEqual(tuple(c.party_id for c in s.party),PARTY_IDS)
        by_id=dict(zip(PARTY_IDS,EXPECTED))
        for c in reversed(s.party):
            self.clear(c);c.name='変更した名前';c.growth_type='MIND';c.sprite=(128,128)
            c.strength,c.agility,c.intellect=999,999,999
            ensure_attack(c,s.skills,discovered=s.discovered_skills)
            self.assertEqual(c.skills,[by_id[c.party_id]])
            self.assertEqual(c.skill_uses,{by_id[c.party_id]:s.skills[by_id[c.party_id]].max_uses})

    def test_normal_basic_stats_and_uses_no_special_damage_rule(self):
        s=self.a.session
        self.assertEqual((s.skills['spark'].int_scale,s.skills['spark'].max_uses,s.skills['spark'].cooldown),(1.2,28,0))
        self.assertEqual((s.skills['punch'].str_scale,s.skills['punch'].max_uses,s.skills['punch'].cooldown),(1,30,0))
        for i,sid in enumerate(EXPECTED):
            c,b=self.ready(i)
            self.clear(c);ensure_attack(c,s.skills,discovered=s.discovered_skills)
            before=c.skill_uses[sid];raw=s.skills[sid].power(c)
            hp=b.enemies[0].hp
            self.cast(b,i,sid)
            self.assertEqual(hp-b.enemies[0].hp,raw)
            self.assertEqual(c.skill_uses[sid],before-1)
            self.assertEqual(c.growth_points,s.skills[sid].growth)

    def test_no_rng_no_trz_no_donor_transfer_and_idempotent(self):
        s=self.a.session
        s.party[2].hp=0;self.clear(s.party[2])
        c=s.party[0];self.clear(c)
        state=s.rng.getstate();trz=(s.treasure.banked,s.treasure.unbanked)
        donor=deepcopy(s.party[2]);archive=set(s.mastered_skills)
        first=ensure_attack(c,s.skills,discovered=s.discovered_skills)
        second=ensure_attack(c,s.skills,discovered=s.discovered_skills)
        self.assertTrue(first);self.assertEqual(second,[])
        self.assertEqual(s.rng.getstate(),state)
        self.assertEqual((s.treasure.banked,s.treasure.unbanked),trz)
        self.assertEqual(s.party[2],donor)
        self.assertEqual(s.mastered_skills,archive)

    def test_surviving_damage_or_drain_even_cooling_down_prevents_rescue(self):
        s=self.a.session;c=s.party[0]
        for sid in ('punch','drain','meteor','spark'):
            self.clear(c);c.learn(s.skills[sid]);c.skill_uses[sid]=1;c.cooldowns[sid]=4
            state=deepcopy(c)
            self.assertEqual(ensure_attack(c,s.skills),[])
            self.assertEqual(c,state)

    def test_zero_stock_cleanup_and_support_counter_do_not_count_as_attack(self):
        s=self.a.session;c=s.party[0]
        self.clear(c)
        for sid in ('punch','heal','counter'):c.learn(s.skills[sid])
        c.skill_uses['punch']=0
        ensure_attack(c,s.skills,discovered=s.discovered_skills)
        self.assertEqual(c.skills,['heal','counter','spark'])
        self.assertNotIn('punch',s.mastered_skills)

    def test_full_support_loadout_replaces_only_last_never_seven_slots(self):
        s=self.a.session
        for c,sid in zip(s.party,EXPECTED):
            self.clear(c)
            for old in SUPPORT:c.learn(s.skills[old])
            before=dict(c.skill_uses)
            lines=ensure_attack(c,s.skills,6,s.discovered_skills)
            self.assertEqual(c.skills,list(SUPPORT[:-1])+[sid])
            self.assertEqual(len(set(c.skills)),6)
            self.assertEqual({k:c.skill_uses[k] for k in SUPPORT[:-1]}, {k:before[k] for k in SUPPORT[:-1]})
            self.assertIn('放棄',lines[0])
            self.assertEqual(ensure_attack(c,s.skills,6),[])

    def test_last_attack_mastered_then_rescue_and_twice_exhausted_rescue_same_id(self):
        s=self.a.session
        for i,rescue_id in enumerate(EXPECTED):
            s.mastered_skills.clear()
            for member in s.party: member.mastered_copies.clear()
            c,b=self.ready(i,'power_strike')
            lines=self.cast(b,i,'power_strike')
            self.assertIn('power_strike',s.mastered_skills)
            self.assertEqual(c.skills,[rescue_id])
            self.assertLess(next(j for j,v in enumerate(lines) if 'MASTERED' in v),
                            next(j for j,v in enumerate(lines) if 'こうげき' in v))
            for repeat in range(2):
                c.skill_uses[rescue_id]=1
                self.cast(b,i,rescue_id)
                self.assertEqual(c.skills,[rescue_id])
                self.assertEqual(c.skill_uses[rescue_id],s.skills[rescue_id].max_uses)
                self.assertIn(rescue_id,s.mastered_skills)
                self.assertIn(rescue_id,c.mastered_copies)
                self.assertEqual(s.skills[rescue_id].power(c),
                    max(1,round((c.strength*s.skills[rescue_id].str_scale+c.intellect*s.skills[rescue_id].int_scale)*1.2)))

    def test_acquisition_not_mastery_and_existing_other_copy_not_promoted(self):
        s=self.a.session;c=s.party[0];mio=s.party[2]
        self.clear(c);lines=ensure_attack(c,s.skills,discovered=s.discovered_skills)
        self.assertIn('spark',s.discovered_skills)
        self.assertNotIn('spark',s.mastered_skills)
        self.assertNotIn('spark',c.mastered_copies)
        self.assertNotIn('spark',mio.mastered_copies)
        c,b=self.ready(0,'spark');self.cast(b,0,'spark')
        self.assertIn('spark',c.mastered_copies)
        self.assertNotIn('spark',mio.mastered_copies)
        self.assertEqual(mio.skill_uses['spark'],28)

    def test_full_twenty_eight_uses_before_re_rescue_and_old_last_hit_not_promoted(self):
        s=self.a.session;c,b=self.ready(0)
        c.intellect=8
        self.cast(b,0,'punch')
        self.assertEqual(c.skill_uses['spark'],28)
        for use in range(1,29):
            hp=b.enemies[0].hp
            lines=self.cast(b,0,'spark')
            self.assertEqual(hp-b.enemies[0].hp,10)  # Last old-copy hit stays normal.
            self.assertEqual(c.skill_uses['spark'],28-use if use<28 else 28)
            self.assertEqual(any('こうげき' in v for v in lines),use==28)
            self.assertEqual('spark' in c.mastered_copies,use==28)
        self.assertEqual(c.used_skills['spark'],28)
        self.assertEqual(c.skills,['spark'])
        hp=b.enemies[0].hp;self.cast(b,0,'spark')
        self.assertEqual(hp-b.enemies[0].hp,12)
        self.assertEqual(c.skill_uses['spark'],27)

    def test_simultaneous_exhaustion_once_each_round_end_then_no_duplicates(self):
        s=self.a.session
        for c in s.party:c.skill_uses[c.skills[0]]=1
        b=Battle(s.party,[Enemy('E',100000,1,1,1,(0,0))],s.skills,
                 mastered_skills=s.mastered_skills,discovered_skills=s.discovered_skills)
        b.queue=deque(('party',Action(i,'SKILL',0,c.skills[0])) for i,c in enumerate(s.party))
        lines=[]
        while b.queue:lines.extend(b.step())
        self.assertEqual(sum('こうげきのてだて' in v for v in lines),4)
        for c,sid in zip(s.party,EXPECTED):self.assertEqual(c.skills,[sid])
        b.queue=deque([('party',Action(0,'GUARD'))]);self.assertFalse(any('こうげき' in v for v in b.step()))

    def test_messages_order_names_and_pixel_width_all_four(self):
        s=self.a.session
        for c,sid in zip(s.party,EXPECTED):
            self.clear(c);lines=ensure_attack(c,s.skills)
            self.assertEqual(lines,[f'{c.name} こうげきのてだてが','なくなった！','ピンチの中で',
                f'{RESCUE_SKILLS[c.party_id][1]}の「{s.skills[sid].name}」を','おもいだした！'])
            self.assertTrue(all(text_width(v)<=144 for v in wrap_lines(lines,36)))

    def test_victory_on_last_attack_keeps_rescue_then_results_and_no_new_spark(self):
        a,s=self.a,self.a.session
        s.settings['spark_chance']=0
        c,b=self.ready(0);b.enemies[0].hp=1
        s.battle=b;s.settled=False;s.auto_recover=False;s.spark_multiplier=1
        lines=self.cast(b,0,'punch')
        self.assertEqual(b.outcome,'VICTORY')
        self.assertIn('spark',c.skills)
        results=s.settle()
        self.assertEqual(sum('こうげき' in v for v in lines),1)
        self.assertEqual(sum('こうげき' in v for v in results),1)
        self.assertFalse(s.pending_replacements)

    def test_start_battle_notice_uses_existing_buttons_and_never_audio_wait(self):
        a=self.a;self.clear(a.session.party[0])
        a.begin_encounter()
        self.assertEqual(a.state,'command')
        self.tick();self.assertEqual(a.overlay,'rescue')
        for button in (pyxel.GAMEPAD1_BUTTON_A,pyxel.GAMEPAD1_BUTTON_B):
            self.tick()  # Release; only new presses advance.
            with patch('rpg.app.text') as text:
                a.draw()
            self.assertTrue(all(c.args[0]+text_width(c.args[2])<=160 for c in text.call_args_list if c.args[1]>=80))
            self.tick(button)
        self.assertIsNone(a.overlay)
        self.assertEqual(a.state,'command')
        self.assertFalse(a.session.rescue_notices)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state,'skill')

    def test_buffered_a_cannot_skip_entry_notice_or_trigger_skill(self):
        a=self.a;self.clear(a.session.party[0]);a.begin_encounter();self.tick()
        with patch.object(pyxel,'btn',side_effect=lambda key:key==pyxel.GAMEPAD1_BUTTON_A), \
             patch.object(pyxel,'btnp',side_effect=lambda key,*args:key==pyxel.GAMEPAD1_BUTTON_A):
            for _ in range(10):a.update()
        self.assertEqual((a.overlay,a.rescue_offset,a.state),('rescue',0,'command'))

    def test_replacement_preserves_existing_rule_no_duplication_or_arbitrary_discard(self):
        s=self.a.session;c=s.party[0]
        self.clear(c)
        for sid in ('punch',*SUPPORT[:4],'counter'):c.learn(s.skills[sid])
        s.settled=True;c.pending_skill='berserk'
        s.resolve_replacement(0,0)
        self.assertEqual(len(c.skills),6);self.assertEqual(c.skills.count('spark'),1)
        self.assertNotIn('counter',c.skills)
        self.assertEqual(c.skill_uses['spark'],28)
        self.assertTrue(s.rescue_notices)
        with self.assertRaises(ValueError):s.resolve_replacement(0,0)
        self.assertEqual(c.skill_uses['spark'],28)
        # Existing optional replacement can refresh an unmastered rescue copy:
        # accept a nonattack in its last slot, then the safety net replaces it.
        c.skill_uses['spark']=2;c.pending_skill='slow'
        s.resolve_replacement(0,5)
        self.assertEqual((len(c.skills),c.skills.count('spark'),c.skill_uses['spark']),(6,1,28))
        self.assertNotIn('spark',s.mastered_skills)

    def test_training_still_refuses_replacing_only_attack_with_support(self):
        s=self.a.session;c=s.party[0]
        self.clear(c)
        for sid in ('punch',*SUPPORT[:5]):c.learn(s.skills[sid])
        s.treasure.banked=100;s.discovered_skills.add('slow');s.relearn(0,'slow')
        before=deepcopy(c);trz=s.treasure.banked
        with self.assertRaises(ValueError):s.resolve_replacement(0,0)
        self.assertEqual(c,before);self.assertEqual(s.treasure.banked,trz)

    def test_field_skill_old_trigger_preserved_and_invalid_cure_does_not_create_rescue(self):
        s=self.a.session;c=s.party[0]
        self.clear(c);c.learn(s.skills['cure'])
        result=s.field_use(0,'cure',0)
        self.assertFalse(result.used);self.assertEqual(c.skills,['cure'])
        c.learn(s.skills['heal']);c.skill_uses['heal']=1;c.hp=1
        result=s.field_use(0,'heal',0)
        self.assertTrue(result.used);self.assertEqual(c.skills,['cure','spark'])
        self.assertTrue(any('おもいだした' in v for v in result.messages))

    def test_old_save_held_skills_uses_names_mastery_unchanged_and_identity_restored(self):
        a=self.a;s=a.session
        for i,c in enumerate(s.party):
            c.name=f'別名{i}';c.skill_uses[c.skills[0]]-=2
        before=json.loads(json.dumps(make_save_data(a)))
        loaded=prepare_saved_game(a,before)[0]
        for i,(old,c) in enumerate(zip(s.party,loaded.party)):
            self.assertEqual(c.party_id,PARTY_IDS[i])
            self.assertEqual((c.name,c.skills,c.skill_uses,c.mastered_copies),
                             (old.name,old.skills,old.skill_uses,old.mastered_copies))
            self.assertNotIn('party_id',before['party'][i])
        self.assertEqual(before['save_version'],1)

    def test_save_before_rescue_does_not_grant_at_load_then_correct_next_trigger(self):
        a=self.a;s=a.session;self.clear(s.party[0])
        before=make_save_data(a);loaded=prepare_saved_game(a,before)[0]
        self.assertEqual(loaded.party[0].skills,[])
        ensure_attack(loaded.party[0],loaded.skills,discovered=loaded.discovered_skills)
        self.assertEqual(loaded.party[0].skills,['spark'])

    def test_rescued_normal_and_mastered_copies_normal_save_and_suspend_exact_once(self):
        a=self.a
        for mastered in (False,True):
            s=a.session
            if mastered:s.mastered_skills.update(EXPECTED)
            for c,sid in zip(s.party,EXPECTED):
                self.clear(c);ensure_attack(c,s.skills,discovered=s.discovered_skills)
                c.skill_uses[sid]-=3
            raw=make_save_data(a);loaded=prepare_saved_game(a,raw)[0]
            for old,c in zip(s.party,loaded.party):
                self.assertEqual((c.party_id,c.skills,c.skill_uses,c.mastered_copies),
                                 (old.party_id,old.skills,old.skill_uses,old.mastered_copies))
            before=json.loads(json.dumps(make_suspend_data(a)))
            self.assertNotIn('party_id',json.dumps(before));self.assertNotIn('rescue_notices',json.dumps(before))
            job_result(a.suspend_manager.save(a));saved=job_result(self.backend.start('read'))
            prepared=a.suspend_manager.prepare(a,saved)
            job_result(self.backend.start('consume',saved));a.activate_suspended_game(prepared)
            self.assertEqual(json.loads(json.dumps(make_suspend_data(a))),before)
            self.assertTrue(self.backend.start('consume',saved).error)
            self.assertEqual(tuple(c.party_id for c in a.session.party),PARTY_IDS)

    def test_pre_rescue_information_not_exposed_in_help_or_replacement(self):
        app=(ROOT/'rpg/app.py').read_text(encoding='utf8')
        readme=(ROOT/'README.md').read_text(encoding='utf8')
        self.assertNotIn('攻撃技なし:末尾を救済パンチに',app)
        self.assertNotIn('**試作用の救済**',readme)
        self.assertNotIn('ピンチの中で',readme)
