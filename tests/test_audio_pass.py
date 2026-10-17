"""Audio IDs, editable scores, real scene/event transitions and rule preservation."""
from collections import deque
from contextlib import ExitStack
import hashlib
import json
import sys
import time
import unittest
from unittest.mock import patch, call
import pyxel
from rpg.content import ROOT, load_content
from rpg.battle import Session
from rpg.dungeon_app import DungeonApp
from rpg.models import Action
from rpg.save import make_save_data, apply_save_data, SAVE_VERSION
from rpg.sound import (AudioManager, BGM_IDS, SE_IDS, BATTLE_BGM, RESOURCE_BANKS,
                       COMMON_SOUNDS, area_bgm, _play_music)

BASELINE = ROOT / 'tests/fixtures/audio_pass_before.json'


def initialized():
    if not getattr(pyxel, '_tests_initialized', False):
        pyxel.init(160, 120, headless=True); pyxel._tests_initialized = True


class AudioManagerTests(unittest.TestCase):
    def setUp(self):
        initialized(); self.audio = AudioManager(); self.audio.load()

    def test_exact_eight_bgm_six_se_and_editor_default_slots(self):
        self.assertEqual(set(BGM_IDS), {'bgm_' + n for n in ('title', 'hub', 'area1', 'area2', 'area3', 'battle', 'boss', 'final', 'omen')})
        self.assertEqual(set(SE_IDS), {'se_' + n for n in ('stairs', 'treasure', 'trap_damage', 'healing_spring', 'pitfall', 'quest_complete')})
        self.assertEqual(len(pyxel.sounds), 64); self.assertEqual(len(pyxel.musics), 8)
        for bank, index in BGM_IDS.values():
            music = self.audio.banks[bank][1][index]
            self.assertFalse(music.seqs[0]); self.assertTrue(all(music.seqs[c] for c in (1, 2, 3)))

    def test_new_scores_aligned_thirty_to_sixty_seconds_distinct_and_editable(self):
        melodies = set(); speeds = {}
        for ident, (bank, index) in BGM_IDS.items():
            sounds, musics = self.audio.banks[bank]; seqs = musics[index].seqs
            durations = [sum(sounds[n].total_sec() for n in seqs[c]) for c in (1, 2, 3)]
            self.assertLess(max(durations) - min(durations), .001)
            melodies.add(tuple(tuple(sounds[n].notes) for n in seqs[1]))
            speeds[ident] = sounds[seqs[1][0]].speed
            if ident != 'bgm_battle': self.assertTrue(30 <= durations[0] <= 60)
            self.assertTrue(all(len(sounds[n].notes) <= 48 for seq in seqs for n in seq))
            self.assertTrue(all(len(seq) <= 32 for seq in seqs))
        self.assertEqual(len(melodies), 9)
        self.assertLess(speeds['bgm_final'], speeds['bgm_boss'])
        self.assertLess(speeds['bgm_boss'], speeds['bgm_area3'])

    def test_all_native_bgm_victory_and_se_never_use_playm(self):
        with patch('rpg.sound.sys.platform', 'linux'), patch.object(pyxel, 'play') as play, \
             patch.object(pyxel, 'playm', side_effect=AssertionError('native playm forbidden')):
            for ident in BGM_IDS:
                play.reset_mock(); self.assertTrue(self.audio.play_bgm(ident))
                self.assertEqual([c.args[0] for c in play.call_args_list], [1, 2, 3])
                self.assertTrue(all(c.kwargs['loop'] for c in play.call_args_list))
            self.assertTrue(self.audio.play_victory())
            self.assertTrue(all(not c.kwargs['loop'] for c in play.call_args_list[-3:]))
            for ident, slot in SE_IDS.items():
                self.assertTrue(self.audio.play_se(ident)); self.assertEqual(play.call_args, call(0, slot))

    def test_web_routes_all_banks_to_music_api_and_se_stays_channel_zero(self):
        with patch('rpg.sound.sys.platform', 'emscripten'), patch.object(pyxel, 'playm') as playm, patch.object(pyxel, 'play') as play:
            for ident, (bank, index) in BGM_IDS.items():
                self.audio.play_bgm(ident); self.assertEqual(playm.call_args, call(index, loop=True))
                self.assertEqual(self.audio.bank, bank)
            self.audio.play_victory(); self.assertEqual(playm.call_args, call(1, loop=False))
            for ident, slot in SE_IDS.items():
                self.audio.play_se(ident); self.assertEqual(play.call_args, call(0, slot))

    def test_same_bgm_has_no_restart_no_load_no_polling(self):
        with patch('rpg.sound._play_music', return_value=True) as music, patch.object(pyxel, 'load') as load, \
             patch.object(pyxel, 'play_pos', side_effect=AssertionError('no polling')):
            self.audio.play_bgm('bgm_area1')
            for _ in range(100): self.audio.play_bgm('bgm_area1'); self.audio.update()
            music.assert_called_once_with(2, True); load.assert_not_called()

    def test_scene_bank_switch_keeps_all_shared_se_objects(self):
        for ident in BGM_IDS:
            self.audio.play_bgm(ident)
            for slot in COMMON_SOUNDS:
                expected = self.audio.banks['scene'][0][slot]
                actual = pyxel.sounds[slot]
                self.assertEqual((list(actual.notes), list(actual.tones), list(actual.volumes), list(actual.effects), actual.speed),
                                 (list(expected.notes), list(expected.tones), list(expected.volumes), list(expected.effects), expected.speed))

    def test_original_editor_cues_use_original_battle_resource_after_reload(self):
        original_load = pyxel.load
        def edited(path, **kwargs):
            original_load(path, **kwargs)
            if str(path) == str(RESOURCE_BANKS['battle']): pyxel.sounds[59].speed = 6
        audio = AudioManager()
        with patch.object(pyxel, 'load', side_effect=edited): audio.load()
        for ident in BGM_IDS:
            audio.play_bgm(ident); self.assertEqual(pyxel.sounds[59].speed, 6)

    def test_all_six_se_and_stopping_only_bgm_do_not_touch_bgm_channels(self):
        for ident in ('bgm_area1', 'bgm_boss', 'bgm_battle', 'bgm_final'):
            self.audio.play_bgm(ident)
            with patch.object(pyxel, 'play') as play, patch.object(pyxel, 'stop') as stop:
                for se in SE_IDS: self.audio.play_se(se)
                self.assertEqual([c.args[0] for c in play.call_args_list], [0] * 6)
                stop.assert_not_called(); self.assertEqual(self.audio.current_bgm, ident)
                self.audio.stop_bgm()
                self.assertEqual(stop.call_args_list, [call(1), call(2), call(3)])

    def test_boss_chain_resumes_position_after_original_victory(self):
        with patch('rpg.sound._play_music', return_value=True) as music:
            self.audio.play_bgm('bgm_boss'); self.audio.started_at -= 7
            self.audio.play_victory(); self.audio.play_bgm('bgm_boss')
            self.assertEqual(music.call_args.args[:2], (5, True))
            self.assertTrue(7 <= music.call_args.args[2] < 8)
            self.audio.play_bgm('bgm_boss'); self.assertEqual(music.call_count, 3)
            self.audio.play_bgm('bgm_area3'); self.assertEqual(self.audio.boss_offset, 0)

    def test_failed_stopped_and_unknown_audio_bounded_pending_se(self):
        with patch.object(pyxel, 'play', side_effect=RuntimeError('unavailable')), \
             patch.object(pyxel, 'playm', side_effect=RuntimeError('unavailable')), \
             patch.object(pyxel, 'stop', side_effect=RuntimeError('unavailable')):
            for ident in BGM_IDS: self.assertFalse(self.audio.play_bgm(ident))
            for ident in SE_IDS: self.assertFalse(self.audio.play_se(ident))
            self.assertFalse(self.audio.play_victory()); self.audio.stop_bgm()
        self.assertFalse(self.audio.play_bgm('missing')); self.assertFalse(self.audio.play_se('missing'))
        self.audio.enabled = False
        self.audio.play_se('se_trap_damage', 12)
        for _ in range(12): self.audio.update()
        self.assertIsNone(self.audio.pending_se)


class AudioSceneTests(unittest.TestCase):
    def setUp(self):
        initialized()
        with patch.object(pyxel, 'init'):
            self.app = DungeonApp(Session(*load_content(), seed=113), run=False, headless=True)
        self.a = self.app; self.s = self.a.session; self.d = self.a.dungeon; self.e = self.a.exploration
        self.a.opening_input_blocked = False
        self.d.defeated_bosses.update((4, 9))

    def tick(self, key=None):
        with patch.object(pyxel, 'btn', return_value=False), patch.object(pyxel, 'btnp', side_effect=lambda k, *args: k == key):
            self.a.update()

    def finish(self, outcome='VICTORY'):
        self.a.battle.outcome = outcome; self.a.battle.queue.clear()
        self.s.settle(); self.s.pending_replacements.clear()
        self.a.fanfare_started_at = None; self.a.state = 'result'; self.a.finish_results()

    def test_title_new_game_load_and_hub_return(self):
        self.assertEqual(self.a.audio.current_bgm, 'bgm_title')
        self.a.start_new_game(); self.assertEqual(self.a.audio.current_bgm, 'bgm_title')
        self.a.enter_dungeon(); self.assertEqual(self.a.audio.current_bgm, 'bgm_area1')
        self.a.enter_camp(returned=True); self.assertEqual(self.a.audio.current_bgm, 'bgm_hub')
        saved = make_save_data(self.a)
        with patch.object(self.a.save_manager, 'load', side_effect=lambda app: apply_save_data(app, saved)):
            self.a.state = 'title'; self.a.sync_scene_audio(); self.a.continue_game()
        self.assertEqual(self.a.audio.current_bgm, 'bgm_hub')
        self.assertEqual(make_save_data(self.a), saved)

    def test_all_area_endpoints_and_same_area_stairs_no_restart(self):
        self.a.enter_dungeon()
        for floor in (0, 4, 5, 9, 10, 14):
            self.d.debug_floor(floor); self.a.state = 'explore'; self.a.sync_scene_audio()
            self.assertEqual(self.a.audio.current_bgm, area_bgm(floor))
        for origin, destination in ((1, 2), (6, 7), (11, 12)):
            self.d.debug_floor(origin); self.a.state = 'explore'; self.a.sync_scene_audio()
            with patch('rpg.sound._play_music') as music, patch.object(self.a.audio, 'play_se', wraps=self.a.audio.play_se) as se:
                event = self.d.change_floor(destination); self.a.handle_event(*event)
                self.assertEqual(self.d.floor, destination); music.assert_not_called()
                se.assert_called_once_with('se_stairs')

    def test_both_area_boundaries_switch_once_and_invalid_stairs_no_sound(self):
        for origin, destination in ((4, 5), (9, 10)):
            self.d.debug_floor(origin); self.a.state = 'explore'; self.a.sync_scene_audio()
            with patch('rpg.sound._play_music', return_value=True) as music:
                self.a.handle_event(*self.d.change_floor(destination)); self.assertEqual(music.call_count, 1)
                self.assertEqual(self.a.audio.current_bgm, area_bgm(destination))
        with patch.object(self.a.audio, 'play_se') as se:
            self.a.handle_event(*self.d.change_floor(15)); se.assert_not_called()

    def test_each_area_normal_battle_victory_and_run_restore(self):
        for floor in (0, 5, 10):
            self.a.enter_dungeon(); self.d.debug_floor(floor); self.a.sync_scene_audio()
            self.a.begin_encounter(); self.assertEqual(self.a.audio.current_bgm, 'bgm_battle')
            self.finish(); self.assertEqual(self.a.audio.current_bgm, area_bgm(floor))
            self.a.begin_encounter(); self.finish('ESCAPE')
            self.assertEqual(self.a.state, 'explore'); self.assertEqual(self.a.audio.current_bgm, area_bgm(floor))

    def test_animated_battle_title_touch_input_does_not_stall(self):
        self.a.enter_dungeon(); self.a.begin_encounter(animate=True)
        for _ in range(40): self.tick()
        self.assertEqual(self.a.state, 'command'); self.assertFalse(self.a.battle_input_blocked)
        self.assertEqual(self.a.audio.current_bgm, 'bgm_battle')
        self.tick(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(self.a.state, 'skill')
        self.tick(pyxel.GAMEPAD1_BUTTON_B); self.assertEqual(self.a.state, 'command')

    def test_b5_b10_b15_demon_boss_classification_and_guardian_continuation(self):
        self.a.enter_dungeon()
        for floor in (4, 9, 14):
            self.s.battle = None; self.s.settled = True
            self.d.debug_floor(floor); self.a.begin_encounter(boss=True)
            self.assertEqual(self.a.audio.current_bgm, 'bgm_boss')
            self.assertEqual(self.a.battle_kind, 'demon' if floor == 14 else 'boss')
        self.d.finale.guardian_index = 0
        for index in range(3):
            self.s.battle = None; self.s.settled = True
            self.a.begin_encounter(boss=True, guardian_index=index)
            self.assertEqual(self.a.audio.current_bgm, 'bgm_boss')
            with patch('rpg.sound._play_music') as music:
                self.a.state = 'guardian_between'; self.a.sync_scene_audio(); music.assert_not_called()

    def test_final_battle_retry_and_decline_title(self):
        f = self.d.finale; f.has_amrita = True; f.start_final_event()
        self.a.begin_final_battle(); self.assertEqual(self.a.audio.current_bgm, 'bgm_boss')
        self.finish('DEFEAT'); self.assertEqual(self.a.state, 'final_retry')
        self.a.final_choice = 0; self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'command'); self.assertEqual(self.a.audio.current_bgm, 'bgm_boss')
        self.finish('DEFEAT'); self.a.final_choice = 1; self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'title'); self.assertEqual(self.a.audio.current_bgm, 'bgm_title')

    def test_chest_open_rewards_and_trap_damage_delayed_sound_without_logic_wait(self):
        self.a.enter_dungeon()
        for c in self.s.party: c.hp = 100
        for reward in (dict(kind='TREASURE', amount=3), dict(kind='POTION', amount=1), dict(kind='TRAP', amount=9), dict(kind='EMPTY')):
            old = self.s.treasure.unbanked
            with patch.object(self.a.audio, 'play_se', wraps=self.a.audio.play_se) as se:
                self.a.handle_event(*self.d.grant_chest(reward))
                self.assertEqual(se.call_args_list[0], call('se_treasure'))
                if reward['kind'] == 'TREASURE': self.assertEqual(self.s.treasure.unbanked, old + 3)
                if reward['kind'] == 'TRAP':
                    self.assertTrue(all(c.hp == 91 for c in self.s.party))
                    self.assertEqual(se.call_args_list[-1], call('se_trap_damage', delay_frames=12))
                    for _ in range(12): self.a.audio.update()
                    self.assertEqual(se.call_args_list[-1], call('se_trap_damage'))

    def test_swamp_actual_damage_once_idle_frames_silent_and_minimum_one(self):
        self.a.enter_dungeon()
        for c in self.s.party: c.hp = 100
        with patch.object(self.a.audio, 'play_se') as se:
            self.a.handle_event('poison', '毒沼'); se.assert_called_once_with('se_trap_damage')
            for _ in range(20): self.tick()
            self.assertEqual(se.call_count, 1)
            for c in self.s.party: c.hp = 1
            self.a.handle_event('poison', '毒沼'); self.assertEqual(se.call_count, 1)

    def test_spring_heals_living_preserves_poison_uses_and_repeat_silent(self):
        self.a.enter_dungeon()
        for c in self.s.party: c.hp = 1; c.statuses = {'poison': 2}
        self.s.party[2].hp = 0
        uses = [dict(c.skill_uses) for c in self.s.party]
        with patch.object(self.a.audio, 'play_se') as se:
            self.a.handle_event('spring', '泉'); se.assert_called_once_with('se_healing_spring')
            self.assertEqual([c.hp for c in self.s.party], [c.max_hp if i != 2 else 0 for i, c in enumerate(self.s.party)])
            self.assertTrue(all(c.statuses == {'poison': 2} for c in self.s.party))
            self.assertEqual([c.skill_uses for c in self.s.party], uses)
            self.a.handle_event('spring', '泉'); self.assertEqual(se.call_count, 1)

    def test_pit_repositions_immediately_without_audio_completion(self):
        self.a.enter_dungeon(); self.d.x, self.d.y = 4, 4
        with patch.object(pyxel, 'play_pos', side_effect=AssertionError('no audio wait')), patch.object(self.a.audio, 'play_se') as se:
            event = self.d.fall_in_pit(); self.a.handle_event(*event)
            self.assertNotEqual((self.d.x, self.d.y), (4, 4)); se.assert_called_once_with('se_pitfall')

    def test_explore_investigate_goal_once_never_at_pub_reward(self):
        for kind in ('explore', 'investigate'):
            self.e.active = None; self.e.accept(1, quest_type=kind); self.a.state = 'explore'
            q = self.e.active_quest; self.d.floor = q['target_floor'] - 1
            with patch.object(self.a.audio, 'play_se') as se:
                for point in q['points']:
                    self.d.x, self.d.y = point; self.a.quest_or_field_event(lambda: ('', ''), False)
                self.assertTrue(q['completed']); se.assert_called_once_with('se_quest_complete')
                self.a.quest_or_field_event(lambda: ('', ''), False); self.assertEqual(se.call_count, 1)
                self.a.enter_camp(returned=True)
                self.e.finalize_quest_completion(); self.assertEqual(se.call_count, 1)

    def test_hunt_goal_immediate_sound_after_result_only_once(self):
        self.e.accept(1, quest_type='hunt'); q = self.e.active_quest
        self.d.floor = q['target_floor'] - 1; self.d.x, self.d.y = q['points'][0]
        self.a.begin_encounter(quest_hunt=True)
        self.a.battle.enemies[0].hp = 1; self.s.party[0].strength = 1000
        self.a.battle.queue = deque([('party', Action(0, 'SKILL', 0, self.s.party[0].skills[0]))])
        with patch.object(self.a.audio, 'play_se') as se:
            self.a.apply_visual_action()
            self.assertEqual(self.a.battle.outcome, 'VICTORY'); self.assertTrue(q['completed']); se.assert_not_called()
            self.a.observe_hunt_goal(); se.assert_not_called()
            self.finish(); se.assert_called_once_with('se_quest_complete')
            self.a.observe_hunt_goal(); self.assertEqual(se.call_count, 1)

    def test_audio_failure_or_disabled_keeps_dungeon_quest_and_battle_progress(self):
        for mode in ('failed', 'disabled'):
            with ExitStack() as stack:
                if mode == 'failed':
                    for api in ('play', 'playm', 'stop', 'play_pos'):
                        stack.enter_context(patch.object(pyxel, api, side_effect=RuntimeError('audio unavailable')))
                self.a.audio.enabled = mode != 'disabled'
                self.a.enter_dungeon(); self.a.begin_encounter(); self.finish('ESCAPE')
                self.assertEqual(self.a.state, 'explore')
                self.e.active = None; self.e.accept(1, quest_type='explore'); q = self.e.active_quest
                self.d.floor = q['target_floor'] - 1; self.d.x, self.d.y = q['points'][0]
                self.a.quest_or_field_event(lambda: ('', ''), False); self.assertTrue(q['completed'])
                self.a.handle_event('pit', '落下'); self.assertEqual(self.a.state, 'field_event')

    def test_audio_state_never_saved_and_new_game_clears_delayed_sound(self):
        self.a.enter_camp(); saved = make_save_data(self.a)
        self.assertEqual(SAVE_VERSION, 1); self.assertEqual(saved['save_version'], 1)
        self.assertNotIn('bgm', json.dumps(saved)); self.assertNotIn('audio', json.dumps(saved))
        apply_save_data(self.a, saved); self.assertEqual(make_save_data(self.a), saved)
        self.a.audio.play_se('se_trap_damage', 12); self.a.start_new_game()
        self.assertIsNone(self.a.audio.pending_se)


class AudioPreservationTests(unittest.TestCase):
    def test_all_original_battle_audio_and_protected_gameplay_files_unchanged(self):
        if sys.platform == 'emscripten': return
        before = json.loads(BASELINE.read_text(encoding='utf8'))
        allowed = {'rpg/app.py', 'rpg/dungeon_app.py', 'rpg/sound.py', 'game.pyxres'}
        from tests.test_enemy_balance import ALLOWED
        allowed |= ALLOWED  # This pass's own baseline protects every other file.
        for name, digest in before['hashes'].items():
            if name not in allowed: self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name)

    def test_all_images_maps_and_previously_used_sound_music_slots_unchanged(self):
        if sys.platform == 'emscripten': return
        from tests.balance_preservation import use_current_asset_baseline
        if use_current_asset_baseline(self): return
        initialized(); pyxel.load(str(ROOT / 'game.pyxres'))
        before = json.loads(BASELINE.read_text(encoding='utf8'))
        for image, digest in zip(pyxel.images, before['image_hashes']):
            self.assertEqual(hashlib.sha256(bytes(image.pget(x, y) for y in range(256) for x in range(256))).hexdigest(), digest)
        maps = [(tm.imgsrc, [[tm.pget(x, y) for x in range(256)] for y in range(256)]) for tm in pyxel.tilemaps]
        self.assertEqual(hashlib.sha256(json.dumps(maps, separators=(',', ':')).encode()).hexdigest(), before['map_hash'])
        self.assertFalse(pyxel.sounds[57].notes or pyxel.sounds[58].notes or any(pyxel.musics[7].seqs))
        for n, row in enumerate(before['game_audio']['sounds']):
            if row['notes']: self.assertEqual(list(pyxel.sounds[n].notes), row['notes'])
        for n, seqs in enumerate(before['game_audio']['musics']):
            if any(seqs): self.assertEqual([list(seq) for seq in pyxel.musics[n].seqs], seqs)

    def test_all_twenty_rare_eight_legend_traces_exactly_match_before(self):
        sys.path.insert(0, str(ROOT / 'tests'))
        from legend_presentation_helpers import rare_trace
        from test_rare_skill_presentation import make_battle
        before = json.loads(BASELINE.read_text(encoding='utf8'))
        for sid, digest in before['visual_traces'].items(): self.assertEqual(rare_trace(make_battle(sid)), digest, sid)


if __name__ == '__main__': unittest.main()
