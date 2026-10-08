"""Real Pyxel: shared base currency and durable battle-start statistics.

Selected floors, hunt position and terminal outcomes are disclosed fixtures.
verify_final_chapter separately runs the actual B10 -> ENDING and five defeats.
"""
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import FONT_HEIGHT, text_width

A, B = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B


def main():
    app = DungeonApp(Session(*load_content(), seed=73), run=False, headless=True)
    calls, starts, headers, shots = [], [], [], []
    original = pyxel.text
    output = ROOT / 'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)

    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        calls.append((x, y, value))
        original(x, y, value, color, font)

    def press(button=None):
        with patch.object(pyxel, 'btnp', side_effect=lambda key, *args: key == button), \
                patch.object(pyxel, 'btn', return_value=False):
            app.update()
        app.draw()

    def shot(name):
        app.draw()
        path = output / ('play_stats_' + name + '.png')
        pyxel.screenshot(str(path), scale=4)
        shots.append(path.relative_to(ROOT).as_posix())

    def read_header():
        calls.clear(); app.draw()
        rows = [row for row in calls if row[2].startswith('TRZ ')]
        assert len(rows) == 1, rows
        x, y, value = rows[0]
        assert y == 2 and x + text_width(value) == 156
        assert value == f'TRZ {app.session.treasure.banked}'
        assert not any('BANKED' in value for x, y, value in calls)
        # Header title and currency must be disjoint.
        title = [row for row in calls if row[1] == 2 and row != rows[0]]
        assert len(title) == 1 and title[0][0] + text_width(title[0][2]) < x
        return rows[0]

    def finish_fixture(outcome='DRAW'):
        before = app.session.total_battles
        app.battle.outcome = outcome
        app.session.settle()
        for actor in list(app.session.pending_replacements):
            app.session.resolve_replacement(actor)
        assert app.session.total_battles == before

    with patch.object(pyxel, 'text', side_effect=bounded), \
            patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
            patch.object(pyxel, 'playm', side_effect=RuntimeError('interrupted')), \
            patch.object(pyxel, 'stop', side_effect=RuntimeError('closed')):
        app.start_new_game(); app.enter_camp(); press()
        s = app.session
        assert s.total_battles == 0
        headers.append(read_header()); shot('hub')
        assert not any(y in (89, 100) and ('TRZ' in value or value.endswith('戦')) for x, y, value in calls)
        for index in range(4):
            app.camp_cursor = index
            press(A)
            assert app.state == 'facility'
            headers.append(read_header())
            shot(('guild', 'training', 'pub', 'shop')[index])
            press(B)
        assert len(set(headers)) == 1
        app.session.debug = True
        read_header()
        app.session.debug = False
        app.camp_cursor = 3; press(A); press(A)
        assert app.state == 'shop'
        price = s.inventory.data['items']['POTION']['price']
        before = s.treasure.banked
        press(A)
        assert s.treasure.banked == before - price
        press(B); read_header(); press(B)
        s.treasure.unbanked = 5
        app.enter_camp(returned=True); press(A)
        assert s.treasure.banked == before - price + 5
        read_header()

        # Real application battle constructors all pass the single Session gateway.
        scenarios = [('normal', 0, None), ('B5', 4, None), ('B10', 9, None),
                     ('guardian1', 14, 0), ('guardian2', 14, 1), ('guardian3', 14, 2),
                     ('demon', 14, None)]
        for name, floor, guardian in scenarios:
            app.dungeon.floor = floor
            before = s.total_battles
            app.begin_encounter(boss=name != 'normal', guardian_index=guardian)
            assert s.total_battles == before + 1
            starts.append(dict(kind=name, total=s.total_battles))
            if name == 'normal':
                app.battle.run_override = True
                app.battle.attempt_run()
                assert app.battle.outcome == 'ESCAPE' and s.total_battles == before + 1
            finish_fixture('ESCAPE' if name == 'normal' else 'DRAW')
        e = app.exploration
        e.accept(1, quest_type='hunt')
        app.dungeon.floor = e.active['target_floor'] - 1
        app.dungeon.x, app.dungeon.y = e.active['points'][0]
        before = s.total_battles
        app.begin_encounter(quest_hunt=True)
        assert s.total_battles == before + 1
        starts.append(dict(kind='quest_hunt', total=s.total_battles))
        finish_fixture('DEFEAT')
        app.enter_camp(defeated=True)
        assert s.total_battles == before + 1
        app.dungeon.finale.guardians_defeated = True
        app.dungeon.finale.claim_amrita()
        app.dungeon.finale.start_final_event()
        app.begin_final_battle()
        starts.append(dict(kind='elysion', total=s.total_battles))
        for retry in range(3):
            before = s.total_battles
            finish_fixture('DEFEAT')
            app.final_checkpoint.restore(s, app.dungeon, e)
            assert s.total_battles == before
            app.begin_final_battle()
            assert s.total_battles == before + 1
            starts.append(dict(kind='retry' + str(retry + 1), total=s.total_battles))
        finish_fixture()
        app.enter_camp()
        app.camp_cursor = 0; press(); press(A); press(A)
        assert app.overlay == 'info'
        calls.clear(); shot('party_status')
        assert any(y == 15 and value.startswith(f'BATTLES {s.total_battles} ') for x, y, value in calls)
        press(B)
        assert app.state == 'facility' and not app.overlay
        last_total = s.total_battles
        app.start_new_game()
        assert app.session.total_battles == 0

    data = dict(shared_five_headers=True, old_hub_currency_removed=True,
                header_changes_after_purchase_and_return=True, counted_starts=starts,
                total_before_new_game=last_total, new_game_zero=True,
                checkpoint_does_not_rewind=True, party_status_displays_total=True,
                pad_only=True, audio_unavailable=True, physical_browser_tested=False,
                physical_smartphone_tested=False, screenshots=shots)
    (ROOT / 'verification/play_stats_ui.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PASS: five shared TRZ headers, shop/return refresh; {last_total} starts across all battle kinds/retries; PARTY STATUS/new game/pad/silence')


if __name__ == '__main__':
    main()
