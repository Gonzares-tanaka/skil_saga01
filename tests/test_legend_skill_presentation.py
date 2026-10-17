"""Eight dedicated LEGEND visuals; model parity, exact RARE preservation, safety."""
from collections import Counter, deque
from dataclasses import replace
import hashlib
import json
import sys
import time
import unittest
from unittest.mock import Mock, patch
from rpg.content import ROOT, load_content, validate_skill

# Also works when the source is injected as a fixture in the actual Pyodide FS.
sys.path.insert(0, str(ROOT / 'tests'))
from test_rare_skill_presentation import make_battle, finish_visual, rule_state
import test_rare_skill_presentation as rare_cases
from legend_presentation_helpers import rare_trace
from rpg.models import Action, Skill
from rpg.battle_presentation import BattlePresentation, MAX_PRESENTATION_SECONDS
from rpg.legend_skill_presentation import (LEGEND_PRESENTATION_IDS, LEGEND_SPRITES,
    LEGEND_MAIN_FRAMES, LEGEND_CHARGE_FRAMES, LEGEND_RESULT_FRAMES,
    LEGEND_AFTERGLOW_FRAMES, legend_presentation_id)

IDS = ('seven_slash', 'meteor', 'full_heal', 'ragnarok', 'starfall', 'miracle', 'sanctuary', 'time_stop')
MAPPING = {sid: 'legend_' + sid for sid in IDS}
BEFORE = ROOT / 'tests/fixtures/legend_presentation_before.json'


class LegendPresentationTests(unittest.TestCase):
    def test_exact_eight_dedicated_ids_and_sixty_two_roster(self):
        skills = load_content()[1]
        self.assertEqual(Counter(s.rarity for s in skills.values()),
                         {'BASIC': 3, 'COMMON': 18, 'UNCOMMON': 13, 'RARE': 20, 'LEGEND': 8})
        self.assertEqual({s.id: s.presentation_id for s in skills.values() if s.rarity == 'LEGEND'}, MAPPING)
        self.assertEqual(set(LEGEND_PRESENTATION_IDS), set(MAPPING.values()))
        for skill in skills.values():
            self.assertEqual(legend_presentation_id(skill), MAPPING.get(skill.id))

    def test_all_data_except_eight_optional_ids_identical_including_rare(self):
        before = json.loads(BEFORE.read_text(encoding='utf8'))['skills']
        now = json.loads((ROOT / 'data/skills.json').read_text(encoding='utf8'))
        self.assertEqual([{k: v for k, v in r.items() if k != 'presentation_id' or r['rarity'] != 'LEGEND'}
                          for r in now], before)

    def test_validation_and_missing_or_invalid_ids_safe_fallback(self):
        skill = load_content()[1]['meteor']
        validate_skill(replace(skill, presentation_id=None))
        for changes in (dict(presentation_id='legend_missing'), dict(presentation_id={}),
                        dict(rarity='RARE'), dict(rarity='COMMON'), dict(rarity='BASIC')):
            with self.assertRaises(ValueError): validate_skill(replace(skill, **changes))
        for value in (None, '', {}, 'legend_missing'):
            self.assertIsNone(legend_presentation_id(replace(skill, presentation_id=value)))
        b = make_battle('meteor', skills={r['id']: Skill(**r) for r in json.loads(BEFORE.read_text(encoding='utf8'))['skills']})
        v = BattlePresentation(b); self.assertTrue(v.start())
        for _ in range(4): v.advance()
        self.assertEqual(v.phase, 'skill_effect')

    def test_eight_skills_match_before_rules_rng_resources_mastery_160_cases(self):
        previous = {r['id']: Skill(**r) for r in json.loads(BEFORE.read_text(encoding='utf8'))['skills']}
        for sid in IDS:
            for seed in (1, 41, 99, 313, 501):
                for mode in ('normal', 'mastered', 'last_use', 'paralyze'):
                    with self.subTest(skill=sid, seed=seed, mode=mode):
                        before, now = make_battle(sid, seed, previous, mode=mode), make_battle(sid, seed, mode=mode)
                        expected = rule_state(before, before.step())
                        _, lines, _, _, applied = finish_visual(now)
                        self.assertEqual(applied, 1)
                        self.assertEqual(rule_state(now, lines), expected)

    def test_all_eight_render_charge_result_afterglow_and_reset(self):
        for sid in IDS:
            surface = Mock()
            visual, _, phases, frames, applied = finish_visual(make_battle(sid), surface)
            self.assertEqual(applied, 1)
            self.assertEqual(phases[:5], ['actor_step', 'legend_charge', 'legend_main',
                                          'legend_result', 'legend_afterglow'])
            self.assertEqual(frames['legend_charge'], LEGEND_CHARGE_FRAMES)
            self.assertEqual(frames['legend_main'], LEGEND_MAIN_FRAMES[MAPPING[sid]])
            self.assertEqual(frames['legend_result'], LEGEND_RESULT_FRAMES)
            self.assertEqual(frames['legend_afterglow'], LEGEND_AFTERGLOW_FRAMES)
            self.assertFalse(visual.legend.id or visual.legend.targets or visual.legend.hp_changes or visual.legend.hp_before)
            self.assertTrue(surface.blt.called)

    def test_seven_visible_strokes_but_single_damage_defense_and_number(self):
        b = make_battle('seven_slash')
        visual = BattlePresentation(b); visual.start(); visual.enter('legend_main')
        draws = []
        for tick in range(14):
            visual.frame = tick; surface = Mock(); visual.draw_effect(surface)
            draws.append(surface.blt.call_args_list[0].args)
        self.assertEqual(len(draws[::2]), 7)
        self.assertGreater(len(set(draws[:12])), 1)
        self.assertNotEqual(draws[0][3], draws[12][3])
        b = make_battle('seven_slash')
        with patch.object(b, '_damage', wraps=b._damage) as damage:
            _, lines, _, _, _ = finish_visual(b)
        self.assertEqual(damage.call_count, 1)
        self.assertEqual(sum(' -' in line for line in lines), 1)

    def test_meteor_falls_from_above_then_impact_and_two_pixel_shake(self):
        visual = BattlePresentation(make_battle('meteor')); visual.start(); visual.enter('legend_main')
        positions = []
        for tick in range(8):
            visual.frame = tick; surface = Mock(); visual.draw_effect(surface)
            positions.append(surface.blt.call_args.args[1])
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[0], 11)
        visual.frame = 8; surface = Mock(); visual.draw_effect(surface)
        self.assertEqual(surface.blt.call_args.args[3], LEGEND_SPRITES['legend_meteor'][0] + 32)
        visual.enter('legend_result')
        self.assertEqual(visual.shake_offset(), (2, 0))
        visual.frame = 3; self.assertEqual(visual.shake_offset(), (0, 0))

    def test_full_heal_matches_formula_and_never_cures_status(self):
        b = make_battle('full_heal'); target = b.party[1]
        target.statuses = {'poison': 2, 'paralyze': 3}
        before = target.hp
        finish_visual(b)
        self.assertEqual(target.hp, min(target.max_hp, before + b.skills['full_heal'].power(b.party[0])))
        self.assertEqual(target.statuses, {'poison': 2, 'paralyze': 3})

    def test_ragnarok_and_starfall_damage_once_per_target_resources_once(self):
        for sid in ('ragnarok', 'starfall'):
            b = make_battle(sid)
            with patch.object(b, '_damage', wraps=b._damage) as damage:
                finish_visual(b)
            self.assertEqual(damage.call_count, 4)
            self.assertEqual(b.party[0].used_skills, {sid: 1})
            self.assertEqual(b.party[0].growth_points, b.skills[sid].growth)
            self.assertTrue(all(enemy.hp < 5000 for enemy in b.enemies))

    def test_starfall_has_four_fixed_projectiles_independent_of_target_count(self):
        for count in (1, 4):
            visual = BattlePresentation(make_battle('starfall', targets=count)); visual.start(); visual.enter('legend_main')
            surface = Mock(); visual.draw_effect(surface)
            self.assertEqual(surface.blt.call_count, 4)
            self.assertTrue(all(call.args[5:7] == (16, 16) for call in surface.blt.call_args_list))

    def test_all_target_main_time_identical_with_one_two_three_four_targets(self):
        for sid in ('ragnarok', 'starfall', 'miracle', 'sanctuary', 'time_stop'):
            counts = []
            for count in (1, 2, 3, 4):
                b = make_battle(sid, targets=count)
                if b.skills[sid].target == 'all_allies':
                    for actor in b.party[count:]: actor.hp = 0
                _, _, _, frames, _ = finish_visual(b)
                counts.append(tuple(frames[p] for p in ('legend_charge', 'legend_main', 'legend_result', 'legend_afterglow')))
            self.assertEqual(len(set(counts)), 1, sid)

    def test_miracle_simultaneous_living_heal_no_revival_or_cure(self):
        b = make_battle('miracle'); b.party[2].hp = 0; b.party[1].statuses = {'sleep': 2}
        before = [c.hp for c in b.party]
        visual = BattlePresentation(b); visual.start(); visual.enter('legend_main')
        self.assertEqual(visual.legend.targets, (('party', 0), ('party', 1), ('party', 3)))
        surface = Mock(); visual.draw_effect(surface); self.assertEqual(surface.blt.call_count, 6)
        finish_visual(b)
        power = b.skills['miracle'].power(b.party[0])
        self.assertEqual([c.hp for c in b.party], [min(1000, before[i] + power) if i != 2 else 0 for i in range(4)])
        self.assertEqual(b.party[1].statuses, {'sleep': 2})

    def test_sanctuary_preserves_point_fifty_five_guard_family_and_no_residual_art(self):
        b = make_battle('sanctuary')
        for actor in b.party: actor.effects['guard_up'] = (.8, 1)
        b.queue.append(('party', Action(1, 'GUARD')))
        visual, _, _, _, _ = finish_visual(b)
        for actor in b.party:
            self.assertEqual(actor.effects['guard_up'], (.55, b.skills['sanctuary'].duration))
        self.assertEqual(b._damage(b.party[1], 100), 55)
        surface = Mock(); visual.draw_effect(surface); surface.blt.assert_not_called()

    def test_time_stop_success_failure_resistance_immunity_control_exclusion(self):
        b = make_battle('time_stop')
        b.enemies[1].status_resistances = {'sleep': 50}
        b.enemies[2].status_immunities = ('sleep',)
        b.enemies[3].statuses = {'paralyze': 3}
        with patch.object(b.rng, 'random', side_effect=[.69, .36]) as rolls:
            _, _, phases, _, applied = finish_visual(b)
        self.assertEqual(rolls.call_count, 2)
        self.assertEqual(applied, 1)
        self.assertEqual([e.statuses for e in b.enemies], [{'sleep': 2}, {}, {}, {'paralyze': 3}])
        self.assertEqual([e['target'] for e in b.status_visual_events], [('enemy', 0)])
        self.assertLess(phases.index('legend_afterglow'), phases.index('status_effect'))
        self.assertEqual(b.party[0].used_skills['time_stop'], 1)
        self.assertNotIn('time_stop', b.party[0].skills)

    def test_time_stop_failed_sleep_still_displays_legend_without_feedback(self):
        b = make_battle('time_stop')
        with patch.object(b.rng, 'random', return_value=.7):
            _, _, phases, _, _ = finish_visual(b)
        self.assertTrue(all(not e.statuses for e in b.enemies))
        self.assertNotIn('status_effect', phases)
        self.assertIn('legend_main', phases)

    def test_time_stop_hands_hold_but_frame_timer_and_update_continue(self):
        b = make_battle('time_stop'); visual = BattlePresentation(b); visual.start(); visual.enter('legend_main')
        refs = []
        for tick in range(12):
            visual.frame = tick; surface = Mock(); visual.draw_effect(surface)
            refs.append(surface.blt.call_args_list[0].args[3:5])
        self.assertNotEqual(refs[0], refs[4])
        self.assertEqual(len(set(refs[4:])), 1)
        self.assertEqual(visual.frame, 11)

    def test_single_short_flash_and_name_only_in_charge_main(self):
        for sid in IDS:
            v = BattlePresentation(make_battle(sid)); v.start(); v.enter('legend_main')
            flashes = [tick for tick in range(LEGEND_MAIN_FRAMES[MAPPING[sid]])
                       if v.legend.flashing('legend_main', tick, *v.legend.targets[0])]
            self.assertLessEqual(len(flashes), 2)
            if flashes: self.assertEqual(flashes[-1] - flashes[0], 1)
            surface = Mock(); v.legend.draw_name(surface, 'legend_main'); self.assertTrue(surface.rectb.called)
            surface = Mock(); v.legend.draw_name(surface, 'actor_return'); surface.rectb.assert_not_called()

    def test_wall_timeouts_resolve_once_without_animation_completion_or_audio(self):
        for sid in IDS:
            b = make_battle(sid); v = BattlePresentation(b); v.start(); ticks = applied = 0
            while v.active:
                v.started_at = time.monotonic() - MAX_PRESENTATION_SECONDS - 1
                event = v.advance(); ticks += 1
                if event == 'apply':
                    alive = [e.alive for e in b.enemies]; hp = [c.hp for c in b.party]
                    b.step(); applied += 1; v.after_action(alive, hp)
                self.assertLess(ticks, 10)
            self.assertEqual(applied, 1)

    def test_all_twenty_rare_draw_timing_traces_identical(self):
        before = json.loads(BEFORE.read_text(encoding='utf8'))
        for sid, digest in before['rare_traces'].items():
            self.assertEqual(rare_trace(make_battle(sid)), digest, sid)


class LegendAssetTests(unittest.TestCase):
    def test_all_old_pixels_maps_audio_including_rare_unchanged(self):
        if sys.platform == 'emscripten': return
        from tests.balance_preservation import use_current_asset_baseline
        if use_current_asset_baseline(self): return
        import pyxel
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True); pyxel._tests_initialized = True
        pyxel.load(str(ROOT / 'game.pyxres'))
        before = json.loads(BEFORE.read_text(encoding='utf8'))
        for bank, image in enumerate(pyxel.images):
            pixels = [image.pget(x, y) for y in range(256) for x in range(256)]
            if bank == 0:
                for y in range(128, 256):
                    for x in range(192):
                        self.assertIn(pixels[y * 256 + x], range(4)); pixels[y * 256 + x] = 0
                for u, v in LEGEND_SPRITES.values():
                    for frame in range(3):
                        self.assertTrue(any(image.pget(x, y) for y in range(v, v + 32)
                                            for x in range(u + frame * 32, u + frame * 32 + 32)))
            self.assertEqual(hashlib.sha256(bytes(pixels)).hexdigest(), before['image_hashes'][bank])
        def digest(value): return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest([(tm.imgsrc, [[tm.pget(x, y) for x in range(256)] for y in range(256)])
                                 for tm in pyxel.tilemaps]), before['map_hash'])
        # AUDIO PASS adds only previously empty game audio; its dedicated audit
        # retains the existing battle score and every image/map/visual trace.

    def test_protected_rules_save_spark_rare_module_and_audio_identical(self):
        if sys.platform == 'emscripten': return
        before = json.loads(BEFORE.read_text(encoding='utf8'))
        allowed = {'rpg/content.py', 'rpg/app.py', 'rpg/battle_presentation.py', 'data/skills.json', 'game.pyxres',
                   'rpg/sound.py', 'rpg/dungeon_app.py'}  # Subsequent AUDIO PASS hooks.
        from tests.test_enemy_balance import ALLOWED
        allowed |= ALLOWED
        for name, digest in before['hashes'].items():
            if 'save' in name.split('/'):
                continue  # Do not treat the user's live progress as a static asset.
            if name not in allowed:
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)


class LegendUITests(rare_cases.RareUITests):
    # Reuse the established real-App helpers, without inheriting its RARE cases.
    test_all_twenty_real_draws_spam_minimum_frames_and_one_execution = None
    test_normal_stopped_and_failed_audio_do_not_gate_rare_progress = None
    test_command_and_victory_progress_after_rare_visual = None
    test_save_has_no_static_presentation_data_and_old_save_roundtrip = None
    test_repeated_all_target_battles_release_visual_targets_and_objects = None

    def test_all_eight_real_updates_fast_input_exactly_once_and_minimum_frames(self):
        for sid in IDS:
            b = make_battle(sid); self.configure(b)
            with patch.object(b, 'step', wraps=b.step) as step:
                frames = self.animate()
            self.assertEqual(step.call_count, 1)
            self.assertEqual(frames['legend_main'], LEGEND_MAIN_FRAMES[MAPPING[sid]])
            self.assertFalse(self.app.battle_visual().active)

    def test_normal_stopped_failed_audio_advance_all_eight(self):
        import pyxel
        from contextlib import ExitStack
        for mode in ('normal', 'stopped', 'failed'):
            for sid in IDS:
                with ExitStack() as stack:
                    if mode != 'normal':
                        for api in ('play', 'playm', 'play_pos'):
                            stack.enter_context(patch.object(pyxel, api,
                                **({'side_effect': RuntimeError('unavailable')} if mode == 'failed' else {'return_value': None})))
                    self.configure(make_battle(sid)); self.animate()
                    self.assertFalse(self.app.battle_visual().active)

    def test_time_stop_update_and_input_observer_run_every_frame_then_command(self):
        self.configure(make_battle('time_stop'))
        with patch.object(self.app.keyboard, 'update', wraps=self.app.keyboard.update) as keyboard:
            frames = self.animate()
        self.assertGreaterEqual(keyboard.call_count, sum(frames.values()))
        for _ in range(60):
            self.app.update()
            if self.app.state == 'command': break
        self.assertEqual(self.app.state, 'command')

    def test_victory_after_seven_slash_and_existing_save_schema(self):
        from rpg.save import make_save_data, apply_save_data
        b = make_battle('seven_slash', targets=1); b.enemies[0].hp = 1
        self.configure(b); self.animate()
        for _ in range(60):
            self.app.update()
            if self.app.state == 'result': break
        self.assertEqual(self.app.state, 'result')
        self.app.enter_camp(); saved = make_save_data(self.app)
        self.assertEqual(saved['save_version'], 1)
        self.assertNotIn('presentation', json.dumps(saved))
        apply_save_data(self.app, saved)
        self.assertEqual(make_save_data(self.app), saved)

    def test_repeated_legend_battles_release_child_objects_and_target_data(self):
        import gc, weakref
        visuals, children = weakref.WeakSet(), weakref.WeakSet()
        for _ in range(10):
            for sid in IDS:
                self.configure(make_battle(sid))
                visual = self.app.battle_visual(); child = visual.legend
                visuals.add(visual); children.add(child)
                self.animate()
                self.assertFalse(child.id or child.name or child.targets or child.hp_before or child.hp_changes)
            gc.collect()
            self.assertLessEqual(len(visuals), 1); self.assertLessEqual(len(children), 1)


if __name__ == '__main__': unittest.main()
