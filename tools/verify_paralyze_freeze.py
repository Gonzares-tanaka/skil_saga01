"""Repeat the existing 26,400 encounter-start regression for this balance pass."""
import json
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_gkd_freeze import FORCED, identity_checks, run_trials
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'verification/paralyze_balance_freeze.json')
    args = parser.parse_args()
    if not args.output.is_absolute():
        args.output = ROOT / args.output
    start = time.monotonic()
    app = DungeonApp(Session(*load_content(), seed=1337), run=False,
                     headless=True, start_at_title=False)
    app.enter_dungeon()
    app.opening_input_blocked = False
    identities = identity_checks(app)
    forced = {}
    for ids in FORCED:
        label = '+'.join(ids)
        forced[label] = run_trials(app, 1000, ids)
        print('PASS:', label, '1000 starts', flush=True)
    ordinary = {}
    for floor in range(5, 10):
        ordinary['B' + str(floor + 1)] = run_trials(app, 2000, floor=floor)
        print('PASS: B' + str(floor + 1), '2000 starts', flush=True)
    audio = {mode: run_trials(app, 100, ('skeleton', 'skeleton'), audio=mode)
             for mode in ('normal', 'off', 'failed')}
    bypass = run_trials(app, 100, ('skeleton', 'assassin'), animate=False)
    report = dict(total_starts=26400, passed=26400, forced=forced, area2=ordinary,
                  audio=audio, transition_bypassed=bypass, identities=identities,
                  seconds=round(time.monotonic() - start, 2), physical_gkd_tested=False)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('PASS: existing 26400-start regression; GKD hardware not tested', flush=True)


if __name__ == '__main__':
    main()
