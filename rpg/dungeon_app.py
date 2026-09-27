"""Small exploration screens around the existing battle UI."""
from collections import deque
import json

import pyxel

from .app import App
from .content import ROOT
from .dungeon import Dungeon, load_dungeon_settings
from .exploration import Exploration
from .text import text, wrap_lines
from .map_resources import load_maps
from .growth import spark_probability
from .growth import growth_bonus
from .labels import EFFECTS, CATEGORIES
from .models import effect_factor, battle_agility
from .sound import play_cue, start_battle_music, stop_battle_music
from .tiles import (DUNGEON_RESOURCE, MAP_IMAGE_BANK, BOSS_FLOORS,
                    TILE_CHEST_OPEN, TILE_BOSS, TILE_BOSS_CLEAR, TILE_SIZE,
                    TILE_FLOOR, TILE_RARE_CHEST, TILE_QUEST)


MAP_X, MAP_Y = 2, 13
MAP_WIDTH = MAP_HEIGHT = 96
PLAYER_WIDTH = PLAYER_HEIGHT = 16
PLAYER_SPRITES = {"up": (64, 0), "down": (80, 0),
                  "right": (96, 0), "left": (112, 0)}


class DungeonApp(App):
    def __init__(self, session, run=True, headless=False):
        if not DUNGEON_RESOURCE.is_file():
            raise ValueError("game.pyxresがありません。同梱リソースを戻してください。")
        super().__init__(session, run=False, headless=headless, battle_on_start=False)
        self.dungeon = Dungeon(load_maps(), session.enemy_data, load_dungeon_settings(), session.rng,
                               session.treasure, session.inventory)
        self.rumors = json.loads((ROOT / "data/pub_messages.json").read_text(encoding="utf-8-sig"))
        self.last_rumor = None
        self.exploration = Exploration(session, self.dungeon)
        self.quest_cursor = self.feedback_cursor = 0
        self.relearn_cursor = self.treasure_cursor = 0
        self.return_lines = []
        self.player_facing = "down"
        self.floor_cursor = self.effect_cursor = self.message_page = 0
        self.menu_cursor = self.item_cursor = self.camp_cursor = self.catalog_cursor = 0
        self.item_kind_cursor = self.shop_cursor = self.pub_cursor = 0
        self.archive_cursor = 0
        self.archive_page = 0
        self.battle = None
        self.battle_is_boss = False
        self.battle_position = None
        self.explore_message = "入口へ戻ると全回復"
        self.enter_camp()
        if run:
            pyxel.run(self.update, self.draw)

    def enter_camp(self, defeated=False, returned=False):
        stop_battle_music()
        quest_failure = []
        if returned:
            self.return_secured = self.session.treasure.secure()
            self.return_lines.extend(self.exploration.return_to_camp(True))
        elif defeated:
            quest_failure = self.exploration.return_to_camp(False)
        for actor in self.session.party:
            actor.recover()
        self.state, self.overlay = "camp", None
        self.camp_cursor = 0
        self.notice_timer = 0
        self.camp_message = "全滅・回復 / 調査はやり直し" if defeated else "全員のHPを回復しました"
        if returned:
            self.state = "return_result"
        elif quest_failure:
            self.show_field_event(quest_failure, return_state="camp")

    def enter_dungeon(self):
        if self.dungeon.cleared:
            # A new trip always starts at B1, even after the clear banner.
            self.dungeon.enter(allow_cleared=True)
            self.exploration.springs.clear()
            self.player_facing = "down"
            self.state, self.notice_timer = "clear", 0
            return
        self.dungeon.enter()
        self.exploration.springs.clear()
        self.player_facing = "down"
        self.state = "explore"
        self.explore_message = "入口から出発した"
        if self.exploration.hint():
            self.show_field_event([self.exploration.hint()])

    def begin_encounter(self, boss=False):
        self.fanfare_started_at = None
        self.fanfare_start_frame = None
        self.battle_position = self.dungeon.floor, self.dungeon.x, self.dungeon.y
        self.battle_is_boss = boss
        self.battle = self.session.next_battle(self.dungeon.make_enemies(boss), recover=False,
                                               spark_multiplier=self.dungeon.spark_multiplier, boss=boss)
        self.notice_timer = 0
        self.log = [self.dungeon.boss_data["name"] + "との決戦!" if boss else "敵と遭遇した!"]
        self.pending = deque()
        self.begin_input()
        if boss:
            stop_battle_music()
        else:
            start_battle_music()

    def finish_results(self):
        if self.session.pending_replacements or self.waiting_for_fanfare():
            return
        stop_battle_music()
        self.trace("RETURN MAP" if self.battle.outcome != "DEFEAT" else "RETURN CAMP")
        if self.battle.outcome == "DEFEAT":
            self.enter_camp(defeated=True)
        elif self.battle_is_boss and self.battle.outcome == "VICTORY":
            self.dungeon.floor, self.dungeon.x, self.dungeon.y = self.battle_position
            self.message_lines = wrap_lines(self.dungeon.defeat_boss(), 36)
            self.state, self.message_page = "boss_after", 0
            self.notice_timer = 0
        else:
            self.state = "explore"
            self.dungeon.floor, self.dungeon.x, self.dungeon.y = self.battle_position
            self.dungeon.grace = self.dungeon.settings["safe_steps"]
            self.explore_message = "HPは持ち越し。進むか帰るか"
            self.notice_timer = 0

    def next_result_label(self):
        if self.battle.outcome == "DEFEAT":
            return "拠点へ"
        if self.battle_is_boss and self.battle.outcome == "VICTORY":
            return "撃破後の会話へ"
        return "探索へ"

    def handle_event(self, event, message):
        if event == "chest":
            lines = [message] + self.exploration.chest_effect(self.dungeon.last_reward)
            play_cue("chest")
            self.show_field_event(lines)
            return
        if event == "poison":
            self.show_field_event([message] + self.exploration.damage(self.dungeon.exploration_settings["poison_damage"]))
            return
        if event == "pit":
            self.show_field_event([message])
            return
        if event == "spring":
            key = self.dungeon.floor, self.dungeon.x, self.dungeon.y
            if key in self.exploration.springs:
                self.show_field_event(["泉は静かだ。次の探索でまた使える"])
            else:
                self.exploration.springs.add(key)
                self.show_field_event([message] + self.exploration.heal(None))
            return
        if event == "stairs" and self.exploration.hint():
            self.show_field_event([message, self.exploration.hint()])
            return
        if message:
            self.explore_message = message
            self.tell(message)
        if event == "boss":
            self.message_lines = wrap_lines(self.dungeon.boss_data["message"], 36)
            self.state, self.message_page, self.notice_timer = "boss_message", 0, 0
        elif event == "battle":
            self.begin_encounter()
        elif event == "base":
            self.return_lines = []
            self.enter_camp(returned=True)

    def update(self):
        self.keyboard.update()
        if self.session.debug and self.pressed(pyxel.KEY_F1) and self.state in ("camp", "explore"):
            self.overlay = None if self.overlay == "feedback_debug" else "feedback_debug"
            self.notice_timer = 0
            return
        if self.overlay in ("catalog", "dungeon_debug", "effects", "treasure_debug"):
            self.notice_timer = max(0, self.notice_timer - 1)
        if (self.overlay == "info" and self.info_tab == 1 and self.state in ("explore", "menu")
                and self.confirm()):
            actor = self.session.party[self.info_character]
            if actor.skills and self.session.skills[actor.skills[self.scroll]].effect == "heal":
                self.field_actor = self.info_character
                self.field_skill = actor.skills[self.scroll]
                self.field_return = self.state
                self.state, self.overlay, self.item_cursor = "field_heal", None, 0
                self.notice_timer = 0
                return
        # Let the existing UI own all combat/inspection key handling.
        if self.pressed(pyxel.KEY_Q, pyxel.KEY_F9, pyxel.KEY_F12, pyxel.KEY_D, pyxel.KEY_TAB, pyxel.KEY_H):
            super().update()
            if not self.session.debug and self.overlay in ("catalog", "dungeon_debug", "effects", "treasure_debug", "feedback_debug"):
                self.overlay = None
            return
        if self.overlay == "feedback_debug":
            self.notice_timer = max(0, self.notice_timer - 1)
            self.update_feedback_debug()
            return
        if self.session.debug and self.pressed(pyxel.KEY_F2) and self.state in ("camp", "explore"):
            self.overlay = None if self.overlay == "treasure_debug" else "treasure_debug"
            self.notice_timer = 0
            return
        if self.overlay == "treasure_debug":
            self.update_treasure_debug()
            return
        if self.session.debug and self.pressed(pyxel.KEY_F4) and self.state in ("camp", "explore", "clear"):
            self.overlay = None if self.overlay == "dungeon_debug" else "dungeon_debug"
            self.floor_cursor = self.dungeon.floor
            self.notice_timer = 0
            return
        if self.session.debug and self.pressed(pyxel.KEY_F3) and self.battle and self.state in ("command", "skill", "target", "resolve", "result"):
            self.overlay = None if self.overlay == "effects" else "effects"
            self.notice_timer = 0
            return
        if self.session.debug and self.battle and self.state == "command":
            if self.pressed(pyxel.KEY_F6):
                self.battle.run_override = True
                self.tell("DEBUG: 次のRUNを成功に固定")
                return
            if self.pressed(pyxel.KEY_F8):
                self.battle.run_override = False
                self.tell("DEBUG: 次のRUNを失敗に固定")
                return
        if self.overlay == "dungeon_debug":
            self.update_dungeon_debug()
            return
        if self.overlay == "effects":
            self.effect_cursor = (self.effect_cursor + self.direction()) % (len(self.battle.enemies) + 4)
            if self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE):
                self.overlay = None
            return
        if self.session.debug and self.pressed(pyxel.KEY_F10) and self.state != "replace":
            self.overlay = None if self.overlay == "catalog" else "catalog"
            self.notice_timer = 0
            return
        if self.overlay == "catalog":
            if self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE):
                self.overlay = None
            else:
                self.catalog_cursor = (self.catalog_cursor + self.direction()) % len(self.session.skills)
                self.info_character = (self.info_character + self.direction(horizontal=True)) % 4
                skill = list(self.session.skills.values())[self.catalog_cursor]
                try:
                    if self.pressed(pyxel.KEY_C):
                        lines = self.session.debug_acquire(skill.id, self.info_character)
                        self.tell(lines[-1])
                    elif self.pressed(pyxel.KEY_V):
                        lines = self.session.debug_set_one(skill.id, self.info_character)
                        self.tell(lines[-1])
                    elif self.pressed(pyxel.KEY_B):
                        if not skill.can_relearn:
                            raise ValueError("再習得対象の技だけを発見できます。")
                        self.session.discovered_skills.add(skill.id)
                        self.tell(skill.name + " DISCOVERED")
                    elif self.pressed(pyxel.KEY_M):
                        self.session.mastered_skills.add(skill.id)
                        self.session.discovered_skills.add(skill.id)
                        self.tell(skill.name + " MASTERED! " + skill.mastery_label)
                    elif self.pressed(pyxel.KEY_R):
                        if self.state not in ("camp", "explore"):
                            raise ValueError("強制再取得は拠点か探索中だけです")
                        if skill.id not in self.session.mastered_skills:
                            raise ValueError("MでMASTEREDにしてください")
                        actor = self.session.party[self.info_character]
                        if skill.id in actor.skills:
                            actor.forget(skill.id)
                        self.tell(self.session.debug_acquire(skill.id, self.info_character)[-1])
                except ValueError as error:
                    self.tell(str(error))
                if self.session.pending_replacements:
                    self.debug_return_state = self.state
                    self.debug_return_overlay = "catalog"
                    self.state, self.overlay = "replace", None
                    self.replacement_cursor, self.replacement_confirm = 0, False
                    self.notice_timer = 0
            return
        if self.overlay:
            super().update()
            return
        if self.state in ("field_event", "quest_board"):
            self.notice_timer = max(0, self.notice_timer - 1)
            self.update_field_ui()
            return
        if self.state in ("relearn_character", "relearn_list", "relearn_confirm", "field_return", "return_result"):
            self.notice_timer = max(0, self.notice_timer - 1)
            self.update_camp_resources()
            return
        if self.state not in ("camp", "archive", "explore", "menu", "items", "item_target", "shop", "pub", "field_heal", "clear", "boss_message", "boss_after"):
            super().update()
            return
        self.notice_timer = max(0, self.notice_timer - 1)
        if self.state in ("camp", "explore") and self.session.debug:
            if self.pressed(pyxel.KEY_F11):
                self.return_lines = ["DEBUG帰還"]
                self.enter_camp(returned=True)
                return
            if self.pressed(pyxel.KEY_F7):
                for actor in self.session.party:
                    actor.recover()
                self.tell("DEBUG: 全員全回復")
                return
            if self.pressed(pyxel.KEY_F5, pyxel.KEY_F6, pyxel.KEY_F8):
                floor = self.dungeon.floor + (-1 if self.pressed(pyxel.KEY_F5) else 1)
                if self.pressed(pyxel.KEY_F8):
                    floor = 4 if self.state == "camp" else next((f for f in BOSS_FLOORS if f > self.dungeon.floor), 4)
                self.state = "explore"
                self.dungeon.debug_floor(floor)
                if self.pressed(pyxel.KEY_F8):
                    self.dungeon.x, self.dungeon.y = self.dungeon.find(floor, TILE_BOSS)
                self.tell(f"DEBUG: {self.dungeon.floor + 1}Fへ移動")
                return
        confirm, cancel = self.confirm(), self.cancel()
        if self.state in ("boss_message", "boss_after"):
            if cancel and self.state == "boss_message":
                self.state = "explore"
            elif confirm:
                if (self.message_page + 1) * 8 < len(self.message_lines):
                    self.message_page += 1
                elif self.state == "boss_message":
                    self.begin_encounter(boss=True)
                else:
                    self.state = "clear" if self.dungeon.cleared else "explore"
                    self.explore_message = "先の階層への道が開いた"
        elif self.state == "camp":
            self.camp_cursor = (self.camp_cursor + self.direction()) % 8
            if confirm:
                if self.camp_cursor == 0:
                    self.enter_dungeon()
                elif self.camp_cursor == 1:
                    self.overlay, self.info_tab, self.scroll = "info", 0, 0
                else:
                    if self.camp_cursor == 2:
                        self.state, self.archive_page, self.archive_cursor = "archive", 0, 0
                    elif self.camp_cursor == 3:
                        self.state, self.notice_timer = "relearn_character", 0
                    elif self.camp_cursor == 4:
                        self.state, self.notice_timer = "quest_board", 0
                    elif self.camp_cursor == 5:
                        self.state, self.shop_cursor = "shop", 0
                    elif self.camp_cursor == 6:
                        self.state, self.pub_cursor = "pub", 0
                    else:
                        self.overlay = "help"
        elif self.state == "shop":
            self.shop_cursor = (self.shop_cursor + self.direction()) % 3
            if cancel:
                self.state = "camp"
            elif confirm:
                item = ("POTION", "PHOENIX ASH", "REMEDY")[self.shop_cursor]
                self.tell(self.session.inventory.buy(item, self.session.treasure)[1])
        elif self.state == "pub":
            self.pub_cursor = (self.pub_cursor + self.direction()) % 2
            if cancel or (confirm and self.pub_cursor):
                self.state = "camp"
            elif confirm:
                cost = self.session.inventory.data["pub_cost"]
                if self.session.treasure.banked < cost:
                    self.tell("確定した宝が足りません")
                else:
                    self.session.treasure.banked -= cost
                    pool = self.rumors["gameplay" if self.session.rng.random() < self.session.inventory.data["pub_gameplay_weight"] else "flavor"]
                    choices = [line for line in pool if line != self.last_rumor] or pool
                    self.last_rumor = self.session.rng.choice(choices)
                    self.show_field_event(["酒場の噂:", self.last_rumor], return_state="pub")
        elif self.state == "archive":
            if cancel:
                self.state = "camp"
            elif confirm:
                self.archive_page = 1 - self.archive_page
            elif self.archive_page:
                self.archive_cursor = (self.archive_cursor + self.direction()) % len(self.session.skills)
        elif self.state == "clear":
            if confirm:
                self.state = "explore"
        elif self.state == "explore":
            if cancel:
                self.state, self.menu_cursor = "menu", 0
                self.notice_timer = 0
            elif confirm:
                lines = self.exploration.investigate()
                if lines:
                    self.show_field_event(lines)
                else:
                    self.handle_event(*self.dungeon.interact())
            else:
                dx, dy = self.direction(horizontal=True), self.direction()
                if dx:
                    dy = 0
                if dx or dy:
                    self.player_facing = ("right" if dx > 0 else "left") if dx else ("down" if dy > 0 else "up")
                    event = self.dungeon.move(dx, dy, self.session.debug)
                    lines = self.exploration.investigate()
                    if lines:
                        self.show_field_event(lines)
                    else:
                        self.handle_event(*event)
        elif self.state == "menu":
            self.menu_cursor = (self.menu_cursor + self.direction()) % 5
            if cancel:
                self.state = "explore"
            elif confirm:
                if self.menu_cursor < 2:
                    self.overlay, self.info_tab, self.scroll = "info", self.menu_cursor, 0
                elif self.menu_cursor < 4:
                    self.state, self.item_cursor = ("items" if self.menu_cursor == 2 else "field_return"), 0
                else:
                    self.overlay = "help"
        elif self.state == "items":
            self.item_kind_cursor = (self.item_kind_cursor + self.direction()) % 3
            if cancel:
                self.state = "menu"
                self.notice_timer = 0
            elif confirm:
                item = ("POTION", "PHOENIX ASH", "REMEDY")[self.item_kind_cursor]
                if item == "REMEDY":
                    self.tell("今は治す状態異常がありません")
                elif self.session.inventory.counts[item] == 0:
                    self.tell("道具がありません")
                else:
                    self.state, self.item_cursor = "item_target", 0
        elif self.state == "item_target":
            self.item_cursor = (self.item_cursor + self.direction()) % 4
            if cancel:
                self.state = "items"
            elif confirm:
                item = ("POTION", "PHOENIX ASH")[self.item_kind_cursor]
                self.tell(self.session.inventory.use(item, self.session.party[self.item_cursor])[1])
        elif self.state == "field_heal":
            self.item_cursor = (self.item_cursor + self.direction()) % 4
            if cancel:
                self.state, self.overlay = self.field_return, "info"
                self.scroll = min(self.scroll, self.info_scroll_limit())
                self.notice_timer = 0
            elif confirm:
                used, lines = self.session.field_heal(self.field_actor, self.field_skill, self.item_cursor)
                if used:
                    play_cue("mastered" if any("MASTERED!" in line for line in lines) else "skill")
                self.tell(lines[-1])

    def draw(self):
        if self.overlay == "feedback_debug":
            self.draw_feedback_debug()
        elif not self.overlay and self.state in ("field_event", "quest_board"):
            self.draw_field_ui()
        elif self.overlay == "treasure_debug":
            self.draw_treasure_debug()
        elif not self.overlay and self.state in ("relearn_character", "relearn_list", "relearn_confirm", "field_return", "return_result"):
            self.draw_camp_resources()
        elif self.overlay in ("dungeon_debug", "effects"):
            pyxel.cls(0)
            self.draw_dungeon_debug() if self.overlay == "dungeon_debug" else self.draw_effects()
        elif self.overlay == "catalog":
            self.draw_catalog()
        elif self.overlay or self.state not in ("camp", "archive", "explore", "menu", "items", "item_target", "shop", "pub", "field_heal", "clear", "boss_message", "boss_after"):
            super().draw()
            if self.overlay == "info" and self.info_tab == 1 and self.state in ("explore", "menu"):
                self.footer("左右:人 上下:技 A:回復/頁 B:閉じる")
        else:
            pyxel.cls(0)
            if self.state == "camp":
                self.draw_camp()
            elif self.state == "archive":
                self.draw_archive()
            elif self.state == "explore":
                self.draw_explore()
            elif self.state == "menu":
                self.draw_menu()
            elif self.state == "items":
                self.draw_items()
            elif self.state == "item_target":
                self.draw_item_target()
            elif self.state == "shop":
                self.draw_shop()
            elif self.state == "pub":
                self.draw_pub()
            elif self.state == "field_heal":
                self.draw_field_heal()
            elif self.state in ("boss_message", "boss_after"):
                self.draw_boss_message()
            else:
                self.draw_clear()

    def draw_camp(self):
        self.title("BASE CAMP / 拠点" + (" DEBUG" if self.session.debug else ""))
        text(4, 18, self.camp_message, 2, 38)
        for i, label in enumerate(("ダンジョンに入る", "パーティ状態", "SKILL ARCHIVE 技図鑑", "スキル再習得", "QUEST BOARD 調査依頼", "SHOP 道具購入", "PUB 情報購入", "操作 HELP")):
            text(10, 24 + i * 10, (">" if i == self.camp_cursor else " ") + label, 3, 36)
        text(8, 104, f"宝{self.session.treasure.banked} 薬{self.dungeon.potions} / {self.session.completed}戦", 2, 36)
        self.footer("D-PAD:選択 A:決定 B:戻る")

    def draw_archive(self):
        skills = list(self.session.skills.values())
        summary = self.session.archive_summary()
        if self.archive_page == 0:
            total = summary["total"]
            discovered = summary["discovered"]
            mastered = summary["mastered"]
            self.title("SKILL ARCHIVE / 技図鑑")
            text(5, 16, f"DISCOVERED {discovered}/{total}  {discovered * 100 // total}%", 3, 37)
            text(5, 27, f"MASTERED   {mastered}/{total}  {mastered * 100 // total}%", 3, 37)
            text(5, 40, "RARITY       発見  習熟  全", 2, 37)
            for i, rarity in enumerate(("BASIC", "COMMON", "UNCOMMON", "RARE", "LEGEND")):
                row = summary["rarities"].get(rarity, {"total": 0, "discovered": 0,
                                                       "mastered": 0})
                text(7, 51 + i * 10,
                     f"{rarity:8} {row['discovered']:2}    {row['mastered']:2}   {row['total']:2}",
                     3 if rarity == "LEGEND" else 2, 37)
            self.footer("A:技一覧 B:拠点へ")
            return
        self.title(f"SKILL LIST {self.archive_cursor + 1}/{len(skills)}")
        start = max(0, min(self.archive_cursor - 4, len(skills) - 7))
        for i, skill in enumerate(skills[start:start + 7]):
            selected = start + i == self.archive_cursor
            known = skill.id in self.session.discovered_skills
            mastered = skill.id in self.session.mastered_skills
            label = skill.name if known else "????????"
            marker = ("D" if known else "-") + ("M" if mastered else "-")
            if selected:
                pyxel.rect(2, 14 + i * 10, 156, 9, 1)
            text(4, 15 + i * 10,
                 f"{start + i + 1:02} {marker} {label}", 3 if selected else 2, 37)
        selected = skills[self.archive_cursor]
        category = CATEGORIES[selected.skill_type] if selected.id in self.session.discovered_skills else "????"
        text(5, 90, "TYPE " + category + "  D=発見 M=習熟", 2, 37)
        if selected.id in self.session.mastered_skills:
            text(5, 100, "MASTERED: " + selected.mastery_label, 2, 37)
        self.footer("上下:技 A:集計 B:拠点へ")

    def draw_explore(self):
        d = self.dungeon
        self.title(f"B{d.floor + 1}F 薬{d.potions} 未確定宝{d.treasure.unbanked}" + (" DEBUG" if self.session.debug else ""))
        camera_x = d.x * TILE_SIZE + TILE_SIZE // 2 - MAP_WIDTH // 2
        camera_y = d.y * TILE_SIZE + TILE_SIZE // 2 - MAP_HEIGHT // 2
        source_x = max(0, camera_x)
        source_y = max(0, camera_y)
        source_right = min(d.width * TILE_SIZE, camera_x + MAP_WIDTH)
        source_bottom = min(d.height * TILE_SIZE, camera_y + MAP_HEIGHT)
        draw_width = max(0, source_right - source_x)
        draw_height = max(0, source_bottom - source_y)
        pyxel.clip(MAP_X, MAP_Y, MAP_WIDTH, MAP_HEIGHT)
        if draw_width and draw_height:
            pyxel.bltm(MAP_X + source_x - camera_x,
                       MAP_Y + source_y - camera_y,
                       d.maps[d.floor], source_x, source_y,
                       draw_width, draw_height)
        for floor, x, y in d.opened:
            if floor == d.floor:
                u, v = TILE_CHEST_OPEN
                pyxel.blt(MAP_X + x * TILE_SIZE - camera_x,
                          MAP_Y + y * TILE_SIZE - camera_y,
                          MAP_IMAGE_BANK, u * TILE_SIZE, v * TILE_SIZE,
                          TILE_SIZE, TILE_SIZE)
        if d.floor in d.defeated_bosses:
            u, v = TILE_BOSS_CLEAR
            x, y = d.boss_positions[d.floor]
            pyxel.blt(MAP_X + x * TILE_SIZE - camera_x,
                      MAP_Y + y * TILE_SIZE - camera_y,
                      MAP_IMAGE_BANK, u * TILE_SIZE, v * TILE_SIZE,
                      TILE_SIZE, TILE_SIZE)
        if self.exploration.active and not self.exploration.surveyed and self.exploration.target[0] == d.floor:
            _, x, y = self.exploration.target
            u, v = TILE_QUEST
            pyxel.blt(MAP_X + x * TILE_SIZE - camera_x, MAP_Y + y * TILE_SIZE - camera_y,
                      MAP_IMAGE_BANK, u * TILE_SIZE, v * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        # Map-only facing sprites in Image Bank 0 of game.pyxres.
        player_x = MAP_X + MAP_WIDTH // 2 - PLAYER_WIDTH // 2
        player_y = MAP_Y + MAP_HEIGHT // 2 - PLAYER_HEIGHT // 2
        pyxel.blt(player_x, player_y, 0, *PLAYER_SPRITES[self.player_facing],
                  PLAYER_WIDTH, PLAYER_HEIGHT, 0)
        pyxel.clip()
        for i, actor in enumerate(self.session.party):
            y = 15 + i * 21
            text(102, y, actor.name, 3 if actor.alive else 1, 14)
            text(102, y + 9, f"{actor.hp}/{actor.max_hp}" if actor.alive else "戦闘不能", 2, 14)
        text(102, 100, f"{d.x},{d.y}", 1, 14)
        self.footer("D-PAD:移動 A:調べる B:メニュー")

    def draw_menu(self):
        self.title(f"{self.dungeon.floor + 1}F / 探索メニュー")
        for i, label in enumerate(("状態 STATUS", "習得技 SKILLS", "道具 ITEM", "RETURNで帰還", "操作 HELP")):
            text(12, 20 + i * 15, (">" if i == self.menu_cursor else " ") + label, 3, 34)
        text(8, 99, "入口かRETURNで宝を確定", 2, 36)
        self.footer("D-PAD:選択 A:決定 B:探索へ")

    def draw_items(self):
        self.title("ITEM / 探索中")
        for i, item in enumerate(("POTION", "PHOENIX ASH", "REMEDY")):
            text(6, 23 + i * 17, (">" if i == self.item_kind_cursor else " ") +
                 f"{item} x{self.session.inventory.counts[item]}", 3 if i == self.item_kind_cursor else 2, 37)
        text(6, 87, "REMEDYは現在使用できません", 2, 37)
        self.footer("上下:選択 A:対象へ B:戻る")

    def draw_item_target(self):
        item = ("POTION", "PHOENIX ASH")[self.item_kind_cursor]
        self.title(item + " / 誰に使う?")
        for i, actor in enumerate(self.session.party):
            y = 34 + i * 15
            if i == self.item_cursor:
                pyxel.rect(3, y - 1, 153, 10, 1)
            text(5, y, (">" if i == self.item_cursor else " ") + actor.name, 3, 14)
            text(67, y, f"HP {actor.hp}/{actor.max_hp}", 2, 22)
        text(5, 99, "無効な対象には消費しません", 2, 37)
        self.footer("上下:選択 A:使う B:戻る")

    def draw_shop(self):
        self.title("SHOP / 道具購入")
        text(5, 16, f"確定した宝 {self.session.treasure.banked}", 3, 37)
        for i, item in enumerate(("POTION", "PHOENIX ASH", "REMEDY")):
            row = self.session.inventory.data["items"][item]
            text(5, 34 + i * 17, (">" if i == self.shop_cursor else " ") +
                 f"{item} {row['price']}宝 x{self.session.inventory.counts[item]}/9",
                 3 if i == self.shop_cursor else 2, 37)
        self.footer("上下:選択 A:購入 B:拠点へ")

    def draw_pub(self):
        self.title("PUB / 情報購入")
        text(8, 24, f"確定した宝 {self.session.treasure.banked}", 3, 35)
        text(8, 39, f"噂を聞く? 宝{self.session.inventory.data['pub_cost']}個", 2, 35)
        for i, label in enumerate(("YES", "NO")):
            text(12, 61 + i * 16, (">" if i == self.pub_cursor else " ") + label, 3, 20)
        self.footer("上下:選択 A:決定 B:拠点へ")

    def draw_clear(self):
        self.title("DUNGEON CLEAR")
        text(12, 28, "B15Fの最終ボスを倒した!", 3, 34)
        text(12, 45, f"{self.session.completed}戦 / {self.session.wins}勝", 2, 34)
        text(12, 60, f"確定宝{self.session.treasure.banked} 未確定{self.session.treasure.unbanked}", 2, 34)
        text(12, 78, "Dで育成結果を確認できます", 2, 34)
        text(12, 93, "調査と宝を持ち帰ろう", 2, 34)
        self.footer("A:探索に戻る")

    def draw_field_heal(self):
        actor = self.session.party[self.field_actor]
        skill = self.session.skills[self.field_skill]
        self.title(f"{skill.name} {actor.skill_uses.get(skill.id, 0)}/{actor.max_uses(skill)}")
        text(5, 17, f"{actor.name} / 誰を回復?", 2, 37)
        for i, target in enumerate(self.session.party):
            y = 34 + i * 15
            text(5, y, (">" if i == self.item_cursor else " ") + target.name, 3, 14)
            text(67, y, f"HP {target.hp}/{target.max_hp}", 2, 22)
        text(5, 99, "回数を消費・探索使用は成長なし", 2, 37)
        self.footer("上下:対象 A:使用 B:技一覧へ")

    def draw_result(self):
        super().draw_result()
        if self.battle.outcome == "DEFEAT":
            self.title("PARTY DEFEATED / 全滅")

    def draw_catalog(self):
        pyxel.cls(0)
        skills = list(self.session.skills.values())
        self.title(f"{self.session.party[self.info_character].name} 全技 {self.catalog_cursor + 1}/{len(skills)}")
        start = max(0, self.catalog_cursor - 5)
        for i, skill in enumerate(skills[start:start + 6]):
            selected = start + i == self.catalog_cursor
            text(5, 16 + i * 9, (">" if selected else " ") + skill.name, 3 if selected else 2, 37)
        self.skill_details(self.session.party[self.info_character], skills[self.catalog_cursor])
        self.footer("C:取得 V:残1 B:発見 M:習熟 R:再")

    def update_camp_resources(self):
        confirm, cancel = self.confirm(), self.cancel()
        if self.state == "return_result":
            if confirm:
                self.state, self.notice_timer = "camp", 0
        elif self.state == "field_return":
            self.item_cursor = (self.item_cursor + self.direction()) % 4
            if cancel:
                self.state = "menu"
            elif confirm:
                try:
                    self.return_lines = self.session.field_return(self.item_cursor)
                except ValueError as error:
                    self.tell(str(error))
                    return
                play_cue("mastered" if any("MASTERED!" in line for line in self.return_lines) else "skill")
                self.enter_camp(returned=True)
        elif self.state == "relearn_character":
            self.info_character = (self.info_character + self.direction()) % 4
            if cancel:
                self.state = "camp"
            elif confirm:
                self.state, self.relearn_cursor = "relearn_list", 0
        elif self.state == "relearn_list":
            candidates = self.session.relearn_candidates()
            if cancel:
                self.state = "relearn_character"
            elif candidates:
                self.relearn_cursor = (self.relearn_cursor + self.direction()) % len(candidates)
                if confirm:
                    self.relearn_skill = candidates[self.relearn_cursor].id
                    self.state, self.notice_timer = "relearn_confirm", 0
        elif self.state == "relearn_confirm":
            if cancel:
                self.state, self.notice_timer = "relearn_list", 0
            elif confirm:
                try:
                    message = self.session.relearn(self.info_character, self.relearn_skill)
                except ValueError as error:
                    self.tell(str(error))
                    return
                if self.session.pending_replacements:
                    # Use the existing replacement/decline UI and its return route.
                    self.debug_return_state, self.debug_return_overlay = "relearn_list", None
                    self.state, self.overlay = "replace", None
                    self.replacement_cursor, self.replacement_confirm = 0, False
                    self.notice_timer = 0
                else:
                    self.state = "relearn_list"
                    self.tell(message)

    def draw_camp_resources(self):
        pyxel.cls(0)
        s = self.session
        if self.state == "return_result":
            self.title("RETURNED TO BASE / 帰還")
            text(6, 19, f"宝を確保: {self.return_secured}個", 3, 37)
            text(6, 32, f"確定宝: {s.treasure.banked}", 3, 37)
            text(6, 45, "未確定宝: 0 / 全員HP回復", 2, 37)
            for i, line in enumerate(wrap_lines(self.return_lines, 36)[:5]):
                text(6, 59 + i * 9, line, 2, 37)
            self.footer("A:拠点へ")
        elif self.state in ("relearn_character", "field_return"):
            returning = self.state == "field_return"
            self.title("RETURN / 使用者を選ぶ" if returning else "再習得 / キャラを選ぶ")
            text(5, 16, f"未確定宝 {s.treasure.unbanked}を確保" if returning else f"確定宝 {s.treasure.banked}", 2, 37)
            for i, actor in enumerate(s.party):
                cursor = self.item_cursor if returning else self.info_character
                text(5, 32 + i * 16, (">" if i == cursor else " ") + actor.name, 3, 20)
                if returning:
                    uses = sum(actor.skill_uses.get(sid, 0) for sid in actor.skills if s.skills[sid].effect == 'return')
                    label = f"残{uses}回" if actor.alive else "戦闘不能"
                else:
                    label = f"技{len(actor.skills)}/{s.settings['skill_slots']}"
                text(94, 32 + i * 16, label, 2, 16)
            self.footer("上下:人 A:帰還 B:戻る" if returning else "上下:人 A:技選択 B:拠点")
        elif self.state == "relearn_list":
            actor = s.party[self.info_character]
            candidates = s.relearn_candidates()
            self.title(actor.name + " / スキル再習得")
            text(5, 16, f"宝{s.treasure.banked} 基本/通常/RARE補助", 2, 37)
            start = max(0, self.relearn_cursor - 5)
            for i, skill in enumerate(candidates[start:start + 6]):
                selected = start + i == self.relearn_cursor
                text(5, 30 + i * 11, (">" if selected else " ") + skill.name, 3 if selected else 2, 23)
                text(101, 30 + i * 11, "所持中" if skill.id in actor.skills else f"宝{skill.relearn_cost}", 2, 14)
            if candidates:
                skill = candidates[self.relearn_cursor]
                text(5, 100, f"再習得{actor.relearn_uses(skill)}/{actor.next_max_uses(skill)}回 / 宝{skill.relearn_cost}", 2, 37)
            else:
                text(5, 35, "再習得できる発見済み技なし", 2, 37)
            self.footer("上下:技 A:確認 B:人選択")
        else:
            actor = s.party[self.info_character]
            skill = s.skills[self.relearn_skill]
            self.title("再習得の確認")
            text(5, 20, actor.name + " / " + skill.name, 3, 37)
            text(5, 36, f"宝コスト {skill.relearn_cost} / 所持{s.treasure.banked}", 2, 37)
            text(5, 50, f"使用回数 {actor.relearn_uses(skill)}/{actor.next_max_uses(skill)}", 3, 37)
            text(5, 66, "満杯なら入れ替えを選択", 2, 37)
            text(5, 82, "取り消しでは宝を消費しない", 2, 37)
            self.footer("A:再習得 B:取り消し")

    def show_field_event(self, lines, return_state="explore"):
        self.field_lines = wrap_lines(lines, 36)
        self.field_page, self.notice_timer = 0, 0
        self.field_after = return_state
        self.state, self.overlay = "field_event", None

    def update_field_ui(self):
        confirm, cancel = self.confirm(), self.cancel()
        if self.state == "field_event":
            if not confirm:
                return
            if (self.field_page + 1) * 8 < len(self.field_lines):
                self.field_page += 1
            elif self.session.pending_replacements:
                self.debug_return_state, self.debug_return_overlay = self.field_after, None
                self.state = "replace"
                self.replacement_cursor, self.replacement_confirm = 0, False
            else:
                self.state = self.field_after
            return
        quests = self.exploration.quest_data["quests"]
        self.quest_cursor = (self.quest_cursor + self.direction()) % len(quests)
        if cancel:
            self.state, self.notice_timer = "camp", 0
        elif confirm:
            try:
                self.tell(self.exploration.accept(quests[self.quest_cursor]["id"]))
            except ValueError as error:
                self.tell(str(error))

    def draw_field_ui(self):
        pyxel.cls(0)
        if self.state == "field_event":
            self.title("探索 / 調査と発見")
            pyxel.rectb(3, 17, 154, 84, 2)
            for i, line in enumerate(self.field_lines[self.field_page * 8:(self.field_page + 1) * 8]):
                text(7, 24 + i * 9, line, 3, 36)
            self.footer("A:次へ")
            return
        self.title("QUEST BOARD / 調査依頼")
        e = self.exploration
        quests = e.quest_data["quests"]
        for i, quest in enumerate(quests):
            if quest["id"] in e.completed:
                status = "達成済み"
            elif e.active and e.active["id"] == quest["id"]:
                status = "帰還待ち" if e.surveyed else "調査中"
            else:
                status = "受注可" if e.unlocked(quest) else "未解放"
            text(5, 19 + i * 15, (">" if i == self.quest_cursor else " ") + quest["name"], 3, 23)
            text(106, 19 + i * 15, status, 2, 12)
        quest = quests[self.quest_cursor]
        text(5, 66, f"B{quest['floors'][0]}～{quest['floors'][1]}F / 報酬 確定宝{quest['reward']}", 2, 37)
        for i, line in enumerate(wrap_lines([quest["description"]], 37)[:2]):
            text(5, 78 + i * 9, line, 2, 37)
        text(5, 99, "調査後に生還 / 全滅で再調査", 2, 37)
        self.footer("上下:依頼 A:受注 B:拠点へ")

    def feedback_options(self):
        rewards = self.dungeon.exploration_settings["CHEST_REWARD_TABLE"]["NORMAL"]
        labels = {"TREASURE": "宝", "POTION": "薬",
                  "SKILL_CHANCE": "閃き抽選", "TRAP": "罠", "EMPTY": "空の箱"}
        options = [(f"宝箱: {labels[r['kind']]} {r.get('amount', '')}", r) for r in rewards]
        options += [("RARE宝箱を足元に生成", "rare"), ("毒沼ダメージ", "poison"),
                    ("落とし穴をテスト", "pit")]
        options += [(f"探索Lv{i} 強制受注", i) for i in (1, 2, 3)]
        return options + [("調査地点へ移動", "warp"), ("調査完了ON/OFF", "survey"),
                          ("選択した人を戦闘不能", "ko"), ("REVIVEを取得", "revive"),
                          ("灰を1個取得", "ash"), ("薬を1個取得", "potion"),
                          ("全アイテムを9個に", "max_items"), ("泉へ移動", "spring"),
                          ("酒場へ", "pub"), ("確定宝+10", "bank10")]

    def update_feedback_debug(self):
        if self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE):
            self.overlay = None
            return
        options = self.feedback_options()
        self.feedback_cursor = (self.feedback_cursor + self.direction()) % len(options)
        self.info_character = (self.info_character + self.direction(horizontal=True)) % 4
        if not self.pressed(pyxel.KEY_Z, pyxel.KEY_RETURN):
            return
        action = options[self.feedback_cursor][1]
        d, e = self.dungeon, self.exploration
        if isinstance(action, dict):
            previous = self.state
            self.handle_event(*d.grant_chest(action))
            if self.state == "field_event":
                self.field_after = previous
        elif action == "rare":
            if self.state != "explore" or d.tile(d.floor, d.x, d.y) != TILE_FLOOR or e.target == (d.floor, d.x, d.y):
                self.tell("探索中の通常の床で使ってください")
                return
            d.maps[d.floor].pset(d.x, d.y, TILE_RARE_CHEST)
            d.opened.discard((d.floor, d.x, d.y))
            d.chest_loot.pop((d.floor, d.x, d.y), None)
            self.overlay = None
            self.tell("RARE宝箱を配置。Zで開く")
        elif action == "ko":
            actor = self.session.party[self.info_character]
            if not actor.alive:
                self.tell(f"{actor.name} はすでに戦闘不能")
            elif sum(c.alive for c in self.session.party) <= 1:
                self.tell("最後の生存者は倒せません")
            else:
                actor.hp = 0
                self.tell(f"DEBUG: {actor.name} 戦闘不能")
        elif action == "revive":
            try:
                self.tell(self.session.debug_acquire("revive", self.info_character)[-1])
                if self.session.pending_replacements:
                    self.debug_return_state, self.debug_return_overlay = self.state, "feedback_debug"
                    self.state, self.overlay = "replace", None
                    self.replacement_cursor, self.replacement_confirm = 0, False
            except ValueError as error:
                self.tell(str(error))
        elif action == "ash":
            self.tell("灰 +1" if self.session.inventory.add("PHOENIX ASH") else "灰は満杯")
        elif action == "potion":
            self.tell("薬 +1" if self.session.inventory.add("POTION") else "薬は満杯")
        elif action == "max_items":
            for item in self.session.inventory.counts:
                self.session.inventory.counts[item] = 9
            self.tell("DEBUG: 全アイテム9個")
        elif action == "spring":
            if self.state != "explore":
                self.tell("探索中に使ってください")
            else:
                from .tiles import TILE_HEAL_POINT
                positions = d.positions(d.floor, TILE_HEAL_POINT)
                if positions:
                    d.x, d.y = positions[0]
                    self.overlay = None
                    self.tell("泉へ移動。Zで調べる")
                else:
                    self.tell("この階に泉はありません")
        elif action == "pub":
            self.state, self.overlay, self.pub_cursor = "pub", None, 0
        elif action == "bank10":
            self.session.treasure.banked += 10
            self.tell("DEBUG: 確定宝+10")
        elif action in ("poison", "pit"):
            if self.state != "explore":
                self.tell("探索中に試してください")
                return
            self.handle_event(*d.fall_in_pit() if action == "pit" else ("poison", "DEBUG毒沼"))
        elif isinstance(action, int):
            e.active, e.target, e.surveyed = None, None, False
            e.completed.discard(action)
            self.tell(e.accept(action, debug=True))
        elif e.active:
            if action == "warp":
                d.floor, d.x, d.y = e.target
                self.state, self.overlay = "explore", None
                d.grace = d.settings["safe_steps"]
                self.tell(e.hint() or "DEBUG: 調査地点へ移動")
            else:
                e.surveyed = not e.surveyed
                self.tell("調査完了 " + ("ON" if e.surveyed else "OFF"))
        else:
            self.tell("先にクエストを受注してください")

    def draw_feedback_debug(self):
        pyxel.cls(0)
        self.title("DEBUG / 探索フィードバック")
        options = self.feedback_options()
        start = max(0, self.feedback_cursor - 5)
        for i, (label, _) in enumerate(options[start:start + 6]):
            text(5, 17 + i * 12, (">" if start + i == self.feedback_cursor else " ") + label, 3, 37)
        target = self.exploration.target
        label = f"調査 B{target[0] + 1}F ({target[1]},{target[2]})" if target else "調査対象なし"
        text(5, 98, label + " / " + self.session.party[self.info_character].name, 2, 37)
        self.footer("左右:人 上下:選択 Z:実行 X:閉じる")

    def update_treasure_debug(self):
        if self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE):
            self.overlay = None
            return
        self.treasure_cursor = (self.treasure_cursor + self.direction()) % 5
        self.info_character = (self.info_character + self.direction(horizontal=True)) % 4
        if not self.pressed(pyxel.KEY_Z, pyxel.KEY_RETURN):
            return
        s = self.session
        if self.treasure_cursor == 0:
            s.treasure.unbanked += 5
        elif self.treasure_cursor == 1:
            s.treasure.banked += 5
        elif self.treasure_cursor == 2:
            s.treasure.unbanked = 0
        elif self.treasure_cursor == 3:
            try:
                self.tell(s.debug_acquire("return", self.info_character)[-1])
            except ValueError as error:
                self.tell(str(error))
            if s.pending_replacements:
                self.debug_return_state, self.debug_return_overlay = self.state, "treasure_debug"
                self.state, self.overlay = "replace", None
                self.replacement_cursor, self.replacement_confirm = 0, False
                self.notice_timer = 0
        elif self.state == "camp":
            self.state, self.overlay = "relearn_character", None
        else:
            self.tell("再習得は拠点で行います。")

    def draw_treasure_debug(self):
        pyxel.cls(0)
        s = self.session
        self.title("DEBUG / 宝と帰還")
        text(5, 16, f"未確定{s.treasure.unbanked} / 確定{s.treasure.banked}", 3, 37)
        for i, label in enumerate(("未確定宝 +5", "確定宝 +5", "未確定宝を0", "RETURNを取得", "拠点の再習得を開く")):
            text(5, 31 + i * 12, (">" if i == self.treasure_cursor else " ") + label, 3, 37)
        text(5, 98, "対象: " + s.party[self.info_character].name, 2, 37)
        self.footer("左右:人 上下:項目 Z:実行 X:戻る")

    def draw_boss_message(self):
        boss = self.dungeon.boss_data
        self.title(f"B{self.dungeon.floor + 1}F / {boss['name']}")
        pyxel.rectb(3, 17, 154, 84, 2)
        for i, line in enumerate(self.message_lines[self.message_page * 8:(self.message_page + 1) * 8]):
            text(7, 24 + i * 9, line, 3, 36)
        more = (self.message_page + 1) * 8 < len(self.message_lines)
        self.footer("A:続きを読む" if more else "A:戦闘開始 B:戻る" if self.state == "boss_message" else "A:先へ進む")

    def update_dungeon_debug(self):
        self.floor_cursor = (self.floor_cursor + self.direction()) % 15
        for key, floor in zip((pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3), BOSS_FLOORS):
            if self.pressed(key):
                self.dungeon.defeated_bosses.symmetric_difference_update({floor})
        if self.pressed(pyxel.KEY_Z, pyxel.KEY_RETURN, pyxel.KEY_B):
            boss = self.pressed(pyxel.KEY_B)
            floor = BOSS_FLOORS[self.floor_cursor // 5] if boss else self.floor_cursor
            self.dungeon.debug_floor(floor)
            if boss:
                self.dungeon.x, self.dungeon.y = self.dungeon.find(floor, TILE_BOSS)
            self.state, self.overlay, self.notice_timer = "explore", None, 0
        elif self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE):
            self.overlay = None
            if self.state == "clear" and not self.dungeon.cleared:
                self.state = "explore"

    def draw_dungeon_debug(self):
        d = self.dungeon
        multiplier = d.settings['spark_multipliers'][self.floor_cursor]
        rate = spark_probability(self.session.settings, multiplier)
        debug_rate = spark_probability(self.session.settings, multiplier, True)
        self.title("DEBUG / 階層とボス")
        text(5, 17, f"移動先 B{self.floor_cursor + 1}F / エリア{self.floor_cursor // 5 + 1}", 3, 37)
        text(5, 29, f"閃き x{multiplier:.2f} 通常{rate:.1%}", 2, 37)
        text(5, 39, f"DEBUG中 {debug_rate:.1%} / 1人ごと", 2, 37)
        for i, floor in enumerate(BOSS_FLOORS):
            flag = "ON 撃破済" if floor in d.defeated_bosses else "OFF 未撃破"
            text(5, 53 + i * 12, f"{i + 1}: B{floor + 1}F {flag}", 3, 37)
        text(5, 92, "上下:階選択 B:エリアのボス前", 2, 37)
        self.footer("Z:移動 1/2/3:撃破切替 X:閉じる")

    def draw_effects(self):
        units = self.battle.enemies + self.session.party
        unit = units[self.effect_cursor % len(units)]
        multiplier = self.session.spark_multiplier
        rate = spark_probability(self.session.settings, multiplier, self.session.debug)
        self.title("DEBUG AUDIO: " + self.audio_state())
        text(5, 16, f"{unit.name} 閃き x{multiplier:.2f} = {rate:.1%}", 2, 37)
        text(5, 27, f"AGI {battle_agility(unit):g} DEF {getattr(unit, 'defense', 0) * effect_factor(unit, 'armor_break'):g}", 2, 37)
        if not self.battle.boss:
            text(5, 98, f"RUN {self.battle.run_chance():.0%} F6成功/F8失敗", 2, 37)
        for i, (effect, (factor, turns)) in enumerate(list(unit.effects.items())[:3]):
            text(5, 40 + i * 10, f"{EFFECTS[effect]} x{factor:g} 残{turns}T", 3, 37)
        if not unit.effects:
            text(5, 44, "補助効果なし", 2, 37)
        if unit in self.session.party:
            uses = unit.category_uses
            text(5, 73, "物/速/魔/補/癒 " + "/".join(str(uses.get(k, 0)) for k in
                 ("physical", "speed", "magic", "support", "healing")), 2, 37)
            text(5, 85, "補正 " + " ".join(f"{s}+{growth_bonus(unit, s, self.session.settings):.0%}"
                 for s in ("HP", "STR", "AGI", "INT")), 2, 37)
        self.footer("上下:敵/味方 F3/X:閉じる")

    def draw_help(self):
        pyxel.cls(0)
        self.title("SPARK / 操作")
        lines = ["D-PAD  移動・選択", "A  決定・調べる・会話送り", "B  キャンセル・戻る", "探索中のB  メニュー", "PC: A=Zキー B=Xキー",
                 "技を使い切るとMASTERED", "調査後に生還して報酬", "入口/RETURNで宝を確定"]
        for i, line in enumerate(lines):
            text(5, 18 + i * 10, line, 3 if i < 5 else 2, 37)
        self.footer("B:閉じる")
