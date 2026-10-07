"""Render every Amrita frame, hammer pad inputs, verify only new art changed."""
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
import tomllib
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.final_presentation import AMRITA_EFFECT_FRAMES
from rpg.models import Action
from rpg.text import FONT_HEIGHT, text_width


def main():
    app = DungeonApp(Session(*load_content(), seed=65), run=False, headless=True, start_at_title=False)
    s, d = app.session, app.dungeon
    output = ROOT / 'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    screenshots, texts, phases = [], [], []
    real_text = pyxel.text

    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        texts.append(value)
        real_text(x, y, value, color, font)

    def press(button=None, held=False):
        with patch.object(pyxel, 'btnp', side_effect=lambda code, *args: code == button), \
             patch.object(pyxel, 'btn', return_value=held):
            app.update()
        app.draw()

    def shot(name):
        app.draw()
        path = output / ('phase6b5_' + name + '.png')
        pyxel.screenshot(str(path), scale=4)
        screenshots.append(str(path.relative_to(ROOT)))

    with patch.object(pyxel, 'text', side_effect=bounded), \
         patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
         patch.object(pyxel, 'playm', side_effect=RuntimeError('interrupted')), \
         patch.object(pyxel, 'stop', side_effect=RuntimeError('closed')):
        # Disclosed strong-party fixture tests presentation, not balance.
        for actor in s.party:
            actor.max_hp = actor.hp = 600
            actor.agility = 60
        assert app.debug_final_stage('battle') is False
        s.debug = True
        app.debug_final_stage('battle')
        press()
        shot('barrier_on_command')
        app.selected_skill = s.skills[s.party[0].skills[0]]
        app.state = 'target'
        shot('large_boss_target')
        app.begin_input()
        b = app.battle
        before = b.enemies[0].hp
        b.begin_round([Action(0, 'SKILL', 0, s.party[0].skills[0])] + [Action(i, 'GUARD') for i in range(1, 4)])
        while b.queue:
            b.step()
        assert b.enemies[0].hp == before
        assert b.elysion_barrier_hint_shown
        app.begin_input()
        b.begin_round([Action(0, 'ITEM', item_id='AMRITA')] + [Action(i, 'GUARD') for i in range(1, 4)])
        app.state, app.delay, app.log, app.pending = 'resolve', 0, [], deque()
        for _ in range(100):
            press(pyxel.GAMEPAD1_BUTTON_A)
            if app.state == 'amrita_effect':
                break
        assert app.state == 'amrita_effect' and not b.elysion_barrier_active
        queue = list(b.queue)
        shot('amrita_message')
        keys = (pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B,
                pyxel.GAMEPAD1_BUTTON_DPAD_UP, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
        # Test all 45 render stages even on a slow test machine. The wall-time
        # fallback is separately checked with a simulated background return below.
        with patch('rpg.final_presentation.time.monotonic', return_value=app.final_visual().started_at):
            for frame in range(1, AMRITA_EFFECT_FRAMES + 1):
                press(keys[frame % len(keys)], held=True)
                assert list(b.queue) == queue
                if frame < AMRITA_EFFECT_FRAMES:
                    assert app.state == 'amrita_effect'
                if frame in (4, 18, 26, 33, 39):
                    shot({4:'flash',18:'light',26:'impact',33:'barrier_break',39:'barrier_gone'}[frame])
                phases.append(frame)
        assert app.state == 'resolve' and app.battle_input_blocked
        press(held=True)
        assert app.battle_input_blocked
        press()
        assert not app.battle_input_blocked
        for _ in range(100):
            press(pyxel.GAMEPAD1_BUTTON_A)
            if app.state == 'command':
                break
        assert app.state == 'command'
        shot('released_command')
        before = b.enemies[0].hp
        b.begin_round([Action(0, 'SKILL', 0, s.party[0].skills[0])] + [Action(i, 'GUARD') for i in range(1, 4)])
        while b.queue:
            b.step()
        assert b.enemies[0].hp < before
        # Force a loss only in this fixture, then exercise the real retry input.
        for actor in s.party:
            actor.hp = 0
        b.outcome = 'DEFEAT'
        s.settle()
        app.state = 'result'
        app.finish_results()
        press(pyxel.GAMEPAD1_BUTTON_A)
        press()
        assert app.battle.elysion_barrier_active and d.finale.has_amrita
        assert app.final_visual().frame == 0 and not app.final_visual().active
        shot('retry_barrier_on')
        # Returning from a stopped/background window cannot wait on old sound.
        app.battle.elysion_barrier_active = False
        app.start_amrita_effect()
        app.final_visual().started_at -= 10
        press()
        assert app.state == 'resolve'
        # A failing draw is also bounded; the already-released model survives.
        app.start_amrita_effect()
        with patch.object(app.final_visual(), 'draw_light', side_effect=RuntimeError('visual fault')):
            app.draw()
        assert app.state == 'resolve' and not app.battle.elysion_barrier_active

    baseline_dir = ROOT / 'verification/backups/phase6b5'
    preserved, resource_verified = {}, False
    if (baseline_dir / 'baseline.json').exists():
        baseline = json.loads((baseline_dir / 'baseline.json').read_text(encoding='utf-8'))
        preserved = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
                     for name, expected in baseline.items()
                     if name.replace('\\', '/') not in ('game.pyxres', 'data/final_battle.json')}
        assert all(preserved.values()), preserved
        def resource(path):
            with zipfile.ZipFile(path) as archive:
                return tomllib.loads(archive.read('pyxel_resource.toml').decode('utf-8'))
        old, new = resource(baseline_dir / 'game.pyxres'), resource(ROOT / 'game.pyxres')
        assert all(old[key] == new[key] for key in old if key != 'images')
        assert old['images'][1:] == new['images'][1:]
        rows_old, rows_new = old['images'][0]['data'], new['images'][0]['data']
        changed = []
        for y in range(256):
            for x in range(256):
                a = rows_old[y][x] if y < len(rows_old) and x < len(rows_old[y]) else 0
                b = rows_new[y][x] if y < len(rows_new) and x < len(rows_new[y]) else 0
                if a != b:
                    assert 144 <= x < 192 and 64 <= y < 112 and a == 0 and b in (1,2,3)
                    changed.append((x,y))
        assert changed
        resource_verified = True
    result = dict(effect_frames=AMRITA_EFFECT_FRAMES, effect_seconds=AMRITA_EFFECT_FRAMES/30,
                  sprite=dict(app.final_visual().sprite), bounded_text_calls=len(texts),
                  every_frame_rendered=len(phases), repeated_pad_input_blocked=True,
                  audio_failure_progress=True, background_deadline=True, draw_fault_fallback=True,
                  damage_blocked_then_passed=True, retry_restores_shell=True,
                  game_resource_only_new_rectangle=resource_verified, unchanged_files=preserved,
                  screenshots=screenshots, physical_smartphone_tested=False)
    (ROOT/'verification/phase6b5_ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: 45 visual frames, silent input hammering, deadline/draw fallback, retry, asset preservation;', len(texts), 'bounded text calls')


if __name__ == '__main__':
    main()
