"""GUILD four-row layout and both UI routes to the finite RETURN skill.

Uses real headless Pyxel, virtual D-PAD/A/B and disclosed skill/objective
fixtures. No enemy, skill or economy data are edited by this verification.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
import rpg.dungeon_app as ui
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.hub import HUB_MENUS, HUB_MENU_Y, HUB_MENU_STEP
from rpg.text import FONT_HEIGHT, text_width

A, B = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B
DOWN, RIGHT = pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT


def main():
    app = DungeonApp(Session(*load_content(), seed=73), run=False, headless=True)
    texts, shots, comparisons = [], [], []
    output = ROOT / 'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    real_text = pyxel.text

    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        texts.append((x, y, value))
        real_text(x, y, value, color, font)

    def press(button=None):
        assert button in (None, A, B, DOWN, RIGHT)
        with patch.object(pyxel, 'btnp', side_effect=lambda key, *args: key == button), \
                patch.object(pyxel, 'btn', return_value=False):
            app.update()
        app.draw()

    def shot(name):
        path = output / ('pre_save_' + name + '.png')
        app.draw()
        pyxel.screenshot(str(path), scale=4)
        shots.append(path.relative_to(ROOT).as_posix())

    def reset(casters=(), uses=3):
        app.start_new_game()
        app.enter_camp()
        press()
        for index in casters:
            app.session.party[index].learn(app.session.skills['return'])
            app.session.party[index].skill_uses['return'] = uses
        return app.session, app.exploration

    def open_return(route, actor=0):
        assert app.state == 'explore'
        press(B)
        if route == 'shortcut':
            for _ in range(3):
                press(DOWN)
            press(A)
        else:
            press(DOWN); press(A)
            assert app.overlay == 'info' and app.info_tab == 1
            for _ in range(actor):
                press(RIGHT)
            selected = app.session.party[actor].skills.index('return')
            for _ in range(selected):
                press(DOWN)
            texts.clear(); app.draw()
            assert any('RETURN' in value for x, y, value in texts)
            press(A)
        assert app.state == 'field_return' and not app.overlay
        assert app.item_cursor == (actor if route == 'skills' else 0)

    with patch.object(pyxel, 'text', side_effect=bounded), \
            patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
            patch.object(pyxel, 'playm', side_effect=RuntimeError('interrupted')), \
            patch.object(pyxel, 'stop', side_effect=RuntimeError('closed')):
        s, e = reset()
        press(A)
        assert app.state == 'facility'
        texts.clear(); shot('guild')
        assert any(value == 'TRZ 3' and y == 2 for x, y, value in texts)
        assert not any('BANKED' in value for x, y, value in texts)
        # All text rectangles on this screen are disjoint, including header TRZ.
        rectangles = [(x, y, x + text_width(v), y + FONT_HEIGHT) for x, y, v in texts if v.strip()]
        for i, a in enumerate(rectangles):
            for b in rectangles[i + 1:]:
                assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (a, b)
        for expected in ('info', 'quest_record', 'save_confirm', 'help'):
            press(A)
            assert (app.state if expected in ('quest_record', 'save_confirm') else app.overlay) == expected
            press(B)
            assert app.state == 'facility' and not app.overlay
            press(DOWN)
        assert len(HUB_MENUS[0]) == 4 and HUB_MENUS[0][2] == 'SAVE'
        future = (('PARTY STATUS', 'QUEST RECORD', 'SAVE', 'HELP'), *HUB_MENUS[1:])
        with patch.object(ui, 'HUB_MENUS', future):
            app.facility_cursor = 3
            texts.clear(); shot('guild_future_four_rows_fixture')
            assert any(v == '>HELP' and y == HUB_MENU_Y + 3 * HUB_MENU_STEP for x, y, v in texts)
            assert HUB_MENU_Y + 3 * HUB_MENU_STEP + 12 < 111
        # Large balances still fit the reserved header area; model value is untouched.
        s.treasure.banked = 12345678901234567890
        texts.clear(); app.draw()
        assert s.treasure.banked == 12345678901234567890
        assert any(v.startswith('TRZ ') and v.endswith('~') and y == 2 for x, y, v in texts)

        for route in ('shortcut', 'skills'):
            for uses in (3, 1):
                s, e = reset((0,), uses)
                e.accept(1, quest_type='explore')
                e.active['flavor_id'] = 'explore_l1_01'
                e.surveyed = True  # The existing Phase 6D tool tests actual objectives.
                reward = e.active['reward']
                s.treasure.unbanked = 5
                app.enter_dungeon()
                open_return(route)
                shot(route + '_uses_' + str(uses))
                with patch.object(s, 'field_return', wraps=s.field_return) as shared:
                    press(A)
                    assert shared.call_count == 1 and shared.call_args.args == (0,)
                    assert app.state == 'quest_thanks'
                    assert s.treasure.banked == 8 and s.treasure.unbanked == 0
                    assert e.quest_clear_counts['explore'] == 0
                    assert s.party[0].skill_uses.get('return', 0) == uses - 1
                    assert ('return' in s.party[0].skills) == (uses > 1)
                    assert ('return' in s.mastered_skills) == (uses == 1)
                    press(A)
                    assert app.state == 'quest_reward'
                    assert s.treasure.banked == 8 + reward
                    assert e.quest_clear_counts['explore'] == 1
                    assert e.completed_quest_ids == ['explore_l1_01']
                    press(A); press()
                    assert app.state == 'camp' and shared.call_count == 1
                    assert not e.finalize_quest_completion()
                    assert s.treasure.banked == 8 + reward and e.quest_clear_counts['explore'] == 1
                comparisons.append(dict(route=route, initial_uses=uses,
                                        remaining=s.party[0].skill_uses.get('return', 0),
                                        mastered='return' in s.mastered_skills,
                                        skills=list(s.party[0].skills), bank=s.treasure.banked,
                                        records=deepcopy(e.quest_record())))
        for uses in (3, 1):
            left, right = [r for r in comparisons if r['initial_uses'] == uses]
            assert {k: v for k, v in left.items() if k != 'route'} == {k: v for k, v in right.items() if k != 'route'}

        # Cancellation from SKILLS returns to its unchanged selected actor/skill.
        s, e = reset((0, 1))
        app.enter_dungeon(); open_return('skills', actor=1)
        press(B)
        assert app.state == 'menu' and app.overlay == 'info' and app.info_character == 1
        assert s.party[1].skills[app.scroll] == 'return'
        press(A); press(A)
        assert app.state == 'return_result'
        assert s.party[0].skill_uses['return'] == 3 and s.party[1].skill_uses['return'] == 2

        for mode in ('missing', 'zero', 'dead', 'guardian'):
            s, e = reset(() if mode == 'missing' else (0,))
            app.enter_dungeon()
            if mode == 'zero':
                s.party[0].skill_uses['return'] = 0
            elif mode == 'dead':
                s.party[0].hp = 0
            elif mode == 'guardian':
                app.dungeon.finale.guardian_index = 0
            s.treasure.unbanked = 5
            before = deepcopy((s.party[0].skill_uses, s.treasure.banked, s.treasure.unbanked))
            open_return('shortcut')
            press(A)
            assert app.state == 'field_return'
            assert (s.party[0].skill_uses, s.treasure.banked, s.treasure.unbanked) == before
            assert app.notice_timer and app.notice
        # Actual battle restrictions are also covered by test_treasure/test_finale.
        s, e = reset((0,))
        app.dungeon.floor = 4  # B5 is an actual boss floor.
        app.begin_encounter(boss=True)
        before = dict(s.party[0].skill_uses)
        try:
            s.field_return(0)
        except ValueError:
            pass
        else:
            raise AssertionError('RETURN permitted during boss battle')
        assert s.party[0].skill_uses == before
        app.session.battle = None  # End fixture; no game action uses this assignment.
        app.enter_camp()
        app.enter_dungeon(); press(B)
        texts.clear(); shot('exploration_menu')
        assert any(v.lstrip('> ') == 'RETURN' for x, y, v in texts)
        assert not any('RETURNで帰還' in v for x, y, v in texts)
        for _ in range(4):
            press(DOWN)
        press(A)
        assert app.overlay == 'help'
        shot('help')

    result = dict(guild_no_text_overlap=True, four_row_fixture_fits=True,
                  guild_save_present=True, banked_header_shared=True,
                  shortcut_and_skills_same_handler=True, identical_return_results=True,
                  both_routes_charge_once=True, last_use_forgets_and_masters=True,
                  missing_zero_dead_guardian_boss_rejected=True,
                  cancel_to_skills_and_multiple_casters=True,
                  safe_return_quest_and_trz_once=True, pad_only=True,
                  audio_unavailable=True, physical_browser_tested=False,
                  physical_smartphone_tested=False, snapshots=comparisons, screenshots=shots)
    (ROOT / 'verification/pre_save_ui.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS: GUILD disjoint header/menu/footer + four-row fixture; RETURN shortcut/SKILLS share finite Uses, mastery, safe return, restrictions; pad-only/silent')


if __name__ == '__main__':
    main()
