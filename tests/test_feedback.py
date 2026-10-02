"""Regressions for playtest feedback, using real resources and combat rules."""
import unittest
from unittest.mock import patch

import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.exploration import Exploration
from rpg.growth import spark
from rpg.map_resources import load_maps
from rpg.models import Action
from rpg.tiles import (TILE_CHEST, TILE_RARE_CHEST, TILE_POISON, TILE_PIT,
                       TILE_HEAL_POINT, TILE_FLOOR, TILE_QUEST, TILE_ENTRANCE,
                       TILE_STAIRS_UP, PASSABLE)


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        self.s = Session(*load_content(), seed=42)
        self.d = Dungeon(load_maps(), self.s.enemy_data, load_dungeon_settings(), self.s.rng, self.s.treasure)
        self.e = Exploration(self.s, self.d)

    def test_editor_tiles_present_and_rare_chests_are_scarce(self):
        normal = rare = 0
        for floor in range(15):
            normal += len(self.d.positions(floor, TILE_CHEST))
            rare += len(self.d.positions(floor, TILE_RARE_CHEST))
        for tile in (TILE_POISON, TILE_PIT, TILE_HEAL_POINT):
            self.assertTrue(any(self.d.positions(floor, tile) for floor in range(15)))
        self.assertGreater(rare, 0)
        self.assertGreater(normal, rare)
        self.d.validate_maps()

    def test_editor_spring_and_rare_chest_are_events(self):
        for floor, tile, event in ((3, TILE_HEAL_POINT, 'spring'), (2, TILE_RARE_CHEST, 'chest')):
            positions = self.d.positions(floor, tile)
            self.assertTrue(positions)
            self.assertIn(tile, PASSABLE)
            self.d.floor = floor
            self.d.x, self.d.y = positions[0]
            self.assertEqual(self.d.interact()[0], event)

    def test_chest_weighted_sampling_and_no_second_reward(self):
        d = self.d
        kinds = set()
        rows = d.exploration_settings['CHEST_REWARD_TABLE']['NORMAL']
        for _ in range(400):
            d.enter()
            d.potions = 0
            d.floor = 1
            d.x, d.y = d.positions(1, TILE_CHEST)[0]
            before = d.treasure.unbanked
            self.assertEqual(d.interact()[0], 'chest')
            reward = d.last_reward
            kinds.add(reward['kind'])
            self.assertEqual(d.treasure.unbanked - before, reward.get('amount', 0) if reward['kind'] == 'TREASURE' else 0)
            self.assertEqual(d.interact()[0], '')
        self.assertEqual(kinds, {r['kind'] for r in rows})
        # Rarity selects its own table, not a fixed chest reward.
        rare_floor = next(floor for floor in range(15) if d.positions(floor, TILE_RARE_CHEST))
        d.debug_floor(rare_floor)
        d.x, d.y = d.positions(rare_floor, TILE_RARE_CHEST)[0]
        rare = [{'kind': 'TREASURE', 'amount': 17, 'weight': 1}]
        d.exploration_settings['CHEST_REWARD_TABLE']['RARE'] = rare
        before = d.treasure.unbanked
        d.interact()
        self.assertEqual(d.treasure.unbanked, before + 17)

    def test_trap_and_poison_do_not_kill_or_revive(self):
        for c, hp in zip(self.s.party, (0, 1, 5, 10)):
            c.hp = hp
        self.e.chest_effect({'kind': 'TRAP', 'amount': 4})
        self.assertEqual([c.hp for c in self.s.party], [0, 1, 1, 6])
        self.d.maps[0].pset(self.d.x + 1, self.d.y, TILE_POISON)
        self.assertEqual(self.d.move(1, 0)[0], 'poison')
        self.e.damage(self.d.exploration_settings['poison_damage'])
        self.assertEqual([c.hp for c in self.s.party], [0, 1, 1, 4])
        self.assertNotEqual(self.d.interact()[0], 'poison')

    def test_chests_never_heal_but_springs_still_do(self):
        tables = self.d.exploration_settings['CHEST_REWARD_TABLE']
        for rows in tables.values():
            self.assertFalse({'HEAL', 'HEAL_ALL'} & {row['kind'] for row in rows})
        for c in self.s.party:
            c.hp -= 5
        self.s.party[0].hp = 0
        before = [c.hp for c in self.s.party]
        self.assertEqual(self.e.chest_effect({'kind': 'HEAL_ALL', 'amount': 12}), [])
        self.assertEqual([c.hp for c in self.s.party], before)
        self.e.heal(12)
        self.assertEqual(sum(c.hp == c.max_hp for c in self.s.party), 3)
        self.assertEqual(self.s.party[0].hp, 0)

    def test_pits_all_floors_never_skip_locked_bosses(self):
        d = self.d
        for floor in range(15):
            d.debug_floor(floor)
            start = d.x, d.y
            d.maps[floor].pset(start[0] + 1, start[1], TILE_PIT)
            self.assertEqual(d.move(1, 0)[0], 'pit')
            self.assertEqual(d.floor, floor)
            self.assertEqual((d.x, d.y), d.find(floor, TILE_ENTRANCE if floor == 0 else TILE_STAIRS_UP))
        for floor in (4, 9):
            d.debug_floor(floor)
            self.assertEqual(d.change_floor(floor + 1)[0], '')
        self.assertEqual(d.defeated_bosses, set())

    def test_editor_moved_gimmicks_and_unreachable_pit_layout(self):
        start = self.d.x, self.d.y
        self.d.maps[0].pset(start[0] + 1, start[1], TILE_HEAL_POINT)
        self.assertEqual(self.d.move(1, 0)[0], 'spring')
        # A pit in the only exit from the entrance must fail map validation.
        self.d.maps[0].pset(start[0] + 1, start[1], TILE_PIT)
        from rpg.tiles import TILE_WALL
        for point in ((start[0] - 1, start[1]), (start[0], start[1] - 1), (start[0], start[1] + 1)):
            self.d.maps[0].pset(*point, TILE_WALL)
        with self.assertRaises(ValueError):
            self.d.validate_maps()

    def test_all_quest_bands_gates_and_reachable_floor_targets(self):
        e = self.e
        with self.assertRaises(ValueError):
            e.accept(2)
        self.d.defeated_bosses.add(4)
        with self.assertRaises(ValueError):
            e.accept(3)
        self.d.defeated_bosses.add(9)
        for qid in (1, 2, 3):
            floors = set()
            for _ in range(30):
                e.active = None
                e.accept(qid)
                floor, x, y = e.target
                floors.add(floor)
                self.assertEqual(self.d.tile(floor, x, y), TILE_QUEST if floor < 10 else TILE_FLOOR)
                self.assertIn((x, y), self.d.reachable(floor))
            self.assertEqual(floors, set(range((qid - 1) * 5, qid * 5)))

    def test_survey_requires_return_and_death_allows_retry(self):
        e = self.e
        e.accept(1)
        with self.assertRaises(ValueError):
            e.accept(1)
        self.assertFalse(e.return_to_camp(True))
        self.d.floor, self.d.x, self.d.y = e.target
        self.assertTrue(e.hint())
        self.assertTrue(e.investigate())
        self.assertFalse(e.investigate())
        self.assertEqual(self.s.treasure.banked, 0)
        self.assertTrue(e.return_to_camp(False))
        self.assertFalse(e.surveyed)
        self.assertTrue(e.active)
        e.investigate()
        self.assertTrue(e.return_to_camp(True))
        self.assertEqual(self.s.treasure.banked, 2)
        self.assertFalse(e.return_to_camp(True))
        self.assertEqual(self.s.treasure.banked, 2)
        with self.assertRaises(ValueError):
            e.accept(1)

    def test_chest_spark_full_slots_replace_before_any_battle(self):
        s = self.s
        c = s.party[0]
        for skill in list(s.skills.values()):
            if len(c.skills) >= s.settings['skill_slots']:
                break
            if skill.id not in c.skills:
                c.learn(skill)
        # Force a LEGEND on the first character, through the same spark path.
        with patch.object(s.rng, 'choice', side_effect=lambda seq: c if seq is s.party else seq[0]), patch.object(s.rng, 'choices', return_value=['LEGEND']):
            self.e.chest_effect({'kind': 'SKILL_CHANCE', 'chance': 1})
        new = c.pending_skill
        self.assertTrue(new)
        self.assertIn(new, s.discovered_skills)
        self.assertTrue(s.field_pending)
        s.resolve_replacement(0, 0)
        self.assertIn(new, c.skills)
        self.assertFalse(s.field_pending)
        self.assertFalse(any('DEBUG' in h for h in c.history))
        self.assertNotIn(new, s.mastered_skills)

    def test_mastery_bonus_acquisition_snapshot_and_no_stacking(self):
        s, c = self.s, self.s.party[0]
        skill = s.skills[c.skills[0]]
        other = s.party[1]
        other.learn(skill)
        b = s.next_battle()
        for _ in range(3):
            c.skill_uses[skill.id] = 1
            c.cooldowns.clear()
            b.enemies[0].hp = 10000
            b._party_action(Action(0, 'SKILL', 0, skill.id))
            self.assertIn(skill.id, s.mastered_skills)
            self.assertNotIn(skill.id, c.skills)
            c.learn(skill)
            self.assertEqual(c.skill_uses[skill.id], skill.max_uses)
            self.assertEqual(c.power_multiplier(skill), 1.2)
            self.assertEqual(c.max_uses(skill), skill.max_uses)
        self.assertEqual(other.max_uses(skill), skill.max_uses)
        self.assertEqual(other.power_multiplier(skill), 1.0)
        other.forget(skill.id)
        other.learn(skill)
        self.assertEqual(other.max_uses(skill), skill.max_uses)
        self.assertEqual(other.power_multiplier(skill), 1.2)

    def test_mastered_attack_scales_final_damage_but_heal_does_not(self):
        s, actor = self.s, self.s.party[0]
        skill = s.skills['punch']
        enemy = s.next_battle().enemies[0]
        enemy.hp = enemy.max_hp = 999
        enemy.defense = 3
        base = skill.power(actor, apply_mastery=False)
        normal = max(1, base - enemy.defense)
        self.assertEqual(s.battle._damage(enemy, base), normal)
        actor.forget(skill.id)
        s.mastered_skills.add(skill.id)
        actor.learn(skill)
        enemy.hp = enemy.max_hp
        self.assertEqual(s.battle._damage(enemy, base, power_bonus=actor.power_multiplier(skill)),
                         round(normal * 1.2))
        actor.forget(skill.id)
        actor.learn(skill)
        self.assertEqual(actor.power_multiplier(skill), 1.2)
        heal = s.skills['heal']
        s.mastered_skills.add(heal.id)
        actor.learn(heal)
        self.assertEqual(actor.power_multiplier(heal), 1.0)
        self.assertEqual(heal.power(actor), heal.power(actor, apply_mastery=False))

    def test_rare_support_relearn_cost_and_mastered_stock(self):
        s, c = self.s, self.s.party[0]
        s.treasure.banked = 20
        s.discovered_skills.update(s.skills)
        for sid in ('armor_break', 'focus'):
            skill = s.skills[sid]
            self.assertTrue(skill.can_relearn)
            self.assertEqual(skill.relearn_cost, 4)
            s.mastered_skills.add(sid)
            s.relearn(0, sid)
            self.assertEqual(c.skill_uses[sid], skill.relearn_uses)
            self.assertEqual(c.max_uses(skill), skill.max_uses)
            self.assertEqual(c.power_multiplier(skill), 1.2 if skill.effect == 'damage' else 1.0)
        self.assertEqual(s.treasure.banked, 12)
        for sid in ('meteor', 'triple_slash'):
            with self.assertRaises(ValueError):
                s.relearn(0, sid)

    def test_mastered_legend_spark_and_discard_does_not_master(self):
        s, c = self.s, self.s.party[0]
        skill = s.skills['meteor']
        c.learn(skill)
        c.forget(skill.id)
        self.assertNotIn(skill.id, s.mastered_skills)
        s.mastered_skills.add(skill.id)
        with patch.object(s.rng, 'choice', return_value=skill):
            spark(c, s.skills, s.settings, s.rng, allowed=['LEGEND'], discovered=s.discovered_skills)
        self.assertEqual(c.skill_uses[skill.id], skill.max_uses)
        self.assertEqual(c.power_multiplier(skill), 1.2)


if __name__ == '__main__':
    unittest.main()
