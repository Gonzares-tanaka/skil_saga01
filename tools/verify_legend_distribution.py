"""Final Web, Pixel2 and diagnostic content/syntax checks; SAVE excluded."""
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tests'))
from test_legend_skill_presentation import MAPPING
from test_rare_skill_presentation import MAPPING as RARE_MAPPING


def main(output=None):
    payload = base64.b64decode(re.search(r'base64: "([^"]+)"', (ROOT / 'dist/game.html').read_text(encoding='utf8'))[1])
    results = {}
    for label, path, prefix in (
            ('web', io.BytesIO(payload), 'spark_web/'),
            ('pixel2', ROOT / 'verification/packages/skill_seekers_gkd.zip', 'Skill_Seekers/'),
            ('diagnostic', ROOT / 'verification/packages/skill_seekers_gkd_diagnostic.zip', 'Skill_Seekers/')):
        with zipfile.ZipFile(path) as z:
            count = 0
            for name in z.namelist():
                assert not any(part in ('save', '__pycache__', '.venv', 'tests') for part in Path(name).parts)
                if not name.startswith(prefix): continue
                relative = name[len(prefix):]
                if not relative or relative.startswith('.') or relative in ('diagnostic_main.py', 'diagnostic_config.json'): continue
                assert z.read(name) == (ROOT / relative).read_bytes(), (label, relative)
                if relative.endswith('.py'):
                    ast.parse(z.read(name).decode('utf8'), filename=relative, feature_version=(3, 11))
                count += 1
            rows = json.loads(z.read(prefix + 'data/skills.json'))
            assert len(rows) == 62
            assert {r['id']: r['presentation_id'] for r in rows if r['rarity'] == 'LEGEND'} == MAPPING
            assert {r['id']: r['presentation_id'] for r in rows if r['rarity'] == 'RARE'} == RARE_MAPPING
            assert json.loads(z.read(prefix + 'data/statuses.json'))['paralyze']['skip_chance'] == .5
            if label == 'pixel2':
                assert z.read('Skill_Seekers.sh') == (ROOT / 'tools/run_gkd.sh').read_bytes().replace(b'\r\n', b'\n')
            if label == 'diagnostic':
                assert z.read(prefix + 'diagnostic_main.py') == (ROOT / 'tools/gkd_diagnostic.py').read_bytes()
                ast.parse(z.read(prefix + 'diagnostic_main.py').decode('utf8'), feature_version=(3, 11))
                assert json.loads(z.read(prefix + 'diagnostic_config.json')) == dict(
                    battle_start_audio=True, skip_transition=False, watchdog_seconds=20)
            results[label] = dict(entries=len(z.namelist()), matching_game_files=count,
                                  roster=62, legends=8, rares=20, save_excluded=True)
        if not isinstance(path, io.BytesIO):
            results[label]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output or ROOT / 'verification/legend_presentation_packages.json').write_text(
        json.dumps(results, indent=2) + '\n', encoding='utf8')
    print('PASS:', results)


if __name__ == '__main__': main()
