"""Record current economy, safe landings and exact protected resource bytes."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rpg.content import load_content
from rpg.battle import Session
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.map_resources import load_maps
from rpg.elevator import arrival_point, b15_elevator_point
from rpg.items import load_items
from rpg.tiles import TILE_CHEST, TILE_RARE_CHEST
from tests.gameplay_preservation import assert_gameplay_preserved


def main():
    import pyxel
    pyxel.init(160, 120, headless=True)
    session = Session(*load_content(), seed=3)
    dungeon = Dungeon(load_maps(), session.enemy_data, load_dungeon_settings(), session.rng)
    dungeon.defeated_bosses.update((4, 9, 14))
    dungeon.finale.guardians_defeated = dungeon.finale.demon_defeated = True
    assert_gameplay_preserved(unittest.TestCase())
    areas = []
    for area in range(3):
        normal = sum(len(dungeon.positions(f, TILE_CHEST)) for f in range(area*5, area*5+5))
        rare = sum(len(dungeon.positions(f, TILE_RARE_CHEST)) for f in range(area*5, area*5+5))
        # All three areas share the received reward table; only count authored boxes.
        table = dungeon.exploration_settings['CHEST_REWARD_TABLE']
        def mean(kind):
            rows = table[kind]
            return sum(r['weight']*r.get('amount', 1) for r in rows if r['kind']=='TREASURE')/sum(r['weight'] for r in rows)
        areas.append(dict(area=area+1, normal_chests=normal, rare_chests=rare,
            expected_trz_if_all_boxes_opened=round(normal*mean('NORMAL')+rare*mean('RARE'), 2),
            normal_chest_expected_trz=mean('NORMAL'), rare_chest_expected_trz=mean('RARE')))
    result = dict(protected_gameplay_assets_verified=True,
        icon=dict(resource='game.pyxres', bank=2, source=[80,0], size=[16,16],
                  screen=[92,92], colors=[0,1,2,3]),
        arrivals={str(f+1):list(arrival_point(dungeon,f)) for f in (5,10,14)},
        shop={k:v['price'] for k,v in load_items()['items'].items()},
        quests=json.loads((ROOT/'data/quests.json').read_text(encoding='utf-8-sig'))['rewards'],
        areas=areas,
        restore_costs={rarity:sorted({s.relearn_cost for s in session.skills.values()
                      if s.rarity==rarity and s.can_relearn})
                      for rarity in ('BASIC','COMMON','UNCOMMON','RARE','LEGEND')},
        no_encounter_rate_changes=True, all_existing_sound_blocks_byte_identical=True,
        all_tilemaps_byte_identical=True, only_new_icon_pixels_changed=True)
    (ROOT/'verification/alpha_gameplay02_audit.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
