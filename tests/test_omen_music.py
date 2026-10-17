"""Offering-event music timing, native-safe playback and silent progression."""
import ast
import hashlib
import json
import sys
import unittest
from unittest.mock import patch
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.sound import BGM_IDS, COMMON_SOUNDS


class OmenMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160, 120, headless=True)
            pyxel._tests_initialized = True

    def setUp(self):
        with patch.object(pyxel, 'init'):
            self.a = DungeonApp(Session(*load_content(), seed=617), run=False, headless=True)
        self.a.enter_camp()
        f = self.a.dungeon.finale
        f.guardians_defeated = True
        f.claim_amrita()
        self.a.show_amrita_offer()
        self.a.opening_input_blocked = False

    def press(self, key=None):
        with patch.object(pyxel, 'btn', return_value=False), \
             patch.object(pyxel, 'btnp', new=lambda k, *args: k == key):
            self.a.update()
            self.a.draw()

    def test_yes_switches_immediately_and_story_pages_never_restart_music(self):
        a = self.a
        self.assertEqual(a.audio.current_bgm, 'bgm_hub')
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((a.state, a.audio.current_bgm), ('final_story', 'bgm_omen'))
        self.assertTrue(a.dungeon.finale.has_amrita)
        with patch('rpg.sound._play_music') as music:
            for _ in range(len(a.final_story_pages()) - 1):
                self.press(pyxel.GAMEPAD1_BUTTON_A)
                self.assertEqual(a.audio.current_bgm, 'bgm_omen')
            for _ in range(90):
                self.press()
            music.assert_not_called()

    def test_later_and_cancel_keep_hub_music_and_allow_another_offer(self):
        for cancel in (False, True):
            self.a.show_amrita_offer()
            self.a.final_choice = 1
            self.press(pyxel.GAMEPAD1_BUTTON_B if cancel else pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual((self.a.state, self.a.audio.current_bgm), ('camp', 'bgm_hub'))
            self.assertFalse(self.a.dungeon.finale.final_event_started)
        self.a.enter_dungeon()
        self.a.enter_camp(returned=True)
        self.press()  # Release input after leaving the exploration screen.
        for _ in range(10):
            if self.a.state == 'amrita_offer':
                break
            self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.state, 'amrita_offer')
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(self.a.audio.current_bgm, 'bgm_omen')

    def test_story_to_boss_then_barrier_break_and_retry_existing_tracks(self):
        a = self.a
        self.press(pyxel.GAMEPAD1_BUTTON_A)
        for _ in a.final_story_pages():
            self.press(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual((a.state, a.audio.current_bgm), ('command', 'bgm_boss'))
        self.assertTrue(a.battle.elysion_barrier_active)
        a.battle.elysion_barrier_active = False
        a.sync_scene_audio()
        self.assertEqual(a.audio.current_bgm, 'bgm_final')
        a.final_checkpoint.restore(a.session, a.dungeon, a.exploration)
        a.begin_final_battle()
        self.assertTrue(a.battle.elysion_barrier_active)
        self.assertEqual(a.audio.current_bgm, 'bgm_boss')

    def test_unavailable_or_muted_audio_never_blocks_event_or_battle(self):
        for muted in (False, True):
            self.setUp()
            a = self.a
            a.audio.enabled = not muted
            with patch.object(pyxel, 'play', side_effect=RuntimeError('audio unavailable')), \
                 patch.object(pyxel, 'stop', side_effect=RuntimeError('audio unavailable')), \
                 patch.object(pyxel, 'playm', side_effect=RuntimeError('audio unavailable')):
                self.press(pyxel.GAMEPAD1_BUTTON_A)
                self.assertEqual((a.state, a.audio.current_bgm), ('final_story', 'bgm_omen'))
                self.assertFalse(a.audio.bgm_started)
                for _ in a.final_story_pages():
                    self.press(pyxel.GAMEPAD1_BUTTON_A)
                self.assertEqual((a.state, a.audio.current_bgm), ('command', 'bgm_boss'))
                self.assertTrue(a.dungeon.finale.has_amrita)

    def test_editor_score_32_seconds_channel_zero_free_and_existing_se_copied(self):
        a = self.a
        self.assertEqual(BGM_IDS['bgm_omen'], ('omen', 0))
        sounds, musics = a.audio.banks['omen']
        seqs = [list(seq) for seq in musics[0].seqs]
        self.assertEqual(seqs, [[], [0, 1], [2, 3], [4, 5]])
        for seq in seqs[1:]:
            self.assertAlmostEqual(sum(sounds[n].total_sec() for n in seq), 32)
        for slot in COMMON_SOUNDS:
            for attr in ('notes', 'tones', 'volumes', 'effects'):
                self.assertEqual(list(getattr(sounds[slot], attr)),
                                 list(getattr(a.audio.banks['battle'][0][slot], attr)))
        # Switching resources must not replace images or the SE's channel.
        a.audio.play_bgm('bgm_omen')
        with patch.object(pyxel, 'play') as play:
            a.audio.play_se('se_stairs')
        play.assert_called_once_with(0, 50)

    def test_native_omen_uses_channel_play_not_playm_and_web_keeps_music_api(self):
        a = self.a
        for platform in ('linux', 'emscripten'):
            a.audio.stop_bgm()
            with patch('rpg.sound.sys.platform', platform), \
                 patch.object(pyxel, 'play') as play, patch.object(pyxel, 'playm') as playm:
                self.assertTrue(a.audio.play_bgm('bgm_omen'))
            if platform == 'linux':
                self.assertEqual([c.args[0] for c in play.call_args_list], [1, 2, 3])
                self.assertTrue(all(c.kwargs['loop'] for c in play.call_args_list))
                playm.assert_not_called()
            else:
                playm.assert_called_once_with(0, loop=True)
                play.assert_not_called()

    def test_title_new_game_and_normal_return_keep_existing_audio(self):
        a = self.a
        a.start_new_game()
        self.assertEqual(a.audio.current_bgm, 'bgm_title')
        a.enter_camp()
        self.assertEqual(a.audio.current_bgm, 'bgm_hub')
        a.enter_dungeon()
        self.assertEqual(a.audio.current_bgm, 'bgm_area1')
        a.enter_camp(returned=True)
        self.assertEqual(a.audio.current_bgm, 'bgm_hub')

    def test_current_user_resources_gameplay_and_audio_manager_methods_unchanged(self):
        if sys.platform == 'emscripten':
            return  # Distribution validation compares the shipped resources.
        before = json.loads((ROOT/'tests/fixtures/omen_music_before.json').read_text(encoding='utf8'))
        for name, digest in before['hashes'].items():
            if name not in ('rpg/sound.py', 'rpg/dungeon_app.py'):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
        for name, cls_name, key, allowed in (
                ('rpg/sound.py', 'AudioManager', 'audio_methods', set()),
                ('rpg/dungeon_app.py', 'DungeonApp', 'app_methods',
                 {'sync_scene_audio', 'start_final_story'})):
            source = (ROOT/name).read_text(encoding='utf8')
            cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == cls_name)
            now = {n.name: hashlib.sha256(ast.get_source_segment(source, n).encode()).hexdigest()
                   for n in cls.body if isinstance(n, ast.FunctionDef)}
            self.assertEqual(now.keys(), before[key].keys())
            for method, digest in before[key].items():
                if method not in allowed:
                    self.assertEqual(now[method], digest, (name, method))


if __name__ == '__main__':
    unittest.main()
