"""160x120 UI. All rules live outside this module."""
from collections import deque
import time

import pyxel

from .art import load_art
from .models import Action
from .labels import TYPES, RARITIES, TARGETS, OUTCOMES, EFFECTS, CURRENCY_NAME
from .text import text, wrap_lines, font
from .sound import init_sound, play_cue, start_battle_music, stop_battle_music, play_victory_music, music_is_playing
from .growth import growth_bonus
from .keyboard import GameKeyboard
from .opening import GAME_TITLE
from .final_battle import AMRITA_ITEM_ID, LORD_OF_ELYSION_ID
from .final_presentation import FinalPresentation, AMRITA_MESSAGE_FRAME


# The official Web touch pad emits gamepad buttons, not keyboard keys.
GAMEPAD_KEYS = {
    pyxel.KEY_UP: pyxel.GAMEPAD1_BUTTON_DPAD_UP,
    pyxel.KEY_DOWN: pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,
    pyxel.KEY_LEFT: pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,
    pyxel.KEY_RIGHT: pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT,
    pyxel.KEY_Z: pyxel.GAMEPAD1_BUTTON_A,
    pyxel.KEY_X: pyxel.GAMEPAD1_BUTTON_B,
}

FANFARE_MAX_WAIT_SECONDS = 4.5
FANFARE_MAX_WAIT_FRAMES = 150


class App:
    def __init__(self, session, run=True, headless=False, battle_on_start=True):
        self.session = session
        pyxel.init(160, 120, title=GAME_TITLE, fps=30,
                   display_scale=5, quit_key=pyxel.KEY_NONE, headless=headless)
        self.keyboard = GameKeyboard(enabled=not headless)
        self.keyboard.update()
        load_art(pyxel)
        font()
        init_sound()
        self.overlay = None
        self.info_character = self.info_tab = self.scroll = 0
        self.result_page = 0
        self.notice = ""
        self.notice_timer = 0
        self.replacement_cursor = 0
        self.replacement_confirm = False
        self.debug_return_state = None
        self.debug_return_overlay = "debug_skills"
        self.debug_cursor = 0
        self.shake_timer = 0
        self.fanfare_started_at = None
        self.fanfare_start_frame = None
        self.fanfare_timed_out = False
        self.debug_events = []
        self.final_presentation = None
        if battle_on_start:
            self.start_battle()
        if run:
            pyxel.run(self.update, self.draw)

    def start_battle(self):
        self.final_presentation = None
        self.notice_timer = 0
        self.fanfare_started_at = None
        self.fanfare_start_frame = None
        self.battle = self.session.next_battle()
        self.log = ["新たな敵が現れた", "4人の行動を選ぼう"]
        self.pending = deque()
        self.begin_input()
        start_battle_music()

    def finish_results(self):
        if self.waiting_for_fanfare():
            return
        stop_battle_music()
        self.trace("NEXT BATTLE")
        self.start_battle()

    def waiting_for_fanfare(self):
        if self.battle.outcome != "VICTORY" or self.fanfare_started_at is None:
            return False
        elapsed = time.monotonic() - self.fanfare_started_at
        frames = pyxel.frame_count - self.fanfare_start_frame
        if elapsed >= FANFARE_MAX_WAIT_SECONDS or frames >= FANFARE_MAX_WAIT_FRAMES:
            if not self.fanfare_timed_out:
                self.fanfare_timed_out = True
                self.trace("FANFARE TIMEOUT")
                stop_battle_music()
            return False
        if not music_is_playing():
            self.fanfare_started_at = None
            self.trace("FANFARE END")
            return False
        return True

    def trace(self, event):
        if self.session.debug:
            message = f"[SPARK] {event} state={self.state} battle={self.session.completed}"
            self.debug_events.append(message)
            self.debug_events = self.debug_events[-40:]
            print(message)

    def audio_state(self):
        try:
            import js
            return str(js.window.sparkAudioState()).upper()
        except Exception:
            return "N/A"

    def next_result_label(self):
        return "次の戦闘"

    def begin_input(self):
        self.state = "command"
        self.actions = []
        self.order = [i for i, c in enumerate(self.session.party) if c.alive]
        self.actor_position = 0
        self.cursor = self.skill_cursor = self.target_cursor = 0
        self.selected_skill = None
        self.selected_item = None
        self.item_cursor = 0

    @property
    def actor_index(self):
        return self.order[min(self.actor_position, len(self.order) - 1)]

    @property
    def actor(self):
        return self.session.party[self.actor_index]

    def pressed(self, *keys):
        return any(self.button_pressed(key) for key in keys)

    def confirm(self):
        return self.pressed(pyxel.KEY_Z, pyxel.KEY_RETURN, pyxel.KEY_SPACE)

    def cancel(self):
        return self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE)

    def confirm_held(self):
        return pyxel.btn(pyxel.KEY_Z) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_A)

    def button_pressed(self, key, hold=0, repeat=0):
        return pyxel.btnp(key, hold, repeat) or (
            key in GAMEPAD_KEYS and pyxel.btnp(GAMEPAD_KEYS[key], hold, repeat))

    def direction(self, horizontal=False):
        low, high = (pyxel.KEY_LEFT, pyxel.KEY_RIGHT) if horizontal else (pyxel.KEY_UP, pyxel.KEY_DOWN)
        return int(self.button_pressed(high, 10, 3)) - int(self.button_pressed(low, 10, 3))

    def tell(self, message):
        self.notice, self.notice_timer = message, 60

    def targets(self):
        if self.selected_item or (self.selected_skill and self.selected_skill.target == "ally"):
            dead = self.selected_item == "PHOENIX ASH" or (self.selected_skill and self.selected_skill.effect == "revive")
            return [(i, target) for i, target in enumerate(self.session.party)
                    if target.alive != bool(dead) and
                    (self.selected_item != "POTION" or target.hp < target.max_hp)]
        return [(i, target) for i, target in enumerate(self.battle.enemies) if target.alive]

    def battle_items(self):
        reserved = {item: sum(a.kind == "ITEM" and a.item_id == item for a in self.actions)
                    for item in ("POTION", "PHOENIX ASH")}
        options = [item for item in reserved if self.session.inventory.counts[item] > reserved[item]]
        if self.battle.can_use_amrita and not any(a.item_id == AMRITA_ITEM_ID for a in self.actions):
            options.append(AMRITA_ITEM_ID)
        return options

    def commit(self, action):
        self.actions.append(action)
        self.actor_position += 1
        self.cursor = self.skill_cursor = self.target_cursor = 0
        self.selected_skill = None
        self.selected_item = None
        if self.actor_position >= len(self.order):
            self.battle.begin_round(self.actions)
            self.state, self.delay = "resolve", 0
            self.log = [f"第{self.battle.round}ターン"]
        else:
            self.state = "command"

    def update(self):
        self.keyboard.update()
        if self.state == 'amrita_effect':
            self.update_amrita_effect()
            return
        self.shake_timer = max(0, self.shake_timer - 1)
        if self.pressed(pyxel.KEY_Q):
            pyxel.quit()
            return
        self.notice_timer = max(0, self.notice_timer - 1)
        if self.pressed(pyxel.KEY_F9):
            self.session.debug = not self.session.debug
            self.tell("DEBUG オン" if self.session.debug else "DEBUG オフ")
            if not self.session.debug and self.overlay == "debug_skills":
                self.overlay = None
            return
        if self.pressed(pyxel.KEY_F12):
            if self.session.debug and self.state in ("camp", "explore", "result") and not self.session.pending_replacements:
                self.overlay = None if self.overlay == "debug_skills" else "debug_skills"
                self.notice_timer = 0
            return
        if self.pressed(pyxel.KEY_D, pyxel.KEY_TAB):
            self.overlay = None if self.overlay == "info" else "info"
            self.scroll = 0
            return
        if self.pressed(pyxel.KEY_H):
            self.overlay = None if self.overlay == "help" else "help"
            return
        confirm, cancel = self.confirm(), self.cancel()
        if self.overlay:
            if cancel:
                self.overlay = None
            elif self.overlay == "debug_skills":
                self.update_debug_skills(confirm)
            elif self.overlay == "info":
                move = self.direction(horizontal=True)
                if move:
                    self.info_character = (self.info_character + move) % 4
                    self.scroll = 0
                if confirm:
                    self.info_tab = (self.info_tab + 1) % 3
                    self.scroll = 0
                else:
                    self.scroll = max(0, min(self.info_scroll_limit(), self.scroll + self.direction()))
            return
        if self.state == "replace":
            self.update_replacement(confirm, cancel)
            return
        if self.state == "result":
            page_count = max(1, (len(self.result_lines) + 8) // 9)
            self.result_page = max(0, min(page_count - 1, self.result_page + self.direction(horizontal=True) + self.direction()))
            if confirm:
                if self.result_page + 1 < page_count:
                    self.result_page += 1
                else:
                    if self.waiting_for_fanfare():
                        return
                    if self.session.pending_replacements:
                        self.notice_timer = 0
                        self.state = "replace"
                        self.trace("REPLACEMENT")
                        self.replacement_cursor = 0
                        self.replacement_confirm = False
                    else:
                        self.finish_results()
            return
        if self.state == "resolve":
            self.delay -= 1
            if self.delay > 0 and not confirm and not self.confirm_held():
                return
            if self.pending:
                self.log.append(self.pending.popleft())
                self.log = self.log[-3:]
                self.delay = 14
            elif self.battle.outcome:
                self.trace("VICTORY START" if self.battle.outcome == "VICTORY" else "BATTLE END")
                stop_battle_music()
                self.notice_timer = 0
                self.result_lines = wrap_lines(self.session.settle())
                self.trace("REWARD GROWTH MASTERY SPARK COMPLETE")
                self.result_page = 0
                self.state = "result"
                self.trace("RESULT")
                if self.battle.outcome == "VICTORY":
                    if play_victory_music():
                        self.fanfare_started_at = time.monotonic()
                        self.fanfare_start_frame = pyxel.frame_count
                        self.fanfare_timed_out = False
                        self.trace("FANFARE START")
                    else:
                        self.fanfare_started_at = None
                        self.trace("FANFARE UNAVAILABLE")
            elif self.battle.queue:
                barrier_before = self.battle.elysion_barrier_active
                self.pending.extend(wrap_lines(self.battle.step()))
                play_cue(self.battle.sound_cue)
                if self.battle.player_hit:
                    self.shake_timer = 6
                if barrier_before and not self.battle.elysion_barrier_active:
                    self.start_amrita_effect()
            else:
                self.begin_input()
            return
        if self.state == "command":
            if self.pressed(pyxel.KEY_A):
                self.battle.begin_round(self.battle.auto_actions())
                self.state, self.delay = "resolve", 0
                self.log = [f"第{self.battle.round}ターン / 自動"]
                return
            vertical, horizontal = self.direction(), self.direction(horizontal=True)
            self.cursor = (((self.cursor // 2 + vertical) % 2) * 2
                           + (self.cursor % 2 + horizontal) % 2)
            if cancel and self.actions:
                self.actions.pop()
                self.actor_position -= 1
                self.cursor = 0
            elif confirm:
                if self.cursor == 0:
                    if self.actor.skills:
                        self.state, self.skill_cursor = "skill", 0
                    else:
                        self.tell("使える技がありません")
                elif self.cursor == 1:
                    self.state, self.item_cursor = "battle_item", 0
                elif self.cursor == 2:
                    self.commit(Action(self.actor_index, "GUARD"))
                else:
                    lines = self.battle.attempt_run()
                    if self.battle.boss:
                        self.tell(lines[0])
                    else:
                        self.actions.clear()
                        self.pending = deque(lines)
                        self.state, self.delay = "resolve", 0
        elif self.state == "battle_item":
            options = self.battle_items()
            if cancel:
                self.state = "command"
                self.selected_item = None
            elif options:
                self.item_cursor = (self.item_cursor + self.direction()) % len(options)
                if confirm:
                    self.selected_item = options[self.item_cursor]
                    if self.selected_item == AMRITA_ITEM_ID:
                        self.commit(Action(self.actor_index, 'ITEM', item_id=AMRITA_ITEM_ID))
                    elif not self.targets():
                        self.tell("使える対象がいません")
                    else:
                        self.state, self.target_cursor = "target", 0
            elif confirm:
                self.tell("使える道具がありません")
        elif self.state == "skill":
            self.skill_cursor = (self.skill_cursor + self.direction()) % len(self.actor.skills)
            if cancel:
                self.state = "command"
                self.selected_skill = None
            elif confirm:
                skill = self.session.skills[self.actor.skills[self.skill_cursor]]
                if self.actor.skill_uses.get(skill.id, 0) <= 0:
                    self.tell("残り回数がありません")
                elif skill.effect == "return":
                    self.tell("RETURNは探索メニューから使用")
                elif self.actor.cooldowns.get(skill.id, 0):
                    self.tell("この技は再使用待ちです")
                elif skill.target == "self":
                    self.commit(Action(self.actor_index, "SKILL", self.actor_index, skill.id))
                else:
                    self.selected_skill = skill
                    if not self.targets():
                        self.selected_skill = None
                        self.tell("使える対象がいません")
                    else:
                        self.state, self.target_cursor = "target", 0
        elif self.state == "target":
            choices = self.targets()
            if not choices:
                self.state = "battle_item" if self.selected_item else "skill"
                return
            self.target_cursor = (self.target_cursor + self.direction() + self.direction(horizontal=True)) % len(choices)
            if cancel:
                self.state = "battle_item" if self.selected_item else "skill"
                self.selected_item = None
                self.selected_skill = None
            elif confirm:
                target = choices[self.target_cursor][0]
                if self.selected_item:
                    self.commit(Action(self.actor_index, "ITEM", target, item_id=self.selected_item))
                else:
                    self.commit(Action(self.actor_index, "SKILL", target, self.selected_skill.id))

    def panel(self, x, y, w, h):
        pyxel.rect(x, y, w, h, 0)
        pyxel.rectb(x, y, w, h, 2)

    def footer(self, value):
        pyxel.rect(0, 111, 160, 9, 1)
        text(4, 112, self.notice if self.notice_timer else value, 3, 38)

    def title(self, value):
        pyxel.rect(0, 0, 160, 11, 3)
        text(4, 2, value, 0, 38)

    def draw(self):
        pyxel.cls(0)
        if self.state == 'amrita_effect':
            try:
                self.draw_battle()
                self.final_visual().draw_light(pyxel)
            except Exception as error:
                # A presentation fault must never hold a resolved ITEM action.
                self.trace('AMRITA VISUAL UNAVAILABLE: ' + type(error).__name__)
                self.finish_amrita_effect()
            finally:
                pyxel.pal()
                pyxel.camera()
        elif self.overlay == "debug_skills":
            self.draw_debug_skills()
        elif self.overlay == "help":
            self.draw_help()
        elif self.overlay == "info":
            self.draw_info()
        elif self.state == "result":
            self.draw_result()
        elif self.state == "replace":
            self.draw_replacement()
        elif self.state == "skill":
            self.draw_skills()
        elif self.state == "battle_item":
            self.draw_battle_items()
        else:
            if self.shake_timer:
                offsets = ((-2, 0), (2, 1), (-1, -1), (1, 0), (0, 1), (0, 0))
                pyxel.camera(*offsets[6 - self.shake_timer])
            self.draw_battle()
            if self.shake_timer:
                pyxel.camera()

    def draw_battle(self):
        flag = " DEBUG" if self.session.debug else ""
        self.title(f"第{self.session.completed + 1}戦 {self.battle.round + (self.state not in ('resolve', 'amrita_effect'))}ターン{flag}")
        # Sparse dithered battlefield, behind the enemy rows.
        for x in range(5, 91, 8):
            pyxel.pset(x, 75, 1)
        for i, enemy in enumerate(self.battle.enemies):
            y = 16 + i * 20
            if enemy.alive:
                if self.battle.is_elysion_battle and enemy.id == LORD_OF_ELYSION_ID:
                    self.draw_lord_of_elysion(enemy)
                else:
                    pyxel.blt(38, y, 0, *enemy.sprite, 16, 16, 0)
        for i, actor in enumerate(self.session.party):
            y = 13 + i * 16
            active = self.state in ("command", "target", "battle_transition") and self.actor_index == i
            pyxel.rect(97, y, 62, 16, 1 if active else 0)
            pyxel.blt(98, y, 0, *actor.sprite, 16, 16, 0)
            text(115, y + 1, actor.name, 3 if actor.alive else 1, 7)
            status = "KO" if not actor.alive else "!" if actor.berserk else "+" if actor.guarding else ""
            text(148, y + 1, status, 3, 2)
            text(115, y + 8, f"{actor.hp}/{actor.max_hp}", 2, 11)
        self.panel(1, 80, 158, 31)
        if self.state in ("command", "battle_transition"):
            for i, label in enumerate(("SKILL 技", "ITEM 道具", "GUARD まもる", "RUN 逃走")):
                text(5 + i % 2 * 75, 84 + i // 2 * 12,
                     (">" if i == self.cursor else " ") + label,
                     3 if i == self.cursor else 2)
            self.footer("A:決定 B:戻る D-PAD:選択")
        elif self.state == "target":
            target_index, target = self.targets()[self.target_cursor]
            ally = self.selected_item or (self.selected_skill and self.selected_skill.target == "ally")
            if ally:
                pyxel.rectb(97, 13 + target_index * 16, 62, 16, 3)
            else:
                if self.battle.is_elysion_battle:
                    x, y, _, h = self.final_visual().bounds()
                    text(x - 8, y + h // 2 - 4, ">", 3)
                else:
                    text(28, 20 + target_index * 20, ">", 3)
            label = self.selected_item or f"{self.selected_skill.name} 残{self.actor.skill_uses[self.selected_skill.id]}"
            text(5, 84, label, 2, 37)
            target_line = f"> {target.name} HP {target.hp}/{target.max_hp}" if ally else f"> {target.name}"
            text(5, 92, target_line, 3, 37)
            text(5, 100, "対象を選んでください", 2)
            self.footer("D-PAD:対象 A:決定 B:戻る")
        else:
            for i, line in enumerate(self.log[-3:]):
                text(5, 84 + i * 8, line, 3 if i == len(self.log[-3:]) - 1 else 2, 37)
            self.footer("" if self.state == 'amrita_effect' else "A:メッセージ送り / 長押しで高速")

    def final_visual(self):
        if getattr(self, 'final_presentation', None) is None:
            self.final_presentation = FinalPresentation(getattr(self, 'final_battle_data', None))
        return self.final_presentation

    def draw_lord_of_elysion(self, enemy):
        self.final_visual().draw_boss(pyxel, enemy, self.battle.elysion_barrier_active)

    def start_amrita_effect(self):
        # The model has already applied the legal ITEM action and released the barrier.
        # Only presentation pauses here, never sound or the game rule itself.
        self.overlay, self.notice_timer, self.shake_timer = None, 0, 0
        self.pending.clear()
        self.log = wrap_lines(self.battle.final_data['amrita_release'][:1], 37)[-3:]
        try:
            self.final_visual().start()
            self.state = 'amrita_effect'
        except Exception:
            self.finish_amrita_effect()

    def finish_amrita_effect(self):
        if getattr(self, 'final_presentation', None) is not None:
            self.final_presentation.reset()
        self.log = wrap_lines(self.battle.final_data['amrita_release'][1:] or
                              self.battle.final_data['amrita_release'], 37)[-3:]
        self.state, self.delay = 'resolve', 14
        # DungeonApp consumes a released frame before accepting subsequent input.
        self.battle_input_blocked = True

    def update_amrita_effect(self):
        if self.pressed(pyxel.KEY_Q):
            pyxel.quit()
            return
        try:
            visual = self.final_visual()
            finished = visual.advance()
        except Exception:
            self.finish_amrita_effect()
            return
        if finished:
            self.finish_amrita_effect()
        elif visual.frame >= AMRITA_MESSAGE_FRAME:
            self.log = wrap_lines(self.battle.final_data['amrita_release'][1:] or
                                  self.battle.final_data['amrita_release'], 37)[-3:]

    def skill_details(self, actor, skill, y=76):
        pyxel.line(4, y - 3, 155, y - 3, 1)
        text(5, y, f"{RARITIES[skill.rarity]} / {TARGETS[skill.target]} 最大{actor.max_uses(skill)}回", 2, 37)
        text(5, y + 8, skill.formula(), 3, 37)
        detail = f"威力 {skill.power(actor)} 待ち {skill.cooldown}T"
        if actor.power_multiplier(skill) > 1:
            detail += " / MASTER x1.2"
        if skill.effect == "berserk":
            detail = "STR x1.5 / 被害 x1.25 / 3T"
        elif skill.effect in EFFECTS:
            detail = EFFECTS[skill.effect] + " / 重複せず更新"
        elif skill.effect == "return":
            detail = f"未確定{CURRENCY_NAME}を持ち帰る"
        elif skill.effect == "revive":
            detail = "戦闘不能の味方1人 / 残数制"
        text(5, y + 16, detail, 2, 37)
        text(5, y + 24, skill.description, 2, 37)

    def draw_skills(self):
        self.title(f"{self.actor.name} / 技 {self.skill_cursor + 1}/{len(self.actor.skills)}")
        start = max(0, self.skill_cursor - 5)
        for row, skill_id in enumerate(self.actor.skills[start:start + 6]):
            skill = self.session.skills[skill_id]
            selected = start + row == self.skill_cursor
            y = 16 + row * 9
            if selected:
                pyxel.rect(3, y - 1, 154, 8, 1)
            text(5, y, (">" if selected else " ") + skill.name, 3, 23)
            wait = self.actor.cooldowns.get(skill_id, 0)
            text(101, y, f"{self.actor.skill_uses.get(skill_id, 0)}/{self.actor.max_uses(skill)}" + ("待" if wait else ""), 2, 14)
        self.skill_details(self.actor, self.session.skills[self.actor.skills[self.skill_cursor]])
        self.footer("D-PAD:選択 A:使用 B:戻る")

    def draw_battle_items(self):
        self.title(f"{self.actor.name} / ITEM")
        options = self.battle_items()
        if not options:
            text(8, 30, "使える道具がありません", 3, 35)
        for i, item in enumerate(options):
            if item == AMRITA_ITEM_ID:
                label = 'アムリタ / KEY ITEM'
            else:
                remaining = self.session.inventory.counts[item] - sum(a.kind == "ITEM" and a.item_id == item for a in self.actions)
                label = f'{item} x{remaining}'
            text(8, 24 + i * 14, (">" if i == self.item_cursor else " ") +
                 label, 3 if i == self.item_cursor else 2, 36)
        if AMRITA_ITEM_ID in options and self.item_cursor == options.index(AMRITA_ITEM_ID):
            text(8, 78, '特殊な障壁を解除 / 1ターン', 2, 36)
            text(8, 90, '道具数と技Usesは消費しない', 2, 36)
        else:
            text(8, 78, "POTION: 生存者のHP回復", 2, 36)
            text(8, 90, "ASH: 戦闘不能を25%で蘇生", 2, 36)
        self.footer("上下:選択 A:使用 B:戻る")

    def draw_result(self):
        outcome = self.battle.outcome
        spark = any("閃き!" in line for line in self.session.results)
        self.title(f"{OUTCOMES[outcome]} / " + ("新たな技の閃き!" if spark else "成長結果"))
        text(5, 15, f"{self.session.completed}戦 {self.session.wins}勝 {self.session.losses}敗 {self.session.draws}分", 2, 37)
        for i, line in enumerate(self.result_lines[self.result_page * 9:self.result_page * 9 + 9]):
            text(7, 27 + i * 8, line, 3 if "閃き" in line or "伝説" in line else 2, 36)
        pages = max(1, (len(self.result_lines) + 8) // 9)
        text(5, 102, f"{self.result_page + 1}/{pages}ページ", 3, 37)
        next_label = "入替へ" if self.session.pending_replacements else self.next_result_label()
        if self.result_page == pages - 1 and self.waiting_for_fanfare():
            self.footer("ファンファーレ再生中…")
            return
        self.footer(f"A:{next_label} D-PAD:ページ" if self.result_page == pages - 1 else "A:続きを読む D-PAD:ページ")

    def info_scroll_limit(self):
        actor = self.session.party[self.info_character]
        if self.info_tab == 1:
            return max(0, len(actor.skills) - 1)
        if self.info_tab == 2:
            return max(0, len(wrap_lines(list(reversed(actor.history)), 36)) - 8)
        return 0

    def draw_info(self):
        actor = self.session.party[self.info_character]
        tab = ("能力", "習得技", "履歴")[self.info_tab]
        self.title(f"< {actor.name}/{TYPES.get(actor.growth_type, actor.growth_type)} > {tab}")
        text(5, 15, f"{self.session.completed}戦 {self.session.wins}勝 {self.session.losses}敗 {self.session.draws}分", 2, 37)
        if self.info_tab == 0:
            pyxel.blt(10, 30, 0, *actor.sprite, 16, 16, 0)
            text(34, 29, f"HP {actor.hp}/{actor.max_hp}", 3, 30)
            text(34, 39, f"STR {actor.strength}  AGI {actor.agility}", 3, 30)
            slots = self.session.settings["skill_slots"]
            text(34, 49, f"INT {actor.intellect} 技 {len(actor.skills)}/{slots}", 3, 30)
            text(5, 64, "基本成長率 / 使用補正", 2)
            rates = self.session.settings["growth_rates"][actor.growth_type]
            for i, stat in enumerate(("HP", "STR", "AGI", "INT")):
                extra = growth_bonus(actor, stat, self.session.settings)
                text(8, 73 + i * 8, f"{stat:3} {rates[stat]:.0%}  +{extra:.0%}", 3, 36)
        elif self.info_tab == 1:
            if actor.skills:
                start = max(0, self.scroll - 5)
                for i, skill_id in enumerate(actor.skills[start:start + 6]):
                    skill = self.session.skills[skill_id]
                    selected = start + i == self.scroll
                    text(5, 24 + i * 8, (">" if selected else " ") + f"{start+i+1}." + skill.name, 3 if selected else 2, 23)
                    text(101, 24 + i * 8, f"{actor.skill_uses.get(skill_id, 0)}/{actor.max_uses(skill)}", 2, 14)
                self.skill_details(actor, self.session.skills[actor.skills[self.scroll]])
            else:
                text(8, 35, "技はまだ覚えていません", 3)
                text(8, 47, "勝利すると閃くかも!", 2)
                text(8, 59, "初戦から伝説の技も対象", 2)
        else:
            lines = wrap_lines(list(reversed(actor.history)), 36) or ["まだ履歴がありません"]
            for i, line in enumerate(lines[self.scroll:self.scroll + 8]):
                text(7, 27 + i * 9, line, 3 if "閃き" in line else 2, 36)
            text(5, 102, "上下:スクロール 新しい順", 2)
        self.footer("左右:人 上下:選択 A:頁 B:閉じる")

    def draw_help(self):
        self.title("SPARK / 操作")
        lines = ["D-PAD  移動・選択", "A  決定・調べる・会話送り", "B  キャンセル・戻る", "探索中のB  メニュー", "PC: A=Zキー B=Xキー",
                 "戦闘 SKILL/ITEM/GUARD/RUN", "GUARD:今ターンの被害半減", "技は使い切ると消滅"]
        for i, line in enumerate(lines):
            text(5, 18 + i * 10, line, 3 if i < 5 else 2, 37)
        self.footer("B:閉じる")

    def update_replacement(self, confirm, cancel):
        index = self.session.pending_replacements[0]
        actor = self.session.party[index]
        if self.replacement_confirm:
            if cancel:
                self.replacement_confirm = False
            elif confirm:
                slot = self.replacement_cursor if self.replacement_cursor < len(actor.skills) else None
                try:
                    self.session.resolve_replacement(index, slot)
                except ValueError as error:
                    self.tell(str(error))
                    return
                self.notice_timer = 0
                self.replacement_confirm = False
                self.replacement_cursor = 0
                if not self.session.pending_replacements:
                    if self.debug_return_state is not None:
                        self.state, self.debug_return_state = self.debug_return_state, None
                        self.overlay = self.debug_return_overlay if self.session.debug else None
                        self.debug_return_overlay = "debug_skills"
                        return
                    self.result_lines = wrap_lines(self.session.results)
                    self.result_page = 0
                    self.state = "result"
            return
        self.replacement_cursor = (self.replacement_cursor + self.direction()) % (len(actor.skills) + 1)
        if cancel:
            self.replacement_cursor = len(actor.skills)
        elif confirm:
            self.replacement_confirm = True

    def draw_replacement(self):
        actor = self.session.party[self.session.pending_replacements[0]]
        new = self.session.skills[actor.pending_skill]
        relearn = self.session.pending_relearn is not None
        uses = actor.relearn_uses(new) if relearn else actor.next_max_uses(new)
        bonus = " / POWER x1.2" if actor.next_power_multiplier(new) > 1 else ""
        self.title(f"{actor.name} / 技の入れ替え{bonus}")
        text(4, 14, f"新: {new.name}", 3, 38)
        text(4, 23, f"{new.relearn_cost} {CURRENCY_NAME}消費 / 再習得{uses}/{actor.next_max_uses(new)}回" if relearn else f"{RARITIES[new.rarity]} 威力{new.power(actor)} {uses}/{actor.next_max_uses(new)}回", 2, 38)
        if self.replacement_confirm:
            if self.replacement_cursor < len(actor.skills):
                old = self.session.skills[actor.skills[self.replacement_cursor]]
                text(4, 42, f"忘れる: {old.name}", 2, 38)
                text(4, 66, f"残数 {actor.skill_uses[old.id]}/{actor.max_uses(old)} 完全に失う", 2, 38)
                text(4, 56, f"覚える: {new.name}", 3, 38)
                text(4, 77, "この技に入れ替えますか?", 3, 38)
                if new.effect not in ("damage", "drain") and not any(self.session.skills[s].effect in ("damage", "drain") for s in actor.skills if s != old.id):
                    text(4, 91, "攻撃技を1つ残してください" if relearn else "攻撃技なし:末尾を救済パンチに", 3, 38)
            else:
                text(4, 48, "新しい技を覚えずに", 2, 38)
                text(4, 62, "見送りますか?", 3, 38)
            self.footer("A:確定 B:選び直す")
            return
        start = max(0, self.replacement_cursor - 4)
        choices = [self.session.skills[s].name for s in actor.skills] + ["新しい技を見送る"]
        for row, label in enumerate(choices[start:start + 5]):
            selected = start + row == self.replacement_cursor
            y = 35 + row * 10
            if selected:
                pyxel.rect(2, y - 1, 156, 9, 1)
            is_old = start + row < len(actor.skills)
            text(4, y, (">" if selected else " ") + f"{start + row + 1}." + label, 3 if selected else 2, 23 if is_old else 38)
            if is_old:
                sid = actor.skills[start + row]
                text(100, y, f"{actor.skill_uses.get(sid, 0)}/{actor.max_uses(self.session.skills[sid])}", 2, 14)
        if self.replacement_cursor < len(actor.skills):
            old = self.session.skills[actor.skills[self.replacement_cursor]]
            text(4, 88, f"旧: {RARITIES[old.rarity]} 威力{old.power(actor)} 待ち{old.cooldown}T", 2, 38)
            text(4, 99, old.formula(), 2, 38)
        else:
            text(4, 92, "覚えている技をそのまま残す", 2, 38)
        self.footer("上下:忘れる技 A:選択 B:見送る")

    def update_debug_skills(self, confirm):
        self.info_character = (self.info_character + self.direction(horizontal=True)) % 4
        self.debug_cursor = (self.debug_cursor + self.direction()) % 6
        if confirm:
            operation = ("one", "restore", "random", "rare", "legend", "fill")[self.debug_cursor]
            try:
                lines = self.session.debug_skills(operation, self.info_character)
            except ValueError as error:
                self.tell(str(error))
                return
            self.tell(lines[-1])
            if self.session.pending_replacements:
                self.debug_return_state = self.state
                self.debug_return_overlay = "debug_skills"
                self.state, self.overlay = "replace", None
                self.replacement_cursor, self.replacement_confirm = 0, False
                self.notice_timer = 0

    def draw_debug_skills(self):
        actor = self.session.party[self.info_character]
        self.title(f"DEBUG 技 / <{actor.name}>")
        labels = ("全員:残り1回にする", "全員:残数を最大に戻す", "選択者:ランダムに閃く", "選択者:希少以上を閃く", "選択者:伝説を閃く", "選択者:技枠を満杯にする")
        for i, label in enumerate(labels):
            text(5, 18 + i * 12, (">" if i == self.debug_cursor else " ") + label, 3 if i == self.debug_cursor else 2, 37)
        text(5, 94, "満杯→伝説で入れ替えを試す", 2, 37)
        self.footer("左右:人 上下:項目 Z:実行 X:戻る")
