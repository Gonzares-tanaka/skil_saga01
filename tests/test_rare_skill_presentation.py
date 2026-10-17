"""All 20 RARE contracts, real resolution parity, bounded visual-only phases."""
from collections import Counter, deque
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import random
import sys
import time
import unittest
from unittest.mock import Mock, patch

from rpg.battle import Battle, Session
from rpg.battle_presentation import BattlePresentation, EFFECT_SPRITES, MAX_PRESENTATION_SECONDS
from rpg.content import ROOT, load_content, validate_skill
from rpg.models import Action, Enemy, Skill
from rpg.rare_skill_presentation import (RARE_PRESENTATION_IDS, RARE_SPRITES,
    RARE_ASSET_BANK, RARE_CAST_FRAMES, RARE_EFFECT_FRAMES, RARE_FEEDBACK_FRAMES,
    rare_presentation_id)

FAMILIES = {
    'rare_impact': ('heavy_break',),
    'rare_slash': ('triple_slash', 'rapid_edge', 'cleaving_storm', 'plague_edge'),
    'rare_magic': ('flare', 'inferno', 'thunder_bind'),
    'rare_dark': ('drain', 'nightmare', 'chaos_spell'),
    'rare_heal': ('heal', 'renew', 'revive', 'cure', 'purify_wind'),
    'rare_support': ('armor_break', 'focus', 'armor_wave', 'focus_field'),
}
MAPPING = {sid: family for family, ids in FAMILIES.items() for sid in ids}
BEFORE = ROOT / 'tests/fixtures/rare_presentation_before.json'


def old_skills():
    return {row['id']: Skill(**row) for row in json.loads(BEFORE.read_text(encoding='utf8'))['skills']}


def make_battle(sid, seed=88, skills=None, targets=4, mode='normal'):
    _, current, party, rows = load_content()
    skills = skills or current
    for actor in party:
        actor.hp, actor.max_hp = 300, 1000
        actor.strength = actor.agility = actor.intellect = 40
    actor = party[0]
    if sid not in actor.skills:
        actor.learn(skills[sid])
    if mode == 'mastered':
        actor.mastered_skills.add(sid)
        actor.mastered_copies.add(sid)
    elif mode == 'last_use':
        actor.skill_uses[sid] = 1
    elif mode == 'paralyze':
        actor.statuses = {'paralyze': 3}
    enemies = [Enemy.from_definition(rows[0], max_hp=5000, defense=7, magic_defense=5)
               for _ in range(targets)]
    if sid == 'revive':
        party[1].hp = 0
        party[1].statuses = {'poison': 2}
    if sid in ('cure', 'purify_wind'):
        party[1].statuses = {'poison': 2, 'paralyze': 3}
        party[2].statuses = {'sleep': 2}
    b = Battle(party, enemies, skills, rng=random.Random(seed))
    target = 1 if skills[sid].target == 'ally' else 0
    b.queue = deque([('party', Action(0, 'SKILL', target, sid))])
    return b


def finish_visual(b, draw=None):
    visual = BattlePresentation(b)
    phases, frames, lines, applied = [], Counter(), [], 0
    if not visual.start():
        return visual, b.step(), phases, frames, 1
    while visual.active:
        if not phases or phases[-1] != visual.phase:
            phases.append(visual.phase)
        frames[visual.phase] += 1
        if draw:
            visual.draw_effect(draw)
        event = visual.advance()
        if event == 'apply':
            alive = [enemy.alive for enemy in b.enemies]
            hp = [actor.hp for actor in b.party]
            lines = b.step()
            applied += 1
            visual.after_action(alive, hp)
        assert sum(frames.values()) < 80, phases
    return visual, lines, phases, frames, applied


def rule_state(b, lines):
    return (lines, [asdict(unit) for unit in b.party + b.enemies], b.rng.getstate(),
            b.outcome, list(b.queue), b.inventory.counts, b.mastered_skills,
            b.discovered_skills, b.resource_events, b.status_visual_events, b.sound_cue)


class RarePresentationTests(unittest.TestCase):
    def test_exact_roster_mapping_and_no_other_rarity_assignment(self):
        skills = load_content()[1]
        self.assertEqual(Counter(s.rarity for s in skills.values()),
                         {'BASIC': 3, 'COMMON': 18, 'UNCOMMON': 13, 'RARE': 20, 'LEGEND': 8})
        self.assertEqual({s.id: s.presentation_id for s in skills.values() if s.rarity == 'RARE'}, MAPPING)
        self.assertEqual(set(RARE_PRESENTATION_IDS), set(FAMILIES))

    def test_all_sixty_two_skill_rows_only_add_rare_presentation_metadata(self):
        before = json.loads(BEFORE.read_text(encoding='utf8'))['skills']
        now = json.loads((ROOT / 'data/skills.json').read_text(encoding='utf8'))
        self.assertEqual([{k: v for k, v in row.items() if k != 'presentation_id'} for row in now], before)
        for row in now:
            self.assertEqual(row.get('presentation_id'),
                             'legend_' + row['id'] if row['rarity'] == 'LEGEND' else MAPPING.get(row['id']))

    def test_validation_and_optional_legacy_fallback(self):
        skill = load_content()[1]['heavy_break']
        validate_skill(replace(skill, presentation_id=None))
        for changes in (dict(presentation_id='rare_missing'), dict(presentation_id={}),
                        dict(presentation_id=7), dict(rarity='COMMON'), dict(rarity='LEGEND')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_skill(replace(skill, **changes))
        for ident in (None, 'rare_missing', {}):
            self.assertIsNone(rare_presentation_id(replace(skill, presentation_id=ident)))
        self.assertIsNone(rare_presentation_id(replace(skill, rarity='LEGEND')))

    def test_all_twenty_rule_rng_resources_mastery_restore_match_before(self):
        previous = old_skills()
        comparisons = 0
        for sid in MAPPING:
            for seed in (1, 41, 99):
                for mode in ('normal', 'mastered', 'last_use', 'paralyze'):
                    with self.subTest(skill=sid, seed=seed, mode=mode):
                        before = make_battle(sid, seed, previous, mode=mode)
                        now = make_battle(sid, seed, mode=mode)
                        expected = rule_state(before, before.step())
                        _, lines, _, _, applied = finish_visual(now)
                        self.assertEqual(applied, 1)
                        self.assertEqual(rule_state(now, lines), expected)
                        self.assertEqual(now.skills[sid].can_relearn, before.skills[sid].can_relearn)
                        self.assertEqual(now.skills[sid].relearn_cost, before.skills[sid].relearn_cost)
                        self.assertEqual(now.skills[sid].relearn_uses, before.skills[sid].relearn_uses)
                        comparisons += 1
        self.assertEqual(comparisons, 240)

    def test_all_twenty_families_render_and_finish_with_fixed_timers(self):
        for sid, family in MAPPING.items():
            with self.subTest(skill=sid):
                surface = Mock()
                visual, _, phases, frames, applied = finish_visual(make_battle(sid), surface)
                self.assertEqual(applied, 1)
                self.assertEqual(phases[:4], ['actor_step', 'rare_cast', 'rare_effect', 'rare_feedback'])
                self.assertEqual(frames['rare_cast'], RARE_CAST_FRAMES)
                self.assertEqual(frames['rare_effect'], RARE_EFFECT_FRAMES)
                self.assertEqual(frames['rare_feedback'], RARE_FEEDBACK_FRAMES)
                u, v = RARE_SPRITES[family]
                self.assertTrue(any(c.args[2] == RARE_ASSET_BANK and c.args[4] == v
                                    and u <= c.args[3] < u + 96 for c in surface.blt.call_args_list))
                self.assertFalse(visual.active or visual.presentation_id or visual.rare_hp_changes)

    def test_multislash_damage_and_defense_calculated_once_per_target(self):
        for sid in ('triple_slash', 'rapid_edge', 'cleaving_storm', 'plague_edge'):
            b = make_battle(sid)
            count = 4 if sid == 'cleaving_storm' else 1
            with patch.object(b, '_damage', wraps=b._damage) as damage:
                _, lines, _, _, applied = finish_visual(b, Mock())
            self.assertEqual(damage.call_count, count, sid)
            self.assertEqual(applied, 1)
            self.assertEqual(sum(' -' in line for line in lines), count)

    def test_all_target_duration_identical_one_and_four_targets(self):
        for sid in ('cleaving_storm', 'inferno', 'armor_wave', 'focus_field', 'purify_wind'):
            results = []
            for count in (1, 4):
                b = make_battle(sid, targets=count)
                if b.skills[sid].target == 'all_allies' and count == 1:
                    for actor in b.party[1:]:
                        actor.hp = 0
                    b.party[0].statuses = {'poison': 3}
                _, _, phases, frames, _ = finish_visual(b)
                results.append((phases, frames))
                self.assertEqual(b.party[0].skill_uses[sid], b.skills[sid].max_uses - 1)
                self.assertEqual(b.party[0].used_skills[sid], 1)
                self.assertEqual(b.party[0].growth_points, b.skills[sid].growth)
                self.assertEqual(b.party[0].cooldowns.get(sid, 0), b.skills[sid].cooldown)
            # Poison tick adds an existing party recoil, independent of RARE FX.
            self.assertEqual(results[0][1]['rare_cast'], results[1][1]['rare_cast'])
            self.assertEqual(results[0][1]['rare_effect'], results[1][1]['rare_effect'])
            self.assertEqual(results[0][1]['rare_feedback'], results[1][1]['rare_feedback'])

    def test_all_target_blits_share_one_frame_and_are_bounded(self):
        for sid in ('cleaving_storm', 'inferno', 'armor_wave', 'focus_field', 'purify_wind'):
            b = make_battle(sid)
            visual = BattlePresentation(b)
            self.assertTrue(visual.start())
            visual.enter('rare_effect')
            surface = Mock()
            visual.draw_effect(surface)
            draws = [c for c in surface.blt.call_args_list if c.args[2] == RARE_ASSET_BANK]
            self.assertEqual(len(draws), 4, sid)
            self.assertLessEqual(surface.blt.call_count, 12)

    def test_fire_lightning_identity_with_common_magic_rune(self):
        for sid, effect in (('flare', 'fire'), ('inferno', 'fire'), ('thunder_bind', 'lightning')):
            b = make_battle(sid)
            visual = BattlePresentation(b); visual.start(); visual.enter('rare_effect')
            surface = Mock(); visual.draw_effect(surface)
            self.assertTrue(any(c.args[2:5] == (2, *EFFECT_SPRITES[effect])
                                for c in surface.blt.call_args_list), sid)
            self.assertEqual(visual.presentation_id, 'rare_magic')

    def test_support_up_and_down_share_asset_with_opposite_direction(self):
        for sid in ('focus', 'focus_field', 'armor_break', 'armor_wave'):
            visual = BattlePresentation(make_battle(sid)); visual.start(); visual.enter('rare_effect')
            visual.frame = 4
            surface = Mock(); visual.draw_effect(surface)
            self.assertTrue(surface.blt.called)
            height = surface.blt.call_args_list[0].args[6]
            self.assertEqual(height, -32 if sid.startswith('armor') else 32)

    def test_damage_then_successful_status_feedback_for_all_four_skills(self):
        for sid, status in (('plague_edge', 'poison'), ('thunder_bind', 'paralyze'),
                            ('nightmare', 'sleep'), ('chaos_spell', 'confusion')):
            b = make_battle(sid)
            with patch.object(b.rng, 'random', return_value=0):
                _, lines, phases, _, _ = finish_visual(b)
            self.assertIn(status, b.enemies[0].statuses)
            self.assertLess(phases.index('rare_effect'), phases.index('rare_feedback'))
            self.assertLess(phases.index('rare_feedback'), phases.index('status_effect'))
            self.assertTrue(any(' -' in line for line in lines))

    def test_failed_status_keeps_damage_and_rare_attack_without_status_feedback(self):
        for sid in ('plague_edge', 'thunder_bind', 'nightmare', 'chaos_spell'):
            b = make_battle(sid)
            with patch.object(b.rng, 'random', return_value=.999):
                _, lines, phases, _, _ = finish_visual(b)
            self.assertFalse(b.enemies[0].statuses)
            self.assertNotIn('status_effect', phases)
            self.assertIn('rare_feedback', phases)
            self.assertTrue(any(' -' in line for line in lines))

    def test_damage_ko_never_applies_status_or_status_feedback(self):
        for sid in ('plague_edge', 'thunder_bind', 'nightmare', 'chaos_spell'):
            b = make_battle(sid, targets=1); b.enemies[0].hp = 1
            with patch.object(b.rng, 'random', return_value=0):
                _, _, phases, _, _ = finish_visual(b)
            self.assertEqual(b.outcome, 'VICTORY')
            self.assertFalse(b.enemies[0].statuses)
            self.assertNotIn('status_effect', phases)
            self.assertIn('enemy_death', phases)

    def test_cures_dont_heal_and_feedback_only_for_removed_statuses(self):
        for sid, expected in (('cure', {1}), ('purify_wind', {1, 2})):
            b = make_battle(sid); hp = [c.hp for c in b.party]
            _, _, phases, _, _ = finish_visual(b)
            self.assertEqual([c.hp for c in b.party], hp)
            self.assertIn('status_effect', phases)
            self.assertEqual({e['target'][1] for e in b.status_visual_events}, expected)
            self.assertTrue(all(e['kind'] == 'cure' for e in b.status_visual_events))

    def test_heal_renew_revive_and_drain_keep_original_hp_rules(self):
        for sid in ('heal', 'renew', 'revive', 'drain'):
            b = make_battle(sid)
            before = [c.hp for c in b.party]
            finish_visual(b)
            if sid == 'revive':
                self.assertEqual(b.party[1].hp, 250)
                self.assertFalse(b.party[1].statuses)
            elif sid in ('heal', 'renew'):
                self.assertEqual(b.party[1].hp, min(1000, before[1] + b.skills[sid].power(b.party[0])))
            else:
                dealt = 5000 - b.enemies[0].hp
                self.assertEqual(b.party[0].hp, min(1000, before[0] + dealt // 2))

    def test_support_modifier_duration_and_refresh_not_stack(self):
        for sid in ('armor_break', 'armor_wave', 'focus', 'focus_field'):
            b = make_battle(sid)
            skill = b.skills[sid]
            group = b.party if skill.target in ('ally', 'all_allies') else b.enemies
            for unit in group:
                unit.effects[skill.effect] = (skill.modifier, 1)
            # Retain another actor in the queue to observe duration before round-end.
            b.queue.append(('party', Action(2, 'GUARD')))
            finish_visual(b)
            indices = range(4) if skill.target.startswith('all_') else (1 if skill.target == 'ally' else 0,)
            for i in indices:
                self.assertEqual(group[i].effects[skill.effect], (skill.modifier, skill.duration))

    def test_impact_shake_and_target_flash_are_small_and_bounded(self):
        visual = BattlePresentation(make_battle('heavy_break')); visual.start()
        visual.enter('rare_effect'); visual.frame = 3
        self.assertTrue(visual.target_flashing('enemy', 0))
        self.assertFalse(visual.target_flashing('enemy', 1))
        visual.frame = 5
        self.assertFalse(visual.target_flashing('enemy', 0))
        visual.enter('rare_feedback')
        shakes = []
        for _ in range(3):
            shakes.append(visual.shake_offset()); visual.advance()
        self.assertEqual(shakes, [(1, 0), (-1, 0), (0, 1)])
        self.assertEqual(visual.shake_offset(), (0, 0))

    def test_wall_timeout_applies_once_and_releases_all_new_phases(self):
        for sid in MAPPING:
            b = make_battle(sid); visual = BattlePresentation(b); visual.start()
            applied, ticks = 0, 0
            while visual.active:
                visual.started_at = time.monotonic() - MAX_PRESENTATION_SECONDS - 1
                event = visual.advance(); ticks += 1
                if event == 'apply':
                    alive = [e.alive for e in b.enemies]; hp = [c.hp for c in b.party]
                    b.step(); applied += 1; visual.after_action(alive, hp)
                self.assertLess(ticks, 9)
            self.assertEqual(applied, 1, sid)

    def test_other_rarities_use_legacy_frames_and_sprites(self):
        skills = load_content()[1]
        for sid, skill in skills.items():
            if skill.rarity in ('RARE', 'LEGEND') or skill.effect == 'return':
                continue
            b = make_battle(sid)
            visual = BattlePresentation(b)
            if visual.start():
                for _ in range(4): visual.advance()
                self.assertEqual(visual.phase, 'skill_effect', sid)
                self.assertIsNone(visual.presentation_id)


class RareAssetTests(unittest.TestCase):
    def test_assets_only_fill_empty_cells_maps_audio_and_existing_art_match(self):
        from tests.balance_preservation import use_current_asset_baseline
        if use_current_asset_baseline(self): return
        if sys.platform == 'emscripten':
            return  # Exact pixel/native hashes and shipped payload audited on PC.
        import pyxel
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True); pyxel._tests_initialized = True
        pyxel.load(str(ROOT / 'game.pyxres'))
        before = json.loads(BEFORE.read_text(encoding='utf8'))
        for bank, image in enumerate(pyxel.images):
            pixels = [image.pget(x, y) for y in range(256) for x in range(256)]
            if bank == 0:
                # The later LEGEND pass only adds art to this formerly blank region.
                # Its own pre-pass pixel audit preserves every existing RARE pixel.
                for y in range(128, 256):
                    for x in range(192):
                        pixels[y * 256 + x] = 0
            if bank == RARE_ASSET_BANK:
                for y in range(96, 192):
                    for x in range(192):
                        self.assertIn(pixels[y * 256 + x], range(4))
                        pixels[y * 256 + x] = 0
                for u, v in RARE_SPRITES.values():
                    for frame in range(3):
                        self.assertTrue(any(image.pget(x, y) for y in range(v, v + 32)
                                            for x in range(u + frame * 32, u + frame * 32 + 32)))
            self.assertEqual(hashlib.sha256(bytes(pixels)).hexdigest(), before['image_hashes'][bank])
        def digest(value):
            return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest([(tm.imgsrc, [[tm.pget(x, y) for x in range(256)]
                                              for y in range(256)]) for tm in pyxel.tilemaps]), before['map_hash'])
        # Subsequent AUDIO PASS audits its added audio separately; old art/maps
        # and all twenty RARE drawing/timer traces remain protected.

    def test_all_protected_code_data_resources_and_native_audio_unchanged(self):
        if sys.platform == 'emscripten':
            return
        before = json.loads(BEFORE.read_text(encoding='utf8'))
        allowed = {'rpg/models.py', 'rpg/content.py', 'rpg/app.py', 'rpg/battle_presentation.py',
                   'data/skills.json', 'game.pyxres', 'rpg/sound.py', 'rpg/dungeon_app.py'}
        from tests.test_enemy_balance import ALLOWED
        allowed |= ALLOWED
        for name, digest in before['hashes'].items():
            if 'save' in name.split('/'):
                continue  # Player progress is mutable; audit save.py/schema separately.
            if name not in allowed:
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)


class RareUITests(unittest.TestCase):
    def setUp(self):
        import pyxel
        from rpg.dungeon_app import DungeonApp
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True); pyxel._tests_initialized = True
        with patch.object(pyxel, 'init'):
            self.app = DungeonApp(Session(*load_content(), seed=711), run=False,
                                  headless=True, start_at_title=False)
        self.app.begin_encounter()
        self.app.confirm = self.app.confirm_held = lambda: True
        self.app.cancel = lambda: True
        self.app.direction = lambda horizontal=False: 1
        self.app.pressed = lambda *args: False

    def configure(self, b):
        a = self.app
        a.battle = a.session.battle = b
        a.session.party, a.session.skills, a.session.inventory = b.party, b.skills, b.inventory
        a.session.settled = False
        a.battle_presentation = None
        a.state, a.delay = 'resolve', 0
        a.pending = deque(); a.log = []
        a.overlay = None
        a.battle_input_blocked = False
        a.opening_input_blocked = False
        a.session.settings['spark_chance'] = 0
        a.session.discovered_skills.update(sid for actor in b.party for sid in actor.skills)

    def animate(self):
        a = self.app
        a.update(); a.draw()
        frames = Counter()
        for _ in range(80):
            if not a.battle_visual().active:
                return frames
            frames[a.battle_visual().phase] += 1
            a.update(); a.draw()
        self.fail('RARE visual stalled')

    def test_all_twenty_real_draws_spam_minimum_frames_and_one_execution(self):
        for sid in MAPPING:
            b = make_battle(sid); self.configure(b)
            with patch.object(b, 'step', wraps=b.step) as step:
                frames = self.animate()
            self.assertEqual(step.call_count, 1, sid)
            self.assertEqual(frames['rare_effect'], RARE_EFFECT_FRAMES)
            self.assertFalse(self.app.battle_visual().active)
            self.assertEqual(self.app.state, 'resolve')

    def test_normal_stopped_and_failed_audio_do_not_gate_rare_progress(self):
        import pyxel
        from contextlib import ExitStack
        for mode in ('normal', 'stopped', 'failed'):
            for sid in ('heavy_break', 'inferno', 'purify_wind', 'chaos_spell'):
                with self.subTest(mode=mode, skill=sid), ExitStack() as stack:
                    if mode != 'normal':
                        for api in ('play', 'playm', 'play_pos'):
                            stack.enter_context(patch.object(pyxel, api,
                                **({'side_effect': RuntimeError('unavailable audio')} if mode == 'failed'
                                   else {'return_value': None})))
                    self.configure(make_battle(sid))
                    frames = self.animate()
                    self.assertEqual(frames['rare_effect'], RARE_EFFECT_FRAMES)
                    self.assertFalse(self.app.battle_visual().active)

    def test_command_and_victory_progress_after_rare_visual(self):
        self.configure(make_battle('heavy_break'))
        self.animate()
        for _ in range(40):
            self.app.update()
            if self.app.state == 'command': break
        self.assertEqual(self.app.state, 'command')
        b = make_battle('heavy_break', targets=1); b.enemies[0].hp = 1
        self.configure(b); self.animate()
        for _ in range(40):
            self.app.update()
            if self.app.state == 'result': break
        self.assertEqual(self.app.state, 'result')
        self.assertTrue(self.app.session.settled)

    def test_save_has_no_static_presentation_data_and_old_save_roundtrip(self):
        from rpg.save import make_save_data, apply_save_data
        self.app.enter_camp()
        for sid in ('inferno', 'purify_wind'):
            self.app.session.party[0].learn(self.app.session.skills[sid])
            self.app.session.discovered_skills.add(sid)
        saved = make_save_data(self.app)
        self.assertNotIn('presentation', json.dumps(saved))
        self.assertEqual(saved['save_version'], 1)
        apply_save_data(self.app, saved)
        self.assertEqual(make_save_data(self.app), saved)

    def test_repeated_all_target_battles_release_visual_targets_and_objects(self):
        import gc
        import weakref
        visuals = weakref.WeakSet()
        for _ in range(20):
            for sid in ('inferno', 'cleaving_storm', 'purify_wind', 'armor_wave', 'focus_field'):
                self.configure(make_battle(sid))
                visual = self.app.battle_visual(); visuals.add(visual)
                self.animate()
                self.assertFalse(visual.active or visual.skill_effect_targets
                                 or visual.status_events or visual.rare_hp_changes or visual.rare_hp_before)
            gc.collect()
            self.assertLessEqual(len(visuals), 1)


if __name__ == '__main__':
    unittest.main()
