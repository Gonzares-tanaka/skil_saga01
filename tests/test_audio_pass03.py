"""Opening BGM timing, strict TITLE/SE protection, and AREA1-only rework."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import sys
import time
import unittest
from unittest.mock import patch
import pyxel
from rpg.battle import Session
from rpg.content import ROOT,load_content
from rpg.dungeon_app import DungeonApp
from rpg.save import make_save_data,apply_save_data,SAVE_VERSION
from rpg.sound import _play_music
from tools.audio_pass02_resource import read_resource,assert_protected_resource

AREA_SOUNDS=set(range(14,21))|{58}


class AudioPass03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        cls.before=json.loads((ROOT/'tests/fixtures/audio_pass03_before.json').read_text(encoding='utf8'))

    def setUp(self):
        with patch.object(pyxel,'init'):
            self.a=DungeonApp(Session(*load_content(),seed=316),run=False,headless=True)

    def tick(self,key=None):
        with patch.object(pyxel,'btn',return_value=False),patch.object(pyxel,'btnp',new=lambda k,*args:k==key):
            self.a.update(); self.a.draw()

    def opening(self):
        a=self.a; self.tick(); self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state,'title_fade'); self.assertEqual(a.audio.current_bgm,'bgm_title')
        seen=[]
        for frame in range(500):
            seen.append((a.state,a.audio.current_bgm,a.intro_page))
            if a.state=='camp': break
            self.tick(pyxel.GAMEPAD1_BUTTON_A if frame%2 else None)
            expected='bgm_title' if a.state in ('title_fade','intro') else 'bgm_hub'
            self.assertEqual(a.audio.current_bgm,expected,(a.state,frame))
        else: self.fail('Opening did not reach normal HUB')
        self.assertTrue({'intro','hub_preview','hub_intro','camp'}<={row[0] for row in seen})
        self.assertEqual({row[2] for row in seen if row[0]=='intro'},set(range(len(a.intro_pages))))
        self.assertTrue(a.hub_intro_shown)
        return seen

    def test_opening_keeps_title_no_transient_hub_no_restart(self):
        with patch('rpg.sound._play_music',wraps=_play_music) as play:
            seen=self.opening()
        # Only the actual first HUB frame switches music. NEW GAME and all
        # story page advances reuse the same running TITLE without a restart.
        self.assertEqual([c.args for c in play.call_args_list],[(1,True)])
        self.assertTrue(all(bgm=='bgm_title' for state,bgm,_ in seen if state in ('title_fade','intro')))

    def test_hub_switch_happens_on_first_preview_frame(self):
        a=self.a; a.start_new_game()
        for _ in range(100):
            self.tick()
            if a.state=='intro': break
        self.tick()  # Release the existing opening input lock before a fresh A press.
        a.intro_page=len(a.intro_pages)-1
        self.assertEqual(a.audio.current_bgm,'bgm_title')
        with patch('rpg.sound._play_music',wraps=_play_music) as play:
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(a.state,'hub_preview'); self.assertEqual(a.audio.current_bgm,'bgm_hub')
            self.assertEqual([c.args for c in play.call_args_list],[(1,True)])
            remaining=a.hub_preview_remaining
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(a.state,'hub_preview'); self.assertEqual(a.hub_preview_remaining,remaining-1)
            self.assertEqual(play.call_count,1)

    def test_load_hub_never_replays_opening(self):
        a=self.a; a.enter_camp(); a.hub_intro_shown=True
        a.session.treasure.banked=17; saved=make_save_data(a)
        a.state='title'; a.sync_scene_audio()
        with patch.object(a.save_manager,'load',side_effect=lambda app:apply_save_data(app,deepcopy(saved))):
            a.continue_game()
        self.assertEqual(a.state,'camp'); self.assertEqual(a.audio.current_bgm,'bgm_hub')
        self.assertEqual(make_save_data(a),saved); self.assertEqual(SAVE_VERSION,1)

    def test_normal_and_defeat_returns_keep_hub_music(self):
        a=self.a
        for defeated,returned in ((False,True),(True,False)):
            a.enter_dungeon(); a.enter_camp(defeated=defeated,returned=returned)
            self.assertEqual(a.audio.current_bgm,'bgm_hub')
            self.assertNotIn(a.state,('title_fade','intro','hub_preview','hub_intro'))

    def test_title_all_other_bgm_se_and_images_maps_exactly_preserved(self):
        from tests.balance_preservation import assert_historical_audio
        assert_historical_audio(self,self.before,AREA_SOUNDS,{2})
        now=read_resource(ROOT/'game.pyxres'); old=self.before['scene']
        self.assertEqual({i for i,s in enumerate(now['sounds']) if s!=old['sounds'][i]},AREA_SOUNDS)
        self.assertEqual(now['musics'],old['musics'])  # Music2 keeps its existing pattern layout.
        self.assertEqual(now['sounds'][50],old['sounds'][50])

    def test_audio_manager_and_all_gameplay_data_unchanged(self):
        if sys.platform=='emscripten': return
        for name,digest in self.before['hashes'].items():
            # Offering cue adds a bank/ID; method preservation has its own test.
            if name not in ('game.pyxres','rpg/dungeon_app.py','rpg/sound.py'):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual(len(self.a.session.skills),62)

    def test_area1_minor_motif_low_bass_tempo_and_loop(self):
        sounds,music=self.a.audio.banks['scene']; seqs=music[2].seqs
        self.assertFalse(seqs[0]); self.assertEqual(len(seqs[1]),4)
        for seq in seqs[1:]:
            self.assertAlmostEqual(sum(sounds[n].total_sec() for n in seq),30.9333333333,places=5)
        self.assertEqual(sounds[14].speed,29)
        self.assertLess(sounds[14].speed,sounds[7].speed)  # Faster than unchanged HUB.
        self.assertEqual(list(sounds[15].notes)[:16],list(sounds[17].notes)[:16])
        chord=list(sounds[20].notes)
        self.assertEqual(chord[6]-chord[2],3)  # D-F is a minor third, rather than a major pastoral chord.
        old=[p for p in self.before['scene']['sounds'][18]['notes'] if p>=0]
        new=[p for p in sounds[18].notes if p>=0]
        self.assertLess(sum(new)/len(new),sum(old)/len(old))

    def test_area_floor_battle_victory_run_and_boundary(self):
        a=self.a; a.enter_dungeon(); a.dungeon.defeated_bosses.add(4)
        self.assertEqual(a.audio.current_bgm,'bgm_area1')
        with patch('rpg.sound._play_music',wraps=_play_music) as play:
            a.handle_event(*a.dungeon.change_floor(1)); self.assertEqual(play.call_count,0)
        for outcome in ('VICTORY','ESCAPE'):
            a.begin_encounter(); self.assertEqual(a.audio.current_bgm,'bgm_battle')
            if outcome=='ESCAPE':
                a.battle.run_override=True; a.battle.attempt_run()
            else: a.battle.outcome='VICTORY'
            a.battle.queue.clear(); a.session.settle()
            for i in list(a.session.pending_replacements): a.session.resolve_replacement(i,None)
            a.fanfare_started_at=None; a.state='result'; a.finish_results()
            self.assertEqual(a.state,'explore'); self.assertEqual(a.audio.current_bgm,'bgm_area1')
        a.dungeon.debug_floor(4); a.state='explore'; a.sync_scene_audio()
        a.handle_event(*a.dungeon.change_floor(5)); self.assertEqual(a.audio.current_bgm,'bgm_area2')

    def test_native_loop_wrap_uses_only_channel_play(self):
        if sys.platform=='emscripten': return
        a=self.a
        with patch.object(pyxel,'playm',side_effect=AssertionError('native playm forbidden')):
            a.audio.play_bgm('bgm_area1')
            self.assertTrue(_play_music(2,True,30.933333333-.04))
            time.sleep(.15)
            self.assertTrue(all(pyxel.play_pos(c) is not None for c in (1,2,3)))

    def test_failed_or_disabled_audio_does_not_hold_story_or_battle(self):
        for mode in ('failed','disabled'):
            self.setUp()
            with ExitStack() as stack:
                if mode=='failed':
                    for api in ('play','playm','stop','play_pos'):
                        stack.enter_context(patch.object(pyxel,api,side_effect=RuntimeError('audio unavailable')))
                self.a.audio.enabled=mode!='disabled'
                self.opening()
                self.a.enter_dungeon(); self.a.opening_input_blocked=False
                self.a.begin_encounter(animate=True)
                for _ in range(40): self.tick()
                self.assertEqual(self.a.state,'command'); self.assertFalse(self.a.battle_input_blocked)
                self.tick(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(self.a.state,'skill')
                self.tick(pyxel.GAMEPAD1_BUTTON_B); self.assertEqual(self.a.state,'command')


if __name__=='__main__': unittest.main()
