"""Small shared consumable inventory and data-driven camp services."""
import json

from .content import ROOT
from .labels import CURRENCY_NAME
from .statuses import active_statuses, clear_statuses


RETURN_FEATHER = 'return_feather'
LEGACY_ITEMS = ("POTION", "PHOENIX ASH", "REMEDY")
ITEMS = (*LEGACY_ITEMS, RETURN_FEATHER)


def load_items():
    data = json.loads((ROOT / "data/items.json").read_text(encoding="utf-8-sig"))
    for item in ITEMS:
        row = data["items"][item]
        if not (type(row["initial"]) is int and 0 <= row["initial"] <= 9
                and type(row["price"]) is int and 1 <= row["price"] <= 99):
            raise ValueError(f"items.json: {item} の数値が不正です")
    if not (type(data["items"]["POTION"]["heal"]) is int and
            1 <= data["items"]["POTION"]["heal"] <= 999):
        raise ValueError("items.json: POTIONの回復量が不正です")
    rules = data["run"]
    if not (0 < rules["min"] <= rules["base"] <= rules["max"] < 1
            and 0 <= rules["agi_factor"] <= 1
            and 0 <= rules["agi_cap"] <= 0.5):
        raise ValueError("items.json: RUN設定が不正です")
    if not (type(data["pub_cost"]) is int and 1 <= data["pub_cost"] <= 99
            and 0 <= data["pub_gameplay_weight"] <= 1):
        raise ValueError("items.json: PUB設定が不正です")
    if not 0 < data["revive_fraction"] <= 1:
        raise ValueError("items.json: 蘇生HP割合が不正です")
    return data


class Inventory:
    def __init__(self, data=None):
        self.data = data or load_items()
        self.counts = {item: self.data["items"][item]["initial"] for item in ITEMS}

    def add(self, item, count=1):
        if item not in ITEMS or count < 1 or self.counts[item] + count > 9:
            return False
        self.counts[item] += count
        return True

    def revival_hp(self, target):
        return max(1, int(target.max_hp * self.data["revive_fraction"]))

    def use(self, item, target):
        if item not in ITEMS or self.counts[item] <= 0:
            return False, "道具がありません"
        if item == RETURN_FEATHER:
            return False, "帰還の羽根は探索メニューで使います"
        if item == "REMEDY":
            if not target.alive:
                return False, "戦闘不能には使えません"
            if not active_statuses(target):
                return False, "今は治す状態異常がありません"
            clear_statuses(target)
            message = f"{target.name} 状態異常を治療"
        elif item == "POTION":
            if not target.alive:
                return False, "戦闘不能には使えません"
            if target.hp >= target.max_hp:
                return False, "HPは満タンです"
            amount = min(self.data["items"][item]["heal"], target.max_hp - target.hp)
            target.hp += amount
            message = f"{target.name} HP +{amount}"
        else:
            if target.alive:
                return False, "戦闘不能の味方を選んでください"
            target.hp = self.revival_hp(target)
            clear_statuses(target)
            message = f"{target.name} 復活 HP {target.hp}/{target.max_hp}"
        self.counts[item] -= 1
        return True, message

    def buy(self, item, treasure):
        if item not in ITEMS:
            raise ValueError("不明な道具です")
        price = self.data["items"][item]["price"]
        label = self.label(item)
        if self.counts[item] >= 9:
            return False, f"{label} は9個で満杯です"
        if treasure.banked < price:
            return False, f"{CURRENCY_NAME}が足りません"
        treasure.banked -= price
        self.add(item)
        return True, f"{label} +1 / {CURRENCY_NAME} -{price}"

    def label(self, item):
        return self.data['items'][item].get('name', item)

    def description(self, item):
        return {
            'POTION': '味方1人のHPを回復する',
            'PHOENIX ASH': '戦闘不能の味方1人を蘇生する',
            'REMEDY': '味方の状態異常を治療する',
            RETURN_FEATHER: 'ダンジョンから帰還 / 1個消費',
        }[item]
