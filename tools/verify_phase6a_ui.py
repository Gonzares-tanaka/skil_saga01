"""Render the deep area and walk the Phase 6A story using real pad inputs.

The main scenario starts with a prepared party at B10's arrival stairs. After
that setup, floors and positions change only through normal D-pad movement.
Audio playback deliberately raises errors throughout this verification.
"""
import json
from pathlib import Path
import sys
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.text import FONT_HEIGHT, text_width
from rpg.tiles import (TILE_BOSS, TILE_GUARDIAN, TILE_HEAL_POINT,
                       TILE_QUEST, TILE_STAIRS_DOWN, TILE_SWITCH, TILE_WARNING)
from tools.verify_expedition import path_to


A, B = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B
DIRECTIONS = {(0, -1): pyxel.GAMEPAD1_BUTTON_DPAD_UP,
              (0, 1): pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,
              (-1, 0): pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,
              (1, 0): pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT}
OUTPUT = ROOT / 'verification' / 'screenshots'


def main(observer=None):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = DungeonApp(Session(*load_content(), seed=51), run=False,
                     headless=True, start_at_title=False)
    real_text, draws, screenshots, steps = pyxel.text, [], [], []
    battle_rows, replacement_count, actual_swap = [], 0, False

    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        draws.append(value)
        real_text(x, y, value, color, font)

    def press(button=None):
        with patch.object(pyxel, 'btnp', side_effect=lambda code, *args: code == button), \
                patch.object(pyxel, 'btn', return_value=False):
            app.update()
        app.draw()

    def shot(name):
        app.notice_timer = 0
        app.draw()
        path = OUTPUT / f'phase6a_{name}.png'
        pyxel.screenshot(str(path), scale=4)
        screenshots.append(str(path.relative_to(ROOT)))

    def close_field():
        for _ in range(40):
            if app.state != 'field_event':
                return
            press(A)
        raise AssertionError('Field story failed to finish')

    def resources():
        return {'hp': [actor.hp for actor in app.session.party],
                'uses': [dict(actor.skill_uses) for actor in app.session.party],
                'items': dict(app.session.inventory.counts)}

    def complete_replacements():
        nonlocal replacement_count, actual_swap
        for _ in range(50):
            if app.state != 'replace':
                return
            replacement_count += 1
            shot(f'replacement_{replacement_count:02}')
            index = app.session.pending_replacements[0]
            actor = app.session.party[index]
            if app.battle_kind == 'guardian' and not actual_swap and index == 0:
                # Preserve RETURN and the attack fallback while actually replacing
                # one support slot during the chained battle's normal reward UI.
                slot = next(i for i, sid in enumerate(actor.skills) if sid not in ('punch', 'return'))
                old, new = actor.skills[slot], actor.pending_skill
                for _ in range(slot):
                    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
                press(A)
                press(A)
                assert new in actor.skills and old not in actor.skills
                actual_swap = True
                continue
            # Other rolls select "decline", then explicitly confirm.
            press(B)
            press(A)
            press(A)
        raise AssertionError('Skill replacement did not finish')

    def fight(force_spark=False):
        assert app.battle is not None
        enemy_names = [enemy.name for enemy in app.battle.enemies]
        kind = app.battle_kind
        guardian_index = app.dungeon.finale.guardian_index
        before = resources()
        screenshot_name = ('guardian_' + str(guardian_index + 1) if kind == 'guardian'
                           else 'demon' if kind == 'demon' else 'battle_' + str(app.session.completed + 1))
        shot(screenshot_name + '_command')
        # A controlled spark roll guarantees that the chained battle covers the
        # ordinary full-slot replacement UI, rather than bypassing that state.
        spark_context = (patch('rpg.growth.spark_probability', return_value=1.0)
                         if force_spark else nullcontext())
        with spark_context:
            for _ in range(12000):
                if app.state == 'result':
                    break
                if app.state == 'command':
                    press(pyxel.KEY_A)  # Existing desktop auto-actions, real battle resolution.
                elif app.state in ('resolve', 'battle_transition'):
                    press(A)
                else:
                    raise AssertionError(('Unexpected combat state', app.state))
            else:
                raise AssertionError('Battle did not reach its result screen')
        assert app.battle.outcome == 'VICTORY', (kind, app.battle.outcome)
        charges_spent = sum(sum(actor.used_skills.values()) for actor in app.session.party)
        assert charges_spent > 0, ('Battle did not consume skill Uses', kind)
        shot(screenshot_name + '_result')
        while app.state in ('result', 'replace'):
            if app.state == 'replace':
                complete_replacements()
                continue
            pages = max(1, (len(app.result_lines) + 8) // 9)
            # The final A actually calls finish_results; ensure it carries wounds,
            # remaining charges and item stock into the next story/map state.
            if app.result_page == pages - 1 and not app.session.pending_replacements:
                settled = resources()
                press(A)
                assert resources() == settled, ('Battle exit refreshed resources', kind)
            else:
                press(A)
        after = resources()
        row = {'kind': kind, 'enemies': enemy_names,
               'rounds': app.battle.round, 'hp_before': before['hp'],
               'hp_after': after['hp'], 'guardian_index': guardian_index,
               'skill_charges_spent': charges_spent,
               'next_state': app.state, 'resources_carried_at_exit': True}
        battle_rows.append(row)
        return row

    def progress_events():
        for _ in range(60):
            if app.state == 'field_event':
                close_field()
            elif app.state == 'replace':
                complete_replacements()
            elif app.state in ('battle_transition', 'command', 'resolve', 'result'):
                fight()
            else:
                return
        raise AssertionError('Non-story event cycle did not finish')

    def walk(goal, stop_state=None):
        d = app.dungeon
        floor = d.floor
        for _ in range(4000):
            if stop_state and app.state == stop_state:
                return
            progress_events()
            assert app.state == 'explore', ('Walk needs exploration', app.state)
            if d.floor != floor or (d.x, d.y) == goal:
                return
            route = path_to(d, goal)
            nx, ny = route[0]
            before = d.x, d.y
            press(DIRECTIONS[(nx - d.x, ny - d.y)])
            steps.append([floor + 1, *before, nx, ny])
            assert d.floor != floor or (d.x, d.y) == (nx, ny), ('D-pad failed', floor, before, (nx, ny))
        raise AssertionError(('Walk failed to reach target', floor, goal))

    def return_menu():
        press(B)
        assert app.state == 'menu'
        for _ in range(3):
            press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        assert app.menu_cursor == 3
        press(A)
        assert app.state == 'field_return'
        press(A)
        assert app.state == 'return_result'
        press(A)
        if app.state == 'amrita_offer':
            # Phase 6B intercepts the first external arrival with the key item.
            # Keep this verifier focused on the completed Phase 6A route.
            shot('amrita_offer_after_RETURN')
            if observer:
                observer('FIRST_AMRITA_OFFER', app)
            press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
            press(A)
        assert app.state == 'camp'

    def prepare_party():
        for actor in app.session.party:
            actor.max_hp = actor.hp = 900
            actor.strength = actor.intellect = 70
            actor.agility = 55
        actor = app.session.party[0]
        for sid in ('return', 'armor_break', 'weaken', 'slow', 'power_up', 'focus', 'guard_up'):
            actor.learn(app.session.skills[sid])
        assert len(actor.skills) == 8

    with patch.object(pyxel, 'text', side_effect=bounded), \
            patch.object(pyxel, 'play', side_effect=RuntimeError('audio unavailable')), \
            patch.object(pyxel, 'playm', side_effect=RuntimeError('audio unavailable')):
        # A separate prepared debug scenario checks shortcuts and the decision to
        # RETURN before accepting a three-battle chain. It precedes a NEW GAME reset.
        app.enter_dungeon()
        initial_position = (app.dungeon.floor, app.dungeon.x, app.dungeon.y)
        for code in (pyxel.KEY_G, pyxel.KEY_M, pyxel.KEY_F4):
            press(code)
            assert app.overlay is None
            assert initial_position == (app.dungeon.floor, app.dungeon.x, app.dungeon.y)
        press(pyxel.KEY_F9)
        press(pyxel.KEY_F4)
        press(pyxel.KEY_M)
        assert app.dungeon.floor == 14 and app.dungeon.finale.guardians_defeated
        assert app.dungeon.tile(14, app.dungeon.x, app.dungeon.y) == TILE_BOSS
        shot('debug_demon')
        app.dungeon.finale.guardians_defeated = False
        press(pyxel.KEY_F4)
        press(pyxel.KEY_G)
        assert app.dungeon.floor == 14
        assert app.dungeon.tile(14, app.dungeon.x, app.dungeon.y) == TILE_WARNING
        press(pyxel.KEY_F9)
        app.session.party[0].learn(app.session.skills['return'])
        press(A)
        assert app.state == 'guardian_warning'
        shot('guardian_warning_cancel')
        press(B)
        assert app.state == 'explore' and app.dungeon.finale.guardian_index is None
        return_menu()
        assert not app.dungeon.finale.guardians_defeated

        # Main route: one disclosed setup at B10, then normal movement only.
        app.start_new_game()
        app.enter_dungeon()
        app.opening_input_blocked = False
        prepare_party()
        d, s, e = app.dungeon, app.session, app.exploration
        d.defeated_bosses.add(4)
        d.debug_floor(9)
        assert not s.debug
        if observer:
            observer('B10_START', app)
        walk(d.find(9, TILE_BOSS), stop_state='boss_message')
        assert app.state == 'boss_message'
        press(A)
        if observer:
            observer('B10_BATTLE', app)
        fight()
        assert app.state == 'boss_after' and 9 in d.defeated_bosses
        shot('B10_victory')
        if observer:
            observer('B10_VICTORY', app)
        press(A)
        assert app.state == 'explore'
        e.accept(3)
        quest_target = e.target
        assert d.tile(*quest_target) == TILE_QUEST

        for floor in range(10, 15):
            walk(d.find(floor - 1, TILE_STAIRS_DOWN))
            progress_events()
            assert d.floor == floor and app.state == 'explore'
            shot(f'B{floor+1}_arrival')
            if observer:
                observer(f'B{floor+1}_ARRIVAL', app)
            preview = pyxel.Image(d.width * 8, d.height * 8)
            preview.bltm(0, 0, d.maps[floor], 0, 0, d.width * 8, d.height * 8)
            preview_path = OUTPUT / f'phase6a_B{floor+1}_tilemap'
            preview.save(str(preview_path), scale=2)
            screenshots.append(str(preview_path.with_suffix('.png').relative_to(ROOT)))
            switches = d.positions(floor, TILE_SWITCH)
            for point in switches:
                walk(point)
                press(A)
                close_field()
                assert floor in d.activated_switches
            for ident, row in d.finale.data['lore'].items():
                if row['floor'] != floor + 1:
                    continue
                walk(d.find(floor, tuple(row['tile'])))
                press(A)
                assert app.state == 'field_event' and ident in d.finale.read_lore
                shot(ident)
                close_field()
                assert all(line in draws for line in app.field_lines)
            if quest_target[0] == floor:
                walk(quest_target[1:])
                progress_events()
                assert e.surveyed
            if floor == 14:
                break

        assert len(d.finale.read_lore) == 6
        walk(d.find(14, TILE_WARNING), stop_state='guardian_warning')
        assert app.state == 'guardian_warning'
        shot('guardian_warning')
        press(A)
        guardian_rows = []
        for index in range(3):
            assert app.state == 'command' and d.finale.guardian_index == index
            if index:
                assert resources() == carried, 'Next guardian refilled party resources'
            guardian_rows.append(fight(force_spark=index == 0))
            expected = 'guardian_after' if index == 2 else 'guardian_between'
            assert app.state == expected
            shot(expected + '_' + str(index + 1))
            if observer:
                observer(f'GUARDIAN_{index+1}_VICTORY', app)
            carried = resources()
            press(B)
            assert app.state == expected  # B cannot escape a chain that has begun.
            assert resources() == carried
            press(A)
        assert app.state == 'explore' and d.finale.guardians_defeated
        assert d.finale.guardian_index is None and replacement_count > 0 and actual_swap
        assert d.can_enter(14, *d.find(14, TILE_GUARDIAN))

        # Prepared injuries test the unchanged spring rules on the actual route.
        s.party[3].hp = 0
        for actor in s.party[:3]:
            actor.hp = min(actor.hp, max(1, actor.max_hp // 2))
        spring_before = resources()
        walk(d.find(14, TILE_HEAL_POINT), stop_state='field_event')
        assert app.state == 'field_event'
        shot('spring_first_use')
        close_field()
        assert [actor.hp for actor in s.party] == [actor.max_hp for actor in s.party[:3]] + [0]
        assert spring_before['uses'] == resources()['uses']
        assert spring_before['items'] == resources()['items']
        if observer:
            observer('SPRING_HP_ONLY', app)
        s.party[0].hp -= 1
        once = resources()
        press(A)
        close_field()
        assert resources() == once, 'Spring worked twice in one expedition'

        walk(d.find(14, TILE_BOSS), stop_state='boss_message')
        assert app.state == 'boss_message'
        if observer:
            observer('BEFORE_DEMON', app)
        press(A)
        fight()
        assert app.state == 'boss_after'
        assert d.finale.demon_defeated and d.finale.has_amrita
        if observer:
            observer('DEMON_VICTORY_AMRITA', app)
        story_pages = []
        while app.state == 'boss_after':
            story_pages.append(app.message_page)
            shot('demon_story_' + str(app.message_page + 1))
            press(A)
        assert story_pages == [0, 1]
        assert all(line in draws for line in app.message_lines)
        assert app.state == 'explore' and d.cleared
        if observer:
            observer('TRUTH_EVENT_FINISHED', app)
        assert e.surveyed
        item_stock = dict(s.inventory.counts)
        return_menu()
        assert d.finale.has_amrita and d.finale.demon_defeated
        assert 3 in e.completed and s.inventory.counts == item_stock
        shot('hub_with_amrita')
        if observer:
            observer('HUB_AFTER_LATER', app)

    result = {
        'main_scenario': 'Prepared HP900 STR70 AGI55 INT70 party at B10 arrival; no warps after setup',
        'audio': 'pyxel.play and pyxel.playm raise RuntimeError for entire test',
        'B10_victory_to_B15_demon_and_RETURN': True,
        'normal_DPAD_steps': len(steps),
        'lore_read_ids': sorted(d.finale.read_lore),
        'quest_Lv3_target': list(quest_target),
        'quest_Lv3_reported': 3 in e.completed,
        'debug_G_M_gated': True,
        'warning_B_cancel_and_RETURN_before_chain': True,
        'guardian_resources_carried_without_refill': True,
        'guardian_battles': guardian_rows,
        'full_slot_replacement_screens': replacement_count,
        'actual_skill_swap_during_guardian_results': actual_swap,
        'spring_living_HP_only_once_Uses_items_KO_unchanged': True,
        'demon_story_pages': len(story_pages),
        'amrita_key_retained_at_hub': d.finale.has_amrita,
        'bounded_text_calls': len(draws),
        'battle_count': len(battle_rows),
        'screenshots': screenshots,
        'physical_smartphone_tested': False,
        'limitations': ['Prepared strong party verifies flow rather than natural growth balance.',
                        'Headless desktop Pyxel with virtual gamepad inputs; no real Safari/Android run.']
    }
    path = ROOT / 'verification' / 'phase6a_ui.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: Phase 6A D-pad/A/B story flow, {len(steps)} normal steps, '
          f'{len(battle_rows)} battles, {len(draws)} bounded text calls')
    return app, result


if __name__ == '__main__':
    main()
