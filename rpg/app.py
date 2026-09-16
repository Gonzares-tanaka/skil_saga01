"""160x120 UI. All rules live outside this module."""
from collections import deque

import pyxel

from .art import load_art
from .models import Action
from .labels import TYPES, RARITIES, TARGETS, OUTCOMES, EFFECTS
from .text import text, wrap_lines, font
from .sound import init_sound, play_cue
from .growth import growth_bonus
from .keyboard import GameKeyboard


class App:
    def __init__(self, session, run=True, headless=False, battle_on_start=True):
        self.session = session
        pyxel.init(160, 120, title="SPARK - Growth Lab", fps=30,
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
        if battle_on_start:
            self.start_battle()
        if run:
            pyxel.run(self.update, self.draw)

    def start_battle(self):
        self.notice_timer = 0
        self.battle = self.session.next_battle()
        self.log = ["新たな敵が現れた", "4人の行動を選ぼう"]
        self.pending = deque()
        self.begin_input()

    def finish_results(self):
        self.start_battle()

    def next_result_label(self):
        return "次の戦闘"

    def begin_input(self):
        self.state = "command"
        self.actions = []
        self.order = [i for i, c in enumerate(self.session.party) if c.alive]
        self.actor_position = 0
        self.cursor = self.skill_cursor = self.target_cursor = 0
        self.selected_skill = None

    @property
    def actor_index(self):
        return self.order[min(self.actor_position, len(self.order) - 1)]

    @property
    def actor(self):
        return self.session.party[self.actor_index]

    def pressed(self, *keys):
        return any(pyxel.btnp(key) for key in keys)

    def direction(self, horizontal=False):
        low, high = (pyxel.KEY_LEFT, pyxel.KEY_RIGHT) if horizontal else (pyxel.KEY_UP, pyxel.KEY_DOWN)
        return int(pyxel.btnp(high, 10, 3)) - int(pyxel.btnp(low, 10, 3))

    def tell(self, message):
        self.notice, self.notice_timer = message, 60

    def targets(self):
        group = self.session.party if self.selected_skill and self.selected_skill.target == "ally" else self.battle.enemies
        return [(i, target) for i, target in enumerate(group) if target.alive]

    def commit(self, action):
        self.actions.append(action)
        self.actor_position += 1
        self.cursor = self.skill_cursor = self.target_cursor = 0
        self.selected_skill = None
        if self.actor_position >= len(self.order):
            self.battle.begin_round(self.actions)
            self.state, self.delay = "resolve", 0
            self.log = [f"第{self.battle.round}ターン"]
        else:
            self.state = "command"

    def update(self):
        self.keyboard.update()
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
        confirm = self.pressed(pyxel.KEY_Z, pyxel.KEY_RETURN, pyxel.KEY_SPACE)
        cancel = self.pressed(pyxel.KEY_X, pyxel.KEY_ESCAPE)
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
                    if self.session.pending_replacements:
                        self.notice_timer = 0
                        self.state = "replace"
                        self.replacement_cursor = 0
                        self.replacement_confirm = False
                    else:
                        self.finish_results()
            return
        if self.state == "resolve":
            self.delay -= 1
            if self.delay > 0 and not confirm and not pyxel.btn(pyxel.KEY_A):
                return
            if self.pending:
                self.log.append(self.pending.popleft())
                self.log = self.log[-3:]
                self.delay = 14
            elif self.battle.outcome:
                self.notice_timer = 0
                self.result_lines = wrap_lines(self.session.settle())
                self.result_page = 0
                self.state = "result"
            elif self.battle.queue:
                self.pending.extend(wrap_lines(self.battle.step()))
                play_cue(self.battle.sound_cue)
                if self.battle.player_hit:
                    self.shake_timer = 6
            else:
                self.begin_input()
            return
        if self.state == "command":
            if self.pressed(pyxel.KEY_A):
                self.battle.begin_round(self.battle.auto_actions())
                self.state, self.delay = "resolve", 0
                self.log = [f"第{self.battle.round}ターン / 自動"]
                return
            self.cursor = (self.cursor + self.direction()) % 2
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
                else:
                    self.commit(Action(self.actor_index, "DEFEND"))
        elif self.state == "skill":
            self.skill_cursor = (self.skill_cursor + self.direction()) % len(self.actor.skills)
            if cancel:
                self.state = "command"
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
                    self.state, self.target_cursor = "target", 0
        elif self.state == "target":
            choices = self.targets()
            self.target_cursor = (self.target_cursor + self.direction() + self.direction(horizontal=True)) % len(choices)
            if cancel:
                self.state = "skill" if self.selected_skill else "command"
            elif confirm:
                target = choices[self.target_cursor][0]
                skill = self.selected_skill
                self.commit(Action(self.actor_index, "SKILL", target, skill.id))

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
        if self.overlay == "debug_skills":
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
        else:
            if self.shake_timer:
                offsets = ((-2, 0), (2, 1), (-1, -1), (1, 0), (0, 1), (0, 0))
                pyxel.camera(*offsets[6 - self.shake_timer])
            self.draw_battle()
            if self.shake_timer:
                pyxel.camera()

    def draw_battle(self):
        flag = " DEBUG" if self.session.debug else ""
        self.title(f"第{self.session.completed + 1}戦 {self.battle.round + (self.state != 'resolve')}ターン{flag}")
        # Sparse dithered battlefield, behind the enemy rows.
        for x in range(5, 91, 8):
            pyxel.pset(x, 75, 1)
        for i, enemy in enumerate(self.battle.enemies):
            y = 16 + i * 20
            if enemy.alive:
                pyxel.blt(38, y, 0, *enemy.sprite, 16, 16, 0)
        for i, actor in enumerate(self.session.party):
            y = 13 + i * 16
            active = self.state in ("command", "target") and self.actor_index == i
            pyxel.rect(97, y, 62, 16, 1 if active else 0)
            pyxel.blt(98, y, 0, *actor.sprite, 16, 16, 0)
            text(115, y + 1, actor.name, 3 if actor.alive else 1, 7)
            status = "KO" if not actor.alive else "!" if actor.berserk else "+" if actor.guarding else ""
            text(148, y + 1, status, 3, 2)
            text(115, y + 8, f"{actor.hp}/{actor.max_hp}", 2, 11)
        self.panel(1, 80, 158, 30)
        if self.state == "command":
            for i, label in enumerate(("たたかう", "まもる")):
                text(5, 84 + i * 8, (">" if i == self.cursor else " ") + label, 3 if i == self.cursor else 2)
            text(48, 84, f"{self.actor.name}の行動", 3, 26)
            text(48, 92, f"技の残数 合計{sum(self.actor.skill_uses.values())}", 2, 26)
            text(48, 100, "A:自動 X:戻る", 2, 26)
            self.footer("Z:決定 D:能力 H:操作 F9:試験")
        elif self.state == "target":
            target_index, target = self.targets()[self.target_cursor]
            ally = self.selected_skill and self.selected_skill.target == "ally"
            if ally:
                pyxel.rectb(97, 13 + target_index * 16, 62, 16, 3)
            else:
                text(28, 20 + target_index * 20, ">", 3)
            text(5, 84, f"{self.selected_skill.name} 残{self.actor.skill_uses[self.selected_skill.id]}", 2, 37)
            target_line = f"> {target.name} HP {target.hp}/{target.max_hp}" if ally else f"> {target.name}"
            text(5, 92, target_line, 3, 37)
            text(5, 100, "対象を選んでください", 2)
            self.footer("矢印:対象 Z:決定 X:戻る")
        else:
            for i, line in enumerate(self.log[-3:]):
                text(5, 84 + i * 8, line, 3 if i == len(self.log[-3:]) - 1 else 2, 37)
            self.footer("Z:送り A長押し:高速 D:能力")

    def skill_details(self, actor, skill, y=76):
        pyxel.line(4, y - 3, 155, y - 3, 1)
        text(5, y, f"{RARITIES[skill.rarity]} / {TARGETS[skill.target]} 最大{skill.max_uses}回", 2, 37)
        text(5, y + 8, skill.formula(), 3, 37)
        detail = f"威力 {skill.power(actor)} 待ち {skill.cooldown}T"
        if skill.effect == "berserk":
            detail = "STR x1.5 / 被害 x1.25 / 3T"
        elif skill.effect in EFFECTS:
            detail = EFFECTS[skill.effect] + " / 重複せず更新"
        elif skill.effect == "return":
            detail = "未確定の宝を持ち帰る"
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
            text(101, y, f"{self.actor.skill_uses.get(skill_id, 0)}/{skill.max_uses}" + ("待" if wait else ""), 2, 14)
        self.skill_details(self.actor, self.session.skills[self.actor.skills[self.skill_cursor]])
        self.footer("上下:選択 Z:使用 X:戻る")

    def draw_result(self):
        outcome = self.battle.outcome
        spark = any("閃き!" in line for line in self.session.results)
        self.title(f"{OUTCOMES[outcome]} / " + ("新たな技の閃き!" if spark else "成長結果"))
        text(5, 15, f"{self.session.completed}戦 {self.session.wins}勝 {self.session.losses}敗 {self.session.draws}分", 2, 37)
        for i, line in enumerate(self.result_lines[self.result_page * 9:self.result_page * 9 + 9]):
            text(7, 27 + i * 8, line, 3 if "閃き" in line or "伝説" in line else 2, 36)
        pages = max(1, (len(self.result_lines) + 8) // 9)
        text(5, 102, f"{self.result_page + 1}/{pages}ページ D:能力", 3, 37)
        next_label = "入替へ" if self.session.pending_replacements else self.next_result_label()
        self.footer(f"Z:{next_label} 矢印:ページ" if self.result_page == pages - 1 else "Z:続きを読む 矢印:ページ")

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
                    text(101, 24 + i * 8, f"{actor.skill_uses.get(skill_id, 0)}/{skill.max_uses}", 2, 14)
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
        self.footer("左右:人 Z:頁 上下 D:閉じる")

    def draw_help(self):
        self.title("SPARK / 育成実験室")
        settings = self.session.settings
        spark_hint = f"F9 閃き {settings['spark_chance']:.0%} → {settings['debug_spark_chance']:.0%}"
        lines = ["たたかう:技選択 まもる:防御", "Z/Enter: 決定・次へ", "X/Esc: 戻る・取り消し", "D/Tab: 能力・技・履歴",
                 "A: 1ターンを自動で戦う", "A長押し: 戦闘ログ高速送り", spark_hint,
                 "Q:終了 F12:技のDEBUG操作", "使い切った技は消滅する", "帰還しても技回数は戻らない", "次戦はHPだけ全回復"]
        for i, line in enumerate(lines):
            text(5, 16 + i * 8, line, 3 if i < 8 else 2, 37)
        self.footer("H/X:閉じる レベル・経験値なし")

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
        uses = new.relearn_uses if relearn else new.max_uses
        self.title(f"{actor.name} / 技の入れ替え")
        text(4, 14, f"新: {new.name}", 3, 38)
        text(4, 23, f"宝{new.relearn_cost}消費 / 再習得{uses}/{new.max_uses}回" if relearn else f"{RARITIES[new.rarity]} 威力{new.power(actor)} {uses}/{new.max_uses}回", 2, 38)
        if self.replacement_confirm:
            if self.replacement_cursor < len(actor.skills):
                old = self.session.skills[actor.skills[self.replacement_cursor]]
                text(4, 42, f"忘れる: {old.name}", 2, 38)
                text(4, 66, f"残数 {actor.skill_uses[old.id]}/{old.max_uses} 完全に失う", 2, 38)
                text(4, 56, f"覚える: {new.name}", 3, 38)
                text(4, 77, "この技に入れ替えますか?", 3, 38)
                if new.effect not in ("damage", "drain") and not any(self.session.skills[s].effect in ("damage", "drain") for s in actor.skills if s != old.id):
                    text(4, 91, "攻撃技を1つ残してください" if relearn else "攻撃技なし:末尾を救済パンチに", 3, 38)
            else:
                text(4, 48, "新しい技を覚えずに", 2, 38)
                text(4, 62, "見送りますか?", 3, 38)
            self.footer("Z:確定 X:選び直す")
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
                text(100, y, f"{actor.skill_uses.get(sid, 0)}/{self.session.skills[sid].max_uses}", 2, 14)
        if self.replacement_cursor < len(actor.skills):
            old = self.session.skills[actor.skills[self.replacement_cursor]]
            text(4, 88, f"旧: {RARITIES[old.rarity]} 威力{old.power(actor)} 待ち{old.cooldown}T", 2, 38)
            text(4, 99, old.formula(), 2, 38)
        else:
            text(4, 92, "覚えている技をそのまま残す", 2, 38)
        self.footer("上下:忘れる技 Z:選択 X:見送る")

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
