"""Real Pyxel rendering, D-pad/A/B final flow and silent repeated retries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.final_battle import AMRITA_ITEM_ID
from rpg.text import FONT_HEIGHT, text_width

A, B = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B
DOWN, RIGHT = pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT


def main():
    app = DungeonApp(Session(*load_content(), seed=61), run=False, headless=True, start_at_title=False)
    output = ROOT / 'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    real_text, texts, screenshots = pyxel.text, [], []
    s, d = app.session, app.dungeon

    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        texts.append(value)
        real_text(x, y, value, color, font)

    def press(button=None):
        with patch.object(pyxel, 'btnp', side_effect=lambda code, *args: code == button), \
             patch.object(pyxel, 'btn', return_value=False):
            app.update()
        app.draw()

    def shot(name):
        app.notice_timer = 0
        app.draw()
        path = output / ('phase6b_' + name + '.png')
        pyxel.screenshot(str(path), scale=4)
        screenshots.append(str(path.relative_to(ROOT)))

    def select_skill(sid):
        assert app.state == 'command'
        actor = app.actor
        press(A)
        assert app.state == 'skill'
        for _ in range(actor.skills.index(sid)):
            press(DOWN)
        press(A)
        assert app.state == 'target', (actor.name, sid, app.state, app.notice)
        press(A)

    def guard():
        assert app.state == 'command'
        press(DOWN)
        assert app.cursor == 2
        press(A)

    def use_amrita():
        assert app.state == 'command'
        uses = dict(app.actor.skill_uses)
        actor = app.actor
        press(RIGHT)
        press(A)
        assert app.state == 'battle_item'
        options = app.battle_items()
        assert AMRITA_ITEM_ID in options
        for _ in range(options.index(AMRITA_ITEM_ID)):
            press(DOWN)
        shot('amrita_item')
        press(A)
        assert app.actions[-1].kind == 'ITEM' and app.actions[-1].item_id == AMRITA_ITEM_ID
        assert actor.skill_uses == uses
        while app.state == 'command':
            guard()
        resolve()
        assert not app.battle.elysion_barrier_active
        assert d.finale.has_amrita and not d.finale.amrita_power_spent
        assert actor.skill_uses == uses
        shot('barrier_released')

    def resolve():
        for _ in range(3000):
            if app.state not in ('resolve', 'battle_transition'):
                return
            press(A)
        raise AssertionError('Battle resolution did not terminate')

    def finish_result():
        for _ in range(600):
            if app.state not in ('result', 'replace'):
                return
            if app.state == 'replace':
                press(B)
                press(A)
                press(A)
            else:
                press(A)
        raise AssertionError('Result/replacement did not terminate')

    def resources():
        return deepcopy({'party': [vars(c) for c in s.party], 'items': s.inventory.counts,
                         'treasure': vars(s.treasure), 'mastered': s.mastered_skills,
                         'discovered': s.discovered_skills, 'flags': d.finale.snapshot(),
                         'counts': (s.completed, s.wins, s.losses, s.draws)})

    with patch.object(pyxel, 'text', side_effect=bounded), \
         patch.object(pyxel, 'play', side_effect=RuntimeError('AudioContext suspended')), \
         patch.object(pyxel, 'playm', side_effect=RuntimeError('AudioContext interrupted')), \
         patch.object(pyxel, 'stop', side_effect=RuntimeError('AudioContext closed')):
        initial_flags = d.finale.snapshot()
        for key in (pyxel.KEY_F4, pyxel.KEY_4, pyxel.KEY_5, pyxel.KEY_6, pyxel.KEY_7):
            press(key)
        assert app.state == 'camp' and not app.overlay
        assert d.finale.snapshot() == initial_flags

        # A normal encounter's ITEM UI must never offer the key.
        app.enter_dungeon()
        app.begin_encounter()
        press(RIGHT)
        press(A)
        assert app.state == 'battle_item' and AMRITA_ITEM_ID not in app.battle_items()
        shot('ordinary_items')
        press(B)
        app.battle.outcome = 'ESCAPE'
        s.settle()
        app.finish_results()

        # Disclosed preparation simulates completed Phase 6A. No resource file changes.
        d.finale.guardians_defeated = True
        d.finale.claim_amrita()
        d.defeated_bosses.update((4, 9, 14))
        for actor in s.party:
            actor.hp = actor.max_hp = 600
            actor.strength = actor.intellect = 70
            actor.agility = 60
        if 'meteor' not in s.party[0].skills:
            s.party[0].learn(s.skills['meteor'])
        s.party[0].skill_uses['meteor'] = 2
        s.inventory.counts = {item: 9 for item in s.inventory.counts}
        s.treasure.banked, s.treasure.unbanked = 50, 5
        s.settings['spark_chance'] = 0
        app.enter_camp(returned=True)
        press(A)
        assert app.state == 'amrita_offer'
        shot('offer')
        press(DOWN)
        press(A)
        assert app.state == 'camp' and d.finale.has_amrita
        for facility in (0, 1, 2, 3):
            app.camp_cursor = facility
            press(A)
            assert app.state == 'facility'
            if facility == 2:
                press(DOWN)
            press(A)
            assert app.state in ('facility', 'archive', 'pub', 'shop')
            if app.overlay or app.state != 'facility':
                press(B)
            press(B)
            assert app.state == 'camp'
        app.camp_cursor = 4
        press(A)
        assert app.state == 'explore'
        app.handle_event('base', '')
        press(A)
        assert app.state == 'amrita_offer'
        press(A)
        assert app.state == 'final_story' and d.finale.has_amrita
        for index in range(len(app.final_story_pages())):
            shot('story_' + str(index + 1))
            press(A)
        assert app.state == 'command' and app.battle.elysion_barrier_active
        checkpoint = app.final_checkpoint
        press()  # Release the story button before battle input.
        before = resources()
        shot('barrier_command')

        # Two real LEGEND actions exhaust METEOR while all attacks are blocked.
        hp = app.battle.enemies[0].hp
        hint_start = len(texts)
        for _ in range(2):
            while s.party[0].cooldowns.get('meteor', 0):
                while app.state == 'command':
                    guard()
                resolve()
            select_skill('meteor')
            while app.state == 'command':
                sid = next(sid for sid in app.actor.skills if s.skills[sid].effect == 'damage')
                select_skill(sid)
            resolve()
            assert app.battle.enemies[0].hp == hp
        assert 'meteor' not in s.party[0].skills and 'meteor' in s.mastered_skills
        assert any('障壁' in line for line in texts[hint_start:])
        assert any('アムリタ' in line for line in texts[hint_start:])
        use_amrita()

        retries = []
        for attempt in range(4):
            if attempt:
                use_amrita()
            # Consume 7 real POTION actions before forcing the loss.
            for _ in range(7):
                s.party[0].hp = 1
                press(RIGHT)
                press(A)
                press(A)
                assert app.state == 'target'
                press(A)
                while app.state == 'command':
                    guard()
                app.battle.enemies[0].strength = app.battle.enemies[0].intellect = 1
                resolve()
            assert s.inventory.counts['POTION'] == before['items']['POTION'] - 7
            # Override only this in-memory enemy to guarantee an actual all-KO outcome.
            boss = app.battle.enemies[0]
            boss.strength = boss.intellect = 2000
            for _ in range(20):
                if app.state != 'command':
                    break
                while app.state == 'command':
                    guard()
                resolve()
            assert app.state == 'result' and app.battle.outcome == 'DEFEAT'
            shot('defeat_' + str(attempt + 1))
            finish_result()
            assert app.state == 'final_retry' and d.finale.has_amrita
            shot('retry_' + str(attempt + 1))
            press(A)
            assert app.final_checkpoint is checkpoint
            assert app.battle.elysion_barrier_active
            assert resources() == before, ('Checkpoint changed', attempt)
            assert all(c.mastered_skills is s.mastered_skills for c in s.party)
            retries.append({'attempt': attempt + 1, 'full_restore': True, 'has_amrita': True,
                            'barrier_active': True, 'potions_restored': True,
                            'exhausted_meteor_restored': 'meteor' in s.party[0].skills})
            press()

        # Win with actual A/B skill selection and reach ENDING with unavailable audio.
        use_amrita()
        for _ in range(50):
            if app.state == 'result':
                break
            while app.state == 'command':
                actor = app.actor
                options = [s.skills[sid] for sid in actor.skills
                           if actor.skill_uses.get(sid, 0) > 0 and not actor.cooldowns.get(sid, 0)
                           and s.skills[sid].effect in ('damage', 'drain')]
                if options:
                    select_skill(max(options, key=lambda skill: skill.power(actor)).id)
                else:
                    guard()
            resolve()
        assert app.battle.outcome == 'VICTORY'
        shot('victory')
        finish_result()
        assert app.state == 'ending'
        assert d.finale.lord_of_elysion_defeated and d.finale.amrita_power_spent
        assert not d.finale.has_amrita
        for index in range(len(app.final_ending_pages())):
            shot('ending_' + str(index + 1))
            press(A)
        assert app.state == 'title'

        # Real DEBUG controls expose all four requested stages only after F9.
        app.start_new_game()
        app.enter_camp()
        app.opening_input_blocked = False
        s, d = app.session, app.dungeon
        press(pyxel.KEY_F9)
        press(pyxel.KEY_F4)
        shot('debug')
        press(pyxel.KEY_4)
        assert d.finale.has_amrita and app.overlay == 'dungeon_debug'
        press(pyxel.KEY_5)
        assert app.state == 'amrita_offer'
        press(B)
        press(pyxel.KEY_F4)
        press(pyxel.KEY_6)
        assert app.state == 'final_story'
        # Return to camp as a debug fixture to open the next shortcut.
        app.enter_camp()
        press(pyxel.KEY_F4)
        press(pyxel.KEY_7)
        assert app.battle.is_elysion_battle and app.battle.elysion_barrier_active

    baseline = json.loads((ROOT / 'verification/backups/phase6b/baseline.json').read_text(encoding='utf-8'))
    preserved = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
                 for name, expected in baseline['files'].items() if name != 'data/dungeon.json'}
    assert all(preserved.values()), preserved
    enemies = json.loads((ROOT / 'data/enemies.json').read_text(encoding='utf-8-sig'))
    assert enemies[:-1] == baseline['enemies'] and enemies[-1]['id'] == 'lord_of_elysion'
    result = {'silent_audio_apis': ['play', 'playm', 'stop'], 'arrival_later_facilities_rearrival': True,
              'ordinary_ITEM_hides_amrita': True, 'story_to_battle': True,
              'physical_and_LEGEND_blocked': True, 'initial_hint_displayed': True,
              'amrita_real_ITEM_action': True, 'retries': retries, 'ending_reached': True,
              'debug_4_5_6_7_gated': True, 'bounded_text_calls': len(texts),
              'preserved_files': preserved, 'existing_enemy_rows_preserved': True,
              'B15_bounds_only': [24, 32], 'screenshots': screenshots,
              'physical_smartphone_tested': False,
              'limitations': ['Prepared party; final boss balance provisional.',
                              'Desktop headless Pyxel and simulated gamepad; not a real browser or phone.']}
    (ROOT / 'verification/phase6b_ui.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: silent pad-only final flow, 4 all-KO retries, ENDING, {len(texts)} bounded text calls')


if __name__ == '__main__':
    main()
