"""Common app fixture for countdown, transition carry and resume tests."""
from copy import deepcopy
import json
from pathlib import Path
import random
import statistics
import tempfile
import unittest
from unittest.mock import patch
import pyxel

from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.dungeon_app import DungeonApp
from rpg.elevator import arrival_point
from rpg.save import FileSaveBackend, make_save_data, prepare_saved_game
from rpg.suspend import FileSuspendBackend, job_result
from rpg.tiles import (FLOOR_TILES, TILE_WALL, TILE_STAIRS_UP, TILE_STAIRS_DOWN,
    TILE_BOSS, TILE_POISON, TILE_PIT, TILE_CHEST, TILE_HEAL_POINT, TILE_SWITCH)
from tests.encounter_preservation import assert_encounter_preserved


class EncounterFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160,120,headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.backend = FileSuspendBackend(root/'suspend.json')
        with patch.object(pyxel,'init'):
            self.a = DungeonApp(Session(*load_content(),seed=303),run=False,headless=True,
                start_at_title=False,save_backend=FileSaveBackend(root/'save.json'),
                suspend_backend=self.backend)
        self.a.audio.enabled = False
        self.tick()
        self.a.hub_intro_shown = True
        self.a.enter_dungeon()
        self.d = self.a.dungeon

    def tick(self,key=None):
        with patch.object(pyxel,'btn',return_value=False), \
             patch.object(pyxel,'btnp',new=lambda k,*args:k==key):
            self.a.update()

    def pair(self,floor=0):
        d = self.d
        for x,y in sorted(d.reachable(floor)):
            if d.tile(floor,x,y) in FLOOR_TILES:
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    if d.tile(floor,x+dx,y+dy) in FLOOR_TILES:
                        d.floor,d.x,d.y = floor,x,y
                        return (x,y),(dx,dy)
        self.fail('no real floor pair')

    def walk(self,start,delta,debug=False):
        sign = 1 if (self.d.x,self.d.y)==start else -1
        return self.d.move(delta[0]*sign,delta[1]*sign,debug=debug)[0]

    def finish(self,floor=0,boss=False,outcome='VICTORY',kind=None):
        a = self.a
        a.dungeon.floor = floor
        a.begin_encounter(boss=boss)
        if kind: a.battle_kind = kind
        a.battle.outcome = outcome
        a.battle.queue.clear()
        a.session.settle()
        for i in list(a.session.pending_replacements): a.session.resolve_replacement(i,None)
        a.dungeon.encounter_remaining = 0
        with patch.object(a,'waiting_for_fanfare',return_value=False):
            a.finish_results()

    def unlock(self):
        self.d.defeated_bosses.update((4,9,14))
        self.d.finale.guardians_defeated = self.d.finale.demon_defeated = self.d.finale.has_amrita = True

