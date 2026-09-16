import hashlib
import copy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import pyxel

from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.tiles import (DUNGEON_RESOURCE, AREA_RESOURCES, TILE_WALL, TILE_FLOOR, TILE_ENTRANCE,
                       TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_CHEST, TILE_BOSS)


class DungeonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pyxel.init(160, 120, headless=True)

    def setUp(self):
        pyxel.load(str(DUNGEON_RESOURCE))
        self.session = Session(*load_content(), seed=123)
        self.settings = load_dungeon_settings()
        self.dungeon = Dungeon(load_maps(), self.session.enemy_data, self.settings, self.session.rng)

    def test_resource_loads_fifteen_reachable_fixed_maps(self):
        d = self.dungeon
        self.assertEqual(len(d.maps), 15)
        for f in range(15):
            self.assertEqual(d.maps[f].imgsrc, 1)
            self.assertTrue(1 <= len(d.positions(f, TILE_CHEST)) <= 3)
        for f in (4, 9, 14):
            self.assertEqual(len(d.positions(f, TILE_BOSS)), 1)

    def test_wall_bounds_and_diagonal_do_not_move_or_roll(self):
        d = self.dungeon
        d.enter()
        before = d.x, d.y, d.steps, d.rng.getstate()
        self.assertEqual(d.move(-1, 0)[0], "")
        self.assertEqual(d.move(1, 1)[0], "")
        self.assertEqual((d.x, d.y, d.steps, d.rng.getstate()), before)
        d.x = -1
        self.assertIsNone(d.tile(0, -1, 1))

    def test_configured_maps_can_be_larger_than_the_viewport(self):
        settings = copy.deepcopy(self.settings)
        settings["width"], settings["height"] = 32, 24
        wide = Dungeon(load_maps(), self.session.enemy_data, settings,
                       random.Random(7))
        self.assertEqual((wide.width, wide.height), (32, 24))
        self.assertEqual(wide.tile(0, 20, 20), TILE_FLOOR)
        settings["width"] = pyxel.tilemaps[0].width + 1
        with self.assertRaisesRegex(ValueError, "width"):
            Dungeon(load_maps(), self.session.enemy_data, settings,
                    random.Random(7))

    def test_walk_encounter_and_safe_steps(self):
        d = self.dungeon
        d.settings["encounter_chance"] = 1
        d.enter()
        self.assertEqual(d.move(1, 0)[0], "")
        self.assertEqual(d.move(1, 0)[0], "")
        self.assertEqual(d.move(-1, 0)[0], "battle")
        self.assertEqual((d.x, d.y), (2, 1))
        self.assertEqual(d.steps, 3)

    def test_random_encounter_rate_and_no_random_fights_on_boss_floor(self):
        d = self.dungeon
        d.grace = 0
        d.x, d.y = 2, 1
        counts = []
        for debug in (False, True):
            count = 0
            for step in range(10000):
                event, _ = d.move(1 if step % 2 == 0 else -1, 0, debug)
                count += event == "battle"
            counts.append(count)
        self.assertTrue(700 < counts[0] < 1100)
        self.assertTrue(4000 < counts[1] < 5000)
        d.debug_floor(4)
        d.settings["debug_encounter_chance"] = 1
        for _ in range(100):
            d.x, d.y = 2, 1
            self.assertEqual(d.move(1, 0, True)[0], "")

    def test_editor_moved_stairs_use_new_arrival_and_exit(self):
        d = self.dungeon
        old = d.find(1, TILE_STAIRS_UP)
        d.maps[1].pset(*old, TILE_FLOOR)
        d.maps[1].pset(2, 1, TILE_STAIRS_UP)
        old_down = d.find(0, TILE_STAIRS_DOWN)
        d.maps[0].pset(*old_down, TILE_FLOOR)
        d.maps[0].pset(3, 1, TILE_STAIRS_DOWN)
        d.x, d.y = 2, 1
        event, _ = d.move(1, 0)
        self.assertEqual(event, "stairs")
        self.assertEqual((d.floor, d.x, d.y), (1, 2, 1))
        event, _ = d.interact()
        self.assertEqual(event, "stairs")
        self.assertEqual((d.floor, d.x, d.y), (0, 3, 1))

    def test_editor_moved_chest_once_per_excursion(self):
        d = self.dungeon
        d.settings["items"]["chest_potion_chance"] = 1
        old = d.positions(0, TILE_CHEST)[0]
        d.maps[0].pset(*old, TILE_FLOOR)
        d.maps[0].pset(2, 1, TILE_CHEST)
        d.enter()
        self.assertEqual(d.move(1, 0)[0], "chest")
        self.assertEqual(d.potions, 3)
        d.interact()
        self.assertEqual(d.potions, 3)
        d.change_floor(1)
        d.change_floor(0)
        d.x, d.y = 2, 1
        d.interact()
        self.assertEqual(d.potions, 3)
        d.enter()
        d.move(1, 0)
        self.assertEqual(d.potions, 4)

    def test_full_potion_inventory_keeps_same_chest_contents(self):
        d = self.dungeon
        d.settings["items"]["chest_potion_chance"] = 1
        d.x, d.y = d.positions(0, TILE_CHEST)[0]
        d.potions = 9
        d.interact()
        self.assertFalse(d.opened)
        d.settings["items"]["chest_potion_chance"] = 0
        d.potions -= 1
        d.interact()
        self.assertEqual((d.potions, d.treasure.unbanked), (9, 0))
        self.assertTrue(d.opened)

    def test_treasure_and_potion_rules(self):
        d = self.dungeon
        d.settings["items"]["chest_potion_chance"] = 0
        d.x, d.y = d.positions(0, TILE_CHEST)[0]
        d.interact()
        self.assertEqual(d.treasure.unbanked, 1)
        self.assertEqual(d.treasure.banked, 0)
        c = self.session.party[0]
        d.use_potion(c)
        self.assertEqual(d.potions, 2)
        c.hp = 0
        d.use_potion(c)
        self.assertEqual(d.potions, 2)
        c.hp = 1
        d.use_potion(c)
        self.assertEqual((c.hp, d.potions), (31, 1))
        d.use_potion(c)
        self.assertEqual((c.hp, d.potions), (c.max_hp, 0))
        c.hp = 1
        d.use_potion(c)
        self.assertEqual(c.hp, 1)

    def test_hp_and_knockout_persist_through_battle_and_growth(self):
        s, d = self.session, self.dungeon
        s.party[0].hp = 11
        s.party[1].hp = 0
        s.party[0].berserk = 3
        enemies = d.make_enemies()
        for e in enemies:
            e.hp = 1
        b = s.next_battle(enemies, recover=False)
        self.assertEqual(s.party[0].hp, 11)
        self.assertEqual(s.party[1].hp, 0)
        self.assertEqual(s.party[0].berserk, 0)
        while not b.outcome:
            b.begin_round(b.auto_actions())
            while b.queue:
                b.step()
        before = [c.hp for c in s.party]
        s.settings["spark_chance"] = 1
        for rates in s.settings["growth_rates"].values():
            rates.update(HP=1, STR=1, AGI=1, INT=1)
        old_max = s.party[0].max_hp
        s.settle()
        self.assertEqual([c.hp for c in s.party], before)
        self.assertGreater(s.party[0].max_hp, old_max)
        self.assertTrue(all(c.skills for c in s.party))
        self.assertIn("持ち越し", s.results[-1])
        s.next_battle(d.make_enemies(), recover=False)
        self.assertEqual([c.hp for c in s.party], before)

    def test_moved_boss_starts_fixed_single_enemy(self):
        d = self.dungeon
        old = d.find(4, TILE_BOSS)
        d.maps[4].pset(*old, TILE_FLOOR)
        d.maps[4].pset(2, 1, TILE_BOSS)
        d.debug_floor(4)
        self.assertEqual(d.move(1, 0)[0], "boss")
        boss = d.make_enemies(boss=True)
        self.assertEqual(len(boss), 1)
        self.assertGreater(boss[0].max_hp, 250)
        self.assertGreater(boss[0].strength, 15)
        d.defeat_boss()
        self.assertEqual(d.interact()[0], "")
        d.enter()
        d.debug_floor(14)
        d.defeat_boss()
        with self.assertRaises(ValueError):
            d.enter()

    def test_editor_resource_save_and_reload_changes_runtime(self):
        original_hash = hashlib.sha256(DUNGEON_RESOURCE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(dir=ROOT / "verification") as directory:
            # Pyxel Editor writes exactly these Image/Tilemap fields into .pyxres.
            edited = Path(directory) / "edited.pyxres"
            pyxel.tilemaps[0].pset(2, 1, TILE_WALL)
            pyxel.images[1].pset(0, 0, 3)
            pyxel.save(str(edited))
            pyxel.load(str(DUNGEON_RESOURCE))
            self.assertEqual(tuple(pyxel.tilemaps[0].pget(2, 1)), TILE_FLOOR)
            pyxel.load(str(edited))
            self.assertEqual(tuple(pyxel.tilemaps[0].pget(2, 1)), TILE_WALL)
            self.assertEqual(pyxel.images[1].pget(0, 0), 3)
            # Runtime maps are independent copies; reload to see Editor changes.
            self.dungeon.maps[0].blt(0, 0, pyxel.tilemaps[0], 0, 0, 256, 256)
            self.assertEqual(self.dungeon.move(1, 0)[0], "")
            self.assertEqual((self.dungeon.x, self.dungeon.y), (1, 1))
        self.assertEqual(hashlib.sha256(DUNGEON_RESOURCE.read_bytes()).hexdigest(), original_hash)

    def test_invalid_event_layout_is_reported(self):
        old = self.dungeon.find(1, TILE_STAIRS_UP)
        self.dungeon.maps[1].pset(*old, TILE_FLOOR)
        with self.assertRaises(ValueError):
            self.dungeon.validate_maps()

    def test_duplicate_enemy_ids_are_reported(self):
        rows = self.session.enemy_data + [self.session.enemy_data[0]]
        with self.assertRaisesRegex(ValueError, "id"):
            Dungeon(load_maps(), rows, self.settings, self.session.rng)

    def test_boss_gates_persist_on_return_and_only_final_clears(self):
        d = self.dungeon
        for floor in (4, 9):
            d.debug_floor(floor)
            d.x, d.y = d.find(floor, TILE_STAIRS_DOWN)
            before = d.floor, d.x, d.y
            self.assertEqual(d.interact()[0], "")
            self.assertEqual((d.floor, d.x, d.y), before)
            d.defeat_boss()
            self.assertFalse(d.cleared)
            self.assertEqual(d.interact()[0], "stairs")
            self.assertEqual(d.floor, floor + 1)
            self.assertEqual(d.interact()[0], "stairs")  # Return upwards.
            d.enter()
            self.assertIn(floor, d.defeated_bosses)
        d.debug_floor(14)
        self.assertEqual(d.boss_data["id"], "depth_lord")
        self.assertFalse(d.positions(14, TILE_STAIRS_DOWN))
        d.defeat_boss()
        self.assertTrue(d.cleared)

    def test_area_maps_are_independent_and_restore_editor_main_banks(self):
        d = self.dungeon
        original = tuple(d.maps[0].pget(2, 1))
        d.maps[5].pset(2, 1, TILE_CHEST)
        self.assertEqual(tuple(d.maps[0].pget(2, 1)), original)
        self.assertEqual(tuple(pyxel.tilemaps[0].pget(2, 1)), original)
        self.assertEqual(self.settings['spark_multipliers'][0], 1)
        d.debug_floor(14)
        self.assertEqual(d.spark_multiplier, 2)

    def test_editor_area_save_reload_and_moved_boss_event(self):
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in AREA_RESOURCES]
        with tempfile.TemporaryDirectory(dir=ROOT / 'verification') as directory:
            edited = Path(directory) / 'area2.pyxres'
            pyxel.load(str(AREA_RESOURCES[1]))
            old = self.dungeon.find(9, TILE_BOSS)
            pyxel.tilemaps[4].pset(*old, TILE_FLOOR)
            pyxel.tilemaps[4].pset(2, 1, TILE_BOSS)
            pyxel.tilemaps[0].pset(2, 1, TILE_WALL)
            pyxel.save(str(edited))
            with patch('rpg.map_resources.AREA_RESOURCES', (AREA_RESOURCES[0], edited, AREA_RESOURCES[2])):
                d = Dungeon(load_maps(), self.session.enemy_data, self.settings, self.session.rng)
            d.debug_floor(5)
            self.assertEqual(d.move(1, 0)[0], '')
            self.assertEqual((d.x, d.y), (1, 1))
            d.debug_floor(9)
            self.assertEqual(d.move(1, 0)[0], 'boss')
            self.assertEqual(d.boss_data['id'], 'skill_keeper')
            self.assertEqual(d.boss_positions[9], (2, 1))
            d.defeat_boss()
            self.assertEqual(d.interact()[0], '')
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in AREA_RESOURCES])

    def test_invalid_depth_and_boss_data_are_reported(self):
        d = self.dungeon
        d.settings['spark_multipliers'][0] = 3
        with self.assertRaisesRegex(ValueError, 'spark_multipliers'):
            d.validate_settings()
        d.settings['spark_multipliers'][0] = 1
        d.enemies['guardian']['message'] = []
        with self.assertRaisesRegex(ValueError, 'message'):
            d.validate_settings()


if __name__ == "__main__":
    unittest.main()
