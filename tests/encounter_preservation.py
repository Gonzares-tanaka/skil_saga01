"""Encounter-only authorization against the received, user-edited asset tree."""
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT
from tools.snapshot_alpha_ux_methods import method_hashes


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/alpha_encounter03_before.json').read_text(encoding='utf8'))


def assert_encounter_resource(case, name='game.pyxres'):
    if (ROOT/'tests/fixtures/ui_phase6a_before.json').exists():
        from tests.ui_phase6a_preservation import protected_hashes
        case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),
                         protected_hashes()[name],name)
        return
    case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), baseline()['hashes'][name], name)


def assert_encounter_preserved(case):
    if (ROOT/'tests/fixtures/skill_balance5b1_before.json').exists():
        from tests.skill_balance_preservation import assert_skill_balance_preserved
        assert_skill_balance_preserved(case)
        return
    before = baseline()
    changed = {'rpg/dungeon.py': {'Dungeon.__init__','Dungeon.validate_settings','Dungeon.fall_in_pit',
                    'Dungeon.change_floor','Dungeon.move','Dungeon.enter','Dungeon.debug_floor','Dungeon.reset_encounter'},
               'rpg/dungeon_app.py': {'DungeonApp.finish_results','DungeonApp.update_guardians',
                    'DungeonApp.travel_elevator','DungeonApp.update_feedback_debug'},
               'rpg/suspend.py': {'make_suspend_data','prepare_suspend_game'},
               'rpg/final_battle.py': set()}
    for name, digest in before['hashes'].items():
        if name not in {*changed, 'data/dungeon.json'}:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    for name, allowed in changed.items():
        current = method_hashes((ROOT/name).read_text(encoding='utf8'))
        old = before['methods'][name]
        case.assertEqual(current.keys() - old.keys(), {'Dungeon.reset_encounter'} if name == 'rpg/dungeon.py' else set(), name)
        case.assertFalse(old.keys() - current.keys(), name)
        for method, digest in old.items():
            if method not in allowed:
                case.assertEqual(current[method], digest, (name,method))
    now = json.loads((ROOT/'data/dungeon.json').read_text(encoding='utf-8-sig'))
    now.pop('encounter_step_ranges')
    old = dict(before['settings'])
    for key in ('encounter_chance','safe_steps','debug_encounter_chance'): old.pop(key)
    case.assertEqual(now, old)
    # Only one durable field is added to the final-battle checkpoint.
    text = (ROOT/'rpg/final_battle.py').read_text(encoding='utf8')
    restored = text.replace('"grace", "encounter_remaining",', '"grace",')
    case.assertIn(before['hashes']['rpg/final_battle.py'], {
        hashlib.sha256(restored.encode()).hexdigest(),
        hashlib.sha256(restored.replace('\n','\r\n').encode()).hexdigest()})
