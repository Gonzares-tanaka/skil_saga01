"""Resource editor changes predate this pass; protect the actual starting files.

Historical pixel snapshots predate the latest editor art. Never regenerate art
to satisfy them. The new pass compares every resource byte to its own baseline.
"""
import hashlib
import json
import sys
from rpg.content import ROOT


def assert_resource_unchanged(case,name,digest):
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
