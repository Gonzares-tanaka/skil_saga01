"""Balance pass contracts, two-action turns, music recovery and final impact."""
from collections import Counter,deque
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import random
import sys
import unittest
from unittest.mock import patch
import pyxel
from rpg.content import ROOT,load_content
from rpg.battle import Battle,Session
from rpg.models import Action,Enemy
from rpg.enemy_actions import choose_enemy_action,enemy_action_rows,action_categories,validate_enemy_action_lists
from rpg.final_presentation import AMRITA_BREAK_FRAME,AMRITA_FLASH_FRAMES
from rpg.sound import AudioManager

ALLOWED={'data/enemies.json','rpg/models.py','rpg/content.py','rpg/enemy_actions.py','rpg/battle.py',
         'rpg/dungeon_app.py','rpg/app.py','rpg/final_presentation.py','rpg/sound.py'}


class EnemyBalanceTests(unittest.TestCase):
    def setUp(self):
        self.s=Session(*load_content(),seed=1501)
        self.rows={r['id']:r for r in self.s.enemy_data}

    def battle(self,sid):
        for c in self.s.party: c.hp=c.max_hp=100000
        enemy=Enemy.from_definition(self.rows[sid])
        b=Battle(self.s.party,[enemy],self.s.skills,max_rounds=100000,rng=random.Random(17),boss=True)
        return b,enemy

    def round(self,b):
        b.begin_round([Action(i,'GUARD') for i,c in enumerate(b.party) if c.alive])
        while b.queue: b.step()

    def app(self):
        from rpg.dungeon_app import DungeonApp
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        with patch.object(pyxel,'init'):
            return DungeonApp(Session(*load_content(),seed=818),run=False,headless=True,start_at_title=False)

    def test_normal_count_roles_and_only_hp_str_int_changed(self):
        before=json.loads((ROOT/'tests/fixtures/enemy_balance_before.json').read_text(encoding='utf8'))
        normal=[r for r in self.s.enemy_data if not r.get('boss')]
        self.assertEqual(len(normal),18)
        for old in before['enemies']:
            current=self.rows[old['id']]
            self.assertEqual(current['id'],old['id']); self.assertEqual(current['sprite'],old['sprite'])
            if old.get('boss'): continue
            self.assertGreater(current['max_hp'],old['max_hp'])
            self.assertGreaterEqual(current['str'],old['str'])
            self.assertGreaterEqual(current['int'],old['int'])
            self.assertLess(current['max_hp']/old['max_hp'],1.36)
            for key in set(old)|set(current):
                if key not in ('max_hp','str','int'): self.assertEqual(current.get(key),old.get(key))

    def test_protected_skills_growth_status_maps_save_assets(self):
        if sys.platform=='emscripten': return
        before=json.loads((ROOT/'tests/fixtures/enemy_balance_before.json').read_text(encoding='utf8'))
        for name,digest in before['hashes'].items():
            if name not in ALLOWED:
                from tests.balance_preservation import assert_resource_unchanged
                assert_resource_unchanged(self,name,digest)
        self.assertEqual(len(self.s.skills),62)

    def test_poison_shared_maxhp_floor_minimum_and_remaining_hp(self):
        for hp,expected in ((20,1),(39,1),(40,2),(100,5),(1080,54)):
            for enemy_target in (False,True):
                b,e=self.battle('depth_lord'); target=e if enemy_target else self.s.party[0]
                target.hp=target.max_hp=hp; target.statuses={'poison':3}
                b._finish_status_turn(target,dict(target.statuses))
                self.assertEqual(target.hp,hp-expected); self.assertEqual(target.statuses['poison'],2)
                target.hp=1
                b._finish_status_turn(target,dict(target.statuses))
                self.assertEqual(target.hp,0); self.assertFalse(target.statuses)

    def test_player_poison_skill_enemy_tick_and_sleep_wake(self):
        b,e=self.battle('depth_lord'); self.s.party[0].learn(self.s.skills['venom_strike'])
        with patch.object(b.rng,'random',return_value=0): b._party_action(Action(0,'SKILL',0,'venom_strike'))
        self.assertEqual(e.statuses['poison'],3)
        e.statuses['sleep']=2; hp=e.hp; b._finish_status_turn(e,dict(e.statuses))
        self.assertEqual(hp-e.hp,54); self.assertNotIn('sleep',e.statuses)

    def test_demon_two_real_actions_and_b10_one(self):
        for sid,count in (('depth_lord',2),('skill_keeper',1),('guardian',1),('lord_of_elysion',1)):
            b,e=self.battle(sid); b.begin_round([Action(i,'GUARD') for i in range(4)])
            self.assertEqual(list(b.queue).count(('enemy',0)),count)
            with patch.object(b,'_enemy_action',wraps=b._enemy_action) as action:
                while b.queue: b.step()
            self.assertEqual(action.call_count,count); self.assertEqual(b.round,1)

    def test_demon_sleep_duration_and_poison_tick_once_per_turn(self):
        b,e=self.battle('depth_lord'); e.statuses={'poison':3,'sleep':2}; hp=e.hp
        self.round(b)
        self.assertEqual(hp-e.hp,54); self.assertEqual(e.statuses,{'poison':2})  # poison wakes sleep
        b,e=self.battle('depth_lord'); e.statuses={'sleep':2}
        with patch.object(b,'_enemy_action',wraps=b._enemy_action) as action:
            self.round(b); self.assertEqual(e.statuses,{'sleep':1}); self.assertEqual(action.call_count,0)
            self.round(b); self.assertFalse(e.statuses); self.assertEqual(action.call_count,0)
            self.round(b); self.assertEqual(action.call_count,2)

    def test_demon_paralyze_one_50percent_roll_and_skips_both(self):
        b,e=self.battle('depth_lord'); e.statuses={'paralyze':3}
        b.queue=deque([('enemy',0),('enemy',0),('party',Action(0,'GUARD'))])
        with patch.object(b.rng,'random',return_value=.49) as draw,patch.object(b,'_enemy_action') as action:
            b.step(); b.step(); self.assertEqual(draw.call_count,1); action.assert_not_called()
        self.assertEqual(e.statuses,{'paralyze':2})

    def test_demon_constraints_many_rounds(self):
        b,e=self.battle('depth_lord'); rng=random.Random(871); recent=[]; counts=Counter()
        for _ in range(10000):
            history=[]
            for move in range(2):
                ident=choose_enemy_action(e,b.enemy_actions,rng,history,recent)
                history.append(ident); recent=(recent+[ident])[-3:]; counts[ident]+=1
            self.assertNotEqual(*history)
            tags=[action_categories(b.enemy_actions[k]) for k in history]
            for category in ('major_aoe','control'):
                self.assertLessEqual(sum(category in t for t in tags),1)
        self.assertEqual(set(counts),{r['id'] for r in e.actions})

    def test_boss_roles_and_buff_does_not_repeat_while_active(self):
        b,e=self.battle('sentinel_armor'); e.effects['power_up']=(1.2,2)
        ids={choose_enemy_action(e,b.enemy_actions,random.Random(i)) for i in range(200)}
        self.assertNotIn('power_up',ids); self.assertIn('guard',ids); self.assertIn('area_attack',ids)
        for sid,needed in (('guardian',{'guard','heavy_attack'}),('skill_keeper',{'double_attack','heavy_attack'}),
                           ('sentinel_speed',{'double_attack','slow','armor_break','paralyze_grab'}),
                           ('sentinel_mind',{'area_magic','sleep_spell','confusion_touch'})):
            self.assertTrue(needed<={r['id'] for r in self.rows[sid]['actions']})

    def test_lord_phases_and_aoe_limit(self):
        b,e=self.battle('lord_of_elysion'); frequencies=[]
        for ratio in (1,.5,.25):
            e.hp=round(e.max_hp*ratio); recent=[]; count=0; rng=random.Random(71)
            for _ in range(10000):
                ident=choose_enemy_action(e,b.enemy_actions,rng,recent=recent)
                recent=(recent+[ident])[-3:]
                count+='major_aoe' in action_categories(b.enemy_actions[ident])
                self.assertFalse(len(recent)==3 and all('major_aoe' in action_categories(b.enemy_actions[k]) for k in recent))
            frequencies.append(count)
        self.assertLess(frequencies[0],frequencies[1]); self.assertLess(frequencies[1],frequencies[2])

    def test_static_ai_validation_and_no_shared_instances(self):
        validate_enemy_action_lists(self.s.enemy_data,self.battle('depth_lord')[0].enemy_actions)
        e=Enemy.from_definition(self.rows['depth_lord']); e.ai['actions_per_round']=1
        self.assertEqual(self.rows['depth_lord']['ai']['actions_per_round'],2)
        bad=deepcopy(self.s.enemy_data); bad[0]['ai']={'actions_per_round':2}
        with self.assertRaises(ValueError): validate_enemy_action_lists(bad,self.battle('depth_lord')[0].enemy_actions)
        bad=deepcopy(self.s.enemy_data); bad[0].pop('actions',None); bad[0]['ai']={'actions_per_round':2}
        with self.assertRaises(ValueError): validate_enemy_action_lists(bad,self.battle('depth_lord')[0].enemy_actions)

    def test_b5_physical_can_penetrate_and_magic_armor_break_help(self):
        b,e=self.battle('guardian'); actor=b.party[0]
        actor.strength=16; actor.intellect=18
        physical=self.s.skills['power_strike'].power(actor)
        e.hp=e.max_hp; normal=b._damage(e,round(physical))
        self.assertGreater(normal,0)
        e.guarding=True; guarded=b._damage(e,round(physical))
        self.assertLess(guarded,normal); self.assertGreater(guarded,0)
        e.guarding=False; e.effects['armor_break']=(.7,3)
        reduced_armor=b._damage(e,round(physical))
        self.assertGreater(reduced_armor,normal)
        magic=b._damage(e,round(self.s.skills['fire'].power(actor)),magic=True)
        self.assertGreater(magic,normal)

    def test_demon_counter_ko_cancels_second_action_and_round_finishes(self):
        b,e=self.battle('depth_lord'); e.hp=1
        e.actions=[dict(id='heavy_attack',weight=1)]
        for c in b.party:
            c.counter=self.s.skills['counter']; c.guarding=True
        b.queue=deque([('enemy',0),('enemy',0)])
        with patch.object(b,'_enemy_action',wraps=b._enemy_action) as action: b.step()
        self.assertEqual(action.call_count,1); self.assertEqual(b.outcome,'VICTORY')
        self.assertFalse(b.queue)

    def test_audio_failed_cache_recovers_without_restarting_success(self):
        audio=AudioManager(); audio.load()
        with patch('rpg.sound._play_music',side_effect=[False,True]) as play:
            self.assertFalse(audio.play_bgm('bgm_boss')); self.assertFalse(audio.bgm_started)
            self.assertFalse(audio.play_bgm('bgm_boss')); self.assertEqual(play.call_count,1)
            audio.retry_after=0
            self.assertTrue(audio.play_bgm('bgm_boss')); self.assertTrue(audio.bgm_started)
            self.assertTrue(audio.play_bgm('bgm_boss')); self.assertEqual(play.call_count,2)

    def test_three_guardian_victories_bgm_restores_real_channels(self):
        app=self.app(); app.enter_dungeon(); app.dungeon.debug_floor(14)
        app.dungeon.finale.start_guardians()
        from contextlib import nullcontext
        native = sys.platform != 'emscripten'
        with patch.object(pyxel,'playm',side_effect=AssertionError('native playm forbidden')) if native else nullcontext():
            for index in range(3):
                app.begin_encounter(boss=True,guardian_index=index)
                self.assertEqual(app.audio.current_bgm,'bgm_boss'); self.assertTrue(app.audio.bgm_started)
                if native: self.assertTrue(all(pyxel.play_pos(c) is not None for c in (1,2,3)))
                app.battle.outcome='VICTORY'; app.session.settle(); app.state='result'
                app.audio.play_victory(); app.fanfare_started_at=None
                for i in list(app.session.pending_replacements): app.session.resolve_replacement(i,None)
                app.finish_results()
                if index<2:
                    self.assertEqual(app.state,'guardian_between')
                    self.assertEqual(app.audio.current_bgm,'bgm_boss')
                    if native: self.assertTrue(all(pyxel.play_pos(c) is not None for c in (1,2,3)))

    def test_amrita_flash_camera_and_bgm_switch_retry_silent(self):
        app=self.app(); f=app.dungeon.finale; f.has_amrita=f.final_event_started=True
        app.begin_final_battle()
        self.assertEqual(app.audio.current_bgm,'bgm_boss'); self.assertTrue(app.battle.elysion_barrier_active)
        app.battle._party_action(Action(0,'ITEM',item_id='AMRITA')); app.start_amrita_effect()
        self.assertFalse(app.battle.elysion_barrier_active)
        self.assertEqual(AMRITA_FLASH_FRAMES,(24,25))
        for frame in (0,24,26,31,32,40):
            app.final_visual().frame=frame; app.sync_scene_audio()
            self.assertEqual(app.audio.current_bgm,'bgm_boss' if frame<32 else 'bgm_final')
            with patch.object(pyxel,'camera',wraps=pyxel.camera) as camera:
                app.draw(); self.assertEqual(camera.call_args.args,())
                if frame==26: self.assertIn((2,0),[c.args for c in camera.call_args_list])
        app.audio.enabled=False
        for _ in range(60):
            with patch.object(pyxel,'btn',new=lambda *a:False),patch.object(pyxel,'btnp',new=lambda *a:False): app.update()
            if app.state!='amrita_effect': break
        self.assertNotEqual(app.state,'amrita_effect')
        app.final_checkpoint.restore(app.session,app.dungeon,app.exploration); app.begin_final_battle()
        self.assertTrue(app.battle.elysion_barrier_active); self.assertTrue(app.dungeon.finale.has_amrita)
        self.assertEqual(app.audio.current_bgm,'bgm_boss')


if __name__=='__main__': unittest.main()
