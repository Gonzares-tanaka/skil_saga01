"""No-status balance preservation, map/art preservation and real Pyxel UI QA."""
from collections import deque
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import sys
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from rpg.battle import Battle, Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Enemy, Action
from rpg.statuses import STATUS_IDS, apply_status, clear_statuses
from rpg.text import text_width, FONT_HEIGHT


def snapshot():
    return ([tuple(im.pget(x, y) for y in range(256) for x in range(256)) for im in pyxel.images],
            [tuple(tm.pget(x, y) for y in range(256) for x in range(256)) for tm in pyxel.tilemaps],
            [(list(s.notes), list(s.tones), list(s.volumes), list(s.effects), s.speed) for s in pyxel.sounds],
            [[list(seq) for seq in m.seqs] for m in pyxel.musics])


def main():
    backup = ROOT / 'verification/backups/status_phase1'
    baseline = json.loads((backup / 'baseline.json').read_text(encoding='utf8'))
    allowed = {'rpg/models.py', 'rpg/battle.py', 'rpg/enemy_actions.py', 'rpg/items.py',
               'rpg/app.py', 'rpg/dungeon_app.py', 'rpg/battle_presentation.py', 'game.pyxres'}
    protected = []
    for name, digest in baseline.items():
        if name not in allowed:
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
            protected.append(name)
    old = ModuleType('rpg._status_baseline'); old.__package__ = 'rpg'
    exec(compile((backup / 'battle.py').read_text(encoding='utf8'), str(backup / 'battle.py'), 'exec'), old.__dict__)
    compared = 0
    for mode in ('normal', 'boss'):
        for seed in range(15):
            settings, skills, _, rows = load_content()
            if mode == 'normal':
                cases = [(key, 'berserker') for key in json.loads((backup / 'enemy_actions.json').read_text())]
            else:
                cases = [(None, row['id']) for row in rows if row.get('boss')]
            for action, enemy_id in cases:
                values = []
                for cls in (old.Battle, Battle):
                    _, skills, party, rows = load_content()
                    for c in party: c.hp = c.max_hp = 1000
                    enemy = Enemy.from_definition(next(r for r in rows if r['id'] == enemy_id), max_hp=10000)
                    if action: enemy.actions = [dict(id=action, weight=1)]
                    b = cls(party, [enemy], skills, rng=random.Random(seed), boss=mode == 'boss')
                    b.queue.append(('enemy', 0))
                    lines = b.step()
                    values.append((lines, [asdict(c) for c in party], asdict(enemy), b.rng.getstate(), b.outcome))
                assert values[0] == values[1], (mode, seed, action, enemy_id)
                compared += 1
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(backup / 'game.pyxres')); before = snapshot()
    pyxel.load(str(ROOT / 'game.pyxres')); after = snapshot()
    assert before[1:] == after[1:], 'Maps/audio changed'
    assert before[0][:2] == after[0][:2], 'Existing sprite/map chips changed'
    pixels = 0
    for i, (a, b) in enumerate(zip(before[0][2], after[0][2])):
        if a == b: continue
        x, y = i % 256, i // 256
        assert 224 <= x < 232 and y < 8 and a == 0 and b in range(4), (x, y)
        pixels += 1
    assert pixels
    with patch.object(pyxel, 'init'):
        app = DungeonApp(Session(*load_content(), seed=74), run=False, headless=True, start_at_title=False)
    app.begin_encounter()
    app.battle.enemies = [Enemy.from_definition(app.session.enemy_data[0]) for _ in range(4)]
    shots, text_calls = [], []
    output = ROOT / 'verification/screenshots'; output.mkdir(parents=True, exist_ok=True)
    original_text = pyxel.text
    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        text_calls.append(value); original_text(x, y, value, color, font)
    def shot(name):
        app.draw()
        path = output / f'status_{name}.png'
        pyxel.screenshot(str(path), scale=4)
        shots.append(path.relative_to(ROOT).as_posix())
    with patch.object(pyxel, 'text', side_effect=bounded):
        for key in STATUS_IDS:
            for unit in app.session.party + app.battle.enemies:
                clear_statuses(unit); apply_status(unit, key)
            shot(key)
        for unit in app.session.party + app.battle.enemies:
            clear_statuses(unit); apply_status(unit, 'poison'); apply_status(unit, 'sleep')
        shot('two_icons')
        app.battle._damage(app.session.party[0], 99999)
        shot('ko')
        app.session.party[0].recover()
        apply_status(app.session.party[0], 'poison'); apply_status(app.session.party[0], 'sleep')
        app.state = 'resolve'
        app.battle.queue = deque([('party', Action(0, 'GUARD'))])
        app.apply_visual_action(); shot('poison_tick')
        app.battle_visual().reset()
        app.state = 'command'; app.overlay = 'status_debug'
        app.status_debug_target = app.status_debug_cursor = 0
        shot('debug')
        app.overlay = None
        app.session.inventory.counts['REMEDY'] = 1
        app.selected_item = 'REMEDY'; app.selected_skill = None; app.state = 'target'; app.target_cursor = 0
        shot('remedy_target')
    result = dict(protected_files=protected,protected_count=len(protected),
                  existing_enemy_weights_stats_skills_growth_quests_save_unchanged=True,
                  unchanged_no_status_outcomes_rng=compared,maps_sound_music_images01_unchanged=True,
                  only_new_confusion_icon_pixels=pixels,status_icon_bank=2,
                  status_icon_coordinates={'poison':[192,0],'paralyze':[200,0],'sleep':[208,0],'confusion':[224,0]},
                  screenshots=shots,text_bounds_checked=len(text_calls))
    (ROOT / 'verification/status_preservation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS:', len(protected), 'protected files;', compared, 'unchanged existing action outcomes;', len(shots), 'UI screenshots')


if __name__ == '__main__': main()
