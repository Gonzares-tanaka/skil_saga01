"""Battle rules independent of Pyxel, shared by the UI and simulation."""
from collections import deque
import random

from .growth import grow_and_spark, spark
from .skill_resources import ensure_attack, MAX_SKILLS
from .models import Action, Enemy, effect_factor, battle_agility
from .labels import OUTCOMES, EFFECTS
from .treasure import Treasure


class Battle:
    def __init__(self, party, enemies, skills, max_rounds=60, rng=None,
                 skill_slots=MAX_SKILLS, discovered_skills=None, mastered_skills=None):
        self.party = party
        self.enemies = enemies
        self.skills = skills
        self.max_rounds = max_rounds
        self.rng = rng or random.Random()
        self.round = 0
        self.outcome = None
        self.queue = deque()
        self.sound_cue = None
        self.player_hit = False
        self.skill_slots = skill_slots
        self.resource_events = []
        self.discovered_skills = discovered_skills if discovered_skills is not None else set()
        self.mastered_skills = mastered_skills if mastered_skills is not None else set()

    def begin_round(self, actions):
        if self.outcome or self.queue:
            raise ValueError("Cannot start a round during resolution or after battle.")
        expected = {i for i, c in enumerate(self.party) if c.alive}
        if len(actions) != len(expected) or {a.actor for a in actions} != expected:
            raise ValueError("Exactly one action per living character is required.")
        for action in actions:
            actor = self.party[action.actor]
            if action.kind not in ("SKILL", "DEFEND"):
                raise ValueError("Unknown action.")
            if action.kind == "SKILL":
                if self.skills.get(action.skill_id) and self.skills[action.skill_id].effect == "return":
                    raise ValueError("RETURNは探索中だけ使えます。")
                if (action.skill_id not in actor.skills or actor.skill_uses.get(action.skill_id, 0) <= 0
                        or actor.cooldowns.get(action.skill_id, 0)):
                    raise ValueError("Skill is unavailable, exhausted or cooling down.")
        self.round += 1
        for actor in self.party:
            actor.guarding = False
            actor.counter = None
        # Guard/counter take effect before attacks regardless of AGI.
        entries = []
        for action in actions:
            actor = self.party[action.actor]
            skill = self.skills[action.skill_id] if action.kind == "SKILL" else None
            priority = 1 if action.kind == "DEFEND" or (skill and skill.effect == "counter") else 0
            entries.append((priority, battle_agility(actor), self.rng.random(), "party", action))
        for i, enemy in enumerate(self.enemies):
            if enemy.alive:
                entries.append((0, battle_agility(enemy), self.rng.random(), "enemy", i))
        entries.sort(key=lambda item: item[:3], reverse=True)
        self.queue.extend((side, action) for _, _, _, side, action in entries)

    def _target(self, group, index):
        if 0 <= index < len(group) and group[index].alive:
            return group[index]
        return next((c for c in group if c.alive), None)

    def _damage(self, target, amount, magic=False):
        factor = (0.5 if target.guarding else 1) * (1.25 if target.berserk else 1) * effect_factor(target, "guard_up")
        defense = getattr(target, "magic_defense", 0) if magic else getattr(target, "defense", 0) * effect_factor(target, "armor_break")
        damage = max(1, round(max(1, amount - defense) * factor))
        removed = min(target.hp, damage)
        target.hp -= removed
        return removed

    def _party_action(self, action):
        actor = self.party[action.actor]
        if not actor.alive:
            return []
        if action.kind == "DEFEND":
            actor.guarding = True
            return [f"{actor.name} は防御"]
        if action.kind != "SKILL":
            raise ValueError("通常攻撃はありません。")
        if action.skill_id not in actor.skills or actor.skill_uses.get(action.skill_id, 0) <= 0 or actor.cooldowns.get(action.skill_id, 0):
            return [f"{actor.name} 技を使用できない"]
        skill = self.skills[action.skill_id]
        if skill.effect == "return":
            return ["RETURNは探索中だけ使えます。"]
        group = self.party if skill.target == "ally" else self.enemies
        if skill.target != "self" and self._target(group, action.target) is None:
            return []
        self.sound_cue = "attack" if skill.rarity == "BASIC" else "skill"
        actor.skill_uses[skill.id] -= 1
        actor.used_skills[skill.id] = actor.used_skills.get(skill.id, 0) + 1
        for stat, contribution in skill.growth.items():
            actor.growth_points[stat] = actor.growth_points.get(stat, 0) + contribution
        actor.cooldowns[skill.id] = skill.cooldown + 1
        lines = [f"{actor.name} {skill.name} 残{actor.skill_uses[skill.id]}"]
        lines.extend(self._skill_effect(actor, skill, action.target))
        if actor.skill_uses[skill.id] == 0:
            actor.forget(skill.id)
            message = f"{actor.name} {skill.name} 使い切り消滅"
            lines.append(message)
            self.resource_events.append(message)
            if skill.id not in self.mastered_skills:
                self.discovered_skills.add(skill.id)
                self.mastered_skills.add(skill.id)
                message = f"{actor.name} {skill.name} MASTERED!"
                lines.append(message)
                self.resource_events.append(message)
        return lines

    def _skill_effect(self, actor, skill, target_index):
        lines = []
        if skill.effect in EFFECTS:
            target = self._target(self.party if skill.target == "ally" else self.enemies, target_index)
            if target is None:
                return []
            target.effects[skill.effect] = (skill.modifier, skill.duration)
            return [f"{target.name} {EFFECTS[skill.effect]} {skill.duration}T"]
        if skill.effect == "counter":
            actor.guarding = True
            actor.counter = skill
            return lines + ["防御し、物理攻撃に反撃"]
        if skill.effect == "berserk":
            actor.berserk = 4  # Includes this setup round and the next 3 rounds.
            return lines + ["STR x1.5 / 被害 x1.25"]
        if skill.effect == "heal":
            target = self._target(self.party, target_index)
            if target is None:
                return lines
            restored = min(target.max_hp - target.hp, skill.power(actor))
            target.hp += restored
            return lines + [f"{target.name} HP +{restored}"]
        target = self._target(self.enemies, target_index)
        if target is None:
            return lines
        dealt = self._damage(target, skill.power(actor), magic=skill.skill_type == "magic")
        suffix = f" ({skill.hits}連撃)" if skill.hits > 1 else ""
        lines.append(f"{target.name} -{dealt}{suffix}")
        if not target.alive:
            lines.append(f"{target.name} 戦闘不能")
        if skill.effect == "drain":
            restored = min(actor.max_hp - actor.hp, dealt // 2)
            actor.hp += restored
            lines.append(f"{actor.name} HP +{restored}")
        return lines

    def _enemy_action(self, index):
        enemy = self.enemies[index]
        living = [c for c in self.party if c.alive]
        if not enemy.alive or not living:
            return []
        target = self.rng.choice(living)
        magic = self.rng.random() < enemy.magic_chance
        self.sound_cue = "skill" if magic else "attack"
        stat = (enemy.intellect if magic else enemy.strength) * effect_factor(enemy, "weaken")
        dealt = self._damage(target, round(stat * self.rng.uniform(0.9, 1.1)), magic=magic)
        self.player_hit = dealt > 0
        lines = [f"{enemy.name} の{'魔法' if magic else '攻撃'}", f"{target.name} -{dealt}"]
        if not target.alive:
            lines.append(f"{target.name} 戦闘不能")
        elif target.counter and not magic:
            returned = self._damage(enemy, target.counter.power(target))
            lines.append(f"反撃 {enemy.name} -{returned}")
            if not enemy.alive:
                lines.append(f"{enemy.name} 戦闘不能")
        return lines

    def step(self):
        """Resolve one queued actor; dead actors skip their action."""
        self.sound_cue = None
        self.player_hit = False
        if self.outcome or not self.queue:
            return []
        side, action = self.queue.popleft()
        lines = self._party_action(action) if side == "party" else self._enemy_action(action)
        if not any(c.alive for c in self.party):
            self.outcome = "DEFEAT"
        elif not any(e.alive for e in self.enemies):
            self.outcome = "VICTORY"
        if self.outcome:
            self.queue.clear()
        if not self.queue:
            for actor in self.party:
                actor.cooldowns = {key: turns - 1 for key, turns in actor.cooldowns.items() if turns > 1}
                actor.berserk = max(0, actor.berserk - 1)
                actor.guarding = False
                actor.counter = None
                messages = ensure_attack(actor, self.skills, self.skill_slots,
                                         self.discovered_skills)
                self.resource_events.extend(messages)
                lines.extend(messages)
            if not self.outcome and self.round >= self.max_rounds:
                self.outcome = "DRAW"
                lines.append("ターン上限: 引き分け")
            for unit in self.party + self.enemies:
                unit.effects = {key: (factor, turns - 1) for key, (factor, turns) in unit.effects.items() if turns > 1}
        if self.outcome:
            self.clear_effects()
        return lines

    def clear_effects(self):
        for unit in self.party + self.enemies:
            unit.effects.clear()
            unit.guarding = False
            unit.berserk = 0
        for actor in self.party:
            actor.counter = None
            actor.cooldowns.clear()

    def auto_actions(self):
        """Convenience for repeated testing; uses the same legal battle actions."""
        actions = []
        target = next((i for i, e in enumerate(self.enemies) if e.alive), 0)
        for i, actor in enumerate(self.party):
            if not actor.alive:
                continue
            available = [self.skills[s] for s in actor.skills if actor.skill_uses.get(s, 0) > 0 and not actor.cooldowns.get(s, 0)]
            injured = [(j, c) for j, c in enumerate(self.party) if c.alive and c.hp < c.max_hp * 0.5]
            heals = [s for s in available if s.effect == "heal"]
            if injured and heals:
                ally, _ = min(injured, key=lambda pair: pair[1].hp / pair[1].max_hp)
                skill = max(heals, key=lambda s: s.power(actor))
                actions.append(Action(i, "SKILL", ally, skill.id))
                continue
            damage = [s for s in available if s.effect in ("damage", "drain")]
            skill = max(damage, key=lambda s: s.power(actor), default=None)
            if skill:
                actions.append(Action(i, "SKILL", target, skill.id))
            else:
                actions.append(Action(i, "DEFEND"))
        return actions


class Session:
    def __init__(self, settings, skills, party, enemy_data, seed=None):
        self.settings, self.skills, self.party = settings, skills, party
        self.enemy_data = enemy_data
        self.rng = random.Random(seed)
        self.debug = False
        self.completed = self.wins = self.losses = self.draws = 0
        self.battle = None
        self.settled = False
        self.results = []
        self.debug_pending = False
        self.discovered_skills = {
            skill_id for character in self.party for skill_id in character.skills
        }
        self.mastered_skills = set()
        self.treasure = Treasure()
        self.pending_relearn = None

    def next_battle(self, enemies=None, recover=True, spark_multiplier=1.0):
        if self.pending_replacements:
            raise ValueError("先に技の入れ替えを決めてください。")
        if self.battle is not None and not self.settled:
            raise ValueError("Finish and settle the current battle first.")
        for character in self.party:
            character.history.extend(ensure_attack(character, self.skills,
                                                    self.settings["skill_slots"],
                                                    self.discovered_skills))
            character.recover() if recover else character.reset_battle_state()
        if not any(c.alive for c in self.party):
            raise ValueError("生存者がいません。拠点へ戻ってください。")
        self.auto_recover = recover
        self.spark_multiplier = spark_multiplier
        if enemies is None:
            scale = min(self.wins, self.settings["enemy_scaling_cap"])
            enemies = []
            pool = [row for row in self.enemy_data if not row.get("boss", False)]
            for i in range(self.rng.randint(2, 3)):
                row = self.rng.choice(pool)
                hp = row["max_hp"] + round(scale * self.settings["enemy_hp_per_win"])
                power = round(scale * self.settings["enemy_power_per_win"])
                enemies.append(Enemy(f"{row['name']} {chr(65 + i)}", hp,
                                     row["str"] + power, row["agi"], row["int"] + power,
                                     tuple(row["sprite"]), row["magic_chance"],
                                     defense=row.get("defense", 0), magic_defense=row.get("magic_defense", 0)))
        if not enemies or not any(e.alive for e in enemies):
            raise ValueError("戦闘には生存する敵が必要です。")
        self.battle = Battle(self.party, enemies, self.skills,
                             self.settings["max_rounds"], self.rng,
                             self.settings["skill_slots"],
                             self.discovered_skills, self.mastered_skills)
        self.settled = False
        self.results = []
        return self.battle

    def settle(self):
        if self.settled:
            return self.results
        if not self.battle or not self.battle.outcome:
            raise ValueError("Battle has not finished.")
        self.battle.clear_effects()
        self.completed += 1
        outcome = self.battle.outcome
        self.results = [f"第{self.completed}戦: {OUTCOMES[outcome]}"]
        self.results.extend(self.battle.resource_events)
        for character in self.party:
            for sid, count in character.used_skills.items():
                character.history.append(f"B{self.completed} {self.skills[sid].name}を{count}回使用")
            character.history.extend(f"B{self.completed} {line}" for line in self.battle.resource_events if character.name in line)
        if self.debug:
            self.results.append("DEBUG: 閃き確率アップ")
        if outcome == "VICTORY":
            self.wins += 1
            for character in self.party:
                self.results.extend(grow_and_spark(character, self.skills, self.settings,
                                                   self.rng, self.completed, self.debug,
                                                   self.discovered_skills, self.spark_multiplier))
        else:
            if outcome == "DEFEAT":
                self.losses += 1
                self.results.append(f"未確定の宝を{self.treasure.lose()}個失った")
            else:
                self.draws += 1
            self.results.append("成長・閃きなし")
            for character in self.party:
                character.history.append(f"B{self.completed} {OUTCOMES[outcome]}: 成長なし")
        self.results.append("次戦でHP回復・技回数は持越" if self.auto_recover else "探索へ戻る・HPと技回数は持ち越し")
        self.settled = True
        return self.results

    @property
    def pending_replacements(self):
        return [i for i, c in enumerate(self.party) if c.pending_skill is not None]

    def resolve_replacement(self, actor_index, slot=None):
        """Choose an old slot, or None to decline; never roll growth again."""
        if not self.settled and not self.debug_pending and self.pending_relearn is None:
            raise ValueError("戦闘結果を確定してください。")
        actor = self.party[actor_index]
        new_id = actor.pending_skill
        if new_id is None:
            raise ValueError("習得待ちの技がありません。")
        new = self.skills[new_id]
        relearn = self.pending_relearn == (actor_index, new_id)
        uses = new.relearn_uses if relearn else new.max_uses
        if slot is None:
            message = f"{actor.name} {new.name} の習得を見送った"
        else:
            if type(slot) is not int or not 0 <= slot < len(actor.skills):
                raise ValueError("無効な入れ替え枠です。")
            if relearn and self.treasure.banked < new.relearn_cost:
                raise ValueError("確定した宝が足りません。")
            old = self.skills[actor.skills[slot]]
            if relearn and new.effect not in ("damage", "drain") and not any(
                self.skills[s].effect in ("damage", "drain") for s in actor.skills if s != old.id
            ):
                raise ValueError("攻撃技を1つ残してください。")
            remaining = actor.skill_uses[old.id]
            actor.forget(old.id)
            actor.learn(new)
            actor.skill_uses[new.id] = uses
            if relearn:
                self.treasure.banked -= new.relearn_cost
            actor.skills.insert(slot, actor.skills.pop())
            message = f"{actor.name} {old.name} {remaining}回 → {new.name} {uses}回"
        if relearn:
            self.pending_relearn = None
        actor.pending_skill = None
        self.results.append(message)
        # Keep the debug provenance from the original spark, even after F9 changes.
        tag = " DEBUG" if self.debug_pending or any(f"B{self.completed} DEBUG " in h for h in actor.history) else ""
        actor.history.append(f"B{self.completed}{tag} {message}")
        rescue = ensure_attack(actor, self.skills, self.settings["skill_slots"],
                               self.discovered_skills)
        self.results.extend(rescue)
        actor.history.extend(rescue)
        if not self.pending_replacements:
            self.debug_pending = False
        return message

    def relearn_candidates(self):
        return [s for s in self.skills.values() if s.id in self.discovered_skills and s.rarity in ("BASIC", "COMMON")]

    def relearn(self, actor_index, skill_id):
        if self.pending_replacements or (self.battle and not self.settled):
            raise ValueError("戦闘・入れ替えを完了してください。")
        skill = self.skills[skill_id]
        if skill not in self.relearn_candidates():
            raise ValueError("再習得できるのは発見済みの基本・通常技です。")
        actor = self.party[actor_index]
        if skill_id in actor.skills:
            raise ValueError("すでに所持しています。残数の補充はできません。")
        if self.treasure.banked < skill.relearn_cost:
            raise ValueError("確定した宝が足りません。")
        if len(actor.skills) >= self.settings['skill_slots']:
            actor.pending_skill = skill_id
            self.pending_relearn = (actor_index, skill_id)
            return "入れ替え確定時に宝を消費します"
        actor.learn(skill)
        actor.skill_uses[skill_id] = skill.relearn_uses
        self.treasure.banked -= skill.relearn_cost
        message = f"{actor.name} {skill.name} 再習得{skill.relearn_uses}回 / 宝-{skill.relearn_cost}"
        actor.history.append(message)
        return message

    def field_return(self, actor_index):
        if self.pending_replacements or (self.battle and not self.settled):
            raise ValueError("戦闘・入れ替えを完了してください。")
        actor = self.party[actor_index]
        skill = next((self.skills[s] for s in actor.skills if self.skills[s].effect == 'return' and actor.skill_uses.get(s, 0) > 0), None)
        if not actor.alive or skill is None:
            raise ValueError("生存者の使用可能なRETURNが必要です。")
        actor.skill_uses[skill.id] -= 1
        lines = [f"{actor.name} {skill.name}で帰還"]
        if actor.skill_uses[skill.id] == 0:
            actor.forget(skill.id)
            lines.append(f"{skill.name} 使い切り消滅")
            if skill.id not in self.mastered_skills:
                self.discovered_skills.add(skill.id)
                self.mastered_skills.add(skill.id)
                lines.append(f"{skill.name} MASTERED!")
        actor.history.extend(lines)
        return lines

    def debug_skills(self, operation, actor_index=0):
        if not self.debug:
            raise ValueError("DEBUG専用です。")
        if self.pending_replacements:
            raise ValueError("先に入れ替えを完了してください。")
        if self.battle and not self.settled:
            raise ValueError("戦闘中は技の変更ができません。")
        actor = self.party[actor_index]
        if operation in ("one", "restore"):
            for member in self.party:
                for sid in member.skills:
                    member.skill_uses[sid] = 1 if operation == "one" else self.skills[sid].max_uses
            lines = ["DEBUG: 全員の技を" + ("残り1回" if operation == "one" else "最大回数")]
        elif operation == "fill":
            candidates = [s for s in self.skills.values() if s.id not in actor.skills]
            self.rng.shuffle(candidates)
            for skill in candidates[:max(0, self.settings["skill_slots"] - len(actor.skills))]:
                actor.learn(skill)
                self.discovered_skills.add(skill.id)
            lines = [f"DEBUG: {actor.name}の技枠を満杯に"]
        elif operation in ("random", "rare", "legend"):
            allowed = None if operation == "random" else {"RARE", "LEGEND"} if operation == "rare" else {"LEGEND"}
            lines = spark(actor, self.skills, self.settings, self.rng, allowed,
                          self.discovered_skills)
            self.debug_pending = bool(self.pending_replacements)
        else:
            raise ValueError("Unknown debug operation")
        affected = self.party if operation in ("one", "restore") else [actor]
        for member in affected:
            member.history.extend("DEBUG " + line for line in lines)
        return lines

    def debug_acquire(self, skill_id, actor_index=0):
        """Force one exact skill through the normal slot/replacement flow."""
        if not self.debug:
            raise ValueError("DEBUG専用です。")
        if self.pending_replacements:
            raise ValueError("先に入れ替えを完了してください。")
        if self.battle and not self.settled:
            raise ValueError("戦闘中は技の変更ができません。")
        actor = self.party[actor_index]
        skill = self.skills[skill_id]
        if skill_id in actor.skills:
            raise ValueError("すでに習得しています。")
        self.discovered_skills.add(skill_id)
        if len(actor.skills) < self.settings["skill_slots"]:
            actor.learn(skill)
            message = f"DEBUG: {actor.name}が{skill.name}を取得"
        else:
            actor.pending_skill = skill_id
            self.debug_pending = True
            message = f"DEBUG: {actor.name}が{skill.name}を取得・入替待ち"
        actor.history.append(message)
        return [message]

    def debug_set_one(self, skill_id, actor_index=0):
        if not self.debug:
            raise ValueError("DEBUG専用です。")
        if self.battle and not self.settled:
            raise ValueError("戦闘中は技の変更ができません。")
        actor = self.party[actor_index]
        if skill_id not in actor.skills:
            raise ValueError("選択中のキャラは未習得です。")
        actor.skill_uses[skill_id] = 1
        message = f"DEBUG: {actor.name} {self.skills[skill_id].name}を残り1回"
        actor.history.append(message)
        return [message]

    def archive_summary(self):
        """Return dynamic archive totals; JSON insertion order is the list order."""
        rarities = {}
        for skill in self.skills.values():
            row = rarities.setdefault(skill.rarity, {"total": 0, "discovered": 0,
                                                      "mastered": 0})
            row["total"] += 1
            row["discovered"] += skill.id in self.discovered_skills
            row["mastered"] += skill.id in self.mastered_skills
        return {
            "total": len(self.skills),
            "discovered": len(self.discovered_skills & self.skills.keys()),
            "mastered": len(self.mastered_skills & self.skills.keys()),
            "rarities": rarities,
        }

    def field_heal(self, actor_index, skill_id, target_index):
        """Exploration healing spends the same stock; growth is battle-only."""
        if self.pending_replacements or (self.battle and not self.settled):
            raise ValueError("戦闘・入れ替えを完了してください。")
        actor, target = self.party[actor_index], self.party[target_index]
        if not actor.alive or skill_id not in actor.skills or actor.skill_uses.get(skill_id, 0) <= 0:
            return False, ["この技を使用できません"]
        skill = self.skills[skill_id]
        if skill.effect != "heal":
            return False, ["探索中は回復技だけ使えます"]
        if not target.alive or target.hp == target.max_hp:
            return False, ["満タン・戦闘不能は消費なし"]
        restored = min(target.max_hp - target.hp, skill.power(actor))
        target.hp += restored
        actor.skill_uses[skill_id] -= 1
        messages = [f"{actor.name} {skill.name}: {target.name} HP +{restored}"]
        if actor.skill_uses[skill_id] == 0:
            actor.forget(skill_id)
            messages.append(f"{skill.name} 使い切り消滅")
            if skill_id not in self.mastered_skills:
                self.discovered_skills.add(skill_id)
                self.mastered_skills.add(skill_id)
                messages.append(f"{actor.name} {skill.name} MASTERED!")
        messages.extend(ensure_attack(actor, self.skills,
                                      self.settings["skill_slots"],
                                      self.discovered_skills))
        actor.history.extend("探索: " + line for line in messages)
        return True, messages
