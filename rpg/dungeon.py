"""Exploration state. Every terrain/event position comes from Tilemap.pget()."""
from collections import deque
import json
import math

from .content import ROOT
from .models import Enemy
from .treasure import Treasure
from .tiles import (BOSS_FLOORS, MAP_IMAGE_BANK, PASSABLE, TILE_FLOOR,
                    TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_CHEST, TILE_ENTRANCE,
                    TILE_CHEST_OPEN, TILE_BOSS, TILE_BOSS_CLEAR)


def load_dungeon_settings():
    return json.loads((ROOT / "data" / "dungeon.json").read_text(encoding="utf-8-sig"))


class Dungeon:
    def __init__(self, tilemaps, enemy_data, settings, rng, treasure=None):
        self.maps = list(tilemaps)
        self.settings, self.rng = settings, rng
        self.enemies = {row["id"]: row for row in enemy_data}
        if len(self.enemies) != len(enemy_data):
            raise ValueError("enemies.json: 敵のidが重複しています。")
        self.width, self.height = settings["width"], settings["height"]
        self.validate_settings()
        self.validate_maps()
        self.floor = 0
        self.x, self.y = self.find(0, TILE_ENTRANCE)
        self.opened = set()
        self.chest_loot = {}
        self.potions = settings["items"]["initial_potions"]
        self.treasure = treasure if treasure is not None else Treasure()
        self.steps = 0
        self.grace = settings["safe_steps"]
        self.defeated_bosses = set()

    @property
    def cleared(self):
        return BOSS_FLOORS[-1] in self.defeated_bosses

    @property
    def spark_multiplier(self):
        return self.settings["spark_multipliers"][self.floor]

    @property
    def boss_data(self):
        return self.enemies[self.settings["floors"][self.floor]["boss_id"]]

    def defeat_boss(self):
        if self.floor not in BOSS_FLOORS:
            raise ValueError("この階にボスはいません。")
        self.defeated_bosses.add(self.floor)
        return self.boss_data["after_message"]

    def validate_settings(self):
        def require(ok, message):
            if not ok:
                raise ValueError("dungeon.json: " + message)
        def number(v, lo, hi):
            return type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi
        max_width = min(tilemap.width for tilemap in self.maps)
        max_height = min(tilemap.height for tilemap in self.maps)
        require(type(self.width) is int and 8 <= self.width <= max_width,
                f"widthは8～{max_width}")
        require(type(self.height) is int and 8 <= self.height <= max_height,
                f"heightは8～{max_height}")
        for key in ("encounter_chance", "debug_encounter_chance"):
            require(number(self.settings[key], 0, 1), key + "は0～1")
        require(type(self.settings["safe_steps"]) is int and 0 <= self.settings["safe_steps"] <= 20, "safe_stepsは0～20")
        items = self.settings["items"]
        require(type(items["max_potions"]) is int and 1 <= items["max_potions"] <= 99, "max_potionsは1～99")
        require(type(items["initial_potions"]) is int and 0 <= items["initial_potions"] <= items["max_potions"], "初期ポーション数が無効")
        require(type(items["potion_heal"]) is int and 1 <= items["potion_heal"] <= 9999, "potion_healは1～9999")
        require(number(items["chest_potion_chance"], 0, 1), "宝箱の確率は0～1")
        require(len(self.maps) == len(self.settings["floors"]) == 15, "マップとfloorsは15階分必要")
        multipliers = self.settings["spark_multipliers"]
        require(len(multipliers) == 15 and all(number(v, 0.01, 100) for v in multipliers), "spark_multipliersは15階分の正の倍率")
        require(multipliers == sorted(multipliers), "spark_multipliersは浅い順に同値か増加")
        for floor, row in enumerate(self.settings["floors"]):
            if floor in BOSS_FLOORS:
                boss = self.enemies.get(row.get("boss_id"), {})
                require(boss.get("boss") and boss.get("floor") == floor + 1, "ボスIDまたは出現floorが無効")
                for key in ("message", "after_message"):
                    lines = boss.get(key)
                    require(isinstance(lines, list) and bool(lines) and all(isinstance(s, str) and s.strip() for s in lines), "ボスの" + key + "は空でない文章の配列")
                continue
            require(len(row["enemy_ids"]) == len(row["weights"]) > 0, "敵候補と重みの数が不一致")
            require(all(i in self.enemies and not self.enemies[i].get("boss") for i in row["enemy_ids"]), "通常敵IDが無効")
            require(all(number(w, 0.001, 10000) for w in row["weights"]), "敵の重みは正の数")
            require(len(row["count"]) == 2 and all(type(v) is int for v in row["count"]) and 1 <= row["count"][0] <= row["count"][1] <= 3, "敵数は1～3")
            require(all(number(row[k], 0.1, 20) for k in ("hp_scale", "power_scale")), "敵の倍率が無効")

    def tile(self, floor, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        return tuple(self.maps[floor].pget(x, y))

    def positions(self, floor, tile):
        return [(x, y) for y in range(self.height) for x in range(self.width)
                if self.tile(floor, x, y) == tile]

    def find(self, floor, tile):
        positions = self.positions(floor, tile)
        if len(positions) != 1:
            raise ValueError(f"{floor + 1}F: タイル{tile}を1個配置してください。")
        return positions[0]

    def validate_maps(self):
        self.boss_positions = {}
        for floor, tilemap in enumerate(self.maps):
            if tilemap.imgsrc != MAP_IMAGE_BANK:
                raise ValueError(f"{floor + 1}FのImage Bankは1にしてください。")
            start = self.find(floor, TILE_ENTRANCE if floor == 0 else TILE_STAIRS_UP)
            if floor < len(self.maps) - 1:
                self.find(floor, TILE_STAIRS_DOWN)
            if floor in BOSS_FLOORS:
                self.boss_positions[floor] = self.find(floor, TILE_BOSS)
            if self.positions(floor, TILE_ENTRANCE) and floor != 0:
                raise ValueError("入口は1Fに配置してください。")
            if (floor == 0 and self.positions(floor, TILE_STAIRS_UP)) or (floor == 14 and self.positions(floor, TILE_STAIRS_DOWN)):
                raise ValueError("B1Fの上り階段・B15Fの下り階段は不要です。")
            if floor not in BOSS_FLOORS and self.positions(floor, TILE_BOSS):
                raise ValueError("ボスはB5F/B10F/B15Fに配置してください。")
            seen, queue = {start}, deque([start])
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    point = x + dx, y + dy
                    if point not in seen and self.tile(floor, *point) in PASSABLE:
                        seen.add(point)
                        queue.append(point)
            events = {TILE_CHEST, TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_ENTRANCE, TILE_BOSS}
            for y in range(self.height):
                for x in range(self.width):
                    if self.tile(floor, x, y) in events and (x, y) not in seen:
                        raise ValueError(f"{floor + 1}F ({x},{y}) のイベントへ通路がつながっていません。")

    def enter(self):
        if self.cleared:
            raise ValueError("このダンジョンはクリア済みです。")
        self.floor = 0
        self.x, self.y = self.find(0, TILE_ENTRANCE)
        self.opened.clear()
        self.chest_loot.clear()
        self.grace = self.settings["safe_steps"]

    def change_floor(self, floor):
        if not 0 <= floor < len(self.maps):
            return "", "これ以上進めません"
        if floor > self.floor:
            for gate in BOSS_FLOORS[:-1]:
                if floor > gate and gate not in self.defeated_bosses:
                    return "", f"B{gate + 1}Fのボスを倒す必要がある"
        arrival = TILE_STAIRS_UP if floor > self.floor else TILE_STAIRS_DOWN
        point = self.find(floor, arrival)  # Resolve before changing state.
        self.floor = floor
        self.x, self.y = point
        self.grace = self.settings["safe_steps"]
        return "stairs", f"B{floor + 1}Fに到着"

    def debug_floor(self, floor):
        self.floor = max(0, min(len(self.maps) - 1, floor))
        self.x, self.y = self.find(self.floor, TILE_ENTRANCE if self.floor == 0 else TILE_STAIRS_UP)
        self.grace = self.settings["safe_steps"]

    def interact(self):
        tile = self.tile(self.floor, self.x, self.y)
        if tile == TILE_ENTRANCE:
            return "base", "入口から帰還した"
        if tile == TILE_STAIRS_UP:
            return self.change_floor(self.floor - 1)
        if tile == TILE_STAIRS_DOWN:
            return self.change_floor(self.floor + 1)
        if tile == TILE_BOSS:
            if self.floor not in self.defeated_bosses:
                return "boss", self.boss_data["name"]
            return "", "この階のボスは撃破済み"
        if tile == TILE_CHEST:
            key = self.floor, self.x, self.y
            if key in self.opened:
                return "", "宝箱は空です"
            if key not in self.chest_loot:
                self.chest_loot[key] = "potion" if self.rng.random() < self.settings["items"]["chest_potion_chance"] else "treasure"
            if self.chest_loot[key] == "potion":
                if self.potions >= self.settings["items"]["max_potions"]:
                    return "", "薬が満杯。宝箱は残した"
                self.potions += 1
                message = "ポーションを1個入手"
            else:
                self.treasure.unbanked += 1
                message = "未確定の宝 +1 / 帰還で確定"
            self.opened.add(key)
            return "chest", message
        return "", "特に何もありません"

    def move(self, dx, dy, debug=False):
        if abs(dx) + abs(dy) != 1:
            return "", ""
        x, y = self.x + dx, self.y + dy
        if self.tile(self.floor, x, y) not in PASSABLE:
            return "", "壁で進めません"
        self.x, self.y = x, y
        self.steps += 1
        tile = self.tile(self.floor, x, y)
        if tile not in (TILE_FLOOR, TILE_CHEST_OPEN, TILE_BOSS_CLEAR):
            return self.interact()
        if self.floor in BOSS_FLOORS:
            return "", ""
        if self.grace and not debug:
            self.grace -= 1
            return "", ""
        chance = self.settings["debug_encounter_chance" if debug else "encounter_chance"]
        if self.rng.random() < chance:
            return "battle", "敵と遭遇した!"
        return "", ""

    def make_enemies(self, boss=False):
        profile = self.settings["floors"][self.floor]
        if boss:
            rows = [self.boss_data]
            hp_scale = power_scale = 1
        else:
            ids = self.rng.choices(profile["enemy_ids"], profile["weights"], k=self.rng.randint(*profile["count"]))
            rows = [self.enemies[i] for i in ids]
            hp_scale, power_scale = profile["hp_scale"], profile["power_scale"]
        return [Enemy(row["name"] + ("" if boss else f" {chr(65 + i)}"),
                      max(1, round(row["max_hp"] * hp_scale)), max(1, round(row["str"] * power_scale)),
                      row["agi"], max(1, round(row["int"] * power_scale)), tuple(row["sprite"]), row["magic_chance"],
                      defense=row.get("defense", 0), magic_defense=row.get("magic_defense", 0))
                for i, row in enumerate(rows)]

    def use_potion(self, character):
        if self.potions == 0:
            return "ポーションがありません"
        if not character.alive:
            return "戦闘不能は拠点で回復します"
        if character.hp == character.max_hp:
            return "HPは満タンです"
        heal = min(self.settings["items"]["potion_heal"], character.max_hp - character.hp)
        character.hp += heal
        self.potions -= 1
        return f"{character.name} HP +{heal}"
