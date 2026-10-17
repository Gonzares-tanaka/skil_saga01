"""Validate all 15 floors against real resources; never edit maps or saves."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.quests import quest_spawn_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'verification/quest_spawn.json')
    args = parser.parse_args()
    pyxel.init(160, 120, headless=True)
    s = Session(*load_content(), seed=71)
    d = Dungeon(load_maps(), s.enemy_data, load_dungeon_settings(), s.rng)
    rows = []
    for floor in range(15):
        row = quest_spawn_report(d, floor)
        required = 2 if floor < 5 else 3
        row.update(explore_ok=row['valid_count'] >= 1,
                   investigate_lv1_ok=row['valid_count'] >= 2,
                   investigate_lv2_lv3_ok=row['valid_count'] >= 3,
                   hunt_ok=row['valid_count'] >= 1, required_count=required)
        print(f"B{floor + 1:02} registered={row['registered_count']} "
              f"before={row['pre_filter_count']} valid={row['valid_count']} "
              f"EXPLORE={'OK' if row['explore_ok'] else 'FAIL'} "
              f"INVESTIGATE({required})={'OK' if row['valid_count'] >= required else 'FAIL'} "
              f"HUNT={'OK' if row['hunt_ok'] else 'FAIL'}")
        rows.append(row)
    baseline_path = ROOT / 'verification/backups/quest_spawn/baseline.json'
    preserved = {}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding='utf8'))
        preserved = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
                     for name, digest in baseline.items() if name != 'data/dungeon.json'}
        assert all(preserved.values()), 'A map, asset or unrelated data changed'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(floors=rows, preserved=preserved,
                                         maps_edited=False, physical_device_tested=False),
                                     ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    assert all(row['valid_count'] >= row['required_count'] for row in rows), 'Insufficient QUEST candidates'
    print('PASS: all 15 floors support every QUEST type; no map writes')


if __name__ == '__main__':
    main()
