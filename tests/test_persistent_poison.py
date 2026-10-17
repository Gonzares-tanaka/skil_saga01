"""Poison lifetime across the real dungeon/session/UI boundaries, without SAVE changes."""
from collections import deque
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.final_battle import make_final_enemy
from rpg.models import Action
from rpg.save import make_save_data, apply_save_data, SAVE_VERSION
from rpg.statuses import apply_status, clear_statuses
from rpg.tiles import FLOOR_TILES, TILE_ENTRANCE, TILE_HEAL_POINT


class PersistentPoisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True

    def setUp(self):
        with patch.object(pyxel,'init'):
            self.app= DungeonApp(Session(*load_content(),seed=890),run=False,headless=True,start_at_title=False)
        self.s,self.d,self.e=self.app.session,self.app.dungeon,self.app.exploration
        self.actor=self.s.party[0]
        for c in self.s.party: c.hp=c.max_hp=1000
        self.d.defeated_bosses.update((4,9))
        self.d.debug_floor(5); self.app.state='explore'
        self.s.inventory.counts['REMEDY']=3

    def start(self,**kwargs):
        self.app.begin_encounter(**kwargs)
        return self.app.battle

    def turn(self,b,actor=0,kind='GUARD'):
        b.queue=deque([('party',Action(actor,kind,0,self.s.party[actor].skills[0]))])
        b.turn_plan=None
        return b.step()

    def finish(self,b,outcome='VICTORY'):
        b.queue.clear(); b.turn_plan=None; b.outcome=outcome
        b.clear_effects(); self.s.settle()
        for c in self.s.party: c.pending_skill=None
        self.app.fanfare_started_at=None; self.app.fanfare_start_frame=None
        self.app.state='result'; self.app.finish_results()

    def press(self,key):
        with patch.object(pyxel,'btnp',side_effect=lambda code,*args:code==key), \
             patch.object(pyxel,'btn',return_value=False):
            self.app.update()

    def test_actual_victory_two_ticks_map_next_battle_tick_expiry(self):
        b=self.start(); apply_status(self.actor,'poison')
        self.turn(b); self.assertEqual(self.actor.statuses,{'poison':2})
        b.enemies=b.enemies[:1]; b.enemies[0].hp=1
        self.s.party[1].strength=1000
        self.turn(b,1,'SKILL')
        self.assertEqual(b.outcome,'VICTORY')
        self.finish(b)
        self.assertEqual(self.app.state,'explore')
        self.assertEqual(self.actor.statuses,{'poison':2})
        b=self.start(); self.assertEqual(self.actor.statuses,{'poison':2})
        hp=self.actor.hp; maximum=self.actor.max_hp
        self.turn(b)
        self.assertEqual(self.actor.hp,hp-max(1,int(maximum*.05)))
        self.assertEqual(self.actor.statuses,{'poison':1})
        self.turn(b); self.assertFalse(self.actor.statuses)
        self.finish(b); self.assertFalse(self.actor.statuses)

    def test_run_preserves_exact_ticks_clears_control_and_enemy_statuses(self):
        b=self.start(); apply_status(self.actor,'poison'); apply_status(self.actor,'sleep')
        self.actor.statuses['poison']=2
        for enemy in b.enemies: apply_status(enemy,'poison'); apply_status(enemy,'paralyze')
        b.run_override=True; b.attempt_run()
        self.assertEqual(self.actor.statuses,{'poison':2})
        self.assertFalse(any(e.statuses for e in b.enemies))
        self.finish(b,'ESCAPE')
        self.assertEqual(self.app.state,'explore')
        self.assertEqual(self.actor.statuses,{'poison':2})
        self.start(); self.assertEqual(self.actor.statuses,{'poison':2})

    def test_each_control_clears_on_victory_and_battle_start_keeps_only_poison(self):
        for control in ('paralyze','sleep','confusion'):
            b=self.start(); apply_status(self.actor,'poison'); apply_status(self.actor,control)
            self.actor.statuses['poison']=2
            self.finish(b)
            self.assertEqual(self.actor.statuses,{'poison':2})
            apply_status(self.actor,control)
            self.start(); self.assertEqual(self.actor.statuses,{'poison':2})
            self.finish(self.app.battle,'ESCAPE')

    def test_draw_preserves_poison_but_wipe_and_recovery_clear_all(self):
        b=self.start(); apply_status(self.actor,'poison'); self.actor.statuses['poison']=1
        self.finish(b,'DRAW'); self.assertEqual(self.actor.statuses,{'poison':1})
        b=self.start(); apply_status(self.actor,'sleep')
        self.finish(b,'DEFEAT')
        self.assertFalse(any(c.statuses for c in self.s.party+b.enemies))
        self.assertIn(self.app.state,('camp','field_event'))
        self.assertTrue(all(c.hp==c.max_hp for c in self.s.party))

    def test_hundred_real_pad_steps_and_elapsed_frames_cannot_tick_poison(self):
        apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
        floor=self.d.floor
        pair=next(((x,y),(x+1,y)) for y in range(self.d.map_bounds(floor)[1])
                  for x in range(self.d.map_bounds(floor)[0]-1)
                  if self.d.tile(floor,x,y) in FLOOR_TILES and self.d.tile(floor,x+1,y) in FLOOR_TILES)
        self.d.x,self.d.y=pair[0]; hp=self.actor.hp; steps=self.d.steps
        with patch.object(self.s.rng,'random',return_value=1):
            for _ in range(50):
                self.press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
                self.press(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)
            for _ in range(200): self.press(None)
        self.assertEqual(self.d.steps,steps+100)
        self.assertEqual(self.actor.hp,hp)
        self.assertEqual(self.actor.statuses,{'poison':2})

    def test_stairs_both_directions_b14_b15_and_pit_keep_poison(self):
        apply_status(self.actor,'poison'); self.actor.statuses['poison']=2; hp=self.actor.hp
        for source,dest in ((5,6),(6,5),(13,14),(14,13)):
            self.d.floor=source
            self.app.handle_event(*self.d.change_floor(dest))
            self.assertEqual(self.d.floor,dest)
            self.assertEqual(self.actor.hp,hp)
            self.assertEqual(self.actor.statuses,{'poison':2})
        self.app.handle_event(*self.d.fall_in_pit())
        self.assertEqual(self.actor.hp,hp)
        self.assertEqual(self.actor.statuses,{'poison':2})

    def test_field_remedy_real_menu_pad_targets_count_hp_uses_and_cancel(self):
        apply_status(self.s.party[2],'poison'); self.s.party[2].statuses['poison']=2
        self.s.party[2].effects={'weaken':(.85,3)}
        before=deepcopy([(c.hp,c.skill_uses) for c in self.s.party])
        self.press(pyxel.GAMEPAD1_BUTTON_B); self.assertEqual(self.app.state,'menu')
        for _ in range(2): self.press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.press(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(self.app.state,'items')
        for _ in range(2): self.press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.press(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(self.app.state,'item_target')
        self.press(pyxel.GAMEPAD1_BUTTON_B); self.assertEqual(self.app.state,'items')
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        for _ in range(2): self.press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertFalse(self.s.party[2].statuses)
        self.assertEqual(self.s.party[2].effects,{'weaken':(.85,3)})
        self.assertEqual(self.s.inventory.counts['REMEDY'],2)
        self.assertEqual([(c.hp,c.skill_uses) for c in self.s.party],before)
        self.assertEqual(self.s.total_battles,0)

    def test_field_remedy_no_status_ko_or_no_items_never_spends(self):
        self.app.state='items'; self.app.item_kind_cursor=2
        self.press(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(self.app.state,'item_target')
        for target in (0,1):
            if target==1: self.s.party[target].hp=0
            self.app.item_cursor=target
            self.press(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(self.s.inventory.counts['REMEDY'],3)
        self.s.inventory.counts['REMEDY']=0
        self.app.state='items'; self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.app.state,'items')
        self.assertEqual(self.s.inventory.counts['REMEDY'],0)

    def test_spring_and_potion_heal_hp_only_without_uses_items_refill(self):
        for floor in (3,14):
            self.d.floor=floor
            self.d.x,self.d.y=self.d.positions(floor,TILE_HEAL_POINT)[0]
            self.actor.hp=20; apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
            uses=deepcopy(self.actor.skill_uses); inventory=deepcopy(self.s.inventory.counts)
            self.app.handle_event(*self.d.interact())
            self.assertEqual(self.actor.hp,self.actor.max_hp)
            self.assertEqual(self.actor.statuses,{'poison':2})
            self.assertEqual(self.actor.skill_uses,uses); self.assertEqual(self.s.inventory.counts,inventory)
        self.actor.hp=20
        self.s.inventory.counts['POTION']=2
        self.assertTrue(self.s.inventory.use('POTION',self.actor)[0])
        self.assertEqual(self.actor.hp,50)
        self.assertEqual(self.actor.statuses,{'poison':2})

    def test_ko_poison_tick_and_revive_clear_without_poison_return(self):
        b=self.start(); self.actor.hp=1; apply_status(self.actor,'poison')
        self.turn(b); self.assertFalse(self.actor.alive); self.assertFalse(self.actor.statuses)
        self.s.inventory.counts['PHOENIX ASH']=1
        self.assertTrue(self.s.inventory.use('PHOENIX ASH',self.actor)[0])
        self.assertFalse(self.actor.statuses)
        self.finish(b); self.start(); self.assertFalse(self.actor.statuses)

    def test_return_pad_clears_and_banks_trz_without_extra_uses(self):
        apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
        self.actor.learn(self.s.skills['return']); self.actor.skill_uses['return']=2
        self.s.treasure.banked,self.s.treasure.unbanked=3,7
        self.app.open_return_skill(); self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.actor.skill_uses['return'],1)
        self.assertEqual((self.s.treasure.banked,self.s.treasure.unbanked),(10,0))
        self.assertFalse(any(c.statuses for c in self.s.party))
        self.assertEqual(self.app.state,'return_result')

    def test_normal_exit_and_other_camp_arrivals_clear_all(self):
        for method in ('exit','camp','wipe'):
            apply_status(self.actor,'poison'); apply_status(self.actor,'confusion')
            if method=='exit':
                self.d.floor=0; self.d.x,self.d.y=self.d.find(0,TILE_ENTRANCE)
                self.app.handle_event(*self.d.interact())
            else: self.app.enter_camp(defeated=method=='wipe')
            self.assertFalse(any(c.statuses for c in self.s.party))

    def test_b15_no_encounters_poison_import_into_guardian_chain(self):
        self.d.floor=14; apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
        floor=14
        pair=next(((x,y),(x+1,y)) for y in range(self.d.map_bounds(floor)[1])
                  for x in range(self.d.map_bounds(floor)[0]-1)
                  if self.d.tile(floor,x,y) in FLOOR_TILES and self.d.tile(floor,x+1,y) in FLOOR_TILES)
        self.d.x,self.d.y=pair[0]
        with patch.object(self.d.rng,'random',side_effect=AssertionError('B15 random encounter')):
            self.assertEqual(self.d.move(1,0)[0],'')
        self.d.finale.start_guardians()
        for index in range(3):
            b=self.start(guardian_index=index)
            self.assertEqual(self.actor.statuses,{'poison':2})
            self.finish(b)
            self.assertEqual(self.actor.statuses,{'poison':2})
        self.assertTrue(self.d.finale.guardians_defeated)

    def test_hunt_victory_preserves_then_safe_return_completes_and_cures(self):
        from test_enemy_roster import hunt_on
        hunt_on(self.app,6,'poison_snake')
        b=self.start(quest_hunt=True)
        b.enemies[0].actions=[dict(id='poison_bite',weight=1)]
        b.queue=deque([('enemy',0)])
        with patch.object(b.rng,'random',return_value=0),patch.object(b.rng,'choice',return_value=self.actor): b.step()
        self.actor.statuses['poison']=2
        self.finish(b)
        self.assertTrue(self.e.active['completed'])
        self.assertEqual(self.actor.statuses,{'poison':2})
        self.app.enter_camp(returned=True)
        self.assertEqual(self.app.state,'quest_thanks')
        self.e.finalize_quest_completion()
        self.assertIsNone(self.e.active)
        self.assertFalse(self.actor.statuses)

    def test_save_after_return_and_load_schema1_never_contains_status(self):
        apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
        self.app.enter_camp(returned=True)
        saved=make_save_data(self.app)
        self.assertEqual(SAVE_VERSION,1); self.assertEqual(saved['save_version'],1)
        self.assertNotIn('statuses',json.dumps(saved))
        apply_status(self.actor,'poison'); apply_status(self.actor,'sleep')
        apply_save_data(self.app,json.loads(json.dumps(saved)))
        self.assertFalse(any(c.statuses for c in self.app.session.party))
        self.assertEqual(make_save_data(self.app),saved)

    def test_prototype_recovery_and_final_battle_never_inherit_poison(self):
        apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
        b=self.s.next_battle(); self.assertFalse(any(c.statuses for c in self.s.party))
        b.outcome='DRAW'; self.s.settle()
        apply_status(self.actor,'poison')
        self.s.next_battle([make_final_enemy(self.s.enemy_data)],recover=False,boss=True,persistent_poison=True)
        self.assertFalse(any(c.statuses for c in self.s.party))
        self.assertFalse(self.s.battle.persistent_poison)

    def test_exploration_and_target_and_party_info_use_existing_poison_icon(self):
        apply_status(self.actor,'poison'); self.actor.statuses['poison']=2
        for draw,state in ((self.app.draw_explore,'explore'),(self.app.draw_item_target,'item_target'),
                           (self.app.draw_info,'explore')):
            self.app.state=state; self.app.item_kind_cursor=2
            self.app.info_tab=self.app.info_character=0
            with patch.object(pyxel,'blt') as blt:
                draw()
            icons=[c.args for c in blt.call_args_list if c.args[2:7]==(2,192,0,8,8)]
            self.assertEqual(len(icons),1)
            self.assertTrue(all(0<=c[0]<=152 and 0<=c[1]<=112 for c in icons))


if __name__=='__main__': unittest.main()
