"""Target/status/field foundations, also exercised by the expanded roster."""
from collections import Counter, deque
from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch

from rpg.battle import Battle, Session
from rpg.battle_presentation import BattlePresentation
from rpg.content import ROOT, load_content, validate_skill
from rpg.models import Action, Enemy
from rpg.skill_resources import ensure_attack
from rpg.skill_targets import target_refs
from rpg.statuses import apply_status, cure_statuses, load_statuses


class SkillFoundationTests(unittest.TestCase):
    def setUp(self):
        self.s = Session(*load_content(), seed=817)
        self.actor = self.s.party[0]
        for c in self.s.party:
            c.hp = c.max_hp = 1000
        self.enemies = [Enemy('E'+str(i), 1000, 1, 1, 1, (0, 0),
                              defense=i*3, magic_defense=i*5) for i in range(4)]
        self.b = Battle(self.s.party, self.enemies, self.s.skills, rng=self.s.rng,
                        discovered_skills=self.s.discovered_skills,
                        mastered_skills=self.s.mastered_skills)

    def fixture(self, base='punch', **changes):
        defaults = dict(id='fixture', name='TEST', relearn_cost=0, relearn_uses=0,
                        field_usable=None)
        defaults.update(changes)
        skill = replace(self.s.skills[base], **defaults)
        validate_skill(skill)
        self.s.skills[skill.id] = skill
        self.actor.learn(skill)
        return skill

    def use(self, skill, target=0):
        # Another queued member keeps ordinary round-end cleanup out of checks.
        self.b.queue = deque([('party', Action(0, 'SKILL', target, skill.id)),
                              ('party', Action(1, 'GUARD'))])
        self.b.turn_plan = None
        return self.b.step()

    def cure(self, **changes):
        defaults = dict(effect='cure', target='ally', skill_type='support',
                        str_scale=0, agi_scale=0, int_scale=0, max_uses=3,
                        rarity='RARE', cure_statuses=tuple(load_statuses()), field_usable=True)
        defaults.update(changes)
        return self.fixture(**defaults)

    def test_roster_rarity_and_archive(self):
        self.assertEqual(len(self.s.skills), 62)
        self.assertEqual(Counter(s.rarity for s in self.s.skills.values()),
                         {'BASIC':3,'COMMON':18,'UNCOMMON':13,'RARE':20,'LEGEND':8})
        self.assertEqual(self.s.archive_summary()['total'], 62)
        raw=json.loads((ROOT/'data/skills.json').read_text(encoding='utf8'))
        self.assertEqual(set(self.s.skills), {row['id'] for row in raw})
        self.assertFalse(any('fixture' in row['id'] for row in raw))

    def test_all_physical_per_target_def_guard_and_one_resource_charge(self):
        skill=self.fixture(target='all_enemies', hits=3, cooldown=2)
        self.enemies[1].hp=0
        self.enemies[2].guarding=True
        self.enemies[3].effects['armor_break']=(.7,3)
        hp=[e.hp for e in self.enemies]; uses=self.actor.skill_uses[skill.id]
        self.use(skill)
        power=skill.power(self.actor)
        self.assertEqual([hp[i]-e.hp for i,e in enumerate(self.enemies)],
                         [power,0,max(1,round((power-6)*.5)),max(1,round(power-9*.7))])
        self.assertEqual(self.actor.skill_uses[skill.id], uses-1)
        self.assertEqual(self.actor.cooldowns[skill.id], 3)
        self.assertEqual(self.actor.used_skills, {skill.id:1})
        self.assertEqual(self.actor.category_uses, {'physical':1})
        self.assertEqual(self.actor.growth_points, skill.growth)

    def test_all_magic_uses_individual_mdef(self):
        skill=self.fixture('fire', target='all_enemies')
        self.actor.intellect=20
        self.enemies[2].effects['armor_break']=(.1,3)
        self.use(skill)
        self.assertEqual([1000-e.hp for e in self.enemies], [40,35,30,25])

    def test_all_damage_keeps_each_target_barrier(self):
        skill=self.fixture(target='all_enemies')
        self.enemies[2].id='lord_of_elysion'
        self.b.elysion_barrier_active=True
        self.b.final_data={'barrier_hint':[]}
        self.use(skill)
        self.assertEqual(self.enemies[2].hp,1000)
        self.assertLess(self.enemies[0].hp,1000)

    def test_all_heal_living_only_and_one_charge(self):
        skill=self.fixture('heal', target='all_allies')
        self.actor.intellect=10
        for c in self.s.party: c.hp=10
        self.s.party[2].hp=0
        self.use(skill)
        self.assertEqual([c.hp for c in self.s.party],[35,35,0,35])
        self.assertEqual(self.actor.skill_uses[skill.id],5)
        self.assertEqual(self.actor.category_uses,{'healing':1})

    def test_all_buff_and_debuff_exclude_ko_refresh_not_stack(self):
        for base,target in (('power_up','all_allies'),('armor_break','all_enemies')):
            with self.subTest(base=base):
                self.setUp(); skill=self.fixture(base,target=target)
                group=self.s.party if target=='all_allies' else self.enemies
                group[2].hp=0
                self.use(skill); self.actor.cooldowns.clear(); self.use(skill)
                for i,c in enumerate(group):
                    self.assertEqual(c.effects.get(skill.effect),None if i==2 else (skill.modifier,3))
                self.assertEqual(self.actor.used_skills[skill.id],2)

    def test_random_one_living_and_no_preview_rng(self):
        skill=self.fixture(target='random_enemy')
        self.enemies[1].hp=0
        state=self.b.rng.getstate()
        expected=random.Random(); expected.setstate(state)
        selected=expected.choice([0,2,3])
        self.b.queue=deque([('party',Action(0,'SKILL',999,skill.id)),('party',Action(1,'GUARD'))])
        visual=BattlePresentation(self.b)
        self.assertTrue(visual.start())
        self.assertEqual(self.b.rng.getstate(),state)
        self.assertEqual(visual.skill_effect_targets,[])
        self.b.step()
        changed=[i for i,e in enumerate(self.enemies) if e.hp not in (0,1000)]
        self.assertEqual(changed,[selected])
        self.assertEqual(self.b.rng.getstate(),expected.getstate())
        self.assertEqual(self.b.player_skill_visual['targets'],[('enemy',selected)])
        visual.after_action([True,False,True,True])
        self.assertEqual(visual.enemy_effect_targets,[('enemy',selected)])
        visual.draw_effect(Mock())
        self.b.step(); self.assertIsNone(self.b.player_skill_visual)

    def test_random_status_uses_same_selected_enemy(self):
        skill=self.fixture(effect='status', target='random_enemy', status_id='poison', status_chance=100)
        self.enemies[2].hp=0
        self.use(skill)
        targets=[i for i,e in enumerate(self.enemies) if e.statuses]
        self.assertEqual(len(targets),1)
        self.assertNotIn(2,targets)
        self.assertEqual(self.b.player_skill_visual['targets'],[('enemy',targets[0])])

    def test_pure_all_four_statuses_damage_free_and_visual_success(self):
        for status in load_statuses():
            with self.subTest(status=status):
                self.setUp()
                skill=self.fixture(effect='status',status_id=status,status_chance=100)
                self.use(skill)
                self.assertEqual(self.enemies[0].hp,1000)
                self.assertEqual(self.enemies[0].statuses,{status:self.b.status_definitions[status].duration})
                self.assertEqual(self.b.status_visual_events[0]['status_id'],status)
                self.assertTrue(any(self.b.status_definitions[status].name in s for s in self.b.status_messages))

    def test_status_chance_fail_zero_and_poison_turn_duration(self):
        skill=self.fixture(effect='status',status_id='poison',status_chance=0)
        self.use(skill); self.assertFalse(self.enemies[0].statuses)
        skill=replace(skill,status_chance=35); self.b.skills[skill.id]=skill
        self.actor.cooldowns.clear()
        with patch.object(self.b.rng,'random',return_value=.99): self.use(skill)
        self.assertFalse(self.enemies[0].statuses)
        self.assertFalse(self.b.status_visual_events)
        self.actor.cooldowns.clear()
        with patch.object(self.b.rng,'random',return_value=.1): self.use(skill)
        enemy=self.enemies[0]; hp=enemy.hp
        self.b.queue=deque([('enemy',0)]); self.b.turn_plan=None; self.b.step()
        self.assertEqual(enemy.hp,hp-50)
        self.assertEqual(enemy.statuses['poison'],2)

    def test_control_exclusion_poison_coexistence_and_refresh(self):
        skill=self.fixture(effect='status',status_id='sleep',status_chance=100)
        apply_status(self.enemies[0],'poison')
        self.use(skill); self.enemies[0].statuses['sleep']=1
        self.actor.cooldowns.clear(); self.use(skill)
        self.assertEqual(self.enemies[0].statuses,{'poison':3,'sleep':2})
        for ident in ('paralyze','confusion'):
            self.b.skills[skill.id]=replace(skill,status_id=ident)
            self.actor.cooldowns.clear(); self.use(self.b.skills[skill.id])
            self.assertEqual(self.enemies[0].statuses,{'poison':3,'sleep':2})

    def test_damage_status_order_ko_and_magic_defense(self):
        for base,status in (('punch','poison'),('fire','confusion')):
            for lethal in (False,True):
                with self.subTest(base=base,lethal=lethal):
                    self.setUp(); self.actor.intellect=20
                    skill=self.fixture(base,status_id=status,status_chance=100)
                    e=self.enemies[0]; e.defense=2; e.magic_defense=7; e.hp=1 if lethal else 1000
                    self.use(skill)
                    expected=1 if lethal else (8-2 if base=='punch' else 40-7)
                    self.assertEqual(e.hp,(1 if lethal else 1000)-expected)
                    self.assertEqual(bool(e.statuses),not lethal)
                    self.assertEqual(self.actor.used_skills[skill.id],1)
                    self.assertEqual(self.actor.growth_points,skill.growth)

    def test_status_resistance_immunity_and_independent_all_rolls(self):
        skill=self.fixture(effect='status',target='all_enemies',status_id='poison',status_chance=50)
        self.enemies[1].status_resistances={'poison':50}
        self.enemies[2].status_immunities=('poison',)
        self.enemies[3].hp=0
        with patch.object(self.b.rng,'random',side_effect=[.4,.4]) as roll:
            self.use(skill)
        self.assertEqual(roll.call_count,2)
        self.assertEqual([bool(e.statuses) for e in self.enemies],[True,False,False,False])

    def test_cure_each_status_no_hp_or_debuff_changes(self):
        for ident in load_statuses():
            with self.subTest(status=ident):
                self.setUp(); skill=self.cure()
                c=self.s.party[1]; apply_status(c,ident); c.hp=75
                c.effects={'weaken':(.8,3),'armor_break':(.7,3),'slow':(.5,3)}
                before=deepcopy(c.effects)
                self.use(skill,1)
                self.assertFalse(c.statuses); self.assertEqual(c.hp,75)
                self.assertEqual(c.effects,before)
                self.assertEqual(self.b.last_skill_cured_count,1)
                self.assertEqual(self.b.status_visual_events[0]['kind'],'cure')

    def test_cure_subset_multiple_and_zero_count(self):
        skill=self.cure(cure_statuses=('poison',))
        c=self.s.party[1]; apply_status(c,'poison'); apply_status(c,'sleep')
        self.use(skill,1)
        self.assertEqual(c.statuses,{'sleep':2}); self.assertEqual(self.b.last_skill_cured_count,1)
        self.actor.cooldowns.clear(); self.use(skill,1)
        self.assertEqual(self.b.last_skill_cured_count,0)
        self.assertEqual(cure_statuses(c,('sleep','poison')),('sleep',))
        self.assertEqual(cure_statuses(c,tuple(load_statuses())),())

    def test_all_cure_living_only(self):
        skill=self.cure(target='all_allies')
        for c in self.s.party: apply_status(c,'poison'); apply_status(c,'sleep')
        # Sleeping actor cannot cast; poison only is sufficient on the actor.
        self.actor.statuses.pop('sleep')
        self.s.party[2].hp=0
        hp=[c.hp for c in self.s.party]
        self.use(skill)
        self.assertEqual(self.b.last_skill_cured_count,5)
        self.assertEqual([c.hp for c in self.s.party],hp)
        self.assertTrue(all(not c.statuses for i,c in enumerate(self.s.party) if i!=2))
        self.assertEqual(self.s.party[2].statuses,{'poison':3,'sleep':2})

    def test_cure_api_never_revives_or_changes_dead_statuses(self):
        c=self.s.party[1]; c.hp=0; c.statuses={'poison':2}
        self.assertEqual(cure_statuses(c,('poison',)),())
        self.assertEqual(c.hp,0); self.assertEqual(c.statuses,{'poison':2})

    def test_field_flags_existing_and_nonfield_rejection(self):
        self.assertEqual({s.id for s in self.s.skills.values() if s.field_usable},
                         {'first_aid','heal','renew','full_heal','return',
                          'group_aid','mending_wind','cure','purify_wind','miracle'})
        self.assertFalse(self.s.field_use(0,'punch').used)

    def test_field_heals_dispatch_and_wrapper_agree_all_four(self):
        for sid in ('first_aid','heal','renew','full_heal'):
            with self.subTest(skill=sid):
                self.setUp(); skill=self.s.skills[sid]; self.actor.learn(skill)
                self.s.party[1].hp=10
                result=self.s.field_use(0,sid,1)
                self.assertTrue(result.used)
                self.assertEqual(self.s.party[1].hp,10+skill.power(self.actor))
                self.assertEqual(self.actor.skill_uses[sid],skill.max_uses-1)
                self.assertFalse(self.actor.used_skills or self.actor.growth_points or self.actor.category_uses)
                self.assertFalse(self.actor.cooldowns)

    def test_field_cure_persistent_poison_no_growth_noop_and_ko(self):
        skill=self.cure(); c=self.s.party[1]; c.statuses={'poison':2}; c.hp=50
        result=self.s.field_use(0,skill.id,1)
        self.assertEqual((result.used,result.cured_count),(True,1))
        self.assertEqual(c.hp,50); self.assertFalse(c.statuses)
        self.assertFalse(self.actor.used_skills or self.actor.growth_points or self.actor.category_uses)
        uses=self.actor.skill_uses[skill.id]
        self.assertFalse(self.s.field_use(0,skill.id,1).used)
        c.hp=0; c.statuses={'poison':2}
        self.assertFalse(self.s.field_use(0,skill.id,1).used)
        self.assertEqual(self.actor.skill_uses[skill.id],uses)

    def test_field_all_cure_spends_once_and_mastered_record_only(self):
        skill=self.cure(target='all_allies',max_uses=1)
        for c in self.s.party: c.statuses={'poison':2}
        self.s.party[2].hp=0
        result=self.s.field_use(0,skill.id)
        self.assertEqual(result.cured_count,3)
        self.assertEqual(self.s.party[2].statuses,{'poison':2})
        self.assertNotIn(skill.id,self.actor.skills)
        self.assertIn(skill.id,self.s.mastered_skills)
        self.actor.learn(skill); self.assertEqual(self.actor.power_multiplier(skill),1)

    def test_field_all_heal_and_self_cure(self):
        skill=self.fixture('heal',target='all_allies')
        for c in self.s.party: c.hp=10
        self.s.party[2].hp=0
        result=self.s.field_use(0,skill.id)
        self.assertTrue(result.used)
        self.assertEqual(self.actor.skill_uses[skill.id],5)
        self.assertEqual(self.s.party[2].hp,0)
        skill=self.cure(id='fixture2',target='self')
        self.actor.statuses={'poison':2}
        self.assertEqual(self.s.field_use(0,skill.id).cured_count,1)

    def test_return_dispatch_preserves_finite_stock_and_mastered(self):
        skill=self.s.skills['return']; self.actor.learn(skill); self.actor.skill_uses[skill.id]=1
        self.s.discovered_skills.add(skill.id)
        result=self.s.field_use(0,skill.id)
        self.assertTrue(result.used and result.returned)
        self.assertIn('return',self.s.mastered_skills)
        self.assertNotIn('return',self.actor.skills)
        self.assertFalse(self.actor.growth_points or self.actor.category_uses)

    def test_restore_existing_fifteen_and_future_rare_cure(self):
        expected={'punch':(1,15),'quick_hit':(1,15),'spark':(1,14),'power_strike':(2,10),
                  'double_slash':(2,8),'quick_stab':(2,13),'fire':(2,8),'ice':(2,10),
                  'first_aid':(2,6),'weaken':(2,4),'slow':(2,4),'power_up':(2,4),
                  'return':(3,1),'armor_break':(4,3),'focus':(4,3)}
        self.assertEqual({sid:(self.s.skills[sid].relearn_cost,self.s.skills[sid].relearn_uses)
                          for sid in expected},expected)
        skill=self.cure(relearn_cost=4,relearn_uses=2)
        self.assertTrue(skill.can_relearn)
        self.actor.forget(skill.id); self.s.discovered_skills.add(skill.id); self.s.treasure.banked=5
        self.s.relearn(0,skill.id)
        self.assertEqual((self.actor.skill_uses[skill.id],self.s.treasure.banked),(2,1))

    def test_attack_rescue_does_not_accept_status_or_cure(self):
        for effect in ('status','cure'):
            with self.subTest(effect=effect):
                self.setUp()
                skill=self.cure() if effect=='cure' else self.fixture(effect='status',status_id='poison',status_chance=100)
                self.actor.forget('punch')
                ensure_attack(self.actor,self.s.skills,discovered=self.s.discovered_skills)
                self.assertEqual(self.actor.skill_uses['punch'],30)

    def test_all_presentation_draws_each_target_without_rng_or_rule_changes(self):
        for base,target in (('fire','all_enemies'),('heal','all_allies')):
            with self.subTest(target=target):
                self.setUp(); skill=self.fixture(base,target=target)
                group=self.enemies if target=='all_enemies' else self.s.party
                group[2].hp=0
                self.b.queue=deque([('party',Action(0,'SKILL',999,skill.id))])
                state=self.b.rng.getstate(); hp=[c.hp for c in group]
                visual=BattlePresentation(self.b); self.assertTrue(visual.start())
                visual.enter('skill_effect'); surface=Mock(); visual.draw_effect(surface)
                self.assertEqual(surface.blt.call_count,3)
                self.assertEqual(state,self.b.rng.getstate()); self.assertEqual(hp,[c.hp for c in group])

    def test_validate_supported_combinations_and_reject_bad_fields(self):
        base=self.s.skills['punch']
        invalid=[dict(target='invalid'),dict(target='all_allies'),dict(status_id='curse'),
                 dict(status_chance=35),dict(status_chance=-1),dict(status_chance=101),
                 dict(status_id='poison',status_chance=float('nan')),dict(status_chance=True),
                 dict(effect='status'),dict(effect='revive',target='all_allies'),
                 dict(effect='cure',target='ally'),dict(cure_statuses=['poison']),
                 dict(effect='cure',target='ally',cure_statuses=['bad']),
                 dict(effect='cure',target='ally',cure_statuses=['poison','poison']),
                 dict(field_usable=True),dict(field_usable='yes'),dict(relearn_cost=4,relearn_uses=0),
                 dict(relearn_cost=0,relearn_uses=2),dict(relearn_cost=-1),
                 dict(relearn_cost=True,relearn_uses=1),dict(relearn_cost=1,relearn_uses=31),
                 dict(effect='heal',target='all_enemies'),dict(effect='return',target='self',field_usable=False)]
        for changes in invalid:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_skill(replace(base,**changes))
        for target in ('enemy','all_enemies','random_enemy'):
            validate_skill(replace(base,target=target,status_id='poison',status_chance=35))
        for target in ('ally','self','all_allies'):
            validate_skill(replace(base,effect='cure',target=target,cure_statuses=('poison',),field_usable=True))

    def app(self):
        import pyxel
        from rpg.dungeon_app import DungeonApp
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        with patch.object(pyxel,'init'):
            app=DungeonApp(Session(*load_content(),seed=87),run=False,headless=True,start_at_title=False)
        app.enter_dungeon(); app.opening_input_blocked=False
        return app

    def press(self,app,key):
        import pyxel
        with patch.object(pyxel,'btnp',side_effect=lambda code,*args:code==key),patch.object(pyxel,'btn',return_value=False):
            app.update(); app.draw()

    def test_pad_auto_targets_skip_target_selection(self):
        import pyxel
        for target in ('all_enemies','all_allies','random_enemy'):
            with self.subTest(target=target):
                app=self.app(); app.begin_encounter(); app.battle_input_blocked=False
                base='heal' if target=='all_allies' else 'punch'
                skill=replace(app.session.skills[base],id='fixture',target=target,relearn_cost=0,relearn_uses=0)
                app.session.skills[skill.id]=skill; app.session.party[0].learn(skill)
                app.begin_input(); app.state='skill'; app.skill_cursor=1
                self.press(app,pyxel.GAMEPAD1_BUTTON_A)
                self.assertEqual(app.state,'command')
                self.assertEqual(app.actions[0].skill_id,skill.id)
                self.assertEqual(app.actor_position,1)

    def test_pad_field_single_cure_and_cancel(self):
        import pyxel
        app=self.app(); s=app.session
        skill=replace(s.skills['punch'],id='fixture',name='治療テスト',effect='cure',target='ally',
                      cure_statuses=('poison','sleep'),field_usable=True,max_uses=3,relearn_cost=0,relearn_uses=0)
        s.skills[skill.id]=skill; s.party[0].learn(skill); s.party[1].statuses={'poison':2}
        app.overlay='info'; app.info_tab=1; app.info_character=0; app.scroll=1
        self.press(app,pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(app.state,'field_heal')
        self.press(app,pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual((app.state,app.overlay),('explore','info'))
        self.press(app,pyxel.GAMEPAD1_BUTTON_A)
        self.press(app,pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.press(app,pyxel.GAMEPAD1_BUTTON_A)
        self.assertFalse(s.party[1].statuses)
        self.assertEqual(s.party[0].skill_uses[skill.id],2)
        self.assertFalse(s.party[0].growth_points)

    def test_pad_field_all_cure_skips_target_selection(self):
        import pyxel
        app=self.app(); s=app.session
        skill=replace(s.skills['punch'],id='fixture',effect='cure',target='all_allies',
                      cure_statuses=('poison',),field_usable=True,max_uses=1,relearn_cost=0,relearn_uses=0)
        s.skills[skill.id]=skill; s.party[0].learn(skill)
        for c in s.party: c.statuses={'poison':2}
        app.overlay='info'; app.info_tab=1; app.info_character=0; app.scroll=1
        self.press(app,pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((app.state,app.overlay),('explore','info'))
        self.assertTrue(all(not c.statuses for c in s.party))
        self.assertEqual(app.scroll,0)

    def test_broken_audio_all_skill_and_status_visual_finish(self):
        import pyxel
        app=self.app(); app.begin_encounter(); app.battle_input_blocked=False
        for c in app.session.party: c.hp=c.max_hp=1000
        skill=replace(app.session.skills['punch'],id='fixture',target='all_enemies',status_id='poison',status_chance=100)
        app.session.skills[skill.id]=skill; app.session.party[0].learn(skill)
        b=app.battle
        for e in b.enemies: e.hp=e.max_hp=1000
        b.queue=deque([('party',Action(0,'SKILL',0,skill.id))]); b.round=1
        app.state='resolve'; app.delay=0; app.confirm=app.confirm_held=lambda:False
        with patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
             patch.object(pyxel,'playm',side_effect=RuntimeError('interrupted')), \
             patch.object(pyxel,'play_pos',side_effect=RuntimeError('closed')):
            app.update()
            for _ in range(150):
                app.update(); app.draw()
                if not app.battle_visual().active and not b.queue and not app.pending: break
            else: self.fail('silent multi/status presentation blocked progress')
        self.assertTrue(all(e.statuses.get('poison')==3 for e in b.enemies))
        self.assertEqual(app.session.party[0].skill_uses[skill.id],29)


if __name__ == '__main__':
    unittest.main()
