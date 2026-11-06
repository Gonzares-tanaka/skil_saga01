"""Resource editor changes predate this pass; protect the actual starting files.

Historical pixel snapshots predate the latest editor art. Never regenerate art
to satisfy them. The new pass compares every resource byte to its own baseline.
"""
import hashlib
import json
import sys
from rpg.content import ROOT


def use_alpha_ux_baseline(case):
    """Historical whole-file snapshots give way to the current scoped pass.

    Preserve user-edited PUB text and every asset as received, while allowing
    only the specific UX methods covered by dedicated behavioral tests.
    """
    if (ROOT/'tests/fixtures/alpha_gameplay02_before.json').exists():
        from tests.gameplay_preservation import assert_gameplay_preserved
        assert_gameplay_preserved(case)
        return True
    path=ROOT/'tests/fixtures/alpha_ux01_before.json'
    if not path.exists(): return False
    if sys.platform=='emscripten': return True  # Native packaging checks bytes.
    from tools.snapshot_alpha_ux_methods import method_hashes
    before=json.loads(path.read_text(encoding='utf-8-sig'))
    methods={
        'rpg/models.py': (set(),{'Character.remember_skill','Character.remembered_skill_index'}),
        'rpg/battle.py': ({'Battle.apply_status','Battle._party_action'},set()),
        'rpg/app.py': ({'App.update','App.draw_skills'},set()),
        'rpg/dungeon_app.py': ({'DungeonApp.__init__','DungeonApp.update_opening',
            'DungeonApp.draw_title_menu','DungeonApp.update','DungeonApp.draw',
            'DungeonApp.draw_menu','DungeonApp.sync_scene_audio'},
            {'DungeonApp.title_options','DungeonApp.refresh_suspend','DungeonApp.can_suspend_game',
             'DungeonApp.update_suspend_io','DungeonApp.activate_suspended_game',
             'DungeonApp.update_suspend_confirm','DungeonApp.draw_suspend'}),
    }
    allowed={*methods,'tools/build_web.py','dist/index.html'}
    for name,digest in before['hashes'].items():
        if name not in allowed:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
    for name,(changed,added) in methods.items():
        current=method_hashes((ROOT/name).read_text(encoding='utf8'))
        old=before['methods'][name]
        case.assertEqual(current.keys(),old.keys()|added,name)
        for method,digest in old.items():
            if method not in changed: case.assertEqual(current[method],digest,(name,method))
    return True


def assert_resource_unchanged(case,name,digest):
    if (name.endswith(('.pyxres','.pyxpal')) and
            (ROOT/'tests/fixtures/b15_elevator_right_assets.json').exists()):
        from tests.ui_phase6a_preservation import protected_hashes
        case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),protected_hashes()[name],name)
        return
    if name == 'game.pyxres' and (ROOT/'tests/fixtures/alpha_gameplay02_before.json').exists():
        from tests.gameplay_preservation import assert_gameplay_resource
        assert_gameplay_resource(case)
        return
    ux_before=ROOT/'tests/fixtures/alpha_ux01_before.json'
    if ux_before.exists():
        current=json.loads(ux_before.read_text(encoding='utf-8-sig'))['hashes'].get(name)
        if current is not None:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),current,name)
            return
    omen_before=ROOT/'tests/fixtures/omen_music_before.json'
    if name.endswith(('.pyxres','.pyxpal')) and omen_before.exists():
        # The user edited effects in Editor after the logo pass. The offering
        # cue lives in a NEW file; every existing asset must stay byte-identical.
        current=json.loads(omen_before.read_text(encoding='utf8'))['hashes'][name]
        case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),current,name)
        return
    title_before=ROOT/'tests/fixtures/title_logo_before.json'
    if name=='game.pyxres' and title_before.exists():
        # The user added their logo in Editor after the earlier audio phases.
        # This task is read-only for ALL resource bytes, including that new art.
        current=json.loads(title_before.read_text(encoding='utf8'))['hashes'][name]
        case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),current,name)
        return
    audio_before=ROOT/'tests/fixtures/audio_pass02_before.json'
    if name=='game.pyxres' and audio_before.exists():
        from tools.audio_pass02_resource import assert_protected_resource
        assert_protected_resource(ROOT/name,json.loads(audio_before.read_text(encoding='utf8')))
    else:
        case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)


def assert_historical_audio(case,before,allowed_sounds,allowed_musics):
    """Audio semantics survive later user Editor art/save-format changes."""
    from tools.audio_pass02_resource import read_resource
    current=read_resource(ROOT/'game.pyxres')
    for kind,allowed in (('sounds',allowed_sounds),('musics',allowed_musics)):
        case.assertEqual(len(current[kind]),len(before['scene'][kind]))
        for index,row in enumerate(current[kind]):
            if index not in allowed: case.assertEqual(row,before['scene'][kind][index],(kind,index))


def use_current_asset_baseline(case):
    if sys.platform == 'emscripten':
        return True  # Exact Web resource payloads are checked by the packager.
    path = ROOT/'tests/fixtures/enemy_balance_before.json'
    if not path.exists(): return False  # Historical suites can still use their own snapshots.
    baseline = json.loads(path.read_text(encoding='utf8'))
    resources = {name: digest for name, digest in baseline['hashes'].items()
                 if name.endswith(('.pyxres', '.pyxpal'))}
    case.assertTrue(resources)
    for name, digest in resources.items():
        assert_resource_unchanged(case,name,digest)
    return True
