"""Current authorization: one icon, one shop item and narrow travel UI methods."""
from functools import lru_cache
import hashlib
import json
from rpg.content import ROOT
from tools.audio_pass02_resource import read_resource, raw_snapshot
from tools.snapshot_alpha_ux_methods import method_hashes


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/alpha_gameplay02_before.json').read_text(encoding='utf8'))


def assert_gameplay_resource(case):
    if (ROOT/'tests/fixtures/alpha_encounter03_before.json').exists():
        from tests.encounter_preservation import assert_encounter_resource
        assert_encounter_resource(case)
        return
    before = baseline()
    now = read_resource(ROOT/'game.pyxres')
    old = before['scene']
    for key in old.keys() | now.keys():
        if key != 'images':
            case.assertEqual(now[key], old[key], key)
    for bank in range(3):
        n, o = now['images'][bank], old['images'][bank]
        case.assertEqual((n['width'], n['height']), (o['width'], o['height']))
        if bank != 2:
            case.assertEqual(n, o, bank)
            continue
        # Resource rows elide trailing zeroes. Compare actual pixel values.
        for y in range(n['height']):
            nr = n['data'][y] if y < len(n['data']) else []
            row = o['data'][y] if y < len(o['data']) else []
            for x in range(n['width']):
                nv = nr[x] if x < len(nr) else 0
                ov = row[x] if x < len(row) else 0
                if 80 <= x < 96 and y < 16:
                    case.assertEqual(ov, 0)
                    case.assertIn(nv, (0, 1, 2, 3))
                else:
                    case.assertEqual(nv, ov, (bank, x, y))
    raw = raw_snapshot(ROOT/'game.pyxres')
    case.assertEqual(raw['other_entries'], before['raw']['other_entries'])
    case.assertEqual(raw['blocks'].keys(), before['raw']['blocks'].keys())
    for key, digest in before['raw']['blocks'].items():
        if key != 'images:2':
            case.assertEqual(raw['blocks'][key], digest, key)


def assert_gameplay_preserved(case):
    if (ROOT/'tests/fixtures/alpha_encounter03_before.json').exists():
        from tests.encounter_preservation import assert_encounter_preserved
        assert_encounter_preserved(case)
        return
    before = baseline()
    changed = {
        'rpg/dungeon_app.py': {'DungeonApp.__init__', 'DungeonApp.handle_event',
            'DungeonApp.sync_scene_audio', 'DungeonApp.update', 'DungeonApp.draw',
            'DungeonApp.draw_camp', 'DungeonApp.draw_explore', 'DungeonApp.draw_items',
            'DungeonApp.draw_shop', 'DungeonApp.update_camp_resources'},
        'rpg/dungeon.py': {'Dungeon.defeat_boss'},
        'rpg/items.py': {'Inventory.use', 'Inventory.buy'},
        'rpg/save.py': {'migrate_save_data'},
    }
    added = {
        'rpg/dungeon_app.py': {'DungeonApp.travel_elevator', 'DungeonApp.safe_return',
            'DungeonApp.can_use_return_feather', 'DungeonApp.use_return_feather',
            'DungeonApp.update_travel', 'DungeonApp.draw_travel'},
        'rpg/items.py': {'Inventory.label'},
    }
    allowed = {*changed, 'rpg/hub.py', 'game.pyxres', 'data/items.json', 'dist/index.html'}
    for name, digest in before['hashes'].items():
        if name not in allowed:
            case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest, name)
    for name in changed:
        now = method_hashes((ROOT/name).read_text(encoding='utf8'))
        old = before['methods'][name]
        case.assertEqual(now.keys(), old.keys() | added.get(name, set()), name)
        for method, digest in old.items():
            if method not in changed[name]:
                case.assertEqual(now[method], digest, (name, method))
    items = json.loads((ROOT/'data/items.json').read_text(encoding='utf-8-sig'))
    items['items'].pop('return_feather')
    # Fixed original prices and all other rules are preserved explicitly.
    case.assertEqual(items, {'items': {'POTION': {'initial': 2, 'price': 1, 'heal': 30},
        'PHOENIX ASH': {'initial': 0, 'price': 4}, 'REMEDY': {'initial': 0, 'price': 2}},
        'run': {'base': .15, 'agi_factor': .005, 'agi_cap': .15, 'min': .10, 'max': .30},
        'revive_fraction': .25, 'pub_cost': 1, 'pub_gameplay_weight': .7})
    assert_gameplay_resource(case)
