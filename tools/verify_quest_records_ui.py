"""Real Pyxel pad-only QUEST thanks, records and all 27 fixed flavors.

Objective completion is a disclosed fixture here; verify_phase6d_ui exercises
actual map objectives, hunt combat, RETURN and ordinary defeat separately.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.quests import QUEST_TYPES, QUEST_COMPLETION_IDS
from rpg.text import FONT_HEIGHT, text_width

A, B = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B
DOWN = pyxel.GAMEPAD1_BUTTON_DPAD_DOWN


def main():
    app = DungeonApp(Session(*load_content(), seed=73), run=False, headless=True)
    app.start_new_game()
    app.enter_camp()
    app.dungeon.defeated_bosses.update((4, 9))
    e, s = app.exploration, app.session
    draws, screenshots, finished = [], [], []
    output = ROOT / 'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    original_text = pyxel.text

    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        draws.append((app.state, value))
        original_text(x, y, value, color, font)

    def press(button=None):
        assert button in (None, A, B, DOWN)
        with patch.object(pyxel, 'btnp', side_effect=lambda key, *a: key == button), \
                patch.object(pyxel, 'btn', return_value=False):
            app.update()
        app.draw()

    def shot(name):
        path = output / ('quest_record_' + name + '.png')
        app.draw()
        pyxel.screenshot(str(path), scale=4)
        screenshots.append(path.relative_to(ROOT).as_posix())

    def guild_record(name=None):
        assert app.state == 'camp'
        app.camp_cursor = 0  # Select only a menu position, never alter records.
        press(A)
        assert app.state == 'facility' and app.facility_index == 0
        press(A)
        assert app.overlay == 'info'
        press(B)
        press(DOWN); press(A)
        assert app.state == 'quest_record'
        before = len(draws)
        app.draw()
        values = [value for state, value in draws[before:]]
        for kind in QUEST_TYPES:
            row = e.quest_record()[kind]
            assert str(row['clears']) in values
            assert f"{row['completed']}/9" in values
            assert f"{row['percent']}%" in values
        total = e.quest_record()['total']
        assert f"{total['completed']}/27" in values
        assert f"{total['percent']}%" in values
        if name:
            shot(name)
        press(B)
        assert app.state == 'facility'
        press(DOWN); press(DOWN); press(A)
        assert app.overlay == 'help'
        press(B); press(B)
        assert app.state == 'camp'

    def accept(kind, level):
        app.camp_cursor = 0
        press(DOWN); press(DOWN); press(A); press(A)
        assert app.state == 'quest_board'
        for _ in range(level - 1):
            press(DOWN)
        press(A)
        for _ in range(QUEST_TYPES.index(kind)):
            press(DOWN)
        press(A)
        assert app.state == 'quest_preview' and not e.active
        offered = deepcopy(e.pending_quest)
        press(A)
        assert e.active == offered
        press(B); press(B)
        assert app.state == 'camp'
        return e.active

    def safe_return(name=None):
        q = deepcopy(e.active)
        flavor = deepcopy(e.quest_flavor())
        counts, ids, bank = dict(e.quest_clear_counts), list(e.completed_quest_ids), s.treasure.banked
        e.surveyed = True  # Objective fixture; actual objectives verified separately.
        app.enter_dungeon()
        app.handle_event('base', '')
        assert app.state == 'quest_thanks'
        assert e.quest_clear_counts == counts and e.completed_quest_ids == ids
        assert s.treasure.banked == bank and e.active
        before = len(draws)
        app.draw()
        values = [v for state, v in draws[before:]]
        assert flavor['requester'] in values
        assert all(line in values for line in flavor['complete_lines'])
        if name:
            shot(name + '_thanks')
        press(B)
        assert app.state == 'quest_thanks' and e.quest_clear_counts == counts
        press(A)
        assert app.state == 'quest_reward' and not e.active
        assert s.treasure.banked == bank + q['reward']
        expected = dict(counts)
        expected[q['type']] += 1
        assert e.quest_clear_counts == expected
        valid = q['flavor_id'] in QUEST_COMPLETION_IDS[q['type']] and flavor['id'] == q['flavor_id']
        assert e.completed_quest_ids == ids + ([q['flavor_id']] if valid and q['flavor_id'] not in ids else [])
        if name:
            shot(name + '_reward')
        press(B)
        assert app.state == 'quest_reward'
        press(A)
        assert app.state == 'camp'
        history = deepcopy((e.quest_clear_counts, e.completed_quest_ids, s.treasure.banked))
        app.enter_camp(returned=True)
        assert app.state == 'return_result'
        press(A)
        assert app.state == 'camp'
        assert (e.quest_clear_counts, e.completed_quest_ids, s.treasure.banked) == history
        finished.append(q['flavor_id'])

    with patch.object(pyxel, 'text', side_effect=bounded), \
            patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
            patch.object(pyxel, 'playm', side_effect=RuntimeError('interrupted')), \
            patch.object(pyxel, 'stop', side_effect=RuntimeError('closed')), \
            patch.object(pyxel, 'play_pos', side_effect=RuntimeError('suspended')):
        press()
        assert e.completed_quest_ids == [] and all(v == 0 for v in e.quest_clear_counts.values())
        guild_record('initial')
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                seen = set()
                for _ in range(3):
                    q = accept(kind, level)
                    assert q['flavor_id'] not in seen and not q['flavor_id'].endswith('_default')
                    seen.add(q['flavor_id'])
                    name = q['flavor_id'] if q['flavor_id'] == 'investigate_l2_01' else None
                    safe_return(name)
                    guild_record('first' if len(finished) == 1 else None)
                assert seen == set(i for i in QUEST_COMPLETION_IDS[kind] if f'_l{level}_' in i)
            assert e.quest_record()[kind]['percent'] == 100
            guild_record(kind + '_complete')
        assert e.quest_record()['total'] == dict(completed=27, total=27, percent=100)
        guild_record('all_complete')
        # Same fixed ID gives a repeat CLEAR, not another unique completion.
        accept('explore', 1)
        e.active['flavor_id'] = 'explore_l1_01'
        safe_return()
        assert e.quest_clear_counts['explore'] == 10 and len(e.completed_quest_ids) == 27
        # All nine fallback pages work, including genuinely missing IDs.
        for kind in QUEST_TYPES:
            for level in (1, 2, 3):
                accept(kind, level)
                e.active['flavor_id'] = f'{kind}_l{level}_default' if level != 2 else 'missing_id'
                safe_return()
                assert len(e.completed_quest_ids) == 27
                assert e.quest_record()['total']['total'] == 27
        history = deepcopy((e.quest_clear_counts, e.completed_quest_ids, s.treasure.banked))
        accept('hunt', 3)
        e.surveyed = True
        app.enter_camp(defeated=True)
        assert app.state != 'quest_thanks' and not e.surveyed
        assert (e.quest_clear_counts, e.completed_quest_ids, s.treasure.banked) == history
        # NEW GAME replaces the session/exploration and clears only new-run records.
        app.start_new_game()
        assert app.exploration.completed_quest_ids == []
        assert all(v == 0 for v in app.exploration.quest_clear_counts.values())
        assert (app.session.treasure.banked, app.session.treasure.unbanked) == (3, 0)

    result = dict(normal_flavors_rendered=27, fallback_pages_rendered=9,
                  fixed_total=27, all_complete_percent=100, clears_before_new_game=history[0],
                  thanks_before_reward=True, repeat_clear_without_duplicate=True,
                  safe_return_no_double_payment=True, defeat_no_records=True,
                  new_game_reset=True, pad_only=True, audio_apis_unavailable=True,
                  objective_fixture=True, text_bounds_calls=len(draws), screenshots=screenshots)
    (ROOT / 'verification/quest_records_ui.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PASS: 27 normal + 9 fallback thanks, CLEAR/unique/100%, GUILD status/help/B, silent pad-only; {len(draws)} bounded text calls')


if __name__ == '__main__':
    main()
