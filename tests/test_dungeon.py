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
                       TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_CHEST, TILE_BOSS, FLOOR_TILES)


class DungeonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

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
        self.assertGreater(sum(len(d.positions(f, TILE_CHEST)) for f in range(15)), 0)
        for f in (4, 9, 14):
            self.assertEqual(len(d.positions(f, TILE_BOSS)), 1)

    def test_wall_bounds_and_diagonal_do_not_move_or_roll(self):
        d = self.dungeon
        d.enter()
        d.x, d.y = 2, 3  # One step west of the authored entrance room wall.
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
        # Controlled floor corridor, independent of the author's entrance placement.
        d.x, d.y = 3, 3
        self.assertEqual(d.move(1, 0)[0], "")
        self.assertEqual(d.move(1, 0)[0], "")
        self.assertEqual(d.move(-1, 0)[0], "battle")
        self.assertEqual((d.x, d.y), (4, 3))
        self.assertEqual(d.steps, 3)

    def test_image_row_64_corridors_allow_movement_reachability_and_encounters(self):
        d = self.dungeon
        d.settings["encounter_chance"] = 1
        for floor in (0, 5):
            start = d.find(floor, TILE_ENTRANCE if floor == 0 else TILE_STAIRS_UP)
            destination = next((start[0] + dx, start[1] + dy)
                               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                               if d.can_enter(floor, start[0] + dx, start[1] + dy))
            for u in range(9):
                with self.subTest(floor=floor, tile=(u, 8)):
                    d.maps[floor].pset(*destination, (u, 8))
                    self.assertTrue(d.can_enter(floor, *destination))
                    self.assertIn(destination, d.reachable(floor))
                    d.floor, d.x, d.y = floor, *start
                    d.grace = 1
                    delta = destination[0] - start[0], destination[1] - start[1]
                    self.assertEqual(d.move(*delta)[0], "")
                    self.assertEqual(d.grace, 0)
                    d.x, d.y = start
                    self.assertEqual(d.move(*delta)[0], "battle")
                    self.assertEqual(d.tile(floor, *destination), (u, 8))
            for tile in ((9, 8), (0, 7), (0, 9)):
                d.maps[floor].pset(*destination, tile)
                self.assertFalse(d.can_enter(floor, *destination))

    def test_random_encounter_rate_is_unchanged(self):
        d = self.dungeon
        d.grace = 0
        d.x, d.y = 4, 3
        counts = []
        for debug in (False, True):
            count = 0
            for step in range(10000):
                event, _ = d.move(1 if step % 2 == 0 else -1, 0, debug)
                count += event == "battle"
            counts.append(count)
        self.assertTrue(700 < counts[0] < 1100)
        self.assertTrue(4000 < counts[1] < 5000)

    def floor_step(self, floor):
        """Use two adjacent authored floor tiles, never mutate the map."""
        d = self.dungeon
        for x, y in sorted(d.reachable(floor)):
            if d.tile(floor, x, y) in FLOOR_TILES:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if d.tile(floor, x + dx, y + dy) in FLOOR_TILES:
                        return (x, y), (dx, dy)
        self.fail(f'B{floor + 1}: no reachable ordinary floor pair')

    def test_b4_b5_b9_b10_b14_roll_encounters_and_boss_clear_does_not_disable_them(self):
        d = self.dungeon
        for floor in (3, 4, 8, 9, 13):
            for cleared in (False, True):
                for debug in (False, True):
                    with self.subTest(floor=floor+1, cleared=cleared, debug=debug):
                        d.debug_floor(floor)
                        if floor in (4, 9):
                            d.defeated_bosses.discard(floor)
                            if cleared:
                                d.defeat_boss()
                        point, delta = self.floor_step(floor)
                        d.x, d.y = point
                        d.grace = 0
                        with patch.object(d.rng, 'random', return_value=0) as roll:
                            self.assertEqual(d.move(*delta, debug=debug)[0], 'battle')
                        roll.assert_called_once_with()

    def test_b5_b10_preserve_safe_steps_and_configured_chance(self):
        d = self.dungeon
        for floor in (4, 9):
            with self.subTest(floor=floor+1):
                point, delta = self.floor_step(floor)
                d.debug_floor(floor)
                with patch.object(d.rng, 'random', return_value=0) as roll:
                    for remaining in (1, 0):
                        d.x, d.y = point
                        self.assertEqual(d.move(*delta)[0], '')
                        self.assertEqual(d.grace, remaining)
                    roll.assert_not_called()
                    d.x, d.y = point
                    self.assertEqual(d.move(*delta)[0], 'battle')
                for debug in (False, True):
                    chance = d.settings['debug_encounter_chance' if debug else 'encounter_chance']
                    for sample, expected in ((chance - 0.001, 'battle'), (chance, '')):
                        d.x, d.y = point
                        with patch.object(d.rng, 'random', return_value=sample):
                            self.assertEqual(d.move(*delta, debug=debug)[0], expected)

    def test_b5_b10_normal_enemies_reuse_exact_previous_profile_and_boss_is_unchanged(self):
        d = self.dungeon
        before = copy.deepcopy((d.settings, d.enemies))
        for floor in (4, 9):
            with self.subTest(floor=floor+1):
                d.debug_floor(floor)
                state = d.rng.getstate()
                actual = d.make_enemies()
                d.rng.setstate(state)
                d.floor = floor - 1
                expected = d.make_enemies()
                self.assertEqual([vars(e) for e in actual], [vars(e) for e in expected])
                d.floor = floor
                boss = d.make_enemies(boss=True)
                self.assertEqual(len(boss), 1)
                self.assertEqual((boss[0].name, boss[0].max_hp), (d.boss_data['name'], d.boss_data['max_hp']))
        self.assertEqual((d.settings, d.enemies), before)

    def test_b15_never_rolls_random_encounters_before_during_or_after_finale(self):
        d = self.dungeon
        d.debug_floor(14)
        point, delta = self.floor_step(14)
        for stage in ('arrival', 'guardian1', 'guardian2', 'guardian3', 'spring', 'demon_clear'):
            if stage == 'guardian1':
                d.finale.start_guardians()
            elif stage in ('guardian2', 'guardian3', 'spring'):
                d.finale.guardian_victory()
            elif stage == 'demon_clear':
                d.defeat_boss()
            for debug in (False, True):
                with self.subTest(stage=stage, debug=debug):
                    d.x, d.y = point
                    d.grace = 0
                    with patch.object(d.rng, 'random', return_value=0) as roll:
                        self.assertEqual(d.move(*delta, debug=debug)[0], '')
                    roll.assert_not_called()

    def test_editor_moved_stairs_use_new_arrival_and_exit(self):
        d = self.dungeon
        old = d.find(1, TILE_STAIRS_UP)
        d.maps[1].pset(*old, TILE_FLOOR)
        d.maps[1].pset(3, 4, TILE_STAIRS_UP)
        old_down = d.find(0, TILE_STAIRS_DOWN)
        d.maps[0].pset(*old_down, TILE_FLOOR)
        start = d.find(0, TILE_ENTRANCE)
        new_down = start[0] + 1, start[1]
        d.maps[0].pset(*new_down, TILE_STAIRS_DOWN)
        d.x, d.y = start
        event, _ = d.move(1, 0)
        self.assertEqual(event, "stairs")
        self.assertEqual((d.floor, d.x, d.y), (1, 3, 4))
        event, _ = d.interact()
        self.assertEqual(event, "stairs")
        self.assertEqual((d.floor, d.x, d.y), (0, *new_down))

    def test_editor_moved_chest_once_per_excursion(self):
        d = self.dungeon
        d.exploration_settings["CHEST_REWARD_TABLE"]["NORMAL"] = [{"kind": "POTION", "amount": 1, "weight": 1}]
        old = d.positions(1, TILE_CHEST)[0]
        d.maps[1].pset(*old, TILE_FLOOR)
        d.maps[1].pset(20, 19, TILE_CHEST)
        d.enter()
        d.change_floor(1)
        self.assertEqual(d.move(1, 0)[0], "chest")
        self.assertEqual(d.potions, 3)
        d.interact()
        self.assertEqual(d.potions, 3)
        d.change_floor(2)
        d.change_floor(1)
        d.x, d.y = 20, 19
        d.interact()
        self.assertEqual(d.potions, 3)
        d.enter()
        d.change_floor(1)
        d.move(1, 0)
        self.assertEqual(d.potions, 4)

    def test_full_potion_inventory_keeps_same_chest_contents(self):
        d = self.dungeon
        d.exploration_settings["CHEST_REWARD_TABLE"]["NORMAL"] = [{"kind": "POTION", "amount": 1, "weight": 1}]
        d.x, d.y = d.positions(1, TILE_CHEST)[0]
        d.floor = 1
        d.potions = 9
        d.interact()
        self.assertFalse(d.opened)
        d.exploration_settings["CHEST_REWARD_TABLE"]["NORMAL"] = [{"kind": "TREASURE", "amount": 1, "weight": 1}]
        d.potions -= 1
        d.interact()
        self.assertEqual((d.potions, d.treasure.unbanked), (9, 0))
        self.assertTrue(d.opened)

    def test_treasure_and_potion_rules(self):
        d = self.dungeon
        d.exploration_settings["CHEST_REWARD_TABLE"]["NORMAL"] = [{"kind": "TREASURE", "amount": 1, "weight": 1}]
        d.x, d.y = d.positions(1, TILE_CHEST)[0]
        d.floor = 1
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
        self.assertEqual(s.results[-1], "探索へ戻る")
        s.next_battle(d.make_enemies(), recover=False)
        self.assertEqual([c.hp for c in s.party], before)

    def test_moved_boss_starts_fixed_single_enemy(self):
        d = self.dungeon
        old = d.find(4, TILE_BOSS)
        d.maps[4].pset(*old, TILE_FLOOR)
        d.maps[4].pset(5, 19, TILE_BOSS)
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
        d.finale.guardians_defeated = True
        d.defeat_boss()
        with self.assertRaises(ValueError):
            d.enter()

    def test_editor_resource_save_and_reload_changes_runtime(self):
        original_hash = hashlib.sha256(DUNGEON_RESOURCE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(dir=ROOT / "verification") as directory:
            # Pyxel Editor writes exactly these Image/Tilemap fields into .pyxres.
            edited = Path(directory) / "edited.pyxres"
            pyxel.tilemaps[0].pset(4, 3, TILE_WALL)
            pyxel.images[1].pset(0, 0, 3)
            pyxel.save(str(edited))
            pyxel.load(str(DUNGEON_RESOURCE))
            self.assertEqual(tuple(pyxel.tilemaps[0].pget(4, 3)), TILE_FLOOR)
            pyxel.load(str(edited))
            self.assertEqual(tuple(pyxel.tilemaps[0].pget(4, 3)), TILE_WALL)
            self.assertEqual(pyxel.images[1].pget(0, 0), 3)
            # Runtime maps are independent copies; reload to see Editor changes.
            self.dungeon.maps[0].blt(0, 0, pyxel.tilemaps[0], 0, 0, 256, 256)
            self.dungeon.x, self.dungeon.y = 3, 3
            self.assertEqual(self.dungeon.move(1, 0)[0], "")
            self.assertEqual((self.dungeon.x, self.dungeon.y), (3, 3))
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
        d.finale.guardians_defeated = True
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
            boss_start = self.dungeon.find(9, TILE_STAIRS_UP)
            new_boss = boss_start[0] + 1, boss_start[1]
            pyxel.tilemaps[4].pset(*new_boss, TILE_BOSS)
            start = self.dungeon.find(5, TILE_STAIRS_UP)
            pyxel.tilemaps[0].pset(start[0] + 1, start[1], TILE_WALL)
            pyxel.save(str(edited))
            with patch('rpg.map_resources.AREA_RESOURCES', (AREA_RESOURCES[0], edited, AREA_RESOURCES[2])):
                d = Dungeon(load_maps(), self.session.enemy_data, self.settings, self.session.rng)
            d.debug_floor(5)
            self.assertEqual(d.move(1, 0)[0], '')
            self.assertEqual((d.x, d.y), start)
            d.debug_floor(9)
            self.assertEqual(d.move(1, 0)[0], 'boss')
            self.assertEqual(d.boss_data['id'], 'skill_keeper')
            self.assertEqual(d.boss_positions[9], new_boss)
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
