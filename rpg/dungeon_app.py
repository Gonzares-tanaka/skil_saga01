"""Small exploration screens around the existing battle UI."""
from collections import deque
from copy import deepcopy
import json

import pyxel

from .app import App
from .battle import Session
from .final_battle import (FinalBattleCheckpoint, load_final_battle_data,
                          make_final_enemy)
from .content import ROOT
from .dungeon import Dungeon, load_dungeon_settings
from .exploration import Exploration
from .text import FONT_HEIGHT, text, text_width, wrap_lines
from .map_resources import load_maps
from .growth import spark_probability
from .growth import growth_bonus
from .labels import EFFECTS, CATEGORIES
from .labels import CURRENCY_NAME
from .quests import (QUEST_TYPES, QUEST_NAMES, QUEST_SYMBOLS, QUEST_FLAVOR_MAX_CHARS,
                     QUEST_FLAVOR_LINE_HEIGHT, QUEST_FLAVOR_LINES_PER_PAGE)
from .models import effect_factor, battle_agility
from .opening import (TITLE_MAIN, TITLE_SUBTITLE, TITLE_OPTIONS, TITLE_FADE_FRAMES,
                       NEW_GAME_BANKED_TRZ,
                      HUB_PREVIEW_FRAMES,
                      INTRO_MARGIN, INTRO_LINE_HEIGHT, load_intro_pages,
                      load_hub_intro_lines)
from .battle_transition import (BATTLE_TRANSITION_HOLD_FRAMES, BATTLE_TRANSITION_FRAMES,
                                BATTLE_TRANSITION_FLASH_FRAMES, draw_pieces)
from .hub import (HUB_IMAGE_BANK, HUB_PICTURE_SIZE, HUB_FACILITIES, HUB_ICONS, HUB_PICTURES,
                  HUB_DESCRIPTIONS, HUB_MENUS)
from .sound import play_cue, start_battle_music, stop_battle_music
from .tiles import (DUNGEON_RESOURCE, MAP_IMAGE_BANK, BOSS_FLOORS,
                    TILE_CHEST_OPEN, TILE_BOSS, TILE_BOSS_CLEAR, TILE_SIZE,
                    TILE_FLOOR, FLOOR_TILES, TILE_RARE_CHEST, TILE_QUEST,
                    TILE_SWITCH, TILE_SWITCH_ON, TILE_DOOR, TILE_DOOR_OPEN,
                    TILE_GUARDIAN, TILE_WARNING)


MAP_X, MAP_Y = 2, 13
MAP_WIDTH = MAP_HEIGHT = 96
PLAYER_WIDTH = PLAYER_HEIGHT = 16
PLAYER_SPRITES = {"up": (64, 0), "down": (80, 0),
                  "right": (96, 0), "left": (112, 0)}
TRANSITION_INPUTS = (pyxel.KEY_UP, pyxel.KEY_DOWN, pyxel.KEY_LEFT, pyxel.KEY_RIGHT,
                     pyxel.KEY_Z, pyxel.KEY_X, pyxel.KEY_RETURN, pyxel.KEY_SPACE,
                     pyxel.KEY_ESCAPE, pyxel.GAMEPAD1_BUTTON_DPAD_UP,
                     pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,
                     pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT, pyxel.GAMEPAD1_BUTTON_A,
                     pyxel.GAMEPAD1_BUTTON_B)
FINAL_EVENT_STATES = ('amrita_offer', 'final_story', 'final_retry', 'ending')


class DungeonApp(App):
    def __init__(self, session, run=True, headless=False, start_at_title=True):
        if not DUNGEON_RESOURCE.is_file():
            raise ValueError("game.pyxresがありません。同梱リソースを戻してください。")
        super().__init__(session, run=False, headless=headless, battle_on_start=False)
        self.initial_content = deepcopy((session.settings, session.skills,
                                         session.party, session.enemy_data))
        self.initial_rng_state = session.rng.getstate()
        self.initial_debug = session.debug
        self.intro_pages = load_intro_pages()
        self.hub_intro_lines = load_hub_intro_lines()
        self.hub_intro_shown = False
        self.title_cursor = self.intro_page = self.title_fade_remaining = 0
        self.hub_preview_remaining = 0
        self.opening_input_blocked = False
        self.dungeon = Dungeon(load_maps(), session.enemy_data, load_dungeon_settings(), session.rng,
                               session.treasure, session.inventory)
        self.rumors = json.loads((ROOT / "data/pub_messages.json").read_text(encoding="utf-8-sig"))
        self.last_rumor = None
        self.exploration = Exploration(session, self.dungeon)
        self.quest_cursor = self.feedback_cursor = 0
        self.quest_type_cursor = 0
        self.quest_flavor_page = 0
        self.quest_offer_cursor = 0
        self.relearn_cursor = self.treasure_cursor = 0
        self.return_lines = []
        self.player_facing = "down"
        self.floor_cursor = self.effect_cursor = self.message_page = 0
        self.menu_cursor = self.item_cursor = self.camp_cursor = self.catalog_cursor = 0
        self.facility_cursor = self.facility_index = 0
        self.facility_back = "camp"
        self.item_kind_cursor = self.shop_cursor = self.pub_cursor = 0
        self.archive_cursor = 0
        self.archive_page = 0
        self.battle = None
        self.battle_is_boss = False
        self.battle_kind = 'normal'
        self.next_guardian_index = None
        self.battle_position = None
        self.battle_transition_image = pyxel.Image(pyxel.width, pyxel.height)
        self.battle_transition_frame = 0
        self.battle_transition_hold = 0
        self.battle_input_blocked = False
        self.final_battle_data = load_final_battle_data()
        self.final_checkpoint = None
        self.final_choice = self.final_story_page = self.ending_page = 0
        self.final_question_page = 0
        self.camp_offer_pending = False
        self.explore_message = "入口へ戻ると全回復"
        self.enter_camp()
        if start_at_title:
            self.state = "title"
        if run:
            pyxel.run(self.update, self.draw)

    def start_new_game(self):
        """Reset every run-owned system before the opening story begins."""
        self.final_presentation = None
        self.session = Session(*deepcopy(self.initial_content))
        self.session.treasure.banked = NEW_GAME_BANKED_TRZ
        self.session.rng.setstate(self.initial_rng_state)
        self.session.debug = self.initial_debug
        self.dungeon = Dungeon(load_maps(), self.session.enemy_data,
                               load_dungeon_settings(), self.session.rng,
                               self.session.treasure, self.session.inventory)
        self.exploration = Exploration(self.session, self.dungeon)
        self.last_rumor = None
        self.return_lines = []
        self.battle = None
        self.battle_is_boss = False
        self.battle_position = None
        self.battle_kind = 'normal'
        self.next_guardian_index = None
        self.final_checkpoint = None
        self.final_choice = self.final_story_page = self.ending_page = 0
        self.final_question_page = 0
        self.camp_offer_pending = False
        self.player_facing = "down"
        self.overlay = None
        self.notice = ""
        self.enter_camp()
        self.intro_page = 0
        self.hub_intro_shown = False
        self.hub_preview_remaining = 0
        self.title_fade_remaining = TITLE_FADE_FRAMES
        self.opening_input_blocked = True
        self.state = "title_fade"

    def update_opening(self):
        if self.state == "title_fade":
            self.title_fade_remaining -= 1
            if self.title_fade_remaining <= 0:
                self.state = "intro"
            return
        if self.state == "hub_preview":
            self.hub_preview_remaining -= 1
            if self.hub_preview_remaining <= 0:
                self.state = "hub_intro"
            return
        if self.opening_input_blocked:
            if not any(pyxel.btn(button) for button in TRANSITION_INPUTS):
                self.opening_input_blocked = False
            return
        if self.state == "title":
            self.title_cursor = (self.title_cursor + self.direction()) % len(TITLE_OPTIONS)
            if self.confirm():
                if self.title_cursor == 0:
                    self.start_new_game()
                else:
                    self.state = "title_no_save"
        elif self.state == "title_no_save":
            if self.confirm() or self.cancel():
                self.state = "title"
        elif self.state == "intro" and self.confirm():
            if self.intro_page + 1 < len(self.intro_pages):
                self.intro_page += 1
            else:
                if self.hub_intro_shown:
                    self.enter_camp()
                else:
                    self.hub_preview_remaining = HUB_PREVIEW_FRAMES
                    self.opening_input_blocked = True
                    self.state = "hub_preview"
        elif self.state == "hub_intro" and self.confirm():
            self.hub_intro_shown = True
            self.enter_camp()
            self.opening_input_blocked = True

    def draw_title_logo(self):
        """Replace only this method with Image Bank blits for future title art."""
        text((pyxel.width - text_width(TITLE_MAIN)) // 2, 28, TITLE_MAIN, 3)
        text((pyxel.width - text_width(TITLE_SUBTITLE)) // 2, 43,
             TITLE_SUBTITLE, 2)

    def draw_title_menu(self):
        for index, label in enumerate(TITLE_OPTIONS):
            y = 70 + index * 17
            display = ("> " if index == self.title_cursor else "  ") + label
            width = text_width(display)
            x = (pyxel.width - width) // 2
            if index == self.title_cursor:
                pyxel.rect(x - 5, y - 2, width + 10, 13, 1)
            text(x, y, display, 3 if index == self.title_cursor else 2)

    def draw_title(self):
        pyxel.cls(0)
        pyxel.line(17, 21, 142, 21, 1)
        self.draw_title_logo()
        pyxel.line(17, 57, 142, 57, 1)
        self.draw_title_menu()
        self.footer("D-PAD:選択 A:決定")

    def draw_title_no_save(self):
        pyxel.cls(0)
        self.draw_title_logo()
        pyxel.rect(14, 68, 132, 22, 1)
        message = "セーブデータがありません"
        text((pyxel.width - text_width(message)) // 2, 75, message, 3)
        self.footer("A/B:タイトルへ")

    def draw_opening_page(self, lines):
        """Center editable story lines, including their intentional blank lines."""
        pyxel.cls(3)
        display_lines = wrap_lines(lines, (pyxel.width - 2 * INTRO_MARGIN) // 4)
        count = len(display_lines)
        line_height = min(INTRO_LINE_HEIGHT, max(FONT_HEIGHT,
                          (pyxel.height - 2 * INTRO_MARGIN - FONT_HEIGHT) // max(1, count - 1)))
        block_height = FONT_HEIGHT + (count - 1) * line_height
        y = (pyxel.height - block_height) // 2
        for line in display_lines:
            if line:
                text((pyxel.width - text_width(line)) // 2, y, line, 0)
            y += line_height

    def draw_intro(self):
        self.draw_opening_page(self.intro_pages[self.intro_page])

    def draw_hub_intro(self):
        self.draw_opening_page(self.hub_intro_lines)

    def enter_camp(self, defeated=False, returned=False):
        stop_battle_music()
        self.dungeon.finale.abort_guardians()
        self.next_guardian_index = None
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
        self.facility_back = "camp"
        self.notice_timer = 0
        self.camp_message = "全滅・回復 / 調査はやり直し" if defeated else "全員のHPを回復しました"
        # All ordinary external arrivals use returned/defeated. Facility exits
        # only change state to camp and cannot re-open this confirmation.
        self.camp_offer_pending = bool((returned or defeated) and self.dungeon.finale.can_offer_amrita)
        self.final_choice = 0
        self.final_question_page = 0
        if returned:
            self.state = "return_result"
        elif quest_failure:
            self.show_field_event(quest_failure, return_state='amrita_offer' if self.camp_offer_pending else 'camp')
            self.camp_offer_pending = False
        elif self.camp_offer_pending:
            self.show_amrita_offer()

    def enter_dungeon(self):
        if self.dungeon.cleared:
            # A new trip always starts at B1, even after the clear banner.
            self.dungeon.enter(allow_cleared=True)
            self.exploration.springs.clear()
            self.player_facing = "down"
            self.state, self.notice_timer = "explore", 0
            return
        self.dungeon.enter()
        self.exploration.springs.clear()
        self.player_facing = "down"
        self.state = "explore"
        self.explore_message = "入口から出発した"
        if self.exploration.hint():
            self.show_field_event([self.exploration.hint()])

    def begin_encounter(self, boss=False, animate=False, guardian_index=None, quest_hunt=False):
        self.final_presentation = None
        boss = boss or guardian_index is not None
        animate = animate and not boss
        if animate:
            # Draw the current position, including the step that triggered battle.
            pyxel.cls(0)
            self.draw_explore()
            self.battle_transition_image.blt(0, 0, pyxel.screen, 0, 0,
                                             pyxel.width, pyxel.height)
        self.fanfare_started_at = None
        self.fanfare_start_frame = None
        self.battle_position = self.dungeon.floor, self.dungeon.x, self.dungeon.y
        self.battle_is_boss = boss
        self.battle_kind = ('quest_hunt' if quest_hunt else 'guardian' if guardian_index is not None else
                            'demon' if boss and self.dungeon.floor == 14 else
                            'boss' if boss else 'normal')
        enemies = self.exploration.make_hunt_enemy() if quest_hunt else self.dungeon.make_enemies(boss, guardian_index)
        self.battle = self.session.next_battle(enemies, recover=False,
                                               spark_multiplier=self.dungeon.spark_multiplier, boss=boss)
        self.notice_timer = 0
        self.log = [self.battle.enemies[0].name + "との決戦!" if boss else "敵と遭遇した!"]
        self.pending = deque()
        self.begin_input()
        self.shake_timer = 0
        self.battle_input_blocked = animate
        self.debug_return_state = None
        self.debug_return_overlay = None
        if boss:
            stop_battle_music()
        elif animate:
            self.state = "battle_transition"
            self.battle_transition_frame = 0
            self.battle_transition_hold = BATTLE_TRANSITION_HOLD_FRAMES
            play_cue("battle_transition")
        else:
            start_battle_music()

    def finish_results(self):
        if self.session.pending_replacements or self.waiting_for_fanfare():
            return
        stop_battle_music()
        if self.battle_kind == 'elysion':
            if self.battle.outcome == 'VICTORY':
                self.dungeon.finale.final_victory()
                self.final_checkpoint = None
                self.state, self.ending_page = 'ending', 0
            else:
                self.state, self.final_choice = 'final_retry', 0
                self.final_question_page = 0
            self.overlay, self.notice_timer = None, 0
            return
        self.trace("RETURN MAP" if self.battle.outcome != "DEFEAT" else "RETURN CAMP")
        if self.battle.outcome == "DEFEAT":
            self.enter_camp(defeated=True)
        elif self.battle_kind == 'guardian':
            self.dungeon.floor, self.dungeon.x, self.dungeon.y = self.battle_position
            f = self.dungeon.finale
            if self.battle.outcome != 'VICTORY':
                f.abort_guardians()
                self.next_guardian_index = None
                self.show_field_event(['守護者との決着はつかなかった。', '連戦は最初からやり直しになる。'])
                return
            finished = f.guardian_victory()
            self.next_guardian_index = f.guardian_index
            self.message_lines = wrap_lines(f.data['guardian_after'] if finished else
                                             f.data['guardian_between'][f.guardian_index - 1], 36)
            self.state = 'guardian_after' if finished else 'guardian_between'
            self.message_page, self.notice_timer = 0, 0
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
            if self.battle_kind == 'quest_hunt' and self.battle.outcome == 'VICTORY':
                self.show_field_event(self.exploration.hunt_victory())

    def next_result_label(self):
        if self.battle_kind == 'elysion':
            return '旅の結末へ' if self.battle.outcome == 'VICTORY' else '再挑戦の確認へ'
        if self.battle.outcome == "DEFEAT":
            return "拠点へ"
        if self.battle_kind == 'guardian' and self.battle.outcome == 'VICTORY':
            return '守護者との連戦へ'
        if self.battle_is_boss and self.battle.outcome == "VICTORY":
            return "撃破後の会話へ"
        return "探索へ"

    def handle_event(self, event, message):
        if event == 'lore':
            self.show_field_event(self.dungeon.finale.read(message))
            return
        if event == 'guardian':
            self.message_lines = wrap_lines(self.dungeon.finale.data['guardian_warning'], 36)
            self.message_page, self.notice_timer = 0, 0
            self.state, self.overlay = 'guardian_warning', None
            return
        if event == "chest":
            lines = [message] + self.exploration.chest_effect(self.dungeon.last_reward)
            play_cue("chest")
            self.show_field_event(lines)
            return
        if event == "poison":
            self.show_field_event([message] + self.exploration.damage(self.dungeon.exploration_settings["poison_damage"]))
            return
        if event in ("pit", "switch"):
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
            self.begin_encounter(animate=True)
        elif event == "base":
            self.return_lines = []
            self.enter_camp(returned=True)

    def update(self):
        self.keyboard.update()
        if self.state == 'amrita_effect':
            super().update()
            return
        if self.state in ("title", "title_no_save", "title_fade", "intro",
                          "hub_preview", "hub_intro"):
            self.update_opening()
            return
        if self.state in FINAL_EVENT_STATES:
            self.update_final_event()
            return
        if self.opening_input_blocked:
            if not any(pyxel.btn(button) for button in TRANSITION_INPUTS):
                self.opening_input_blocked = False
            return
        if self.state == "battle_transition":
            if self.battle_transition_hold:
                self.battle_transition_hold -= 1
                return
            self.battle_transition_frame += 1
            if self.battle_transition_frame >= BATTLE_TRANSITION_FRAMES:
                self.state = "command"
                start_battle_music()
            return
        if self.battle_input_blocked:
            # Require a released frame, then a fresh press for the first command.
            if not any(pyxel.btn(button) for button in TRANSITION_INPUTS):
                self.battle_input_blocked = False
            return
        if self.state in ('guardian_warning', 'guardian_between', 'guardian_after'):
            self.update_guardians()
            return
        if self.session.debug and self.state == "explore" and not self.overlay and self.pressed(pyxel.KEY_T):
            self.begin_encounter(animate=True)
            return
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
        if self.state in ("field_event", "quest_board", "quest_type", "quest_preview"):
            self.notice_timer = max(0, self.notice_timer - 1)
            self.update_field_ui()
            return
        if self.state in ("relearn_character", "relearn_list", "relearn_confirm", "field_return", "return_result"):
            self.notice_timer = max(0, self.notice_timer - 1)
            self.update_camp_resources()
            return
        if self.state not in ("camp", "facility", "archive", "explore", "menu", "items", "item_target", "shop", "pub", "field_heal", "clear", "boss_message", "boss_after"):
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
                    if floor == 14:
                        self.dungeon.finale.guardians_defeated = True
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
                    self.state = "explore"
                    self.explore_message = ('アムリタを持ち帰ろう' if self.dungeon.finale.has_amrita else
                                            '先の階層への道が開いた')
        elif self.state == "camp":
            self.camp_cursor = (self.camp_cursor + self.direction()) % len(HUB_FACILITIES)
            if confirm:
                if self.camp_cursor == 4:
                    self.enter_dungeon()
                else:
                    self.facility_index = self.camp_cursor
                    self.facility_cursor = 0
                    self.state = "facility"
        elif self.state == "facility":
            self.facility_cursor = (self.facility_cursor + self.direction()) % len(HUB_MENUS[self.facility_index])
            if cancel:
                self.facility_back = "camp"
                self.state = "camp"
            elif confirm:
                facility, option = self.facility_index, self.facility_cursor
                if facility == 3 and option == 1:
                    self.facility_back = "camp"
                    self.state = "camp"
                else:
                    self.facility_back = "facility"
                    if facility == 0:
                        if option == 0:
                            self.overlay, self.info_tab, self.scroll = "info", 0, 0
                        else:
                            self.overlay = "help"
                    elif facility == 1:
                        if option == 0:
                            self.state, self.archive_page, self.archive_cursor = "archive", 0, 0
                        else:
                            self.state, self.notice_timer = "relearn_character", 0
                    elif facility == 2:
                        self.state = "quest_board" if option == 0 else "pub"
                        self.quest_cursor = self.pub_cursor = 0
                        self.quest_type_cursor = 0
                        self.quest_flavor_page = 0
                    else:
                        self.state, self.shop_cursor = "shop", 0
        elif self.state == "shop":
            self.shop_cursor = (self.shop_cursor + self.direction()) % 3
            if cancel:
                self.state = self.facility_back
            elif confirm:
                item = ("POTION", "PHOENIX ASH", "REMEDY")[self.shop_cursor]
                self.tell(self.session.inventory.buy(item, self.session.treasure)[1])
        elif self.state == "pub":
            self.pub_cursor = (self.pub_cursor + self.direction()) % 2
            if cancel or (confirm and self.pub_cursor):
                self.state = self.facility_back
            elif confirm:
                cost = self.session.inventory.data["pub_cost"]
                if self.session.treasure.banked < cost:
                    self.tell(f"確定した{CURRENCY_NAME}が足りません")
                else:
                    self.session.treasure.banked -= cost
                    pool = self.rumors["gameplay" if self.session.rng.random() < self.session.inventory.data["pub_gameplay_weight"] else "flavor"]
                    choices = [line for line in pool if line != self.last_rumor] or pool
                    self.last_rumor = self.session.rng.choice(choices)
                    self.show_field_event(["酒場の噂:", self.last_rumor], return_state="pub")
        elif self.state == "archive":
            if cancel:
                self.state = self.facility_back
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
                self.quest_or_field_event(self.dungeon.interact, contact=False)
            else:
                dx, dy = self.direction(horizontal=True), self.direction()
                if dx:
                    dy = 0
                if dx or dy:
                    self.player_facing = ("right" if dx > 0 else "left") if dx else ("down" if dy > 0 else "up")
                    previous = self.dungeon.floor, self.dungeon.x, self.dungeon.y
                    event = self.dungeon.move(dx, dy, self.session.debug)
                    if (self.dungeon.floor, self.dungeon.x, self.dungeon.y) != previous:
                        self.quest_or_field_event(lambda: event, contact=True)
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
        if self.state == "title":
            self.draw_title()
        elif self.state == "title_no_save":
            self.draw_title_no_save()
        elif self.state == "title_fade":
            pyxel.cls(0)
        elif self.state == "intro":
            self.draw_intro()
        elif self.state == "hub_preview":
            pyxel.cls(0)
            self.draw_camp()
        elif self.state == "hub_intro":
            self.draw_hub_intro()
        elif self.state in FINAL_EVENT_STATES:
            self.draw_final_event()
        elif self.state == "battle_transition":
            flash = self.battle_transition_frame in BATTLE_TRANSITION_FLASH_FRAMES
            if flash:
                # Brighten existing palette indices for a single frame; no new colors.
                pyxel.pal(0, 2)
                pyxel.pal(1, 3)
                pyxel.pal(2, 3)
            try:
                super().draw()
                draw_pieces(self.battle_transition_image, self.battle_transition_frame)
            finally:
                if flash:
                    pyxel.pal()
        elif self.overlay == "feedback_debug":
            self.draw_feedback_debug()
        elif not self.overlay and self.state in ('guardian_warning', 'guardian_between', 'guardian_after'):
            pyxel.cls(0)
            self.draw_guardians()
        elif not self.overlay and self.state in ("field_event", "quest_board", "quest_type", "quest_preview"):
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
        elif self.overlay or self.state not in ("camp", "facility", "archive", "explore", "menu", "items", "item_target", "shop", "pub", "field_heal", "clear", "boss_message", "boss_after"):
            super().draw()
            if self.overlay == "info" and self.info_tab == 1 and self.state in ("explore", "menu"):
                self.footer("左右:人 上下:技 A:回復/頁 B:閉じる")
        else:
            pyxel.cls(0)
            if self.state == "camp":
                self.draw_camp()
            elif self.state == "facility":
                self.draw_facility()
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
        self.title("BASE / TOWN HUB" + (" DEBUG" if self.session.debug else ""))
        for i, (name, sprite) in enumerate(zip(HUB_FACILITIES, HUB_ICONS)):
            y = 16 + i * 19
            if i == self.camp_cursor:
                pyxel.rect(3, y - 1, 82, 18, 1)
                pyxel.rectb(3, y - 1, 82, 18, 3)
            pyxel.blt(5, y, HUB_IMAGE_BANK, *sprite, 16, 16, 0)
            text(24, y + 5, (">" if i == self.camp_cursor else " ") + name,
                 3 if i == self.camp_cursor else 2, 18)
        pyxel.blt(94, 20, HUB_IMAGE_BANK, *HUB_PICTURES[self.camp_cursor],
                  HUB_PICTURE_SIZE, HUB_PICTURE_SIZE, 0)
        text(91, 89, f"{self.session.completed}戦", 2, 16)
        text(91, 100, f"{CURRENCY_NAME} {self.session.treasure.banked}", 2, 16)
        self.footer("D-PAD:選択 A:入る B:戻る")

    def draw_facility(self):
        index = self.facility_index
        self.title(HUB_FACILITIES[index] + " / BASE")
        pyxel.blt(94, 20, HUB_IMAGE_BANK, *HUB_PICTURES[index],
                  HUB_PICTURE_SIZE, HUB_PICTURE_SIZE, 0)
        text(6, 22, HUB_DESCRIPTIONS[index], 2, 21)
        for i, label in enumerate(HUB_MENUS[index]):
            y = 57 + i * 18
            if i == self.facility_cursor:
                pyxel.rect(4, y - 2, 86, 14, 1)
            text(8, y, (">" if i == self.facility_cursor else " ") + label,
                 3 if i == self.facility_cursor else 2, 21)
        text(7, 100, f"BANKED {CURRENCY_NAME} {self.session.treasure.banked}", 2, 30)
        self.footer("D-PAD:選択 A:決定 B:拠点")

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
        width, height = d.map_bounds(d.floor)
        self.title(f"B{d.floor + 1}F 薬{d.potions} 未確定{CURRENCY_NAME}{d.treasure.unbanked}" + (" DEBUG" if self.session.debug else ""))
        camera_x = d.x * TILE_SIZE + TILE_SIZE // 2 - MAP_WIDTH // 2
        camera_y = d.y * TILE_SIZE + TILE_SIZE // 2 - MAP_HEIGHT // 2
        source_x = max(0, camera_x)
        source_y = max(0, camera_y)
        source_right = min(width * TILE_SIZE, camera_x + MAP_WIDTH)
        source_bottom = min(height * TILE_SIZE, camera_y + MAP_HEIGHT)
        draw_width = max(0, source_right - source_x)
        draw_height = max(0, source_bottom - source_y)
        pyxel.clip(MAP_X, MAP_Y, MAP_WIDTH, MAP_HEIGHT)
        if draw_width and draw_height:
            pyxel.bltm(MAP_X + source_x - camera_x,
                       MAP_Y + source_y - camera_y,
                       d.maps[d.floor], source_x, source_y,
                       draw_width, draw_height)
        # Candidate markers stay editable in Tilemap but look like ordinary floor.
        if d.floor in d.activated_switches:
            for source, replacement in ((TILE_SWITCH, TILE_SWITCH_ON), (TILE_DOOR, TILE_DOOR_OPEN)):
                for x, y in d.positions(d.floor, source):
                    u, v = replacement
                    pyxel.blt(MAP_X + x * TILE_SIZE - camera_x,
                              MAP_Y + y * TILE_SIZE - camera_y,
                              MAP_IMAGE_BANK, u * TILE_SIZE, v * TILE_SIZE,
                              TILE_SIZE, TILE_SIZE)
        for x, y in d.positions(d.floor, TILE_QUEST):
            u, v = d.floor_appearance(d.floor, x, y)
            pyxel.blt(MAP_X + x * TILE_SIZE - camera_x,
                      MAP_Y + y * TILE_SIZE - camera_y,
                      MAP_IMAGE_BANK, u * TILE_SIZE, v * TILE_SIZE,
                      TILE_SIZE, TILE_SIZE)
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
        for x, y in self.exploration.visible_points():
            bank, u, v = QUEST_SYMBOLS[self.exploration.active_quest['type']]
            pyxel.blt(MAP_X + x * TILE_SIZE - camera_x, MAP_Y + y * TILE_SIZE - camera_y,
                      bank, u, v, TILE_SIZE, TILE_SIZE, 0)
        # Map-only facing sprites in Image Bank 0 of game.pyxres.
        if d.floor == 14 and d.finale.guardians_defeated:
            x, y = d.find(14, TILE_GUARDIAN)
            u, v = d.floor_appearance(14, x, y)
            pyxel.blt(MAP_X + x * TILE_SIZE - camera_x, MAP_Y + y * TILE_SIZE - camera_y,
                      MAP_IMAGE_BANK, u * TILE_SIZE, v * TILE_SIZE, TILE_SIZE, TILE_SIZE)
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
        text(8, 99, f"入口かRETURNで{CURRENCY_NAME}を確定", 2, 36)
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
        text(5, 16, f"確定{CURRENCY_NAME} {self.session.treasure.banked}", 3, 37)
        for i, item in enumerate(("POTION", "PHOENIX ASH", "REMEDY")):
            row = self.session.inventory.data["items"][item]
            text(5, 34 + i * 17, (">" if i == self.shop_cursor else " ") +
                 f"{item} {row['price']} {CURRENCY_NAME} x{self.session.inventory.counts[item]}/9",
                 3 if i == self.shop_cursor else 2, 37)
        self.footer("上下:選択 A:購入 B:拠点へ")

    def draw_pub(self):
        self.title("PUB / 情報購入")
        text(8, 24, f"確定{CURRENCY_NAME} {self.session.treasure.banked}", 3, 35)
        text(8, 39, f"噂を聞く? {self.session.inventory.data['pub_cost']} {CURRENCY_NAME}", 2, 35)
        for i, label in enumerate(("YES", "NO")):
            text(12, 61 + i * 16, (">" if i == self.pub_cursor else " ") + label, 3, 20)
        self.footer("上下:選択 A:決定 B:拠点へ")

    def draw_clear(self):
        self.title("アムリタ取得")
        text(12, 28, "デーモンを倒した!", 3, 34)
        text(12, 45, f"{self.session.completed}戦 / {self.session.wins}勝", 2, 34)
        text(12, 60, f"{CURRENCY_NAME} 確定{self.session.treasure.banked} 未確定{self.session.treasure.unbanked}", 2, 34)
        text(12, 78, "Dで育成結果を確認できます", 2, 34)
        text(12, 93, f"依頼の成果と{CURRENCY_NAME}を持ち帰ろう", 2, 34)
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
                if self.camp_offer_pending and self.dungeon.finale.can_offer_amrita:
                    self.show_amrita_offer()
        elif self.state == "field_return":
            if self.dungeon.finale.guardian_index is not None:
                self.tell(self.dungeon.finale.data['return_locked'][0])
                return
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
                self.state = self.facility_back
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
            text(6, 19, f"{self.return_secured} {CURRENCY_NAME}を確保", 3, 37)
            text(6, 32, f"確定{CURRENCY_NAME}: {s.treasure.banked}", 3, 37)
            text(6, 45, f"未確定{CURRENCY_NAME}: 0 / 全員HP回復", 2, 37)
            for i, line in enumerate(wrap_lines(self.return_lines, 36)[:5]):
                text(6, 59 + i * 9, line, 2, 37)
            self.footer("A:拠点へ")
        elif self.state in ("relearn_character", "field_return"):
            returning = self.state == "field_return"
            self.title("RETURN / 使用者を選ぶ" if returning else "再習得 / キャラを選ぶ")
            text(5, 16, f"未確定{CURRENCY_NAME} {s.treasure.unbanked}を確保" if returning else f"確定{CURRENCY_NAME} {s.treasure.banked}", 2, 37)
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
            text(5, 16, f"{CURRENCY_NAME} {s.treasure.banked} 基本/通常/RARE補助", 2, 37)
            start = max(0, self.relearn_cursor - 5)
            for i, skill in enumerate(candidates[start:start + 6]):
                selected = start + i == self.relearn_cursor
                text(5, 30 + i * 11, (">" if selected else " ") + skill.name, 3 if selected else 2, 23)
                text(101, 30 + i * 11, "所持中" if skill.id in actor.skills else f"{skill.relearn_cost} {CURRENCY_NAME}", 2, 14)
            if candidates:
                skill = candidates[self.relearn_cursor]
                text(5, 100, f"再習得{actor.relearn_uses(skill)}/{actor.next_max_uses(skill)}回 / {skill.relearn_cost} {CURRENCY_NAME}", 2, 37)
            else:
                text(5, 35, "再習得できる発見済み技なし", 2, 37)
            self.footer("上下:技 A:確認 B:人選択")
        else:
            actor = s.party[self.info_character]
            skill = s.skills[self.relearn_skill]
            self.title("再習得の確認")
            text(5, 20, actor.name + " / " + skill.name, 3, 37)
            text(5, 36, f"COST {skill.relearn_cost} {CURRENCY_NAME} / 所持{s.treasure.banked}", 2, 37)
            text(5, 50, f"使用回数 {actor.relearn_uses(skill)}/{actor.next_max_uses(skill)}", 3, 37)
            text(5, 66, "満杯なら入れ替えを選択", 2, 37)
            text(5, 82, f"取り消しでは{CURRENCY_NAME}を消費しない", 2, 37)
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
        e = self.exploration
        if self.state == "quest_preview":
            if cancel:
                e.decline_preview()
                self.state, self.notice_timer = "quest_type", 0
                return
            pages = self.quest_flavor_pages(e.pending_quest)
            if self.quest_flavor_page + 1 < len(pages):
                if confirm:
                    self.quest_flavor_page += 1
                return
            self.quest_offer_cursor = (self.quest_offer_cursor + self.direction()) % 2
            if confirm:
                if self.quest_offer_cursor:
                    e.decline_preview()
                    self.state, self.notice_timer = "quest_type", 0
                else:
                    try:
                        message = e.accept_preview()
                        self.state, self.quest_flavor_page = "quest_board", 0
                        self.tell(message)
                    except ValueError as error:
                        self.tell(str(error))
            return
        if cancel:
            self.state = "quest_board" if self.state == "quest_type" else self.facility_back
            self.notice_timer = 0
            return
        if e.active_quest:
            if confirm:
                pages = self.quest_flavor_pages()
                if len(pages) > 1:
                    self.quest_flavor_page = (self.quest_flavor_page + 1) % len(pages)
                    self.notice_timer = 0
                else:
                    self.tell(e.message('already_active'))
            return
        if self.state == "quest_board":
            self.quest_cursor = (self.quest_cursor + self.direction()) % len(e.quest_data['levels'])
            if confirm:
                row = e.quest_data['levels'][self.quest_cursor]
                if e.unlocked(row):
                    self.state, self.quest_type_cursor, self.notice_timer = "quest_type", 0, 0
                else:
                    self.tell(f"B{row['gate']}Fボス撃破でLv{row['level']}解放")
        else:
            self.quest_type_cursor = (self.quest_type_cursor + self.direction()) % len(QUEST_TYPES)
            if confirm:
                try:
                    level = e.quest_data['levels'][self.quest_cursor]['level']
                    e.preview_quest(level, QUEST_TYPES[self.quest_type_cursor])
                    self.state, self.notice_timer = "quest_preview", 0
                    self.quest_flavor_page = self.quest_offer_cursor = 0
                except ValueError as error:
                    self.tell(str(error))

    def quest_flavor_pages(self, quest=None):
        lines = wrap_lines(self.exploration.quest_flavor(quest)['lines'], QUEST_FLAVOR_MAX_CHARS)
        return [lines[i:i + QUEST_FLAVOR_LINES_PER_PAGE]
                for i in range(0, len(lines), QUEST_FLAVOR_LINES_PER_PAGE)]

    def draw_field_ui(self):
        pyxel.cls(0)
        if self.state == "field_event":
            self.title("探索 / 調査と発見")
            pyxel.rectb(3, 17, 154, 84, 2)
            for i, line in enumerate(self.field_lines[self.field_page * 8:(self.field_page + 1) * 8]):
                text(7, 24 + i * 9, line, 3, 36)
            self.footer("A:次へ")
            return
        self.title("QUEST BOARD / 依頼")
        e = self.exploration
        preview = self.state == "quest_preview"
        q = e.pending_quest if preview else e.active_quest
        if q:
            text(5, 15, e.quest_name(q) + (" / 受注確認" if preview else ""), 3, 37)
            pages = self.quest_flavor_pages(q)
            for i, line in enumerate(pages[self.quest_flavor_page % len(pages)]):
                text(7, 28 + i * QUEST_FLAVOR_LINE_HEIGHT, line, 2, QUEST_FLAVOR_MAX_CHARS)
            text(7, 58, "― " + e.quest_flavor(q)['requester'], 2, 36)
            text(5, 71, f"対象 B{q['target_floor']}F / {q['progress']} / {q['required_count']}", 3, 37)
            text(5, 83, f"報酬 {q['reward']} {CURRENCY_NAME}" + (" / 安全帰還" if preview else ""), 3, 37)
            if preview:
                if self.quest_flavor_page + 1 < len(pages):
                    self.footer("A:依頼文の続き B:受注しない")
                else:
                    for i, label in enumerate(("受注する", "受注しない")):
                        selected = i == self.quest_offer_cursor
                        text(5, 94 + i * 9, (">" if selected else " ") + label, 3 if selected else 2, 37)
                    self.footer("上下:選択 A:決定 B:戻る")
            else:
                text(5, 98, "目的達成・安全帰還で報酬" if q['completed'] else "安全帰還で報酬 / 全滅で進行失う", 2, 37)
                self.footer("A:依頼文の続き B:戻る" if len(pages) > 1 else "受注中 / B:戻る")
        elif self.state == "quest_type":
            row = e.quest_data['levels'][self.quest_cursor]
            level = row['level']
            text(5, 19, f"Lv{level} B{row['floors'][0]}～{row['floors'][1]}F / 種別", 3, 37)
            for i, kind in enumerate(QUEST_TYPES):
                selected = i == self.quest_type_cursor
                reward = e.quest_data['rewards'][kind][str(level)]
                text(5, 36 + i * 19, (">" if selected else " ") + QUEST_NAMES[kind], 3 if selected else 2, 15)
                text(85, 36 + i * 19, f"{reward} {CURRENCY_NAME}", 2, 17)
            text(5, 98, "安全帰還で報酬 / 同時1件", 2, 37)
            self.footer("上下:種別 A:依頼文 B:Lv選択")
        else:
            text(5, 19, "クエストLvを選ぶ", 3, 37)
            levels = e.quest_data['levels']
            for i, row in enumerate(levels):
                selected = i == self.quest_cursor
                label = f"Lv{row['level']} B{row['floors'][0]}～{row['floors'][1]}F"
                if not e.unlocked(row):
                    label += " 未解放"
                text(5, 36 + i * 19, (">" if selected else " ") + label, 3 if selected else 2, 37)
            row = levels[self.quest_cursor]
            hint = "解放済み / 同時受注1件" if e.unlocked(row) else f"B{row['gate']}Fボス撃破でLv{row['level']}解放"
            text(5, 98, hint, 2, 37)
            self.footer("上下:Lv A:種別選択 B:戻る")

    def quest_or_field_event(self, field_event, contact):
        if self.exploration.hunt_here():
            self.begin_encounter(quest_hunt=True, animate=contact)
            return
        lines = self.exploration.investigate()
        if lines:
            self.show_field_event(lines)
        else:
            self.handle_event(*field_event())

    def feedback_options(self):
        rewards = self.dungeon.exploration_settings["CHEST_REWARD_TABLE"]["NORMAL"]
        labels = {"TREASURE": CURRENCY_NAME, "POTION": "薬",
                  "SKILL_CHANCE": "閃き抽選", "TRAP": "罠", "EMPTY": "空の箱"}
        options = [(f"宝箱: {labels[r['kind']]} {r.get('amount', '')}", r) for r in rewards]
        options += [("RARE宝箱を足元に生成", "rare"), ("毒沼ダメージ", "poison"),
                    ("落とし穴をテスト", "pit")]
        options += [(f"探索Lv{i} 強制受注", i) for i in (1, 2, 3)]
        return options + [("調査地点へ移動", "warp"), ("調査完了ON/OFF", "survey"),
                          ("選択した人を戦闘不能", "ko"), ("REVIVEを取得", "revive"),
                          ("灰を1個取得", "ash"), ("薬を1個取得", "potion"),
                          ("全アイテムを9個に", "max_items"), ("泉へ移動", "spring"),
                          ("酒場へ", "pub"), (f"確定{CURRENCY_NAME}+10", "bank10")]

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
            if self.state != "explore" or d.tile(d.floor, d.x, d.y) not in FLOOR_TILES or e.target == (d.floor, d.x, d.y):
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
            self.tell(f"DEBUG: 確定{CURRENCY_NAME}+10")
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
        self.title(f"DEBUG / {CURRENCY_NAME}と帰還")
        text(5, 16, f"未確定{s.treasure.unbanked} / 確定{s.treasure.banked}", 3, 37)
        for i, label in enumerate((f"未確定{CURRENCY_NAME} +5", f"確定{CURRENCY_NAME} +5", f"未確定{CURRENCY_NAME}を0", "RETURNを取得", "拠点の再習得を開く")):
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

    def update_guardians(self):
        confirm, cancel = self.confirm(), self.cancel()
        if self.state == 'guardian_warning' and cancel:
            self.state = 'explore'
            return
        if not confirm:
            return
        if (self.message_page + 1) * 8 < len(self.message_lines):
            self.message_page += 1
            return
        f = self.dungeon.finale
        if self.state == 'guardian_warning':
            f.start_guardians()
            self.next_guardian_index = 0
            self.begin_encounter(boss=True, guardian_index=0)
        elif self.state == 'guardian_between':
            self.begin_encounter(boss=True, guardian_index=f.guardian_index)
        else:
            self.next_guardian_index = None
            self.dungeon.grace = self.dungeon.settings['safe_steps']
            self.state = 'explore'

    def draw_guardians(self):
        self.title('B15F / 守護者')
        pyxel.rectb(3, 17, 154, 84, 2)
        for i, line in enumerate(self.message_lines[self.message_page * 8:(self.message_page + 1) * 8]):
            text(7, 24 + i * 9, line, 3, 36)
        more = (self.message_page + 1) * 8 < len(self.message_lines)
        label = ('A:連戦へ B:戻る' if self.state == 'guardian_warning' else
                 'A:次の戦い' if self.state == 'guardian_between' else 'A:泉の先へ')
        self.footer('A:続きを読む' if more else label)

    def show_amrita_offer(self):
        self.state, self.overlay, self.notice_timer = 'amrita_offer', None, 0
        self.final_choice = 0
        self.final_question_page = 0
        self.camp_offer_pending = False

    def start_final_story(self):
        self.dungeon.finale.start_final_event()
        self.state, self.overlay = 'final_story', None
        self.final_story_page = 0

    def begin_final_battle(self):
        self.final_presentation = None
        f = self.dungeon.finale
        if not f.final_event_started or not f.has_amrita or f.amrita_power_spent:
            raise ValueError('アムリタを持って最終イベントへ進んでください。')
        if self.final_checkpoint is None:
            self.final_checkpoint = FinalBattleCheckpoint.capture(self.session, self.dungeon, self.exploration)
        self.battle = self.session.next_battle([make_final_enemy(self.session.enemy_data)],
            recover=False, boss=True, final_progress=f, final_data=self.final_battle_data)
        self.battle_kind, self.battle_is_boss = 'elysion', True
        self.battle_position = None
        self.overlay, self.notice_timer, self.shake_timer = None, 0, 0
        self.debug_return_state, self.debug_return_overlay = None, 'debug_skills'
        self.fanfare_started_at = self.fanfare_start_frame = None
        self.fanfare_timed_out = False
        self.log = wrap_lines(self.final_battle_data['battle_start'], 37)[-3:]
        self.pending = deque()
        self.begin_input()
        self.battle_input_blocked = True
        start_battle_music()

    def update_final_event(self):
        if self.pressed(pyxel.KEY_Q):
            pyxel.quit()
            return
        if self.pressed(pyxel.KEY_F9):
            self.session.debug = not self.session.debug
            return
        confirm, cancel = self.confirm(), self.cancel()
        if self.state in ('amrita_offer', 'final_retry'):
            page = getattr(self, 'final_question_page', 0)
            if page + 1 < len(self.final_question_pages()) and not cancel:
                if confirm:
                    self.final_question_page = page + 1
                return
            self.final_choice = (self.final_choice + self.direction()) % 2
            if cancel:
                self.final_choice = 1
                confirm = True
            if not confirm:
                return
            if self.state == 'amrita_offer':
                if self.final_choice:
                    self.state = 'camp'
                else:
                    self.start_final_story()
            elif self.final_choice:
                stop_battle_music()
                self.state, self.title_cursor = 'title', 0
                self.opening_input_blocked = True
            else:
                if self.final_checkpoint is None:
                    raise ValueError('決戦前の記録がありません。')
                stop_battle_music()
                self.final_checkpoint.restore(self.session, self.dungeon, self.exploration)
                self.begin_final_battle()
        elif self.state == 'final_story' and confirm:
            pages = self.final_story_pages()
            if self.final_story_page + 1 < len(pages):
                self.final_story_page += 1
            else:
                self.begin_final_battle()
        elif self.state == 'ending' and confirm:
            pages = self.final_ending_pages()
            if self.ending_page + 1 < len(pages):
                self.ending_page += 1
            else:
                self.state, self.title_cursor = 'title', 0
                self.opening_input_blocked = True

    def final_story_pages(self):
        pages = []
        for block in self.final_battle_data['story_pages']:
            lines = wrap_lines(block, 36)
            pages.extend(lines[i:i + 8] for i in range(0, len(lines), 8))
        return pages

    def final_question_pages(self):
        key = 'offer_question' if self.state == 'amrita_offer' else 'retry_question'
        lines = wrap_lines(self.final_battle_data[key], 36)
        return [lines[i:i + 5] for i in range(0, len(lines), 5)]

    def final_ending_pages(self):
        lines = wrap_lines(self.final_battle_data['victory'] + [''] + self.final_battle_data['ending_lines'], 36)
        return [lines[i:i + 8] for i in range(0, len(lines), 8)]

    def draw_final_event(self):
        pyxel.cls(0)
        if self.state in ('amrita_offer', 'final_retry'):
            self.title('王への献上' if self.state == 'amrita_offer' else '決戦 / 再挑戦')
            pages = self.final_question_pages()
            page = getattr(self, 'final_question_page', 0)
            for i, line in enumerate(pages[page]):
                text((pyxel.width - text_width(line)) // 2, 24 + i * 9, line, 3)
            if page + 1 < len(pages):
                self.footer('A:続きを読む B:戻る')
                return
            options = ('はい', '後で' if self.state == 'amrita_offer' else 'いいえ')
            for i, label in enumerate(options):
                display = ('> ' if self.final_choice == i else '  ') + label
                text((pyxel.width - text_width(display)) // 2, 78 + i * 14,
                     display, 3 if self.final_choice == i else 2)
            self.footer('上下:選択 A:決定 B:タイトルへ' if self.state == 'final_retry' else
                        '上下:選択 A:決定 B:戻る')
        else:
            ending = self.state == 'ending'
            self.title('旅の結末' if ending else '王城')
            pages = self.final_ending_pages() if ending else self.final_story_pages()
            current = self.ending_page if ending else self.final_story_page
            for i, line in enumerate(pages[current]):
                text(7, 24 + i * 9, line, 3, 36)
            last = current + 1 == len(pages)
            self.footer('A:タイトルへ' if ending and last else 'A:決戦へ' if last else 'A:続きを読む')

    def debug_final_stage(self, stage):
        if not self.session.debug or stage not in ('key', 'offer', 'story', 'battle'):
            return False
        if self.session.pending_replacements:
            self.tell('先に技の入替を終えてください。')
            return False
        f = self.dungeon.finale
        f.abort_guardians()
        f.guardians_defeated = f.demon_defeated = f.has_amrita = True
        f.final_event_started = f.lord_of_elysion_defeated = f.amrita_power_spent = False
        self.dungeon.defeated_bosses.add(14)
        self.final_checkpoint = None
        if stage == 'key':
            self.tell('DEBUG: アムリタ所持ON')
        else:
            self.enter_camp()
            if stage == 'offer':
                self.show_amrita_offer()
            else:
                self.start_final_story()
                if stage == 'battle':
                    self.begin_final_battle()
        return True

    def update_dungeon_debug(self):
        for key, stage in ((pyxel.KEY_4, 'key'), (pyxel.KEY_5, 'offer'),
                           (pyxel.KEY_6, 'story'), (pyxel.KEY_7, 'battle')):
            if self.pressed(key):
                self.debug_final_stage(stage)
                return
        self.floor_cursor = (self.floor_cursor + self.direction()) % 15
        for key, floor in zip((pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3), BOSS_FLOORS):
            if self.pressed(key):
                self.dungeon.defeated_bosses.symmetric_difference_update({floor})
                if floor == 14:
                    defeated = floor in self.dungeon.defeated_bosses
                    f = self.dungeon.finale
                    f.abort_guardians()
                    f.guardians_defeated = f.demon_defeated = f.has_amrita = defeated
        if self.pressed(pyxel.KEY_G, pyxel.KEY_M):
            demon = self.pressed(pyxel.KEY_M)
            self.dungeon.debug_floor(14)
            f = self.dungeon.finale
            f.abort_guardians()
            if demon:
                f.guardians_defeated = True
            self.dungeon.x, self.dungeon.y = self.dungeon.find(14, TILE_BOSS if demon else TILE_WARNING)
            self.state, self.overlay, self.notice_timer = 'explore', None, 0
            return
        if self.pressed(pyxel.KEY_Z, pyxel.KEY_RETURN, pyxel.KEY_B):
            boss = self.pressed(pyxel.KEY_B)
            floor = BOSS_FLOORS[self.floor_cursor // 5] if boss else self.floor_cursor
            self.dungeon.debug_floor(floor)
            if boss:
                self.dungeon.x, self.dungeon.y = self.dungeon.find(floor, TILE_BOSS)
                if floor == 14:
                    self.dungeon.finale.guardians_defeated = True
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
            text(5, 51 + i * 10, f"{i + 1}: B{floor + 1}F {flag}", 3, 37)
        text(5, 82, 'G:守護者前 M:デーモン前', 2, 37)
        text(5, 92, '4:秘宝 5:献上 6:会話 7:決戦', 2, 37)
        text(5, 102, '上下:階 B:ボス前', 2, 37)
        self.footer("Z:移動 1/2/3:撃破切替 X:閉じる")

    def draw_effects(self):
        units = self.battle.enemies + self.session.party
        unit = units[self.effect_cursor % len(units)]
        multiplier = self.session.spark_multiplier
        rate = spark_probability(self.session.settings, multiplier, self.session.debug)
        self.title("DEBUG AUDIO: " + self.audio_state())
        text(5, 16, f"{unit.name} 閃き x{multiplier:.2f} = {rate:.1%}", 2, 37)
        text(5, 27, f"AGI {battle_agility(unit):g} DEF {getattr(unit, 'defense', 0) * effect_factor(unit, 'armor_break'):g} GUARD {'ON' if unit.guarding else 'OFF'}", 2, 37)
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
                 "戦闘 SKILL/ITEM/GUARD/RUN", "GUARD:今ターンの被害半減", "技を使い切るとMASTERED", f"入口/RETURNで{CURRENCY_NAME}を確定"]
        for i, line in enumerate(lines):
            text(5, 18 + i * 10, line, 3 if i < 5 else 2, 37)
        self.footer("B:閉じる")
