"""Fixed enemy identity across spawn paths, names, sprites and saved hunts."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pyxel

from rpg.art import load_art
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.exploration import Exploration
from rpg.final_battle import make_final_enemy
from rpg.final_presentation import FinalPresentation
from rpg.map_resources import load_maps
from rpg.models import Enemy
from rpg.save import apply_save_data, make_save_data


class EnemyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        load_art(pyxel)
        self.content = load_content()
        self.s = Session(*deepcopy(self.content), seed=92)
        self.d = Dungeon(load_maps(), self.s.enemy_data, load_dungeon_settings(),
                         self.s.rng, self.s.treasure, self.s.inventory)
        self.e = Exploration(self.s, self.d)

    def test_normal_encounters_keep_ids_with_duplicate_species_and_name_suffixes(self):
        seen = set()
        duplicate_seen = False
        for floor in range(14):
            self.d.floor = floor
            for seed in range(20):
                self.s.rng.seed(seed)
                enemies = self.d.make_enemies()
                duplicate_seen |= len({enemy.id for enemy in enemies}) < len(enemies)
                for index, enemy in enumerate(enemies):
                    row = self.d.enemies[enemy.id]
                    self.assertEqual(enemy.name, f"{row['name']} {chr(65 + index)}")
                    self.assertFalse(row.get('boss'))
                    seen.add(enemy.id)
        self.assertTrue(duplicate_seen)
        self.assertEqual(seen, {row['id'] for row in self.s.enemy_data if not row.get('boss')})

    def test_boss_and_guardian_ids_and_existing_sprite_reuse(self):
        for floor, ident, sprite in ((4, 'guardian', (112, 16)),
                                     (9, 'skill_keeper', (144, 16)),
                                     (14, 'depth_lord', (192, 16))):
            self.d.floor = floor
            enemy, = self.d.make_enemies(boss=True)
            self.assertEqual((enemy.id, enemy.sprite), (ident, sprite))
            self.assertEqual(enemy.name, self.d.enemies[ident]['name'])
        self.d.floor = 14
        for index, ident, sprite in ((0, 'sentinel_armor', (112, 16)),
                                     (1, 'sentinel_speed', (144, 16)),
                                     (2, 'sentinel_mind', (160, 16))):
            enemy, = self.d.make_enemies(guardian_index=index)
            self.assertEqual((enemy.id, enemy.sprite), (ident, sprite))
            self.assertTrue(any(pyxel.images[0].pget(x, y) for x in range(sprite[0], sprite[0]+16)
                                for y in range(sprite[1], sprite[1]+16)))

    def test_display_name_changes_do_not_change_identity_or_trigger_final_barrier(self):
        row = deepcopy(self.d.enemies['slime'])
        row['name'] = self.d.enemies['lord_of_elysion']['name']
        enemy = Enemy.from_definition(row, name=row['name'] + ' A')
        self.assertEqual(enemy.id, 'slime')
        self.assertEqual(enemy.name, row['name'] + ' A')
        battle = Battle(self.s.party, [enemy], self.s.skills, boss=True)
        self.assertFalse(battle.is_elysion_battle)
        self.assertFalse(battle.elysion_barrier_active)

    def test_prototype_generation_also_preserves_fixed_ids(self):
        seen = set()
        rows = self.d.enemies
        for seed in range(60):
            s = Session(*deepcopy(self.content), seed=seed)
            for index, enemy in enumerate(s.next_battle().enemies):
                self.assertEqual(enemy.name, f"{rows[enemy.id]['name']} {chr(65 + index)}")
                seen.add(enemy.id)
        self.assertEqual(seen, {row['id'] for row in self.s.enemy_data if not row.get('boss')})

    def test_hunt_save_load_and_display_name_change_keep_saved_enemy_id(self):
        app = SimpleNamespace(session=self.s, dungeon=self.d, exploration=self.e,
                              initial_content=self.content, hub_intro_shown=True)
        self.d.defeated_bosses.update((4, 9))
        for level in (1, 2, 3):
            app.exploration.active = None
            app.exploration.accept(level, quest_type='hunt')
            saved = make_save_data(app)
            ident = saved['active_quest']['hunt_enemy_id']
            original_name = next(row['name'] for row in self.content[3] if row['id'] == ident)
            for row in app.initial_content[3]:
                if row['id'] == ident:
                    row['name'] = original_name + ' renamed'
            apply_save_data(app, saved)
            self.assertEqual(make_save_data(app), saved)
            q = app.exploration.active_quest
            app.dungeon.floor = q['target_floor'] - 1
            app.dungeon.x, app.dungeon.y = q['points'][0]
            enemy, = app.exploration.make_hunt_enemy()
            self.assertEqual(enemy.id, ident)
            self.assertEqual(enemy.name, original_name + ' renamed')

    def test_final_boss_keeps_identity_barrier_and_dedicated_48px_draw(self):
        enemy = make_final_enemy(self.s.enemy_data)
        self.assertEqual(enemy.id, 'lord_of_elysion')
        battle = Battle(self.s.party, [enemy], self.s.skills, boss=True)
        self.assertTrue(battle.is_elysion_battle and battle.elysion_barrier_active)
        visual = FinalPresentation()
        with patch.object(pyxel, 'blt') as blt:
            visual.draw_boss(pyxel, enemy, False)
        self.assertEqual(blt.call_args.args[2:7], (0, 144, 64, 48, 48))
