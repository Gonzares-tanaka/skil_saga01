"""Small shared consumable inventory and data-driven camp services."""
import json

from .content import ROOT


ITEMS = ("POTION", "PHOENIX ASH", "REMEDY")


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
            and 0 <= rules["agi_factor"] <= 1):
        raise ValueError("items.json: RUN設定が不正です")
    if not (type(data["pub_cost"]) is int and 1 <= data["pub_cost"] <= 99
            and 0 <= data["pub_gameplay_weight"] <= 1):
        raise ValueError("items.json: PUB設定が不正です")
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

    def use(self, item, target):
        if item not in ITEMS or self.counts[item] <= 0:
            return False, "道具がありません"
        if item == "REMEDY":
            return False, "今は治す状態異常がありません"
        if item == "POTION":
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
            target.hp = max(1, target.max_hp // 4)
            message = f"{target.name} 復活 HP {target.hp}/{target.max_hp}"
        self.counts[item] -= 1
        return True, message

    def buy(self, item, treasure):
        if item not in ITEMS:
            raise ValueError("不明な道具です")
        price = self.data["items"][item]["price"]
        if self.counts[item] >= 9:
            return False, f"{item} は9個で満杯です"
        if treasure.banked < price:
            return False, "確定した宝が足りません"
        treasure.banked -= price
        self.add(item)
        return True, f"{item} +1 / 宝 -{price}"
