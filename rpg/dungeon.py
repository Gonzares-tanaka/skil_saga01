"""Exploration state. Every terrain/event position comes from Tilemap.pget()."""
from collections import Counter, deque
import json
import math

from .content import ROOT
from .models import Enemy
from .labels import CURRENCY_NAME
from .treasure import Treasure
from .exploration import load_exploration_settings
from .items import Inventory
from .finale import FinaleProgress
from .tiles import (BOSS_FLOORS, MAP_IMAGE_BANK, PASSABLE, FLOOR_TILES, TILE_FLOOR,
                    TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_CHEST, TILE_ENTRANCE,
                    TILE_CHEST_OPEN, TILE_BOSS, TILE_BOSS_CLEAR,
                    TILE_RARE_CHEST, TILE_POISON, TILE_PIT, PIT_TILES, TILE_HEAL_POINT,
                    TILE_QUEST, TILE_SWITCH, TILE_SWITCH_ON, TILE_DOOR, TILE_DOOR_OPEN,
                    LORE_TILES, TILE_GUARDIAN, TILE_WARNING)


def load_dungeon_settings():
    return json.loads((ROOT / "data" / "dungeon.json").read_text(encoding="utf-8-sig"))


class Dungeon:
    def __init__(self, tilemaps, enemy_data, settings, rng, treasure=None, inventory=None):
        self.maps = list(tilemaps)
        self.settings, self.rng = settings, rng
        self.exploration_settings = load_exploration_settings()
        self.last_reward = None
        self.enemies = {row["id"]: row for row in enemy_data}
        if len(self.enemies) != len(enemy_data):
            raise ValueError("enemies.json: 敵のidが重複しています。")
        self.width, self.height = settings["width"], settings["height"]
        self.finale = FinaleProgress()
        self.validate_settings()
        self.validate_maps()
        self.floor = 0
        self.x, self.y = self.find(0, TILE_ENTRANCE)
        self.opened = set()
        self.activated_switches = set()  # Floor IDs, retained until the next expedition.
        self.chest_loot = {}
        self.inventory = inventory if inventory is not None else Inventory()
        self.treasure = treasure if treasure is not None else Treasure()
        self.steps = 0
        self.grace = settings["safe_steps"]
        self.defeated_bosses = set()

    @property
    def cleared(self):
        return BOSS_FLOORS[-1] in self.defeated_bosses

    @property
    def potions(self):
        return self.inventory.counts["POTION"]

    @potions.setter
    def potions(self, value):
        self.inventory.counts["POTION"] = value

    @property
    def spark_multiplier(self):
        return self.settings["spark_multipliers"][self.floor]

    @property
    def boss_data(self):
        return self.enemies[self.settings["floors"][self.floor]["boss_id"]]

    def defeat_boss(self):
        if self.floor not in BOSS_FLOORS:
            raise ValueError("この階にボスはいません。")
        if self.floor == 14:
            self.finale.claim_amrita()
            self.defeated_bosses.add(self.floor)
            return self.finale.data['demon_after']
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
        require(len(self.maps) == len(self.settings["floors"]) == 15, "マップとfloorsは15階分必要")
        multipliers = self.settings["spark_multipliers"]
        require(len(multipliers) == 15 and all(number(v, 0.01, 100) for v in multipliers), "spark_multipliersは15階分の正の倍率")
        require(multipliers == sorted(multipliers), "spark_multipliersは浅い順に同値か増加")
        for floor, row in enumerate(self.settings["floors"]):
            width, height = self.map_bounds(floor)
            require(type(width) is int and 8 <= width <= self.maps[floor].width,
                    f'{floor + 1}F: widthはTilemap内の8以上の整数です')
            require(type(height) is int and 8 <= height <= self.maps[floor].height,
                    f'{floor + 1}F: heightはTilemap内の8以上の整数です')
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
        for ident in self.finale.data['guardian_ids']:
            row = self.enemies.get(ident, {})
            require(row.get('boss') and row.get('floor') == 15, '守護者はfloor 15のboss敵が必要です')

    def map_bounds(self, floor):
        profile = self.settings['floors'][floor]
        return profile.get('width', self.width), profile.get('height', self.height)

    def tile(self, floor, x, y):
        width, height = self.map_bounds(floor)
        if not (0 <= x < width and 0 <= y < height):
            return None
        return tuple(self.maps[floor].pget(x, y))

    def positions(self, floor, tile):
        width, height = self.map_bounds(floor)
        return [(x, y) for y in range(height) for x in range(width)
                if self.tile(floor, x, y) == tile]

    def floor_appearance(self, floor, x, y):
        """Use a nearby authored floor when covering an event marker."""
        width, height = self.map_bounds(floor)
        for radius in range(1, max(width, height)):
            candidates = [self.tile(floor, px, py)
                          for py in range(max(0, y - radius), min(height, y + radius + 1))
                          for px in range(max(0, x - radius), min(width, x + radius + 1))
                          if max(abs(px - x), abs(py - y)) == radius
                          and self.tile(floor, px, py) in FLOOR_TILES]
            if candidates:
                return Counter(candidates).most_common(1)[0][0]
        return TILE_FLOOR

    def find(self, floor, tile):
        positions = self.positions(floor, tile)
        if len(positions) != 1:
            raise ValueError(f"{floor + 1}F: タイル{tile}を1個配置してください。")
        return positions[0]

    def validate_maps(self):
        self.boss_positions = {}
        for floor, tilemap in enumerate(self.maps):
            width, height = self.map_bounds(floor)
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
            if self.positions(floor, TILE_DOOR) and not self.positions(floor, TILE_SWITCH):
                raise ValueError(f"{floor + 1}F: 閉扉には同じ階のスイッチが必要です。")
            if floor == 14:
                self.find(floor, TILE_GUARDIAN)
                self.find(floor, TILE_WARNING)
                self.find(floor, TILE_HEAL_POINT)
            elif self.positions(floor, TILE_GUARDIAN) or self.positions(floor, TILE_WARNING):
                raise ValueError('守護者・警告地点はB15Fだけに配置してください。')
            for y in range(height):
                for x in range(width):
                    tile = self.tile(floor, x, y)
                    if tile in LORE_TILES and self.finale.lore_at(floor, tile) is None:
                        raise ValueError(f'{floor + 1}F: この石碑タイルには文章がありません。')
            seen = self._reachable(floor, through_stairs=True)
            events = {TILE_CHEST, TILE_RARE_CHEST, TILE_HEAL_POINT, TILE_STAIRS_UP, TILE_STAIRS_DOWN, TILE_ENTRANCE, TILE_BOSS, TILE_QUEST, TILE_SWITCH, TILE_DOOR, TILE_GUARDIAN, TILE_WARNING} | LORE_TILES
            for y in range(height):
                for x in range(width):
                    if self.tile(floor, x, y) in events and (x, y) not in seen:
                        raise ValueError(f"{floor + 1}F ({x},{y}) のイベントへ通路がつながっていません。")

    def reachable(self, floor):
        """Potential quest reachability, including doors unlocked by a reachable switch."""
        return self._reachable(floor)

    def _reachable(self, floor, through_stairs=False):
        start = self.find(floor, TILE_ENTRANCE if floor == 0 else TILE_STAIRS_UP)
        allowed = PASSABLE - PIT_TILES
        if not through_stairs:
            allowed -= {TILE_ENTRANCE, TILE_STAIRS_UP, TILE_STAIRS_DOWN}
        for doors_open in (False, True):
            seen, queue = {start}, deque([start])
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    point = x + dx, y + dy
                    tile = self.tile(floor, *point)
                    if point not in seen and (tile in allowed or doors_open and tile == TILE_DOOR):
                        seen.add(point)
                        queue.append(point)
            if doors_open or not any(self.tile(floor, *p) == TILE_SWITCH for p in seen):
                return seen

    def can_enter(self, floor, x, y):
        tile = self.tile(floor, x, y)
        if tile == TILE_GUARDIAN:
            return self.finale.guardians_defeated
        return tile in PASSABLE or tile == TILE_DOOR and floor in self.activated_switches

    def grant_chest(self, reward):
        """Apply inventory rewards; the field UI applies HP/spark effects once."""
        kind, amount = reward["kind"], reward.get("amount", 1)
        if kind in ("POTION", "PHOENIX ASH", "REMEDY") and self.inventory.counts[kind] + amount > 9:
            return "", f"{kind} は満杯。宝箱は残した"
        self.last_reward = reward
        if kind == "TREASURE":
            self.treasure.unbanked += amount
            message = f"{amount} {CURRENCY_NAME}を手に入れた。未確定 / 帰還で確定"
        elif kind in ("POTION", "PHOENIX ASH", "REMEDY"):
            self.inventory.add(kind, amount)
            message = f"{kind} を{amount}個入手"
        else:
            message = "宝箱は空だった" if kind == "EMPTY" else "宝箱を開けた!"
        return "chest", message

    def fall_in_pit(self):
        self.x, self.y = self.find(self.floor, TILE_ENTRANCE if self.floor == 0 else TILE_STAIRS_UP)
        self.grace = self.settings["safe_steps"]
        return "pit", "落とし穴! この階の入口へ戻された"

    def enter(self, allow_cleared=False):
        if self.cleared and not allow_cleared:
            raise ValueError("このダンジョンはクリア済みです。")
        self.floor = 0
        self.x, self.y = self.find(0, TILE_ENTRANCE)
        self.opened.clear()
        self.activated_switches.clear()
        self.chest_loot.clear()
        self.finale.abort_guardians()
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
        if tile in LORE_TILES:
            return 'lore', self.finale.lore_at(self.floor, tile)
        if tile in (TILE_GUARDIAN, TILE_WARNING):
            if not self.finale.guardians_defeated:
                return 'guardian', self.finale.data['guardian_warning'][0]
            return '', '守護者の気配は消えている'
        if tile == TILE_SWITCH:
            if self.floor in self.activated_switches:
                return "", "スイッチはON。扉は開いている"
            self.activated_switches.add(self.floor)
            return "switch", "スイッチON! この階の扉が開いた"
        if tile == TILE_ENTRANCE:
            return "base", "入口から帰還した"
        if tile == TILE_STAIRS_UP:
            return self.change_floor(self.floor - 1)
        if tile == TILE_STAIRS_DOWN:
            return self.change_floor(self.floor + 1)
        if tile == TILE_BOSS:
            if self.floor == 14 and not self.finale.guardians_defeated:
                return 'guardian', self.finale.data['guardian_warning'][0]
            if self.floor not in self.defeated_bosses:
                return "boss", self.boss_data["name"]
            return "", "この階のボスは撃破済み"
        if tile == TILE_HEAL_POINT:
            return "spring", "回復の泉"
        if tile in (TILE_CHEST, TILE_RARE_CHEST):
            key = self.floor, self.x, self.y
            if key in self.opened:
                return "", "宝箱は空です"
            if key not in self.chest_loot:
                rows = self.exploration_settings["CHEST_REWARD_TABLE"]["RARE" if tile == TILE_RARE_CHEST else "NORMAL"]
                self.chest_loot[key] = self.rng.choices(rows, [r["weight"] for r in rows])[0].copy()
            result = self.grant_chest(self.chest_loot[key])
            if result[0]:
                self.opened.add(key)
            return result
        return "", "特に何もありません"

    def move(self, dx, dy, debug=False):
        if abs(dx) + abs(dy) != 1:
            return "", ""
        x, y = self.x + dx, self.y + dy
        if not self.can_enter(self.floor, x, y):
            if self.tile(self.floor, x, y) == TILE_GUARDIAN:
                return 'guardian', self.finale.data['guardian_warning'][0]
            if self.tile(self.floor, x, y) == TILE_DOOR:
                return "", "閉じた扉。同じ階のスイッチを探そう"
            return "", "壁で進めません"
        self.x, self.y = x, y
        self.steps += 1
        tile = self.tile(self.floor, x, y)
        if tile == TILE_POISON:
            return "poison", "毒沼に足を踏み入れた"
        if tile in PIT_TILES:
            return self.fall_in_pit()
        if tile == TILE_SWITCH:
            return "", "スイッチ: Aで操作" if self.floor not in self.activated_switches else "スイッチはON"
        if tile in LORE_TILES:
            return '', '石碑: Aで読む'
        if tile not in FLOOR_TILES and tile not in (TILE_CHEST_OPEN, TILE_BOSS_CLEAR, TILE_QUEST,
                        TILE_DOOR, TILE_DOOR_OPEN, TILE_SWITCH_ON, TILE_GUARDIAN):
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

    def make_enemies(self, boss=False, guardian_index=None):
        profile = self.settings["floors"][self.floor]
        if guardian_index is not None:
            if self.floor != 14 or guardian_index not in (0, 1, 2):
                raise ValueError('守護者はB15Fの3体です。')
            rows = [self.enemies[self.finale.data['guardian_ids'][guardian_index]]]
            boss = True
            hp_scale = power_scale = 1
        elif boss:
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
        return self.inventory.use("POTION", character)[1]
