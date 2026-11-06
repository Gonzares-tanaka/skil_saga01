"""Explicit suspend, exact expedition restoration, cursor memory, boss sleep."""
from collections import deque
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import pyxel

from rpg.battle import Battle, Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Action, Enemy
from rpg.quests import spawn_candidates
from rpg.save import FileSaveBackend, make_save_data, SaveError
from rpg.suspend import (FileSuspendBackend, SuspendManager, make_suspend_data,
                         prepare_suspend_game, job_result)
from rpg.tiles import TILE_CHEST, TILE_RARE_CHEST, TILE_DOOR, TILE_HEAL_POINT


def encoded(data):
    return json.loads(json.dumps(data))


class SuspendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True); pyxel._tests_initialized = True

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.backend = FileSuspendBackend(root/'save/suspend.json')
        self.normal = FileSaveBackend(root/'save/save.json')
        with patch.object(pyxel, 'init'):
            self.a = DungeonApp(Session(*load_content(), seed=128), run=False, headless=True,
                start_at_title=False, save_backend=self.normal, suspend_backend=self.backend)
        self.tick()
        self.a.hub_intro_shown = True
        self.a.enter_dungeon()

    def tick(self, key=None):
        with patch.object(pyxel, 'btn', return_value=False), \
             patch.object(pyxel, 'btnp', new=lambda k, *args: k == key):
            self.a.update(); self.a.draw()

    def rich(self, floor=6):
        a=self.a; s,d,e=a.session,a.dungeon,a.exploration
        d.defeated_bosses.update((4,9)); d.debug_floor(floor)
        a.player_facing='left'
        s.treasure.banked,s.treasure.unbanked=17,13
        s.inventory.counts.update(POTION=7,REMEDY=1,**{'PHOENIX ASH':2})
        c=s.party[0]
        for sid in ('fire','return'):
            c.learn(s.skills[sid]); s.discovered_skills.add(sid)
        c.hp=17; c.statuses={'poison':3}; c.skill_uses['fire']=2
        c.cooldowns={'fire':2}; c.growth_points={'INT':2.5}
        c.used_skills={'fire':3}; c.category_uses={'magic':3}
        c.effects={'power_up':(1.2,2)}; c.counter=s.skills['counter']
        c.remember_skill('fire'); s.party[1].hp=0
        e.accept(floor//5+1,quest_type='investigate')
        q=e.active; q['target_floor']=floor+1
        q['points']=[list(p) for p in reversed(spawn_candidates(d,floor)[-q['required_count']:])]
        q['investigated_points']=[q['points'][-1]]; q['progress']=1
        d.steps,d.grace=42,2
        for f in range(15):
            springs=d.positions(f,TILE_HEAL_POINT)
            if springs: e.springs.add((f,*springs[0]))
        chests=d.positions(floor,TILE_CHEST)+d.positions(floor,TILE_RARE_CHEST)
        if chests:
            p=(floor,*chests[0]); d.opened.add(p)
            d.chest_loot[p]={'kind':'TREASURE','amount':2}; d.last_reward=deepcopy(d.chest_loot[p])
        a.state='explore'; a.overlay=None

    def save_ui(self):
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.a.menu_cursor=5
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state,'suspend_confirm')
        self.assertEqual(self.a.suspend_choice,1)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.tick()
        self.assertEqual(self.a.state,'title')
        self.assertEqual(self.a.audio.current_bgm,'bgm_title')

    def resume_ui(self):
        self.tick()
        self.a.title_cursor=2
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        for _ in range(4): self.tick()

    def test_b1_b7_b13_roundtrip_every_runtime_field_and_single_use(self):
        for floor in (0,6,12):
            with self.subTest(floor=floor+1):
                if floor: self.setUp()
                self.rich(floor)
                before=encoded(make_suspend_data(self.a))
                self.save_ui()
                self.assertTrue(self.backend.path.exists())
                self.assertIn('中断から',self.a.title_options())
                self.resume_ui()
                self.assertEqual(self.a.state,'explore')
                self.assertEqual(encoded(make_suspend_data(self.a)),before)
                self.assertFalse(self.backend.path.exists() or self.backend.claim.exists())
                self.assertNotIn('中断から',self.a.title_options())
                second=self.backend.start('read')
                with self.assertRaises(SaveError): job_result(second)

    def test_random_and_flavor_streams_resume_without_rerolls(self):
        self.rich()
        rng=random.Random(); rng.setstate(self.a.session.rng.getstate())
        flavor=random.Random(); flavor.setstate(self.a.exploration.flavor_rng.getstate())
        expected=[rng.random() for _ in range(30)]
        expected_flavor=[flavor.random() for _ in range(30)]
        self.save_ui(); self.resume_ui()
        self.assertEqual([self.a.session.rng.random() for _ in range(30)],expected)
        self.assertEqual([self.a.exploration.flavor_rng.random() for _ in range(30)],expected_flavor)

    def test_opened_chest_cached_roll_and_spring_cannot_repeat(self):
        self.rich()
        self.save_ui(); self.resume_ui()
        d=self.a.dungeon
        if d.opened:
            d.floor,d.x,d.y=next(iter(d.opened))
            before=self.a.session.treasure.unbanked
            self.assertEqual(d.interact()[0],'')
            self.assertEqual(self.a.session.treasure.unbanked,before)
        self.assertTrue(self.a.exploration.springs)

    def test_normal_save_kept_and_old_version_load_uses_saved_trz(self):
        a=self.a; a.enter_camp(); a.state='facility'; a.facility_index=0
        a.session.treasure.banked=19
        a.save_manager.save(a); normal=self.normal.path.read_bytes()
        self.assertEqual(json.loads(normal)['save_version'],1)
        a.enter_dungeon(); a.session.treasure.unbanked=8
        self.save_ui(); self.resume_ui()
        self.assertEqual(self.normal.path.read_bytes(),normal)
        a.continue_game()
        self.assertEqual(a.state,'camp')
        self.assertEqual((a.session.treasure.banked,a.session.treasure.unbanked),(19,0))

    def test_corrupt_and_incompatible_data_never_consumed_or_applied(self):
        self.rich(); data=encoded(make_suspend_data(self.a))
        samples=['{bad json',json.dumps({**data,'suspend_version':999})]
        bad=deepcopy(data); bad['dungeon']['x']=999999; samples.append(json.dumps(bad))
        for raw in samples:
            with self.subTest(raw=raw[:30]):
                self.backend.path.parent.mkdir(parents=True,exist_ok=True)
                self.backend.path.write_text(raw,encoding='utf8')
                self.a.state='title'; self.a.suspend_available=True; self.a.opening_input_blocked=False
                party=self.a.session.party
                self.a.title_cursor=2; self.tick(pyxel.GAMEPAD1_BUTTON_A)
                for _ in range(3): self.tick()
                self.assertEqual(self.a.state,'title_no_save')
                self.assertIs(self.a.session.party,party)
                self.assertEqual(self.backend.path.read_text(encoding='utf8'),raw)

    def test_write_failure_stays_in_game_without_touching_normal_save(self):
        self.rich(); self.normal.write({'sentinel':'normal'})
        before=self.normal.path.read_bytes()
        with patch('rpg.suspend.FileSaveBackend.write',side_effect=OSError('full disk')):
            self.tick(pyxel.GAMEPAD1_BUTTON_B); self.a.menu_cursor=5
            self.tick(pyxel.GAMEPAD1_BUTTON_A); self.a.suspend_choice=0
            self.tick(pyxel.GAMEPAD1_BUTTON_A); self.tick()
        self.assertEqual(self.a.state,'suspend_confirm')
        self.assertTrue(self.a.suspend_error)
        self.assertEqual(self.normal.path.read_bytes(),before)
        self.assertFalse(self.backend.path.exists())

    def test_delete_failure_rolls_back_storage_and_does_not_publish_restore(self):
        self.rich(); self.save_ui(); raw=self.backend.path.read_bytes()
        party=self.a.session.party
        unlink=Path.unlink
        def fail_claim(path,*args,**kwargs):
            if path == self.backend.claim: raise PermissionError('cannot consume')
            return unlink(path,*args,**kwargs)
        with patch.object(Path,'unlink',new=fail_claim): self.resume_ui()
        self.assertEqual(self.a.state,'title_no_save')
        self.assertIs(self.a.session.party,party)
        self.assertEqual(self.backend.path.read_bytes(),raw)
        self.assertFalse(self.backend.claim.exists())

    def test_precommit_crash_claim_is_recoverable_and_consumes_once(self):
        self.rich(); self.save_ui()
        self.backend.path.replace(self.backend.claim)
        self.resume_ui()
        self.assertEqual(self.a.state,'explore')
        self.assertFalse(self.backend.path.exists() or self.backend.claim.exists())

    def test_same_file_cannot_be_consumed_twice(self):
        self.rich(); self.save_ui()
        raw=job_result(self.backend.start('read'))
        job_result(self.backend.start('consume',raw))
        with self.assertRaises(SaveError): job_result(self.backend.start('consume',raw))

    def test_only_stable_exploration_and_no_automatic_checkpoint(self):
        for state in ('command','skill','resolve','result','replace','field_event','final_story',
                      'guardian_between','boss_message','battle_transition','field_heal'):
            self.a.state=state
            self.assertFalse(self.a.can_suspend_game(),state)
            with self.assertRaises(SaveError): self.a.suspend_manager.save(self.a)
        self.a.state='explore'
        for _ in range(60): self.tick()
        self.assertFalse(self.backend.path.exists())
        self.a.overlay='info'; self.assertFalse(self.a.can_suspend_game())
        self.a.overlay=None; self.a.dungeon.finale.guardian_index=0
        self.assertFalse(self.a.can_suspend_game())

    def test_resume_bgm_steps_battle_and_return_are_normal(self):
        self.rich(6); self.save_ui(); self.resume_ui(); a=self.a
        self.assertEqual(a.audio.current_bgm,'bgm_area2')
        event=a.dungeon.change_floor(7); a.handle_event(*event)
        self.assertEqual(a.dungeon.floor,7)
        a.begin_encounter()
        self.assertEqual(a.audio.current_bgm,'bgm_battle')
        self.assertEqual(a.session.party[0].statuses,{'poison':3})
        for enemy in a.battle.enemies: enemy.hp=1
        for _ in range(10):
            if a.battle.outcome: break
            a.battle.begin_round(a.battle.auto_actions())
            while a.battle.queue: a.battle.step()
        self.assertEqual(a.battle.outcome,'VICTORY')
        a.session.settle()
        for index in list(a.session.pending_replacements): a.session.resolve_replacement(index)
        a.handle_event('base','')
        self.assertEqual(a.session.treasure.unbanked,0)

    def test_map_patch_and_open_door_restore_without_regeneration(self):
        self.rich(12); d=self.a.dungeon
        floor=next(f for f in range(15) if d.positions(f,TILE_DOOR))
        d.floor=floor; d.x,d.y=d.positions(floor,TILE_DOOR)[0]; d.activated_switches.add(floor)
        # The debug chest operation is the only runtime Tilemap edit. Persist
        # its difference from authored resources without changing those files.
        points=spawn_candidates(d,0); x,y=points[0]
        d.maps[0].pset(x,y,TILE_RARE_CHEST)
        before=encoded(make_suspend_data(self.a))
        prepared=prepare_suspend_game(self.a,before)
        self.assertTrue(prepared[1].can_enter(floor,d.x,d.y))
        self.assertEqual(tuple(prepared[1].maps[0].pget(x,y)),TILE_RARE_CHEST)

    def test_amrita_story_and_quest_state_restore_without_rewards(self):
        self.rich(12); a=self.a
        a.dungeon.finale.guardians_defeated=True; a.dungeon.finale.claim_amrita()
        a.dungeon.defeated_bosses.add(14)
        a.dungeon.finale.read_lore.add('B11_01')
        before=encoded(make_suspend_data(a)); self.save_ui(); self.resume_ui()
        self.assertEqual(encoded(make_suspend_data(a)),before)
        self.assertTrue(a.dungeon.finale.has_amrita)
        self.assertFalse(a.dungeon.finale.final_event_started)

    def test_menu_and_three_title_rows_fit_under_unchanged_logo(self):
        self.a.state='menu'
        with patch('rpg.dungeon_app.text') as text:
            self.a.draw_menu()
        self.assertTrue(any('中断' in c.args[2] for c in text.call_args_list))
        self.a.suspend_available=True
        with patch('rpg.dungeon_app.text') as text,patch.object(pyxel,'blt') as blt:
            self.a.draw_title()
        blt.assert_any_call(16,23,1,0,192,128,32)
        rows=[c for c in text.call_args_list if any(x in c.args[2] for x in ('はじめから','つづきから','中断から'))]
        self.assertEqual(len(rows),3)
        self.assertTrue(all(58<c.args[1]<104 for c in rows))

    def test_actual_skill_menu_remembers_only_execution_not_cancel_or_queue(self):
        a=self.a; c=a.session.party[0]
        for sid in ('fire','ice'): c.learn(a.session.skills[sid])
        a.begin_encounter(); self.tick()
        c.remember_skill('ice')
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((a.state,a.skill_cursor),('skill',2))
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(c.last_skill_id,'ice')
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.skill_cursor,2)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state,'target')
        self.tick(pyxel.GAMEPAD1_BUTTON_B)
        self.assertEqual(c.last_skill_id,'ice')
        self.tick(pyxel.GAMEPAD1_BUTTON_A); self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(c.last_skill_id,'ice')  # Queued but not yet used.
        self.tick(pyxel.GAMEPAD1_BUTTON_B)  # Undo the queued action.
        self.assertEqual(c.last_skill_id,'ice')
        a.battle._party_action(Action(0,'SKILL',0,'fire'))
        a.state='command'; self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.skill_cursor,1)
        c.skills.clear(); self.tick()
        self.assertEqual(a.state,'command')

    def test_newer_identical_checkpoint_cannot_be_consumed_by_old_reader(self):
        self.rich(); job_result(self.a.suspend_manager.save(self.a))
        old=job_result(self.backend.start('read'))
        job_result(self.a.suspend_manager.save(self.a))
        new=job_result(self.backend.start('read'))
        self.assertNotEqual(old,new)
        with self.assertRaises(SaveError): job_result(self.backend.start('consume',old))
        self.assertEqual(job_result(self.backend.start('read')),new)


class CursorAndBossTests(unittest.TestCase):
    def test_only_authorized_code_and_instructions_changed_all_data_assets_unchanged(self):
        if (ROOT/'tests/fixtures/alpha_gameplay02_before.json').exists():
            from tests.gameplay_preservation import assert_gameplay_preserved
            assert_gameplay_preserved(self)
            self.assertEqual(len(load_content()[1]),62)
            return
        if __import__('sys').platform == 'emscripten': return
        before=json.loads((ROOT/'tests/fixtures/alpha_ux01_before.json').read_text(encoding='utf-8-sig'))
        allowed={'rpg/models.py','rpg/app.py','rpg/battle.py','rpg/dungeon_app.py',
                 'tools/build_web.py','dist/index.html'}
        for name,digest in before['hashes'].items():
            if name not in allowed:
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(len(load_content()[1]),62)

    def battle(self,boss=False,enemy_id='slime'):
        _,skills,party,rows=load_content()
        enemy=Enemy.from_definition(next(r for r in rows if r['id']==enemy_id),max_hp=10000)
        return Battle(party,[enemy],skills,rng=random.Random(12),boss=boss)

    def test_four_independent_skill_ids_and_nearby_fallback(self):
        b=self.battle()
        for i,c in enumerate(b.party):
            for sid in ('fire','ice','heal'):
                if sid not in c.skills: c.learn(b.skills[sid])
            sid=c.skills[i%len(c.skills)]
            b._party_action(Action(i,'SKILL',0,sid))
            self.assertEqual(c.last_skill_id,sid)
            self.assertEqual(c.remembered_skill_index(),i%len(c.skills))
        c=b.party[0]; c.remember_skill('ice'); c.forget(c.skills[0])
        self.assertEqual(c.skills[c.remembered_skill_index()],'ice')
        index=c.remembered_skill_index(); c.forget('ice')
        self.assertEqual(c.remembered_skill_index(),min(c.last_skill_index,len(c.skills)-1))
        c.learn(b.skills['thunder'])
        self.assertLess(c.remembered_skill_index(),len(c.skills))

    def test_last_use_records_before_skill_disappears_and_empty_is_safe(self):
        b=self.battle(); c=b.party[0]; c.skill_uses['punch']=1
        b._party_action(Action(0,'SKILL',0,'punch'))
        self.assertEqual(c.last_skill_id,'punch'); self.assertEqual(c.remembered_skill_index(),0)
        self.assertNotIn('punch',c.skills)

    def test_failed_cure_and_cooldown_do_not_record_usage(self):
        b=self.battle(); c=b.party[0]
        c.learn(b.skills['cure']); c.learn(b.skills['fire'])
        b._party_action(Action(0,'SKILL',0,'punch')); remembered=c.last_skill_id
        b._party_action(Action(0,'SKILL',0,'cure'))
        self.assertEqual(c.last_skill_id,remembered)
        c.cooldowns['fire']=3; b._party_action(Action(0,'SKILL',0,'fire'))
        self.assertEqual(c.last_skill_id,remembered)

    def test_all_seven_bosses_reject_every_sleep_skill_damage_and_uses_unchanged(self):
        _,_,_,rows=load_content()
        ids=[r['id'] for r in rows if r.get('boss')]
        self.assertEqual(set(ids),{'guardian','skill_keeper','sentinel_armor','sentinel_speed',
                                  'sentinel_mind','depth_lord','lord_of_elysion'})
        for ident in ids:
            for sid in ('sleep_spell','nightmare','time_stop'):
                with self.subTest(boss=ident,skill=sid):
                    b=self.battle(True,ident); b.elysion_barrier_active=False
                    c=b.party[0]; c.learn(b.skills[sid])
                    b.skills={**b.skills,sid:replace(b.skills[sid],status_chance=100)}
                    uses=c.skill_uses[sid]; hp=b.enemies[0].hp
                    b._party_action(Action(0,'SKILL',0,sid))
                    self.assertNotIn('sleep',b.enemies[0].statuses)
                    self.assertTrue(any('無効' in s for s in b.status_messages))
                    self.assertEqual(c.skill_uses.get(sid,0),uses-1)
                    self.assertLess(b.enemies[0].hp,hp) if sid=='nightmare' else self.assertEqual(b.enemies[0].hp,hp)

    def test_normal_sleep_other_ailments_and_enemy_sleep_unchanged(self):
        b=self.battle()
        self.assertTrue(b.apply_status(b.enemies[0],'sleep',100))
        self.assertEqual(b.enemies[0].statuses['sleep'],b.status_definitions['sleep'].duration)
        b=self.battle(True,'depth_lord')
        for status in ('poison','paralyze','confusion'):
            b.enemies[0].statuses={}
            self.assertTrue(b.apply_status(b.enemies[0],status,100),status)
        self.assertTrue(b.apply_status(b.party[0],'sleep',100))

    def test_nightmare_damage_identical_to_same_skill_without_sleep(self):
        losses=[]
        for enabled in (True,False):
            b=self.battle(True,'depth_lord'); c=b.party[0]
            c.learn(b.skills['nightmare'])
            if not enabled:
                b.skills={**b.skills,'nightmare':replace(b.skills['nightmare'],status_id=None)}
            before=b.enemies[0].hp
            b._party_action(Action(0,'SKILL',0,'nightmare'))
            losses.append(before-b.enemies[0].hp)
        self.assertEqual(losses[0],losses[1])


if __name__=='__main__': unittest.main()
