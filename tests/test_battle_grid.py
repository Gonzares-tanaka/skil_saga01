"""Four real targets share positions with cursor, effects and death animation."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import pyxel
import test_battle_extra as fixtures
from rpg.battle_presentation import (ENEMY_GRID_POSITIONS, enemy_position,
                                     BATTLE_STRIP_Y, EFFECT_SPRITES)


class EnemyGridTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.BattleExtraTests()
        fixture.setUp()
        self.app=fixture.app
        enemy=self.app.battle.enemies[0]
        self.app.battle.enemies=[deepcopy(enemy) for _ in range(4)]
        for i,e in enumerate(self.app.battle.enemies):
            e.name='Enemy '+chr(65+i)
        self.app.confirm=lambda:False
        self.app.cancel=lambda:False

    def test_four_enemy_sprites_stay_above_strip_and_outside_party_status_icons(self):
        a=self.app
        with patch.object(pyxel,'blt',wraps=pyxel.blt) as draws:
            a.draw()
        for i,(x,y) in enumerate(ENEMY_GRID_POSITIONS):
            self.assertLessEqual(y+16,BATTLE_STRIP_Y)
            self.assertLessEqual(x+16,66)
            self.assertIn((x,y,0,*a.battle.enemies[i].sprite,16,16,0),
                          [call.args for call in draws.call_args_list])
        self.assertEqual(len(set(ENEMY_GRID_POSITIONS)),4)

    def test_each_target_cursor_and_effect_matches_the_corresponding_slot(self):
        a=self.app
        a.actor.learn(a.session.skills['fire'])
        a.selected_skill=a.session.skills['fire']
        a.state='target'
        for i,(x,y) in enumerate(ENEMY_GRID_POSITIONS):
            a.target_cursor=i
            with patch('rpg.app.text') as text:
                a.draw()
            self.assertIn((x-8,y+4,'>',3),[c.args for c in text.call_args_list])
            self.assertTrue(any(c.args[2]=='> Enemy '+chr(65+i) for c in text.call_args_list))
            visual=a.battle_visual()
            visual.target=('enemy',i)
            visual.effect='fire'
            visual.enter('skill_effect')
            with patch.object(pyxel,'blt') as effect:
                visual.draw_effect(pyxel)
            effect.assert_called_once_with(x,y,2,*EFFECT_SPRITES['fire'],16,16,0)
            visual.reset()

    def test_fourth_target_can_be_selected_and_survivors_keep_original_slots(self):
        a=self.app
        a.actor.learn(a.session.skills['fire'])
        a.selected_skill=a.session.skills['fire']
        a.state,a.target_cursor='target',3
        a.confirm=lambda:True
        a.update()
        self.assertEqual(a.actions[-1].target,3)
        a.battle.enemies[1].hp=0
        a.state='resolve'
        visual=a.battle_visual()
        visual.after_action([True]*4)
        visual.frame=16
        with patch.object(pyxel,'blt',wraps=pyxel.blt) as draws,patch.object(pyxel,'clip',wraps=pyxel.clip) as clip:
            a.draw()
        x,y=ENEMY_GRID_POSITIONS[1]
        self.assertIn((x,y+visual.enemy_visual(1)[1],0,*a.battle.enemies[1].sprite,16,16,0),
                      [c.args for c in draws.call_args_list])
        self.assertIn((0,11,96,y+16-11),[c.args for c in clip.call_args_list])
        for i in (0,2,3):
            self.assertIn((*ENEMY_GRID_POSITIONS[i],0,*a.battle.enemies[i].sprite,16,16,0),
                          [c.args for c in draws.call_args_list])

    def test_dungeon_generates_four_and_rejects_more_than_four(self):
        d=self.app.dungeon
        d.floor=1
        d.validate_settings()
        self.assertEqual(d.settings['floors'][1]['count'],[2,4])
        with patch.object(d.rng,'randint',return_value=4):
            self.assertEqual(len(d.make_enemies()),4)
        d.settings['floors'][1]['count']=[2,5]
        with self.assertRaises(ValueError):d.validate_settings()

    def test_single_enemy_position_is_unchanged(self):
        self.assertEqual(enemy_position(0,1),(38,16))


if __name__=='__main__':unittest.main()
