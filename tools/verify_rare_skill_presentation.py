"""Render editable sprites and real RARE battle phases for visual review."""
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tests'))
import pyxel
from test_rare_skill_presentation import RareUITests, make_battle, MAPPING, BEFORE
from rpg.rare_skill_presentation import RARE_SPRITES
from rpg.text import text_width, FONT_HEIGHT
from rpg.battle import Battle
from rpg.content import load_content
from rpg.models import Enemy


def main():
    fixture = RareUITests(); fixture.setUp(); app = fixture.app
    output = ROOT / 'verification/screenshots/rare'; output.mkdir(parents=True, exist_ok=True)
    image = pyxel.Image(192, 96)
    image.blt(0, 0, pyxel.images[1], 0, 96, 192, 96)
    image.save(str(output / 'asset_sheet.png'), scale=4)
    shots, phases, bounds = [], {}, []
    native_text = pyxel.text
    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        bounds.append((x, y)); native_text(x, y, value, color, font)
    with patch.object(pyxel, 'text', side_effect=bounded):
        for sid in MAPPING:
            b = make_battle(sid); fixture.configure(b)
            app.update()
            visual = app.battle_visual(); recorded = []
            for tick in range(80):
                if not visual.active: break
                if not recorded or recorded[-1] != visual.phase: recorded.append(visual.phase)
                if (visual.phase == 'rare_effect' and visual.frame == 4
                        or visual.phase in ('rare_cast', 'rare_feedback', 'status_effect') and visual.frame == 1):
                    app.draw()
                    name = sid + '_' + visual.phase + '.png'
                    pyxel.screenshot(str(output / name), scale=4)
                    shots.append((output / name).relative_to(ROOT).as_posix())
                app.update(); app.draw()
            assert not visual.active
            phases[sid] = recorded
        boss_cases = []
        for ident, sid, barrier in (('guardian', 'heavy_break', False),
                                    ('lord_of_elysion', 'inferno', True),
                                    ('lord_of_elysion', 'chaos_spell', False)):
            b = make_battle(sid)
            row = next(r for r in load_content()[3] if r['id'] == ident)
            boss = Battle(b.party, [Enemy.from_definition(row)], b.skills, rng=b.rng, boss=True)
            boss.queue = b.queue
            boss.elysion_barrier_active = barrier
            fixture.configure(boss); app.update()
            visual = app.battle_visual()
            for tick in range(80):
                if not visual.active: break
                if visual.phase == 'rare_effect' and visual.frame == 4:
                    app.draw()
                    path = output / (ident + '_' + sid + '.png')
                    pyxel.screenshot(str(path), scale=4)
                    shots.append(path.relative_to(ROOT).as_posix())
                app.update(); app.draw()
            assert not visual.active
            boss_cases.append(dict(boss=ident, skill=sid, barrier=barrier, progressed=True))
    before = json.loads(BEFORE.read_text(encoding='utf8'))
    allowed = {'rpg/models.py', 'rpg/content.py', 'rpg/app.py', 'rpg/battle_presentation.py',
               'data/skills.json', 'game.pyxres', 'rpg/sound.py', 'rpg/dungeon_app.py'}
    protected = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                 for name, digest in before['hashes'].items()
                 if name not in allowed and 'save' not in name.split('/')}
    assert all(protected.values()), [name for name, ok in protected.items() if not ok]
    report = dict(mapping=MAPPING, families=RARE_SPRITES, bank=1, frame_size=32, frames=3,
                  all_twenty_rendered=True, phases=phases, screenshots=shots,
                  boss_cases=boss_cases,
                  text_bounds_checked=len(bounds), protected_files=protected,
                  protected_count=len(protected), physical_gkd_tested=False)
    (ROOT / 'verification/rare_presentation.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('PASS:', len(shots), 'real phase screenshots;', len(bounds), 'text bounds;', len(protected), 'protected files')


if __name__ == '__main__':
    main()
