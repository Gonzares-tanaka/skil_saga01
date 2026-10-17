"""User-owned logo pixels, unchanged menu/audio, and draw-only source change."""
import ast
from copy import deepcopy
import hashlib
import json
import sys
import unittest
from unittest.mock import patch
import pyxel
from rpg.battle import Session
from rpg.content import ROOT,load_content
from rpg.dungeon_app import DungeonApp
from rpg.opening import TITLE_MAIN,TITLE_SUBTITLE
from rpg.save import make_save_data,apply_save_data


class TitleLogoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        cls.before=json.loads((ROOT/'tests/fixtures/title_logo_before.json').read_text(encoding='utf8'))

    def setUp(self):
        with patch.object(pyxel,'init'):
            self.a=DungeonApp(Session(*load_content(),seed=628),run=False,headless=True)

    def tick(self,key=None):
        with patch.object(pyxel,'btn',return_value=False),patch.object(pyxel,'btnp',new=lambda k,*args:k==key):
            self.a.update(); self.a.draw()

    def test_logo_uses_exact_region_native_size_center_and_no_colkey(self):
        with patch.object(pyxel,'blt') as blt,patch('rpg.dungeon_app.text') as text:
            self.a.draw_title_logo()
        blt.assert_called_once_with(16,23,1,0,192,128,32)
        text.assert_not_called()

    def test_rendered_pixels_match_user_image_and_menu_is_separate(self):
        self.a.draw()
        source=pyxel.images[1]
        pixels=[]
        for y in range(32):
            for x in range(128):
                value=source.pget(x,192+y); pixels.append(value)
                self.assertEqual(pyxel.pget(16+x,23+y),value,(x,y))
        self.assertEqual(hashlib.sha256(bytes(pixels)).hexdigest(),self.before['logo']['sha256'])
        self.assertLess(23+32,57)  # Bottom separator; menu highlight starts at y68.
        self.assertTrue(all(pyxel.pget(x,21)==1 and pyxel.pget(x,57)==1 for x in range(17,143)))

    def test_no_old_title_text_in_title_or_no_save_screen(self):
        for state in ('title','title_no_save'):
            self.a.state=state
            with patch.object(pyxel,'text',wraps=pyxel.text) as text:
                self.a.draw()
            shown=[c.args[2] for c in text.call_args_list]
            self.assertNotIn(TITLE_MAIN,shown); self.assertNotIn(TITLE_SUBTITLE,shown)
            if state=='title':
                self.assertIn('> はじめから',shown); self.assertIn('  つづきから',shown)

    def test_menu_cursor_new_game_and_opening_audio_unchanged(self):
        a=self.a; self.assertEqual(a.state,'title'); self.assertEqual(a.audio.current_bgm,'bgm_title')
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN); self.assertEqual(a.title_cursor,1)
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_UP); self.assertEqual(a.title_cursor,0)
        self.tick(pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(a.state,'title_fade')
        seen=set()
        for frame in range(500):
            seen.add(a.state)
            if a.state=='camp': break
            self.tick(pyxel.GAMEPAD1_BUTTON_A if frame%2 else None)
            self.assertEqual(a.audio.current_bgm,'bgm_title' if a.state in ('title_fade','intro') else 'bgm_hub')
        else: self.fail('Opening did not reach HUB')
        self.assertTrue({'intro','hub_preview','hub_intro','camp'}<=seen)

    def test_continue_uses_existing_load_and_saved_values(self):
        a=self.a; a.enter_camp(); a.session.treasure.banked=17; saved=make_save_data(a)
        a.state='title'; a.sync_scene_audio()
        self.tick(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        with patch.object(a.save_manager,'load',side_effect=lambda app:apply_save_data(app,deepcopy(saved))):
            self.tick(pyxel.GAMEPAD1_BUTTON_A)
        self.assertEqual(a.state,'camp'); self.assertEqual(a.audio.current_bgm,'bgm_hub')
        self.assertEqual(make_save_data(a),saved)

    def test_every_resource_and_all_other_methods_unchanged(self):
        if sys.platform!='emscripten':
            for name,digest in self.before['hashes'].items():
                if name.endswith(('.pyxres','.pyxpal')):
                    from tests.balance_preservation import assert_resource_unchanged
                    assert_resource_unchanged(self,name,digest)
                elif name not in ('rpg/dungeon_app.py','rpg/sound.py'):
                    self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
            source=(ROOT/'rpg/dungeon_app.py').read_text(encoding='utf8')
            cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='DungeonApp')
            methods={n.name:hashlib.sha256(ast.get_source_segment(source,n).encode()).hexdigest()
                for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
            self.assertEqual(methods.keys(),self.before['methods'].keys())
            for name,digest in self.before['methods'].items():
                # Omen pass changes only these two audio entry points; its own
                # baseline checks every other method including draw_title_logo.
                if name not in ('draw_title_logo','sync_scene_audio','start_final_story'):
                    self.assertEqual(methods[name],digest,name)
        self.assertEqual(len(self.a.session.skills),62)


if __name__=='__main__': unittest.main()
