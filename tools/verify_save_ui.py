"""File SAVE/CONTINUE with real headless Pyxel and a fresh Python process."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.save import FileSaveBackend, BrowserSaveBackend, SaveError, make_save_data
from rpg.text import FONT_HEIGHT, text_width

A, B, DOWN = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN


def main():
    with tempfile.TemporaryDirectory(prefix='skill_seekers_save_') as temp:
        path = Path(sys.argv[2]) if len(sys.argv) > 1 else Path(temp) / 'save/save.json'
        app = DungeonApp(Session(*load_content(), seed=73), run=False, headless=True,
                         save_backend=FileSaveBackend(path))
        calls, shots = [], []
        real = pyxel.text

        def bounded(x, y, value, color, font=None):
            assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
            assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
            calls.append(value)
            real(x, y, value, color, font)

        def press(button=None):
            with patch.object(pyxel, 'btnp', side_effect=lambda key, *args: key == button), \
                    patch.object(pyxel, 'btn', return_value=False):
                app.update()
            app.draw()

        def shot(name):
            folder = ROOT / 'verification/screenshots'
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / ('save_' + name + '.png')
            app.draw(); pyxel.screenshot(str(target), scale=4)
            shots.append(target.relative_to(ROOT).as_posix())

        with patch.object(pyxel, 'text', side_effect=bounded), patch.object(pyxel, 'play'), \
                patch.object(pyxel, 'playm'), patch.object(pyxel, 'stop'):
            if len(sys.argv) > 1:
                press(DOWN); press(A)
                assert app.state == 'camp' and not app.camp_offer_pending
                assert app.session.treasure.banked == 17 and app.session.treasure.unbanked == 0
                assert app.session.total_battles == 123
                assert app.session.party[0].skill_uses['punch'] == 17
                assert app.session.party[0].skill_uses['fire'] == 2
                assert app.hub_intro_shown and app.dungeon.finale.has_amrita
                assert app.exploration.active['flavor_id'] == 'investigate_l2_01'
                assert app.exploration.quest_flavor()['requester'] == '歴史研究者'
                assert app.final_checkpoint is None
                press()
                app.enter_dungeon(); app.handle_event('base', '')
                assert app.state == 'return_result'
                press(A)
                assert app.state == 'amrita_offer'
                print('PASS: fresh Python process TITLE CONTINUE -> HUB, no INTRO/immediate offer; reentry offer works')
                return
            app.start_new_game(); app.enter_camp(); press()
            s, d, e = app.session, app.dungeon, app.exploration
            assert (s.treasure.banked, s.treasure.unbanked, s.total_battles) == (3, 0, 0)
            app.hub_intro_shown = True
            s.treasure.banked, s.total_battles = 17, 123
            s.discovered_skills.update(('fire', 'return'))
            s.mastered_skills.add('fire')
            for sid in ('fire', 'return'):
                s.party[0].learn(s.skills[sid])
            s.party[0].skill_uses.update(punch=17, fire=2, **{'return': 2})
            s.party[0].strength += 5
            s.inventory.counts.update({'POTION': 2, 'PHOENIX ASH': 7, 'REMEDY': 9})
            d.defeated_bosses.update((4, 9, 14))
            d.finale.guardians_defeated = True
            d.finale.claim_amrita()
            e.accept(2, quest_type='investigate')
            e.active['flavor_id'] = 'investigate_l2_01'
            e.quest_clear_counts.update(explore=5, investigate=3, hunt=2)
            e.completed_quest_ids = ['explore_l1_01', 'investigate_l2_02', 'hunt_l1_01']
            expected = make_save_data(app)
            press(A); press(DOWN); press(DOWN); press(A)
            assert app.state == 'save_confirm'
            shot('confirm')
            press(B)
            assert app.state == 'facility' and not path.exists()
            press(A); press(DOWN); press(A)
            assert app.state == 'facility' and not path.exists()
            press(A); press(A)
            assert app.state == 'save_result' and path.exists()
            assert app.save_message == 'セーブしました。'
            shot('success'); press(B)
            assert app.state == 'facility'
            subprocess.run([sys.executable, '-X', 'utf8', __file__, '--load-check', str(path)], check=True)
            for state in ('explore', 'command', 'field_event', 'guardian_between', 'final_retry'):
                app.state = state
                with_error = False
                try:
                    app.save_manager.save(app)
                except SaveError:
                    with_error = True
                assert with_error and json.loads(path.read_text(encoding='utf-8')) == expected
            app.state, app.facility_index = 'facility', 0
            press(A)
            with patch.object(app.save_manager.backend, 'write', side_effect=PermissionError('test')):
                press(A)
            assert app.state == 'save_result' and 'できません' in app.save_message
            shot('write_failure'); press(B)
            assert app.state == 'facility'
            valid = path.read_bytes()
            for value in ('{broken', '{"save_version":999}', '{"save_version":1}', '{"save_version":true}'):
                path.write_text(value, encoding='utf-8')
                previous = app.session
                app.continue_game()
                assert app.state == 'title_no_save' and app.session is previous
                assert path.read_text(encoding='utf-8') == value
                shot('load_failure'); press(B)
                assert app.state == 'title'
            path.unlink()
            app.continue_game()
            assert app.state == 'title_no_save' and 'ありません' in app.title_save_message
            path.write_bytes(valid)
            app.continue_game()
            assert app.state == 'camp' and make_save_data(app) == expected
            press(); shot('loaded_hub')
            app.session.treasure.banked = 22
            app.camp_cursor = 0; press(A); press(DOWN); press(DOWN); press(A); press(A)
            assert app.state == 'save_result'
            app.continue_game()
            assert app.session.treasure.banked == 22
            # Storage errors must not silently fall back to a virtual file.
            app.save_manager.backend = BrowserSaveBackend()
            press(); press(A); press(DOWN); press(DOWN); press(A); press(A)
            assert app.state == 'save_result' and 'できません' in app.save_message
            press(B)
            assert app.state == 'facility'
            app.continue_game()
            assert app.state == 'title_no_save' and '読み込めません' in app.title_save_message
            assert json.loads(path.read_text(encoding='utf-8'))['banked_trz'] == 22

        report = dict(real_json_file=True, fresh_python_process_continue=True,
                      save_confirm_cancel_and_no=True, success_message=True,
                      failure_returns_to_guild=True, forbidden_states_rejected=True,
                      invalid_load_preserves_file_and_game=True, no_intro_after_load=True,
                      amrita_offer_deferred_until_reentry=True, resave_overwrites=True,
                      trz_not_added=True, pad_only=True, bounded_text_calls=len(calls), screenshots=shots,
                      browser_storage_failure_without_file_fallback=True,
                      physical_browser_tested=False, physical_smartphone_tested=False)
        (ROOT / 'verification/save_ui.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('PASS: GUILD file SAVE/cancel/failure, fresh-process CONTINUE, strict invalid-load handling, resave and Amrita reentry')


if __name__ == '__main__':
    main()
