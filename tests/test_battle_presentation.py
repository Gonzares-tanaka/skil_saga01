"""Presentation timing, real sprite draws and unchanged battle/growth results."""
from collections import deque
from copy import deepcopy
from dataclasses import replace
import time
import unittest
from unittest.mock import patch

import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Action
from rpg.save import make_save_data, apply_save_data
from rpg.battle_presentation import (BattlePresentation, ASSET_BANK, KO_SPRITE_U, KO_SPRITE_V,
    EFFECT_SPRITES, STATUS_SPRITES, effect_id, draw_status_icons, dungeon_floor_color, result_pages,
    STEP_PIXELS, STEP_FRAMES, EFFECT_FRAMES, EFFECT_FRAME_TICKS, DEATH_FRAMES)
from rpg.app import FANFARE_PRESENTATION_FRAMES


class BattlePresentationTests(unittest.TestCase):
    def setUp(self):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True
        with patch.object(pyxel, 'init'):
            self.app = DungeonApp(Session(*load_content(), seed=193), run=False, headless=True, start_at_title=False)
        self.app.begin_encounter()
        self.app.state, self.app.delay = 'resolve', 0
        self.app.session.settings['spark_chance'] = 0
        self.app.confirm = lambda: True
        self.app.cancel = lambda: True
        self.app.pressed = lambda *args: False
        self.app.direction = lambda horizontal=False: 1
        self.app.confirm_held = lambda: True

    def queue(self, actor=0, skill='punch', target=0):
        c = self.app.session.party[actor]
        if skill not in c.skills:
            c.learn(self.app.session.skills[skill])
        self.app.battle.queue = deque([('party', Action(actor, 'SKILL', target, skill))])
        self.app.battle.round = 1
        self.app.pending.clear()
        self.app.battle_visual().reset()
        self.app.state, self.app.delay = 'resolve', 0

    def play_action(self):
        self.app.update()
        for _ in range(100):
            if not self.app.battle_visual().active:
                return
            self.app.update()
        self.fail('presentation did not end')

    def test_only_acting_member_steps_six_pixels_and_always_returns(self):
        self.app.battle.enemies[0].hp = 999
        for index in (0, 1, 0, 1):
            self.queue(index)
            self.app.update()
            visual = self.app.battle_visual()
            for _ in range(STEP_FRAMES):
                self.app.update()
            self.assertEqual(visual.phase, 'skill_effect')
            self.assertEqual(visual.actor_offset(index), -STEP_PIXELS)
            self.assertTrue(all(visual.actor_offset(i) == 0 for i in range(4) if i != index))
            for _ in range(60):
                if not visual.active:
                    break
                self.app.update()
            self.assertFalse(visual.active)
            self.assertEqual([visual.actor_offset(i) for i in range(4)], [0]*4)

    def test_input_spam_cannot_apply_damage_or_spend_uses_before_impact(self):
        self.queue(1)
        c = self.app.session.party[1]
        uses, hp = c.skill_uses['punch'], self.app.battle.enemies[0].hp
        self.app.update()
        for _ in range(STEP_FRAMES + EFFECT_FRAMES * EFFECT_FRAME_TICKS - 1):
            self.app.update()
            self.assertEqual(c.skill_uses['punch'], uses)
            self.assertEqual(self.app.battle.enemies[0].hp, hp)
            self.assertEqual(self.app.state, 'resolve')
        self.app.update()
        self.assertEqual(c.skill_uses['punch'], uses-1)

    def test_dead_actor_and_guard_do_not_step(self):
        self.queue()
        self.app.session.party[0].hp = 0
        self.assertFalse(self.app.battle_visual().start())
        self.app.battle.queue = deque([('party', Action(1,'GUARD'))])
        self.assertFalse(self.app.battle_visual().start())

    def test_effect_target_and_missing_or_unknown_effect_fallback(self):
        for sid, side in (('punch','enemy'),('fire','enemy'),('heal','party'),
                          ('power_up','party'),('weaken','enemy')):
            self.queue(0,sid)
            self.assertTrue(self.app.battle_visual().start())
            self.assertEqual(self.app.battle_visual().target, (side,0))
            self.assertIn(self.app.battle_visual().effect, EFFECT_SPRITES)
        skill = self.app.session.skills['fire']
        for value in (None, '', 'unknown', {}):
            self.assertEqual(effect_id(replace(skill,effect_id=value)), 'blunt')

    def test_ko_revival_and_status_icons_use_actual_editable_sprites(self):
        c = self.app.session.party[0]
        c.hp = 0
        c.statuses = ['poison','sleep','paralyze']
        self.app.begin_input()
        original = pyxel.blt
        draws = []
        with patch.object(pyxel, 'blt', side_effect=lambda *args: (draws.append(args),original(*args))):
            self.app.draw()
        self.assertIn((98,13,ASSET_BANK,KO_SPRITE_U,KO_SPRITE_V,16,16,0),draws)
        self.assertFalse(any(a[2:5] == (ASSET_BANK,*STATUS_SPRITES['poison']) for a in draws))
        self.app.session.inventory.counts['PHOENIX ASH'] = 1
        self.app.battle.queue = deque([('party',Action(1,'ITEM',0,item_id='PHOENIX ASH'))])
        self.app.state, self.app.delay = 'resolve',0
        self.play_action()
        self.assertGreater(c.hp,0)
        draws.clear()
        with patch.object(pyxel, 'blt', side_effect=lambda *args: (draws.append(args),original(*args))):
            self.app.draw()
        self.assertIn((98,13,0,*c.sprite,16,16,0),draws)
        self.assertEqual(len([a for a in draws if a[2] == ASSET_BANK and a[4]==0 and a[5:7]==(8,8)]),0)
        self.assertEqual(c.statuses, {})  # KO/Revive never restores temporary ailments.
        c.statuses = {'poison': 3, 'sleep': 2}
        u,v = STATUS_SPRITES['poison']
        pyxel.images[ASSET_BANK].pset(u,v,3)
        pyxel.cls(0)
        draw_status_icons(pyxel,c,20,20)
        self.assertEqual(pyxel.pget(20,20),3)
        self.assertEqual(pyxel.pget(98,13),0)  # Display helper did not alter HP/actor pixels.

    def test_killed_enemy_blinks_sinks_and_blocks_next_action_and_settlement(self):
        self.queue()
        self.app.battle.enemies[0].hp = 1
        self.app.session.party[0].strength = 100
        self.app.update()
        for _ in range(STEP_FRAMES + EFFECT_FRAMES * EFFECT_FRAME_TICKS):
            self.app.update()
        visual = self.app.battle_visual()
        self.assertEqual(visual.phase,'enemy_death')
        self.assertFalse(self.app.session.settled)
        self.assertEqual(visual.enemy_visual(0),(True,0))
        for _ in range(3):
            self.app.update()
        self.assertFalse(visual.enemy_visual(0)[0])
        self.assertEqual(visual.enemy_visual(0)[1],0)
        for i in range(1,len(self.app.battle.enemies)):
            self.assertEqual(visual.enemy_visual(i),(True,0))
        for _ in range(DEATH_FRAMES-3):
            self.app.update()
            self.assertEqual(self.app.state,'resolve')
        self.assertFalse(visual.enemy_visual(0)[0])

    def test_frame_and_resume_timeout_progress_even_with_completely_broken_audio(self):
        self.queue()
        with patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
             patch.object(pyxel,'playm',side_effect=RuntimeError('interrupted')), \
             patch.object(pyxel,'play_pos',side_effect=RuntimeError('closed')), \
             patch.object(pyxel,'stop',side_effect=RuntimeError('unavailable')):
            self.app.update()
            visual = self.app.battle_visual()
            for _ in range(5):
                if not visual.active:
                    break
                visual.started_at = time.monotonic() - 3
                self.app.update()
            self.assertFalse(visual.active)
            self.assertFalse(self.app.battle.queue)

    def test_presentation_preserves_entire_rule_state_rng_damage_and_uses(self):
        b = self.app.battle
        b.begin_round(b.auto_actions())
        direct = deepcopy(b)
        while direct.queue:
            direct.step()
        for _ in range(1000):
            self.app.update()
            if not b.queue and not self.app.battle_visual().active:
                break
        self.assertEqual(b.party,direct.party)
        self.assertEqual(b.enemies,direct.enemies)
        self.assertEqual(b.rng.getstate(),direct.rng.getstate())
        self.assertEqual((b.outcome,b.resource_events,b.mastered_skills),(direct.outcome,direct.resource_events,direct.mastered_skills))

    def test_growth_pages_group_each_character_and_skip_no_growth_without_mutation(self):
        party = self.app.session.party
        a,b = party[:2]
        snapshot = deepcopy(party)
        lines = [f'{a.name} HP +4', f'{a.name} INT +1', f'{b.name} STR +1',
                 f'{party[2].name} 変化なし', f'{party[3].name} 変化なし', f'{a.name} 閃き! テスト']
        pages = result_pages(lines,party)
        growth = [p for p in pages if p['kind']=='growth']
        self.assertEqual([p['actor'] for p in growth],[0,1])
        self.assertEqual(len(growth[0]['lines']),3)
        self.assertEqual(party,snapshot)
        self.assertFalse(any(p['kind']=='growth' for p in result_pages([c.name+' 変化なし' for c in party],party)))
        self.app.set_result_pages(lines)
        self.assertEqual(len(self.app.result_lines),len(pages)*9)

    def test_floor_colors_match_all_three_areas_and_special_battle_is_independent(self):
        for floor in range(15):
            self.app.dungeon.floor = floor
            self.assertEqual(dungeon_floor_color(self.app.dungeon,pyxel),(0,2,3)[floor//5])

    def test_fanfare_wait_uses_visual_ticks_never_audio_channel_state(self):
        self.app.battle.outcome = 'VICTORY'
        self.app.fanfare_started_at = time.monotonic()
        self.app.fanfare_start_frame = pyxel.frame_count
        self.app.fanfare_visual_frames = FANFARE_PRESENTATION_FRAMES
        with patch('rpg.app.music_is_playing',side_effect=AssertionError('audio consulted')):
            self.assertFalse(self.app.waiting_for_fanfare())

    def test_animation_is_not_saved_and_existing_save_roundtrip_still_works(self):
        self.app.enter_camp()
        saved = make_save_data(self.app)
        self.assertFalse(any('presentation' in key or 'animation' in key for key in saved))
        apply_save_data(self.app,saved)
        self.assertEqual(make_save_data(self.app),saved)


if __name__ == '__main__':
    unittest.main()
