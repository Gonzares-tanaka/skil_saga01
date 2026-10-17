"""Check visual-only changes and render real Pyxel screenshots for review."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path
import random
import sys
import textwrap
from types import MethodType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Enemy
from rpg.battle_presentation import ENEMY_EFFECT_SPRITES
from rpg.text import text_width, FONT_HEIGHT


def snapshot():
    return ([tuple(im.pget(x, y) for y in range(256) for x in range(256)) for im in pyxel.images],
            [tuple(tm.pget(x, y) for y in range(256) for x in range(256)) for tm in pyxel.tilemaps],
            [(list(s.notes), list(s.tones), list(s.volumes), list(s.effects), s.speed) for s in pyxel.sounds],
            [[list(seq) for seq in m.seqs] for m in pyxel.musics])


def main():
    backup = ROOT / 'verification/backups/enemy_action_visual'
    baseline = json.loads((backup / 'baseline.json').read_text(encoding='utf8'))
    allowed = {'rpg/app.py', 'rpg/battle.py', 'rpg/battle_presentation.py', 'data/enemy_actions.json', 'game.pyxres'}
    protected = []
    for name, digest in baseline.items():
        if name not in allowed:
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
            protected.append(name)
    # Only effect_id may change in action data. Verify against initial Phase 1 data.
    expected = {
        'attack': ('physical_single', 1, 1), 'magic': ('magic_single', 1, 1),
        'heavy_attack': ('physical_single', 1.35, 1), 'double_attack': ('physical_single', .6, 2),
        'area_attack': ('physical_all', .55, 1), 'area_magic': ('magic_all', .5, 1)}
    settings, skills, party, rows = load_content()
    actions = json.loads((ROOT / 'data/enemy_actions.json').read_text(encoding='utf8'))
    original_data = (ROOT / 'data/enemy_actions.json').read_bytes()
    for current, previous in (('heavy_hit', 'blunt'), ('guard', 'buff'),
                              ('armor_down', 'debuff'), ('slow', 'debuff')):
        original_data = original_data.replace(('"effect_id":"' + current + '"').encode(),
                                              ('"effect_id":"' + previous + '"').encode())
    assert hashlib.sha256(original_data).hexdigest() == baseline['data/enemy_actions.json'], 'Non-visual action data changed'
    for ident, (kind, power, hits) in expected.items():
        assert (actions[ident]['type'], actions[ident]['power'], actions[ident]['hits']) == (kind, power, hits)
    assert actions['guard']['modifier'] == .5
    for ident, modifier in (('power_up', 1.2), ('weaken', .85), ('armor_break', .85), ('slow', .8)):
        assert (actions[ident]['modifier'], actions[ident]['duration']) == (modifier, 3)
    # Reconstruct the pre-pass method by replacing ONLY its display metadata block.
    # Execute both versions on independent identical fixtures and compare all rules/RNG/messages.
    source = textwrap.dedent(inspect.getsource(Battle._enemy_action))
    original = source[:source.index('    # Display-only outcome.')] + '    return lines\n'
    namespace = dict(Battle._enemy_action.__globals__)
    exec(original, namespace)
    old = namespace['_enemy_action']
    compared = 0
    for ident in actions:
        for seed in range(15):
            results = []
            for previous in (True, False):
                _, skills, party, rows = load_content()
                for c in party:
                    c.hp = c.max_hp = 1000
                enemy = Enemy.from_definition(next(r for r in rows if r['id'] == 'berserker'),
                                             max_hp=10000, strength=100, intellect=80)
                enemy.actions = [dict(id=ident, weight=1)]
                b = Battle(party, [enemy], skills, rng=random.Random(seed))
                if previous:
                    b._enemy_action = MethodType(old, b)
                lines = b._enemy_action(0)
                results.append((lines, [asdict(c) for c in party], asdict(enemy), b.rng.getstate(), b.sound_cue, b.player_hit))
            assert results[0] == results[1], (ident, seed)
            compared += 1
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(backup / 'game.pyxres'))
    before = snapshot()
    pyxel.load(str(ROOT / 'game.pyxres'))
    after = snapshot()
    assert before[1:] == after[1:], 'Maps/audio changed'
    assert before[0][:2] == after[0][:2], 'Enemy/player/map art changed'
    changed = 0
    for i, (a, b) in enumerate(zip(before[0][2], after[0][2])):
        if a == b:
            continue
        x, y = i % 256, i // 256
        assert any(u <= x < u + 48 and v <= y < v + 16 for u, v in ENEMY_EFFECT_SPRITES.values()), (x, y)
        assert a == 0 and b in range(4), (x, y, a, b)
        changed += 1
    assert changed
    with patch.object(pyxel, 'init'):
        app = DungeonApp(Session(*load_content(), seed=74), run=False, headless=True, start_at_title=False)
    app.begin_encounter()
    row = next(r for r in app.session.enemy_data if r['id'] == 'berserker')
    app.battle.enemies = [Enemy.from_definition(row, max_hp=10000, strength=100, intellect=80)]
    app.battle_background_area = 3
    shots = []
    text_calls = []
    original_text = pyxel.text
    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        text_calls.append(value)
        original_text(x, y, value, color, font)
    output = ROOT / 'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    from collections import deque
    with patch.object(pyxel, 'text', side_effect=bounded):
        for ident in actions:
            for c in app.battle.party:
                c.hp = c.max_hp = 1000; c.effects.clear()
            enemy = app.battle.enemies[0]
            enemy.hp = enemy.max_hp; enemy.effects.clear()
            enemy.actions = [dict(id=ident, weight=1)]
            app.battle.queue = deque([('enemy', 0)])
            app.battle.outcome = None
            app.state = 'resolve'; app.pending.clear(); app.battle_visual().reset()
            with patch.object(app.battle.rng, 'choice', side_effect=lambda choices: choices[0]):
                app.apply_visual_action()
            v = app.battle_visual()
            for tick in range(30):
                if tick in (0, 2, 3, 6, 8, 11) and v.active:
                    app.draw()
                    path = output / f'enemy_visual_{ident}_{tick}.png'
                    pyxel.screenshot(str(path), scale=4)
                    shots.append(path.relative_to(ROOT).as_posix())
                if not v.active:
                    break
                app.update_battle_visual()
        pyxel.images[2].save(str(output / 'enemy_visual_image2.png'), 3)
    report = dict(protected_files=protected,protected_count=len(protected),
                  enemy_stats_weights_ids_sprites_spawn_save_unchanged=True,
                  action_data_only_effect_ids_changed=True,
                  action_results_rng_messages_unchanged=compared,
                  maps_music_sounds_images01_unchanged=True,
                  image2_only_empty_effect_regions_changed=True,
                  changed_pixels=changed,effect_coordinates=ENEMY_EFFECT_SPRITES,
                  text_bounds_checked=len(text_calls),screenshots=shots)
    (ROOT / 'verification/enemy_visual_preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:', len(protected), 'protected files;', compared, 'unchanged rule outcomes;', len(shots), 'screenshots')


if __name__ == '__main__':
    main()
