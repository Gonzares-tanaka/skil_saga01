"""Actual pixel contrast, including B14's light floor and the pale lens."""
import unittest

import pyxel

from rpg.art import draw_quest_symbol, load_art
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.quests import QUEST_SYMBOLS, spawn_candidates
from rpg.tiles import TILE_QUEST


class QuestVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160,120,headless=True)
            pyxel._tests_initialized = True
        load_art(pyxel)
        session = Session(*load_content(), seed=81)
        cls.dungeon = Dungeon(load_maps(), session.enemy_data, load_dungeon_settings(), session.rng)

    def setUp(self):
        pyxel.clip()

    def test_reproduce_pale_investigation_lens_disappearing_on_pale_background(self):
        bank, u, v = QUEST_SYMBOLS['investigate']
        lens = [(x,y) for y in range(8) for x in range(8) if pyxel.images[bank].pget(u+x,v+y)==3]
        self.assertGreater(len(lens), 10)
        pyxel.cls(3)
        pyxel.blt(30,30,bank,u,v,8,8,0)
        self.assertTrue(all(pyxel.pget(30+x,30+y)==3 for x,y in lens))
        draw_quest_symbol(pyxel,30,30,bank,u,v)
        # Original lens pixels retain their colors; a dark outline makes its shape visible.
        self.assertTrue(all(pyxel.pget(30+x,30+y)==3 for x,y in lens))
        self.assertTrue(any(pyxel.pget(30+x+dx,30+y+dy)==0 for x,y in lens
                            for dx,dy in ((0,-1),(0,1),(-1,0),(1,0))))

    def test_all_symbols_have_dark_contours_on_every_actual_candidate_floor(self):
        d = self.dungeon
        for floor in range(15):
            for point in spawn_candidates(d,floor):
                tile = d.tile(floor,*point)
                background = d.floor_appearance(floor,*point) if tile==TILE_QUEST else tile
                for kind,(bank,u,v) in QUEST_SYMBOLS.items():
                    with self.subTest(floor=floor+1, point=point, kind=kind):
                        pyxel.cls(3)
                        pyxel.blt(30,30,1,background[0]*8,background[1]*8,8,8)
                        draw_quest_symbol(pyxel,30,30,bank,u,v)
                        pixels = {(x,y):pyxel.images[bank].pget(u+x,v+y)
                                  for y in range(8) for x in range(8)}
                        contour = set()
                        for (x,y), color in pixels.items():
                            if color:
                                self.assertEqual(pyxel.pget(30+x,30+y),color)
                                contour.update((x+dx,y+dy) for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)))
                        contour = [p for p in contour if not pixels.get(p,0)]
                        self.assertTrue(contour)
                        self.assertTrue(all(pyxel.pget(30+x,30+y)==0 for x,y in contour))

    def test_drawing_never_edits_the_sprite_or_palette(self):
        bank,u,v = QUEST_SYMBOLS['investigate']
        before = [pyxel.images[bank].pget(u+x,v+y) for y in range(8) for x in range(8)]
        colors = list(pyxel.colors)
        pyxel.cls(3)
        draw_quest_symbol(pyxel,30,30,bank,u,v)
        self.assertEqual(before,[pyxel.images[bank].pget(u+x,v+y) for y in range(8) for x in range(8)])
        self.assertEqual(list(pyxel.colors),colors)


if __name__=='__main__':
    unittest.main()
