"""Only two original scores may change; all user SE/gameplay bytes are protected."""
from contextlib import ExitStack
import hashlib
import json
import sys
import time
import unittest
from unittest.mock import patch,call
import pyxel
from rpg.battle import Session
from rpg.content import ROOT,load_content
from rpg.dungeon_app import DungeonApp
from rpg.sound import AudioManager,_play_music,SE_IDS,BGM_IDS
from tools.audio_pass02_resource import (read_resource,assert_protected_resource,
                                        ALLOWED_SOUNDS,ALLOWED_MUSICS)


class AudioPass02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        cls.before=json.loads((ROOT/'tests/fixtures/audio_pass02_before.json').read_text(encoding='utf8'))

    def setUp(self):
        with patch.object(pyxel,'init'):
            self.a=DungeonApp(Session(*load_content(),seed=213),run=False,headless=True)

    def tick(self,key=None):
        with patch.object(pyxel,'btn',return_value=False),patch.object(pyxel,'btnp',new=lambda k,*args:k==key):
            self.a.update(); self.a.draw()

    def finish(self,outcome):
        a=self.a; a.battle.outcome=outcome; a.battle.queue.clear(); a.session.settle()
        for i in list(a.session.pending_replacements): a.session.resolve_replacement(i,None)
        a.fanfare_started_at=None; a.state='result'; a.finish_results()

    def test_only_two_music_and_their_private_sounds_change(self):
        from tests.balance_preservation import assert_historical_audio
        assert_historical_audio(self,self.before,ALLOWED_SOUNDS,ALLOWED_MUSICS)
        now=read_resource(ROOT/'game.pyxres'); old=self.before['scene']
        self.assertEqual({i for i,row in enumerate(now['sounds']) if row!=old['sounds'][i]},ALLOWED_SOUNDS)
        self.assertEqual({i for i,row in enumerate(now['musics']) if row!=old['musics'][i]},ALLOWED_MUSICS)
        for music in (1,3,4,5,6,7):
            self.assertFalse(ALLOWED_SOUNDS.intersection(n for seq in now['musics'][music]['seqs'] for n in seq))

    def test_all_code_gameplay_assets_and_diagnostic_files_unchanged(self):
        if sys.platform=='emscripten': return  # Package contents are independently compared on PC.
        for name,digest in self.before['hashes'].items():
            # Omen pass adds an audio ID/bank, but preserves all AudioManager
            # methods (checked in test_omen_music).
            if name not in ('game.pyxres','rpg/dungeon_app.py','rpg/sound.py'):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(len(self.a.session.skills),62)

    def test_user_stairs_and_every_se_match_in_both_runtime_banks(self):
        for audio_id in ('bgm_title','bgm_area1','bgm_hub','bgm_battle','bgm_boss','bgm_final'):
            self.a.audio.play_bgm(audio_id)
            for slot in (50,51,52,53,54,55,60,61,62,63):
                sound=pyxel.sounds[slot]
                row=dict(notes=list(sound.notes),tones=list(sound.tones),volumes=list(sound.volumes),
                         effects=list(sound.effects),speed=sound.speed)
                self.assertEqual(row,self.before['scene']['sounds'][slot],(audio_id,slot))
            with patch.object(pyxel,'play') as play:
                self.a.audio.play_se('se_stairs'); play.assert_called_once_with(0,50)

    def test_exact_loop_lengths_three_voices_and_tempos(self):
        bank=self.a.audio.banks['scene']; sounds,musics=bank
        for music,speed,seconds in ((0,36,38.4),(2,29,32*29*4/120)):
            seqs=musics[music].seqs
            self.assertFalse(seqs[0]); self.assertEqual([len(s) for s in seqs[1:]],[4,4,4])
            for seq in seqs[1:]:
                self.assertAlmostEqual(sum(sounds[n].total_sec() for n in seq),seconds,places=4)
                self.assertTrue(all(sounds[n].speed==speed and len(sounds[n].notes)==32 for n in seq))
        self.assertEqual(3600/sounds[0].speed,100)
        self.assertAlmostEqual(3600/sounds[14].speed,124.137931,places=5)

    def test_melody_reworked_reprises_and_harmonic_development(self):
        sounds=self.a.audio.banks['scene'][0]
        for n in (*range(4),*range(14,18)):
            notes=list(sounds[n].notes)
            self.assertNotEqual(notes,self.before['scene']['sounds'][n]['notes'])
            self.assertGreaterEqual(len(set(notes)-{-1}),7)
            self.assertTrue(all(-1<=pitch<=59 for pitch in notes))
        self.assertEqual(list(sounds[1].notes)[:16],list(sounds[3].notes)[:16])
        self.assertEqual(list(sounds[15].notes)[:16],list(sounds[17].notes)[:16])
        self.assertNotEqual(list(sounds[4].notes),list(sounds[5].notes))
        self.assertNotEqual(list(sounds[18].notes),list(sounds[19].notes))
        self.assertGreater(min(sounds[14].notes[:6]),min(sounds[0].notes))

    def test_title_intro_preview_hub_then_b1_music(self):
        a=self.a; self.assertEqual(a.audio.current_bgm,'bgm_title')
        self.tick(); self.tick(pyxel.GAMEPAD1_BUTTON_A)
        seen=set()
        for frame in range(500):
            seen.add(a.state)
            if a.state=='camp': break
            self.tick(pyxel.GAMEPAD1_BUTTON_A if frame%2 else None)
            self.assertEqual(a.audio.current_bgm,'bgm_title' if a.state in ('title_fade','intro') else 'bgm_hub')
        else: self.fail('Opening did not reach HUB')
        self.assertTrue({'intro','hub_preview','hub_intro'}<=seen)
        a.enter_dungeon(); self.assertEqual(a.audio.current_bgm,'bgm_area1')

    def test_stairs_1_to_2_4_to_5_no_restart_5_to_6_switches(self):
        a=self.a; a.enter_dungeon(); a.dungeon.defeated_bosses.update((4,9))
        for origin,destination in ((0,1),(3,4)):
            a.dungeon.debug_floor(origin); a.state='explore'; a.sync_scene_audio()
            with patch('rpg.sound._play_music',return_value=True) as music,patch.object(pyxel,'play',wraps=pyxel.play) as play:
                a.handle_event(*a.dungeon.change_floor(destination))
                music.assert_not_called(); self.assertIn(call(0,50),play.call_args_list)
            self.assertEqual(a.audio.current_bgm,'bgm_area1')
        a.dungeon.debug_floor(4); a.state='explore'; a.sync_scene_audio()
        with patch('rpg.sound._play_music',return_value=True) as music:
            a.handle_event(*a.dungeon.change_floor(5)); music.assert_called_once_with(3,True)
        self.assertEqual(a.audio.current_bgm,'bgm_area2')

    def test_victory_and_run_restore_new_area1(self):
        a=self.a; a.enter_dungeon()
        for outcome in ('VICTORY','ESCAPE'):
            a.begin_encounter(); self.assertEqual(a.audio.current_bgm,'bgm_battle')
            if outcome=='VICTORY': a.audio.play_victory()
            self.finish(outcome)
            self.assertEqual(a.state,'explore'); self.assertEqual(a.audio.current_bgm,'bgm_area1')

    def test_native_real_loop_wrap_and_shared_stairs_do_not_stop_bgm(self):
        if sys.platform=='emscripten': return  # Native backend only; Web audio is exercised separately.
        a=self.a
        with patch.object(pyxel,'playm',side_effect=AssertionError('native playm forbidden')):
            for audio_id,seconds in (('bgm_title',38.4),('bgm_area1',32*29*4/120)):
                self.assertTrue(a.audio.play_bgm(audio_id))
                self.assertTrue(_play_music(BGM_IDS[audio_id][1],True,seconds-.04))
                a.audio.play_se('se_stairs'); time.sleep(.15)
                for channel in (1,2,3):
                    position=pyxel.play_pos(channel)
                    self.assertIsNotNone(position)
                    self.assertLess(position[1],8)  # Passed the end and wrapped into the opening bar.

    def test_disabled_or_throwing_audio_never_blocks_new_scenes_or_battle(self):
        a=self.a
        for mode in ('disabled','failed'):
            with ExitStack() as stack:
                if mode=='failed':
                    for api in ('play','playm','stop','play_pos'):
                        stack.enter_context(patch.object(pyxel,api,side_effect=RuntimeError('audio unavailable')))
                a.audio.enabled=mode!='disabled'; a.start_new_game(); a.enter_camp(); a.enter_dungeon()
                a.opening_input_blocked=False; a.begin_encounter(animate=True)
                for _ in range(40): self.tick()
                self.assertEqual(a.state,'command'); self.assertFalse(a.battle_input_blocked)
                self.tick(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(a.state,'skill')
                self.tick(pyxel.GAMEPAD1_BUTTON_B); self.assertEqual(a.state,'command')
                self.finish('VICTORY'); self.assertEqual(a.state,'explore')


if __name__=='__main__': unittest.main()
