"""5B-1 coefficients, exact acquisition previews, single-hit rules and v1 saves."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json
from unittest.mock import patch

from tests.encounter_fixture import EncounterFixture
from tests.skill_balance_preservation import assert_skill_balance_preserved, baseline
from tests.rescue5c_preservation import adopted_skill_rows
from tests.test_rare_skill_presentation import make_battle, finish_visual
from rpg.content import load_content
from rpg.models import Skill
from rpg.save import make_save_data, prepare_saved_game
from rpg.suspend import make_suspend_data, job_result


IDS = ('double_slash', 'triple_slash', 'rapid_edge', 'seven_slash')
SPECS = ((1.15, 0, 2, 15, 1), (1, 0, 3, 8, 2),
         (.35, .65, 4, 6, 3), (.55, .15, 7, 4, 4))


class SkillBalance5B1Tests(EncounterFixture):
    def test_only_authorized_methods_and_data_changed_all_other_files_exact(self):
        assert_skill_balance_preserved(self)

    def test_four_coefficients_hits_uses_cooldowns_and_all_sixty_two_rarities(self):
        skills = self.a.session.skills
        for sid, expected in zip(IDS, SPECS):
            s = skills[sid]
            self.assertEqual((s.str_scale, s.agi_scale, s.hits, s.max_uses, s.cooldown), expected)
            self.assertEqual((s.int_scale, s.target, s.effect), (0, 'enemy', 'damage'))
        self.assertEqual(Counter(s.rarity for s in skills.values()),
                         dict(BASIC=3, COMMON=18, UNCOMMON=13, RARE=20, LEGEND=8))

    def test_future_preview_equals_learned_copy_with_single_rounding_all_four(self):
        # Many fractional bases expose incorrect double rounding in a preview.
        for sid in (*IDS, 'punch', 'full_heal'):
            skill = self.a.session.skills[sid]
            for strength, agility in ((53,20),(28,54),(3,1),(7,9),(11,17)):
                for mastered in (False,True):
                    actor = deepcopy(self.a.session.party[0])
                    for old in list(actor.skills): actor.forget(old)
                    actor.mastered_skills = {sid} if mastered else set()
                    actor.strength, actor.agility = strength, agility
                    expected = skill.power(actor, next_copy=True)
                    self.assertFalse(actor.skills or actor.mastered_copies)
                    actor.learn(skill)
                    self.assertEqual(expected, skill.power(actor), (sid,strength,agility,mastered))
                    raw = (strength*skill.str_scale + agility*skill.agi_scale + actor.intellect*skill.int_scale)*skill.hits
                    self.assertEqual(expected, max(1,round(raw*(1.2 if mastered and skill.effect=='damage' else 1))))

    def test_shared_mastery_does_not_promote_current_normal_copy(self):
        actor = self.a.session.party[0]
        actor.strength = 53
        actor.mastered_skills.add('punch')
        skill = self.a.session.skills['punch']
        self.assertEqual(skill.power(actor), 53)
        self.assertEqual(skill.power(actor,next_copy=True), 64)
        self.assertEqual(skill.power(actor,apply_mastery=False,next_copy=True),53)
        self.assertNotIn('punch',actor.mastered_copies)

    def test_replacement_ui_new_future_old_current_and_training(self):
        a, actor = self.a, self.a.session.party[0]
        actor.strength = 53
        for sid in (*IDS, 'punch'):
            for mastered in (False,True):
                actor.mastered_skills.clear()
                if mastered: actor.mastered_skills.add(sid)
                actor.pending_skill = sid
                for training in (False,True):
                    if training and not a.session.skills[sid].can_relearn:
                        continue
                    a.session.pending_relearn = (0,sid) if training else None
                    a.replacement_cursor, a.replacement_confirm = 0,False
                    with patch('rpg.app.text') as text:
                        a.draw_replacement()
                    rows = {c.args[1]:c.args[2] for c in text.call_args_list}
                    self.assertIn(f'威力{a.session.skills[sid].power(actor,next_copy=True)}', rows[23])
                    self.assertIn('威力53', rows[88])
                    self.assertTrue(all(0<=c.args[0]<160 and 0<=c.args[1]<120 for c in text.call_args_list))
                    self.assertNotIn('punch',actor.mastered_copies)

    def test_four_aggregate_damage_defense_hp_and_resources_exactly_once(self):
        for sid in IDS:
            for mode in ('normal','mastered','last_use'):
                b = make_battle(sid,mode=mode)
                actor,enemy,skill = b.party[0],b.enemies[0],b.skills[sid]
                before,uses = enemy.hp,actor.skill_uses[sid]
                expected = round(max(1,skill.power(actor,apply_mastery=False)-enemy.defense)*actor.power_multiplier(skill))
                with patch.object(b,'_damage',wraps=b._damage) as damage, \
                     patch.object(b,'_lose_hp',wraps=b._lose_hp) as hp_change:
                    _, lines, _, _, applied = finish_visual(b)
                self.assertEqual(applied,1)
                damage.assert_called_once()
                hp_change.assert_called_once()
                self.assertEqual(before-enemy.hp,expected)
                self.assertEqual(sum(' -' in line for line in lines),1)
                self.assertEqual(actor.skill_uses.get(sid,0),uses-1)
                self.assertEqual(actor.used_skills,{sid:1})
                self.assertEqual(actor.growth_points,skill.growth)
                if uses==1:
                    self.assertNotIn(sid,actor.skills)
                    self.assertIn(sid,b.mastered_skills)

    def test_full_heal_initial_text_dynamic_remaining_and_unchanged_healing(self):
        b = make_battle('full_heal')
        skill = b.skills['full_heal']
        expected=next(r for r in adopted_skill_rows(baseline()['skills']) if r['id']=='full_heal')
        self.assertEqual(skill.description,expected['description'])
        self.assertNotIn('残り2回',skill.description)
        self.assertEqual((skill.int_scale,skill.max_uses,skill.cooldown),(10,2,0))
        finish_visual(b)
        self.assertEqual(b.party[0].skill_uses['full_heal'],1)
        a = self.a
        a.session.party = b.party
        a.order, a.actor_position = [0,1,2,3],0
        a.skill_cursor = b.party[0].skills.index('full_heal')
        with patch('rpg.app.text') as text:
            a.draw_skills()
        self.assertTrue(any(c.args[2]=='1/2' for c in text.call_args_list))
        self.assertEqual(skill.power(b.party[0],next_copy=True),400)

    def set_skill_states(self,mode):
        s = self.a.session
        for actor in s.party:
            for sid in list(actor.skills): actor.forget(sid)
            actor.mastered_skills = s.mastered_skills
            for sid in IDS:
                if mode=='mastered': s.mastered_skills.add(sid)
                actor.learn(s.skills[sid])
                actor.skill_uses[sid] -= 1
                s.discovered_skills.add(sid)
        if mode=='shared_only':
            s.mastered_skills.update(IDS)

    def test_existing_v1_saves_ids_uses_copy_mastery_and_current_definitions(self):
        for mode in ('normal','mastered','shared_only'):
            self.a.session.mastered_skills.clear()
            self.set_skill_states(mode)
            # Serialize with the actual pre-adjustment definitions, then load
            # using current content. Coefficients are deliberately not saved.
            current = self.a.session.skills
            self.a.session.skills = {r['id']:Skill(**r) for r in baseline()['skills']}
            try:
                data = json.loads(json.dumps(make_save_data(self.a)))
            finally:
                self.a.session.skills = current
            self.assertEqual(data['save_version'],1)
            for row in data['party'][0]['skills']:
                self.assertEqual(set(row),{'skill_id','uses','max_uses','mastered_copy'})
            restored = prepare_saved_game(self.a,data)[0]
            for old,actor in zip(self.a.session.party,restored.party):
                self.assertEqual((actor.skills,actor.skill_uses,actor.mastered_copies),
                                 (old.skills,old.skill_uses,old.mastered_copies))
                for sid in IDS:
                    self.assertEqual(restored.skills[sid],self.a.session.skills[sid])
                    self.assertEqual(restored.skills[sid].power(actor),self.a.session.skills[sid].power(old))

    def test_suspend_all_four_exact_state_single_use_and_new_coefficients(self):
        for mode in ('normal','mastered','shared_only'):
            self.a.session.mastered_skills.clear()
            self.set_skill_states(mode)
            before = json.loads(json.dumps(make_suspend_data(self.a)))
            job_result(self.a.suspend_manager.save(self.a))
            raw = job_result(self.backend.start('read'))
            prepared = self.a.suspend_manager.prepare(self.a,raw)
            job_result(self.backend.start('consume',raw))
            self.a.activate_suspended_game(prepared)
            self.d = self.a.dungeon
            self.assertEqual(json.loads(json.dumps(make_suspend_data(self.a))),before)
            self.assertTrue(self.backend.start('consume',raw).error)
            for sid,spec in zip(IDS,SPECS):
                s=self.a.session.skills[sid]
                self.assertEqual((s.str_scale,s.agi_scale,s.hits,s.max_uses,s.cooldown),spec)

    def test_kai_late_gain_and_expected_instant_burst_order(self):
        actor = self.a.session.party[1]
        actor.strength,actor.agility = 28,54
        previous = {r['id']:Skill(**r) for r in baseline()['skills']}
        now = self.a.session.skills
        for sid in ('rapid_edge','seven_slash'):
            self.assertGreater(now[sid].power(actor),previous[sid].power(actor))
        self.assertGreater(now['double_slash'].power(actor),now['power_strike'].power(actor))
        self.assertGreater(now['triple_slash'].power(actor),now['double_slash'].power(actor))
