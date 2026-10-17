"""Render real LEGEND phases, all combat contexts, and checkpoint retries."""
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tests'))
import pyxel
from test_legend_skill_presentation import LegendUITests, IDS, MAPPING, BEFORE
from test_rare_skill_presentation import make_battle
from test_enemy_roster import hunt_on
from test_final_battle import FinalBattleTests
from rpg.legend_skill_presentation import LEGEND_SPRITES
from rpg.battle import Battle
from rpg.content import load_content
from rpg.models import Enemy, Action
from rpg.text import text_width, FONT_HEIGHT


def main():
    fixture = LegendUITests(); fixture.setUp(); app = fixture.app
    output = ROOT / 'verification/screenshots/legend'; output.mkdir(parents=True, exist_ok=True)
    sheet = pyxel.Image(192, 128)
    sheet.blt(0, 0, pyxel.images[0], 0, 128, 192, 128)
    sheet.save(str(output / 'asset_sheet.png'), scale=4)
    shots, contexts, frames, bounds = [], [], {}, []
    native_text = pyxel.text
    def bounded(x, y, value, color, font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x, y, value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x, y, value)
        bounds.append((x, y)); native_text(x, y, value, color, font)
    def animate(sid, label, capture=False):
        app.update(); app.draw()
        v = app.battle_visual(); phases = []
        for tick in range(80):
            if not v.active: break
            if not phases or phases[-1] != v.phase: phases.append(v.phase)
            if capture and (v.phase == 'legend_main' and v.frame in (2, 8, 12)
                            or v.phase in ('legend_charge', 'legend_result', 'legend_afterglow', 'status_effect') and v.frame == 1):
                path = output / f'{label}_{sid}_{v.phase}_{v.frame}.png'
                app.draw(); pyxel.screenshot(str(path), scale=4)
                shots.append(path.relative_to(ROOT).as_posix())
            app.update(); app.draw()
        assert not v.active and not v.legend.id
        contexts.append(dict(context=label, skill=sid, phases=phases, ticks=tick, passed=True))
        return tick
    with patch.object(pyxel, 'text', side_effect=bounded):
        for sid in IDS:
            fixture.configure(make_battle(sid))
            frames[sid] = animate(sid, 'normal', capture=True)
        # Real HUNT construction and classification, with synthetic high HP to
        # observe the whole effect before any quest reward screen.
        app.session.battle = None; app.session.settled = True
        hunt_on(app, 1, 'slime'); app.begin_encounter(quest_hunt=True)
        assert app.battle_kind == 'quest_hunt'
        b = app.battle
        for e in b.enemies: e.hp = e.max_hp = 5000
        if 'starfall' not in b.party[0].skills: b.party[0].learn(b.skills['starfall'])
        b.queue.clear(); b.queue.append(('party', Action(0, 'SKILL', 0, 'starfall')))
        fixture.configure(b); animate('starfall', 'hunt', capture=True)
        for ident in ('guardian', 'skill_keeper', 'sentinel_armor', 'sentinel_speed',
                      'sentinel_mind', 'depth_lord', 'lord_of_elysion'):
            for sid in IDS:
                original = make_battle(sid)
                row = next(r for r in load_content()[3] if r['id'] == ident)
                b = Battle(original.party, [Enemy.from_definition(row, max_hp=5000)],
                           original.skills, rng=original.rng, boss=True)
                b.queue = original.queue
                if ident == 'lord_of_elysion': b.elysion_barrier_active = False
                fixture.configure(b); animate(sid, ident, capture=sid in ('meteor', 'time_stop'))
    final = FinalBattleTests(); final.setUp()
    for i, sid in enumerate(IDS):
        final.s.party[i // 2].learn(final.s.skills[sid]); final.s.discovered_skills.add(sid)
    final.launch()
    expected = [(list(c.skills), dict(c.skill_uses)) for c in final.s.party]
    for _ in range(3):
        final.a.battle.queue.append(('party', Action(0, 'SKILL', 0, 'seven_slash')))
        assert final.a.battle_visual().start()
        final.fail(); final.press(pyxel.GAMEPAD1_BUTTON_A)
        assert [(list(c.skills), dict(c.skill_uses)) for c in final.s.party] == expected
        assert not final.a.battle_visual().legend.id
        assert final.a.battle.elysion_barrier_active and final.d.finale.has_amrita
    before = json.loads(BEFORE.read_text(encoding='utf8'))
    allowed = {'rpg/content.py', 'rpg/app.py', 'rpg/battle_presentation.py', 'data/skills.json', 'game.pyxres',
               'rpg/sound.py', 'rpg/dungeon_app.py'}  # AUDIO PASS separately audits gameplay/art/audio.
    protected = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                 for name, digest in before['hashes'].items()
                 if name not in allowed and 'save' not in name.split('/')}
    assert all(protected.values()), [name for name, ok in protected.items() if not ok]
    report = dict(mapping=MAPPING, bank=0, assets=LEGEND_SPRITES, frame_size=32, frames=3,
                  screenshots=shots, contexts=contexts, context_count=len(contexts),
                  final_retries=3, legend_roster_restored=True, normal_frames=frames,
                  text_bounds_checked=len(bounds), protected_files=protected,
                  protected_count=len(protected), physical_gkd_tested=False)
    (ROOT / 'verification/legend_presentation.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('PASS:', len(shots), 'screenshots;', len(contexts), 'contexts; 3 LEGEND checkpoint retries;',
          len(bounds), 'text bounds;', len(protected), 'protected files')


if __name__ == '__main__': main()
