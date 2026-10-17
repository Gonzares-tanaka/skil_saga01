"""PC file SAVE, complete process exit, TITLE LOAD, progress and resave.

All files live in an isolated temporary directory. Actual Pyxel update/draw
uses simulated D-PAD/A/B; no player file or game data is edited.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

CHECK = r'''
from pathlib import Path
import json, sys
from unittest.mock import patch
sys.path.insert(0, str(Path.cwd()))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.quests import QUEST_COMPLETION_IDS
from rpg.save import FileSaveBackend, make_save_data
path, expected_path, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
app = DungeonApp(Session(*load_content(), seed=71), run=False, headless=True,
                 save_backend=FileSaveBackend(path))
A, B, DOWN = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN
def press(button=None):
    with patch.object(pyxel, 'btnp', side_effect=lambda key, *args: key == button), patch.object(pyxel, 'btn', return_value=False):
        app.update()
    app.draw()
def save():
    press(A); press(DOWN); press(DOWN); press(A)
    assert app.state == 'save_confirm'
    press(A)
    assert app.state == 'save_result' and app.save_message == 'セーブしました。'
def expected():
    return {'data': make_save_data(app), 'flavor': app.exploration.quest_flavor()}
if mode == 'write':
    app.start_new_game(); app.enter_camp(); press()
    assert (app.session.treasure.banked, app.session.total_battles) == (3, 0)
    assert not app.exploration.completed_quest_ids
    assert not any(app.exploration.quest_clear_counts.values())
    app.hub_intro_shown = True
    s, d, e = app.session, app.dungeon, app.exploration
    s.treasure.banked, s.total_battles = 21, 128
    s.discovered_skills.update(('fire', 'return', 'revive'))
    s.mastered_skills.add('fire')
    for sid in ('fire', 'return', 'revive'): s.party[0].learn(s.skills[sid])
    s.party[0].skill_uses.update(punch=17, fire=2, **{'return': 1, 'revive': 2})
    s.party[0].history.append('別プロセスで復元する日本語成長記録')
    for c in s.party:
        c.max_hp = c.hp = 500
        c.strength, c.agility, c.intellect = 70, 55, 70
    s.inventory.counts.update({'POTION': 2, 'PHOENIX ASH': 7, 'REMEDY': 9})
    d.defeated_bosses.update((4, 9, 14))
    d.finale.guardians_defeated = True
    d.finale.claim_amrita()
    e.accept(2, quest_type='investigate')
    e.active['flavor_id'] = 'investigate_l2_01'
    e.active['progress'] = 1
    e.active['investigated_points'] = e.active['points'][:1]
    e.quest_clear_counts.update(explore=5, investigate=3, hunt=4)
    e.completed_quest_ids = [sid for kind, count in e.quest_clear_counts.items()
                            for sid in QUEST_COMPLETION_IDS[kind][:count]]
    expected_path.write_text(json.dumps(expected(), ensure_ascii=False), encoding='utf-8')
    save()
    assert json.loads(path.read_text(encoding='utf-8')) == expected()['data']
else:
    press(DOWN); press(A); press()
    assert app.state == 'camp' and app.final_checkpoint is None and not app.camp_offer_pending
    assert expected() == json.loads(expected_path.read_text(encoding='utf-8'))
    assert app.session.treasure.unbanked == 0
    if mode == 'advance':
        assert (app.session.treasure.banked, app.session.total_battles) == (21, 128)
        battle = app.session.next_battle()
        assert app.session.total_battles == 129
        for _ in range(80):
            if battle.outcome: break
            battle.begin_round(battle.auto_actions())
            while battle.queue: battle.step()
        assert battle.outcome == 'VICTORY'
        app.session.settle()
        for index in list(app.session.pending_replacements): app.session.resolve_replacement(index)
        app.enter_camp()
        app.session.treasure.banked += 1
        app.exploration.active['progress'] = 2
        app.exploration.active['investigated_points'] = app.exploration.active['points'][:2]
        expected_path.write_text(json.dumps(expected(), ensure_ascii=False), encoding='utf-8')
        save()
    else:
        assert (app.session.treasure.banked, app.session.total_battles) == (22, 129)
        assert app.exploration.active['progress'] == 2
print('PASS:', mode, 'PC Python', sys.version.split()[0], 'Pyxel', pyxel.VERSION)
'''


def main():
    with tempfile.TemporaryDirectory(prefix='seekers_phase7c_') as temp:
        save = Path(temp) / 'configured-save' / 'save.json'
        expected = Path(temp) / 'expected.json'
        for mode in ('write', 'advance', 'read'):
            subprocess.run([sys.executable, '-X', 'utf8', '-c', CHECK, str(save), str(expected), mode], cwd=ROOT, check=True)
        final = json.loads(save.read_text(encoding='utf-8'))
    report = dict(separate_processes=3, writer_exits_before_continue=True,
                  restart_after_resave=True, configurable_directory_created=True,
                  full_save_data_equal=True, same_quest_requester_and_text=True,
                  banked_trz_before=21, banked_trz_after=22,
                  total_battles_before=128, total_battles_after=129,
                  quest_clear_counts=final['quest_clear_counts'],
                  unique_quest_count=len(final['completed_quest_ids']),
                  normal_hub_without_intro_or_immediate_offer=True,
                  final_checkpoint_absent=True, pad_only_headless=True,
                  python_version=sys.version, physical_gkd_tested=False)
    (ROOT / 'verification/phase7c_pc_save.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
