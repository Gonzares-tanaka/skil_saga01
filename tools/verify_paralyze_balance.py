"""Verify the one-value balance change and both rebuilt distribution payloads."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_paralyze_balance import sample_turns


def main():
    before = json.loads((ROOT / 'verification/paralyze_balance_before.json').read_text(encoding='utf-8-sig'))
    original = before['statuses']
    assert original['paralyze']['skip_chance'] == .35
    expected = json.loads(json.dumps(original))
    expected['paralyze']['skip_chance'] = .5
    current = json.loads((ROOT / 'data/statuses.json').read_text(encoding='utf8'))
    assert current == expected, 'Only paralyze.skip_chance may change'
    protected = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
                 for name, digest in before['hashes'].items() if name != 'data/statuses.json'}
    assert all(protected.values()), [name for name, ok in protected.items() if not ok]
    html = (ROOT / 'dist/game.html').read_text(encoding='utf8')
    payload = base64.b64decode(re.search(r'base64: "([^"]+)"', html)[1])
    packages = {}
    for label, archive_path, prefix in (
            ('web', io.BytesIO(payload), 'spark_web/'),
            ('pixel2', ROOT / 'verification/packages/skill_seekers_gkd.zip', 'Skill_Seekers/')):
        with zipfile.ZipFile(archive_path) as archive:
            checked = 0
            for name in archive.namelist():
                assert not any(part in ('save', '__pycache__', '.venv', 'tests') for part in Path(name).parts)
                if name == 'Skill_Seekers.sh':
                    assert archive.read(name) == (ROOT / 'tools/run_gkd.sh').read_bytes().replace(b'\r\n', b'\n')
                elif name.startswith(prefix) and not name.endswith('/'):
                    relative = name[len(prefix):]
                    if relative.startswith('.'):
                        continue  # Official exporter startup script.
                    assert archive.read(name) == (ROOT / relative).read_bytes(), (label, relative)
                    checked += 1
            assert json.loads(archive.read(prefix + 'data/statuses.json')) == expected
            packages[label] = dict(entries=len(archive.namelist()), source_files_matched=checked,
                                   paralyze_skip_chance=.5, save_excluded=True)
    samples = {side: sample_turns(side) for side in ('party', 'enemy')}
    assert all(.48 <= sample['rate'] <= .52 for sample in samples.values()), samples
    report = dict(old_skip_chance=.35, new_skip_chance=.5, duration=3,
                  only_balance_value_changed=True, protected_files=protected,
                  protected_count=len(protected), samples=samples, packages=packages,
                  pixel2_sha256=hashlib.sha256((ROOT / 'verification/packages/skill_seekers_gkd.zip').read_bytes()).hexdigest(),
                  physical_gkd_tested=False)
    (ROOT / 'verification/paralyze_balance.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('PASS:', len(protected), 'protected files; samples:', samples, '; packages:', packages)


if __name__ == '__main__':
    main()
