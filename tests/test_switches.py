"""Actual editable B7 tiles: blocked doors, A activation, expedition lifetime."""
import unittest
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.tiles import (TILE_SWITCH, TILE_DOOR, TILE_FLOOR, TILE_WALL,
                       TILE_QUEST, TILE_STAIRS_UP)


class SwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        s = Session(*load_content(), seed=52)
        self.d = Dungeon(load_maps(), s.enemy_data, load_dungeon_settings(), s.rng)
        self.d.settings['encounter_chance'] = 0
        self.d.debug_floor(6)

    def test_door_blocks_without_steps_or_encounter_roll(self):
        d = self.d
        door = d.positions(6, TILE_DOOR)[0]
        d.x, d.y = door[0] - 1, door[1]
        before = d.x, d.y, d.steps, d.rng.getstate()
        event, message = d.move(1, 0)
        self.assertEqual(event, '')
        self.assertIn('閉じた扉', message)
        self.assertEqual(before, (d.x, d.y, d.steps, d.rng.getstate()))

    def test_switch_requires_a_then_opens_door_without_mutating_map(self):
        d = self.d
        sx, sy = d.positions(6, TILE_SWITCH)[0]
        d.x, d.y = sx, sy - 1
        self.assertEqual(d.move(0, 1)[0], '')
        self.assertNotIn(6, d.activated_switches)
        self.assertEqual(d.interact()[0], 'switch')
        self.assertEqual(d.interact()[0], '')
        door = d.positions(6, TILE_DOOR)[0]
        d.x, d.y = door[0] - 1, door[1]
        self.assertEqual(d.move(1, 0)[0], '')
        self.assertEqual((d.x, d.y), door)
        self.assertEqual(d.tile(6, *door), TILE_DOOR)
        self.assertFalse(d.can_enter(5, *door))  # Different floor's wall remains a wall.

    def test_stairs_preserve_switch_and_enter_resets_only_expedition_state(self):
        d = self.d
        d.x, d.y = d.positions(6, TILE_SWITCH)[0]
        d.interact()
        d.defeated_bosses.add(4)
        d.change_floor(7)
        d.change_floor(6)
        self.assertIn(6, d.activated_switches)
        d.treasure.unbanked = 4
        potions = d.potions
        d.enter()
        self.assertEqual(d.activated_switches, set())
        self.assertEqual(d.defeated_bosses, {4})
        self.assertEqual((d.treasure.unbanked, d.potions), (4, potions))
        self.assertFalse(d.can_enter(6, *d.positions(6, TILE_DOOR)[0]))

    def test_quest_behind_door_is_reachable_after_legal_activation(self):
        d = self.d
        self.assertIn((20, 6), d.positions(6, TILE_QUEST))
        self.assertIn((20, 6), d.reachable(6))
        self.assertEqual(d.activated_switches, set())
        d.validate_maps()

    def test_editor_moved_switch_is_discovered_without_coordinate_data(self):
        d = self.d
        old = d.positions(6, TILE_SWITCH)[0]
        new = (3, 11)
        d.maps[6].pset(*old, TILE_FLOOR)
        d.maps[6].pset(*new, TILE_SWITCH)
        d.validate_maps()
        d.x, d.y = new
        self.assertEqual(d.interact()[0], 'switch')
        self.assertTrue(d.can_enter(6, *d.positions(6, TILE_DOOR)[0]))

    def test_switch_behind_own_door_and_door_without_switch_are_rejected(self):
        d = self.d
        old = d.positions(6, TILE_SWITCH)[0]
        d.maps[6].pset(*old, TILE_FLOOR)
        with self.assertRaisesRegex(ValueError, 'スイッチ'):
            d.validate_maps()
        d.maps[6].pset(18, 5, TILE_SWITCH)
        with self.assertRaisesRegex(ValueError, 'イベント'):
            d.validate_maps()

    def test_all_same_floor_doors_open_together(self):
        d = self.d
        d.maps[6].pset(16, 4, TILE_DOOR)
        d.validate_maps()
        d.x, d.y = d.positions(6, TILE_SWITCH)[0]
        d.interact()
        self.assertTrue(all(d.can_enter(6, *p) for p in d.positions(6, TILE_DOOR)))
