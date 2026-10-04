"""Editable deep-area story and session progress; no ordinary item inventory."""
import json
from .content import ROOT
from .tiles import LORE_TILES


def load_finale_data():
    data = json.loads((ROOT / 'data' / 'finale.json').read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('finale.json: オブジェクト形式で指定してください。')
    def lines(value):
        return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)
    lore = data.get('lore', {})
    if not isinstance(lore, dict) or not 5 <= len(lore) <= 7:
        raise ValueError('finale.json: 石碑文章は5～7件必要です。')
    used = set()
    for ident, row in lore.items():
        if not isinstance(row, dict):
            raise ValueError('finale.json: 石碑の定義はオブジェクトです: ' + ident)
        coords = row.get('tile', [])
        if not isinstance(coords, list) or len(coords) != 2 or not all(type(v) is int for v in coords):
            raise ValueError('finale.json: 石碑タイルは整数2個です: ' + ident)
        tile = tuple(coords)
        if tile not in LORE_TILES or tile in used or row.get('floor') not in range(11, 15) or not lines(row.get('lines')):
            raise ValueError('finale.json: 石碑の階・タイル・文章が不正です: ' + ident)
        used.add(tile)
    ids = data.get('guardian_ids', [])
    if (not isinstance(ids, list) or len(ids) != 3 or not all(isinstance(v, str) and v.strip() for v in ids)
            or len(set(ids)) != 3):
        raise ValueError('finale.json: 守護者IDは異なる3件が必要です。')
    for key in ('guardian_warning', 'guardian_after', 'demon_after', 'return_locked'):
        if not lines(data.get(key)):
            raise ValueError('finale.json: ' + key + 'は空でない文章の配列です。')
    between = data.get('guardian_between', [])
    if not isinstance(between, list) or len(between) != 2 or not all(lines(v) for v in between):
        raise ValueError('finale.json: 連戦間の文章は2件必要です。')
    return data


class FinaleProgress:
    """All durable Phase 6A flags live here; only NEW GAME creates a new instance."""
    def __init__(self, data=None):
        self.data = data if data is not None else load_finale_data()
        self.guardian_index = None
        self.guardians_defeated = False
        self.demon_defeated = False
        self.has_amrita = False
        self.read_lore = set()

    def start_guardians(self):
        if self.guardians_defeated or self.guardian_index is not None:
            raise ValueError('守護者の連戦は開始できません。')
        self.guardian_index = 0

    def guardian_victory(self):
        if self.guardian_index not in (0, 1, 2):
            raise ValueError('守護者との連戦中ではありません。')
        if self.guardian_index == 2:
            self.guardians_defeated = True
            self.guardian_index = None
            return True
        self.guardian_index += 1
        return False

    def abort_guardians(self):
        # Completed guardians stay defeated; a failed incomplete attempt restarts at #1.
        self.guardian_index = None

    def claim_amrita(self):
        if not self.guardians_defeated:
            raise ValueError('守護者を倒してからデーモンに挑んでください。')
        self.demon_defeated = True
        self.has_amrita = True

    def lore_at(self, floor, tile):
        return next((ident for ident, row in self.data['lore'].items()
                     if row['floor'] == floor + 1 and tuple(row['tile']) == tile), None)

    def read(self, ident):
        self.read_lore.add(ident)
        return self.data['lore'][ident]['lines']
