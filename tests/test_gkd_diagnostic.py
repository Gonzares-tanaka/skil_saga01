"""Native music workaround, diagnostic observers and bounded/flushable logs."""
from collections import deque
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,call
import pyxel
from rpg.sound import _play_music
from rpg.content import load_content
from rpg.battle import Session
from rpg.dungeon_app import DungeonApp
from tools.gkd_diagnostic import Diagnostic,LOG_LIMIT


class GKDDiagnosticTests(unittest.TestCase):
    def test_native_plays_exact_editor_sequences_no_playm(self):
        with patch('rpg.sound.sys.platform','linux'),patch.object(pyxel,'musics',
                [SimpleNamespace(seqs=[[],[1,2],[3],[4,5]])]), \
                patch.object(pyxel,'play') as play,patch.object(pyxel,'playm',side_effect=AssertionError('native playm forbidden')):
            self.assertTrue(_play_music(0,True))
            self.assertEqual(play.call_args_list,[call(1,[1,2],loop=True),call(2,[3],loop=True),call(3,[4,5],loop=True)])
            self.assertTrue(_play_music(0,False))
            self.assertEqual(play.call_args_list[-3:],[call(1,[1,2],loop=False),call(2,[3],loop=False),call(3,[4,5],loop=False)])

    def test_web_keeps_playm(self):
        with patch('rpg.sound.sys.platform','emscripten'),patch.object(pyxel,'playm') as playm,patch.object(pyxel,'play') as play:
            self.assertTrue(_play_music(0,True)); self.assertTrue(_play_music(1,False))
            self.assertEqual(playm.call_args_list,[call(0,loop=True),call(1,loop=False)])
            play.assert_not_called()

    def test_empty_score_not_reported_as_playing(self):
        with patch('rpg.sound.sys.platform','linux'),patch.object(pyxel,'musics',[SimpleNamespace(seqs=[[],[],[],[]])]):
            self.assertFalse(_play_music(0,True))

    def test_logs_flush_rotation_and_snapshot_indices(self):
        with tempfile.TemporaryDirectory() as temp:
            diag=Diagnostic(temp,watchdog=False)
            try:
                diag.app=SimpleNamespace(state='command',order=[0],actor_position=0,battle_input_blocked=True,
                    opening_input_blocked=False,dungeon=SimpleNamespace(floor=5),pending=deque(),
                    battle=SimpleNamespace(queue=deque(),enemies=[SimpleNamespace(id='skeleton',name='A',sprite=(80,16)),
                                                                 SimpleNamespace(id='skeleton',name='B',sprite=(80,16))]))
                diag.checkpoint('TEST')
                row=json.loads(diag.path.read_text(encoding='utf8').splitlines()[-1])
                self.assertEqual([e['index'] for e in row['enemies']],[0,1]); self.assertEqual(row['floor'],6)
                for _ in range(300): diag.checkpoint('ROTATION',padding='x'*1500)
                self.assertLessEqual(diag.path.stat().st_size,LOG_LIMIT)
                self.assertLessEqual(diag.path.with_suffix('.jsonl.1').stat().st_size,LOG_LIMIT)
            finally: diag.close()

    def test_original_exception_recorded_and_propagated(self):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        with tempfile.TemporaryDirectory() as temp,patch.object(pyxel,'init'):
            app=DungeonApp(Session(*load_content()),run=False,headless=True,start_at_title=False)
            diag=Diagnostic(temp,watchdog=False).install()
            try:
                app.session.battle=None; app.session.settled=True
                with patch.object(app.dungeon,'make_enemies',side_effect=ValueError('fixture exception')):
                    with self.assertRaisesRegex(ValueError,'fixture exception'): app.begin_encounter()
                self.assertIn('GAME_EXCEPTION',diag.path.read_text(encoding='utf8'))
            finally: diag.close()

    def test_real_start_checkpoints_and_diagnostic_switches(self):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        for audio,skip in ((True,False),(False,False),(True,True)):
            with self.subTest(audio=audio,skip=skip),tempfile.TemporaryDirectory() as temp,patch.object(pyxel,'init'):
                app=DungeonApp(Session(*load_content()),run=False,headless=True,start_at_title=False)
                app.enter_dungeon(); app.opening_input_blocked=False
                diag=Diagnostic(temp,dict(battle_start_audio=audio,skip_transition=skip),watchdog=False).install()
                try:
                    with patch.object(pyxel,'btn',new=lambda *a:False),patch.object(pyxel,'btnp',new=lambda *a:False):
                        app.begin_encounter(animate=True)
                        for _ in range(30): app.update(); app.draw()
                    rows=[json.loads(line) for line in diag.path.read_text(encoding='utf8').splitlines()]
                    events=[r['event'] for r in rows]
                    for event in ('ENCOUNTER_DETECTED','ENEMY_GROUP_CREATED','ENEMY_INSTANCES_READY','BATTLE_OBJECT_CREATED',
                                  'BATTLE_PRESENTATION_CREATED','ACTIVE_PLAYER_SELECTED','COMMAND_MENU_CREATED','COMMAND_READY'):
                        self.assertIn(event,events)
                    self.assertEqual(app.state,'command'); self.assertFalse(app.battle_input_blocked)
                    if not audio: self.assertIn('AUDIO_SKIPPED_DIAGNOSTIC',events)
                    if skip: self.assertIn('TRANSITION_BYPASS_DIAGNOSTIC',events)
                    else:
                        self.assertIn('TRANSITION_COMPLETE',events); self.assertIn('INPUT_UNLOCKED',events)
                finally: diag.close()


if __name__=='__main__': unittest.main()
