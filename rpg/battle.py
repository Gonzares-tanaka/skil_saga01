"""Battle rules independent of Pyxel, shared by the UI and simulation."""
from collections import deque
import random

from .growth import grow_and_spark, spark, growth_bonus
from .skill_resources import ensure_attack, MAX_SKILLS
from .models import Action, Character, Enemy, FieldSkillResult, effect_factor, battle_agility
from .skill_targets import target_refs
from .labels import OUTCOMES, EFFECTS, CURRENCY_NAME
from .treasure import Treasure
from .items import Inventory
from .final_battle import AMRITA_ITEM_ID, LORD_OF_ELYSION_ID, load_final_battle_data
from .enemy_actions import load_enemy_actions, choose_enemy_action
from .statuses import (load_statuses, active_statuses, apply_status, clear_statuses,
                       damage_hp, control_decision, confusion_target, cure_statuses)


GUARD_DAMAGE_MULTIPLIER = 0.5
COUNTER_DAMAGE_MULTIPLIER = 0.5


class Battle:
    def __init__(self, party, enemies, skills, max_rounds=60, rng=None,
                 skill_slots=MAX_SKILLS, discovered_skills=None, mastered_skills=None,
                 inventory=None, run_settings=None, boss=False, final_progress=None, final_data=None,
                 enemy_actions=None, status_definitions=None, persistent_poison=False):
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
        self.enemy_actions = load_enemy_actions() if enemy_actions is None else enemy_actions
        self.enemy_action_visual = None
        self.player_skill_visual = None
        self.last_skill_cured_count = 0
        self.status_definitions = load_statuses() if status_definitions is None else status_definitions
        self.status_visual_events = []
        self.status_messages = []
        self.turn_plan = None
        self.enemy_turn_progress = {}
        self.enemy_round_actions = {}
        self.enemy_recent_actions = {}
        self.skill_slots = skill_slots
        self.resource_events = []
        self.discovered_skills = discovered_skills if discovered_skills is not None else set()
        self.mastered_skills = mastered_skills if mastered_skills is not None else set()
        self.inventory = inventory or Inventory()
        self.run_settings = run_settings or self.inventory.data["run"]
        self.boss = boss
        self.run_override = None
        self.is_elysion_battle = boss and any(e.id == LORD_OF_ELYSION_ID for e in enemies)
        self.persistent_poison = persistent_poison and not self.is_elysion_battle
        self.final_progress = final_progress
        self.final_data = (final_data or load_final_battle_data()) if self.is_elysion_battle else None
        self.elysion_barrier_active = self.is_elysion_battle
        self.elysion_barrier_hint_shown = False
        self.elysion_barrier_hint_pending = False
        for actor in self.party:
            actor.mastered_skills = self.mastered_skills

    def begin_round(self, actions):
        if self.outcome or self.queue:
            raise ValueError("Cannot start a round during resolution or after battle.")
        expected = {i for i, c in enumerate(self.party) if c.alive}
        if len(actions) != len(expected) or {a.actor for a in actions} != expected:
            raise ValueError("Exactly one action per living character is required.")
        if sum(a.kind == 'ITEM' and a.item_id == AMRITA_ITEM_ID for a in actions) > 1:
            raise ValueError('アムリタは1ターンに1人だけが使えます。')
        for action in actions:
            actor = self.party[action.actor]
            if action.kind not in ("SKILL", "ITEM", "GUARD", "DEFEND", "STATUS"):
                raise ValueError("Unknown action.")
            if action.kind == 'STATUS' and 'confusion' not in active_statuses(actor):
                raise ValueError('STATUS is reserved for confused actors.')
            if action.kind == "SKILL":
                if self.skills.get(action.skill_id) and self.skills[action.skill_id].effect == "return":
                    raise ValueError("RETURNは探索中だけ使えます。")
                if (action.skill_id not in actor.skills or actor.skill_uses.get(action.skill_id, 0) <= 0
                        or actor.cooldowns.get(action.skill_id, 0)):
                    raise ValueError("Skill is unavailable, exhausted or cooling down.")
                skill = self.skills[action.skill_id]
                if skill.effect == "revive" and not (0 <= action.target < len(self.party) and not self.party[action.target].alive):
                    raise ValueError("REVIVEは戦闘不能の味方だけに使えます。")
            if action.kind == "ITEM":
                if action.item_id == AMRITA_ITEM_ID:
                    if not self.can_use_amrita:
                        raise ValueError('今はアムリタを使えません。')
                    continue
                if action.item_id not in ("POTION", "PHOENIX ASH", "REMEDY") or self.inventory.counts[action.item_id] <= 0:
                    raise ValueError("使用できる道具がありません。")
                if not 0 <= action.target < len(self.party):
                    raise ValueError("対象が不正です。")
                if (action.item_id == "PHOENIX ASH") == self.party[action.target].alive:
                    raise ValueError("道具の対象が不正です。")
                if action.item_id == "POTION" and self.party[action.target].hp >= self.party[action.target].max_hp:
                    raise ValueError("HPが満タンの味方には薬を使えません。")
                if action.item_id == 'REMEDY' and not active_statuses(self.party[action.target]):
                    raise ValueError('今は治す状態異常がありません')
        self.round += 1
        self.enemy_turn_progress.clear()
        self.enemy_round_actions.clear()
        for actor in self.party:
            actor.guarding = False
            actor.counter = None
        # Guard/counter take effect before attacks regardless of AGI.
        entries = []
        for action in actions:
            actor = self.party[action.actor]
            skill = self.skills[action.skill_id] if action.kind == "SKILL" else None
            priority = 1 if action.kind in ("GUARD", "DEFEND") or (skill and skill.effect == "counter") else 0
            entries.append((priority, battle_agility(actor), self.rng.random(), "party", action))
        for i, enemy in enumerate(self.enemies):
            if enemy.alive:
                entries.append((0, battle_agility(enemy), self.rng.random(), "enemy", i))
        entries.sort(key=lambda item: item[:3], reverse=True)
        for _, _, _, side, action in entries:
            self.queue.append((side, action))
            if side == 'enemy' and self.enemies[action].ai.get('actions_per_round', 1) == 2:
                self.queue.append((side, action))

    def _target(self, group, index):
        if 0 <= index < len(group) and group[index].alive:
            return group[index]
        return next((c for c in group if c.alive), None)

    def _damage(self, target, amount, magic=False, power_bonus=1.0):
        if self.elysion_barrier_active and getattr(target, 'id', '') == LORD_OF_ELYSION_ID:
            if not self.elysion_barrier_hint_shown:
                self.elysion_barrier_hint_shown = self.elysion_barrier_hint_pending = True
            return 0
        guard_factor = (COUNTER_DAMAGE_MULTIPLIER if getattr(target, "counter", None)
                        else GUARD_DAMAGE_MULTIPLIER) if target.guarding else 1
        if isinstance(target, Enemy) and target.guarding:
            guard_factor = target.guard_multiplier
        factor = guard_factor * (1.25 if target.berserk else 1) * effect_factor(target, "guard_up")
        # Characters have no DEF stat. Reuse armor_break as a physical damage
        # vulnerability; enemies retain their existing flat-DEF reduction rule.
        if not magic and not isinstance(target, Enemy):
            factor /= effect_factor(target, "armor_break")
        defense = getattr(target, "magic_defense", 0) if magic else getattr(target, "defense", 0) * effect_factor(target, "armor_break")
        damage = max(1, round(max(1, round(max(1, amount - defense) * factor)) * power_bonus))
        return self._lose_hp(target, damage)

    def _status_event(self, target, status_id, kind):
        side, group = ('enemy', self.enemies) if isinstance(target, Enemy) else ('party', self.party)
        index = next((i for i, unit in enumerate(group) if unit is target), None)
        if index is not None:
            self.status_visual_events.append(dict(status_id=status_id, kind=kind, target=(side, index)))

    def _lose_hp(self, target, amount):
        removed, woke = damage_hp(target, amount)
        if woke:
            self.status_messages.append(f'{target.name} は目を覚ました。')
            self._status_event(target, 'sleep', 'wake')
        return removed

    def apply_status(self, target, status_id, chance=100):
        applied = apply_status(target, status_id, chance, self.rng, self.status_definitions)
        if applied:
            self.status_messages.append(f'{target.name} は{self.status_definitions[status_id].name}になった。')
            self._status_event(target, status_id, 'apply')
        return applied

    def prepare_turn(self):
        """Cache a control check once, before a preview, without popping the queue."""
        if not self.queue:
            return None
        entry = self.queue[0]
        if self.turn_plan is None or self.turn_plan[0] != entry:
            side, action = entry
            unit = self.party[action.actor] if side == 'party' else self.enemies[action]
            cached = self.enemy_turn_progress.get(action) if side == 'enemy' else None
            states = cached[0] if cached else active_statuses(unit) if unit.alive else {}
            decision = cached[1] if cached else control_decision(unit, self.status_definitions, self.rng) if unit.alive else None
            self.turn_plan = entry, states, decision
        return self.turn_plan

    def _confusion_action(self, unit, side):
        definition = self.status_definitions['confusion']
        allies, foes = (self.party, self.enemies) if side == 'party' else (self.enemies, self.party)
        target = confusion_target(unit, allies, foes, definition, self.rng)
        lines = [f'{unit.name} は{definition.name}している！']
        self._status_event(unit, 'confusion', 'control')
        if target is None:
            return lines + [f'{unit.name} は何もしなかった。']
        power = unit.strength * definition.power * effect_factor(unit, 'power_up') * effect_factor(unit, 'weaken')
        if unit.berserk:
            power *= 1.5
        dealt = self._damage(target, round(power))
        self.player_hit |= not isinstance(target, Enemy) and dealt > 0
        self.sound_cue = 'attack'
        lines.append(f'{unit.name} の{definition.name}攻撃 {target.name} -{dealt}')
        if not target.alive:
            lines.append(f'{target.name} 戦闘不能')
        return lines

    def _finish_status_turn(self, unit, states):
        lines = []
        if not unit.alive:
            clear_statuses(unit)
            return lines
        if 'poison' in states and 'poison' in active_statuses(unit):
            amount = max(1, int(unit.max_hp * self.status_definitions['poison'].damage_fraction))
            # Preserve the final boss's existing barrier; poison bypasses normal armor/guard.
            dealt = self._damage(unit, amount) if self.elysion_barrier_active and getattr(unit, 'id', '') == LORD_OF_ELYSION_ID else self._lose_hp(unit, amount)
            self.player_hit |= not isinstance(unit, Enemy) and dealt > 0
            lines.append(f'{unit.name} {self.status_definitions["poison"].name} -{dealt}')
            self._status_event(unit, 'poison', 'tick')
            if not unit.alive:
                lines.append(f'{unit.name} 戦闘不能')
        for ident in states:
            current = active_statuses(unit)
            if ident not in current:
                continue
            if current[ident] > 1:
                unit.statuses[ident] -= 1
            else:
                unit.statuses.pop(ident)
                lines.append(f'{unit.name} の{self.status_definitions[ident].name}が消えた。')
        return lines

    def _party_action(self, action):
        actor = self.party[action.actor]
        if not actor.alive:
            return []
        if action.kind in ("GUARD", "DEFEND", "STATUS"):
            actor.guarding = True
            return [f"{actor.name} はまもる"]
        if action.kind == "ITEM":
            if action.item_id == AMRITA_ITEM_ID:
                if not self.can_use_amrita:
                    return list(self.final_data['amrita_unavailable']) if self.final_data else ['今はアムリタを使えない。']
                self.elysion_barrier_active = False
                self.sound_cue = 'skill'
                return [f'{actor.name} アムリタ'] + self.final_data['amrita_release']
            used, message = self.inventory.use(action.item_id, self.party[action.target])
            if used:
                self.sound_cue = "skill"
            return [f"{actor.name} {action.item_id}", message]
        if action.kind != "SKILL":
            raise ValueError("通常攻撃はありません。")
        if action.skill_id not in actor.skills or actor.skill_uses.get(action.skill_id, 0) <= 0 or actor.cooldowns.get(action.skill_id, 0):
            return [f"{actor.name} 技を使用できない"]
        skill = self.skills[action.skill_id]
        if skill.effect == "return":
            return ["RETURNは探索中だけ使えます。"]
        if skill.effect == "revive" and not (0 <= action.target < len(self.party) and not self.party[action.target].alive):
            return ["戦闘不能の味方がいません"]
        if skill.effect == 'cure' and skill.target == 'ally' and not (
                0 <= action.target < len(self.party) and self.party[action.target].alive):
            return ['治療できる生存者を選んでください']
        targets = target_refs(skill, action.actor, self.party, self.enemies, action.target, self.rng)
        if not targets:
            return []
        # Recheck at execution: another actor may already have cured the target.
        # Failed cures spend the queued turn, but never Uses/growth/cooldown.
        if skill.effect == 'cure' and not any(
                set(active_statuses(self.party[index])) & set(skill.cure_statuses)
                for side, index in targets):
            return ['治療対象なし。技回数は消費しません']
        if skill.target == 'random_enemy':
            self.player_skill_visual = dict(effect_id=skill.effect_id, targets=targets)
        self.sound_cue = "attack" if skill.rarity == "BASIC" else "skill"
        actor.skill_uses[skill.id] -= 1
        actor.used_skills[skill.id] = actor.used_skills.get(skill.id, 0) + 1
        actor.category_uses[skill.skill_type] = actor.category_uses.get(skill.skill_type, 0) + 1
        for stat, contribution in skill.growth.items():
            actor.growth_points[stat] = actor.growth_points.get(stat, 0) + contribution
        actor.cooldowns[skill.id] = skill.cooldown + 1
        lines = [f"{actor.name} {skill.name} 残{actor.skill_uses[skill.id]}"]
        lines.extend(self._skill_effect(actor, skill, action.target, targets))
        if actor.skill_uses[skill.id] == 0:
            actor.forget(skill.id)
            message = f"{actor.name} {skill.name} 使い切り消滅"
            lines.append(message)
            self.resource_events.append(message)
            if skill.id not in self.mastered_skills:
                self.discovered_skills.add(skill.id)
                self.mastered_skills.add(skill.id)
                message = f"{actor.name} {skill.name} MASTERED! {skill.mastery_label}"
                self.sound_cue = "mastered"
                lines.append(message)
                self.resource_events.append(message)
        return lines

    def _skill_effect(self, actor, skill, target_index, targets=None):
        self.last_skill_cured_count = 0
        if skill.effect == "counter":
            actor.guarding = True
            actor.counter = skill
            return ["防御し、物理攻撃に反撃"]
        if skill.effect == "berserk":
            actor.berserk = 4  # Includes this setup round and the next 3 rounds.
            return ["STR x1.5 / 被害 x1.25"]
        if targets is None:
            index = next(i for i, unit in enumerate(self.party) if unit is actor)
            targets = target_refs(skill, index, self.party, self.enemies, target_index, self.rng)
        lines = []
        for side, index in targets:
            target = (self.party if side == 'party' else self.enemies)[index]
            lines.extend(self._skill_target_effect(actor, skill, target))
        return lines

    def _skill_target_effect(self, actor, skill, target):
        lines = []
        if skill.effect in EFFECTS:
            target.effects[skill.effect] = (skill.modifier, skill.duration)
            return [f"{target.name} {EFFECTS[skill.effect]} {skill.duration}T"]
        if skill.effect == 'status':
            self.apply_status(target, skill.status_id, skill.status_chance)
            return []
        if skill.effect == 'cure':
            removed = cure_statuses(target, skill.cure_statuses)
            self.last_skill_cured_count += len(removed)
            for status_id in removed:
                self._status_event(target, status_id, 'cure')
            return [f"{target.name} " + ('状態異常を治療' if removed else '治療対象なし')]
        if skill.effect == "heal":
            restored = min(target.max_hp - target.hp, skill.power(actor))
            target.hp += restored
            return lines + [f"{target.name} HP +{restored}"]
        if skill.effect == "revive":
            target.hp = self.inventory.revival_hp(target)
            clear_statuses(target)
            return [f"{target.name} 復活 HP {target.hp}/{target.max_hp}"]
        dealt = self._damage(target, round(skill.power(actor, apply_mastery=False)
                                          * effect_factor(actor, "weaken")),
                             magic=skill.skill_type == "magic",
                             power_bonus=actor.power_multiplier(skill))
        suffix = f" ({skill.hits}連撃)" if skill.hits > 1 else ""
        lines.append(f"{target.name} -{dealt}{suffix}")
        if not target.alive:
            lines.append(f"{target.name} 戦闘不能")
        if skill.effect == "drain":
            restored = min(actor.max_hp - actor.hp, dealt // 2)
            actor.hp += restored
            lines.append(f"{actor.name} HP +{restored}")
        if skill.status_id is not None and target.alive:
            self.apply_status(target, skill.status_id, skill.status_chance)
        return lines

    def _enemy_action(self, index):
        enemy = self.enemies[index]
        living = [c for c in self.party if c.alive]
        self.enemy_action_visual = None
        self.player_skill_visual = None
        self.last_skill_cured_count = 0
        if not enemy.alive or not living:
            return []
        # Enemy GUARD survives the round boundary, until its next own action.
        if index not in self.enemy_turn_progress:
            enemy.guarding = False
        if enemy.ai:
            ident = choose_enemy_action(enemy, self.enemy_actions, self.rng,
                        self.enemy_round_actions.get(index, ()), self.enemy_recent_actions.get(index, ()))
        else:
            ident = choose_enemy_action(enemy, self.enemy_actions, self.rng)
        if ident is None:
            # Preserve the legacy target -> magic -> damage RNG sequence.
            targets = [self.rng.choice(living)]
            ident = 'magic' if self.rng.random() < enemy.magic_chance else 'attack'
        else:
            kind = self.enemy_actions[ident].target
            targets = living if kind == 'all_players' else (
                [self.rng.choice(living)] if kind == 'random_player' else [])
        action = self.enemy_actions[ident]
        if enemy.ai:
            self.enemy_round_actions.setdefault(index, []).append(ident)
            self.enemy_recent_actions[index] = (self.enemy_recent_actions.get(index, []) + [ident])[-3:]
        magic = action.type.startswith('magic')
        self.sound_cue = 'attack' if action.type.startswith('physical') else 'skill'
        lines = [f"{enemy.name} の{action.name}"]
        if action.type == 'guard':
            enemy.guarding, enemy.guard_multiplier = True, action.modifier
        elif action.type in ('buff', 'debuff'):
            target = enemy if action.type == 'buff' else targets[0]
            target.effects[action.effect] = (action.modifier, action.duration)
            lines.append(f"{target.name} {EFFECTS[action.effect]} {action.duration}T")
        elif action.type == 'status':
            hit_targets, hits_done = [], 0
        else:
            stat = (enemy.intellect if magic else enemy.strength * effect_factor(enemy, 'power_up'))
            stat *= effect_factor(enemy, 'weaken') * action.power
            hits_done = 0
            hit_targets = []
            for target in targets:
                for hit in range(action.hits):
                    if not target.alive or not enemy.alive:
                        break  # Never transfer remaining hits after KO.
                    if hit == 0:
                        hit_targets.append(target)
                    dealt = self._damage(target, round(stat * self.rng.uniform(0.9, 1.1)), magic=magic)
                    hits_done = max(hits_done, hit + 1)
                    self.player_hit |= dealt > 0
                    lines.append(f"{target.name} -{dealt}")
                    if not target.alive:
                        lines.append(f"{target.name} 戦闘不能")
                    elif target.counter and not magic:
                        returned = self._damage(enemy, round(target.counter.power(target)
                                                             * effect_factor(target, 'weaken')))
                        lines.append(f"反撃 {enemy.name} -{returned}")
                        if not enemy.alive:
                            lines.append(f"{enemy.name} 戦闘不能")
                if not enemy.alive:
                    break
        if action.status_id:
            for target in targets:
                self.apply_status(target, action.status_id, action.status_chance)
        # Display-only outcome. Presentation never selects actions or applies damage.
        damage_action = action.type.startswith(('physical', 'magic'))
        shown = hit_targets if damage_action else targets
        self.enemy_action_visual = dict(enemy_id=enemy.id, enemy_index=index,
            action_id=ident, effect_id=action.effect_id,
            targets=[('enemy', index)] if action.target == 'self' else
                [('party', next(i for i, actor in enumerate(self.party) if actor is target)) for target in shown],
            repeats=hits_done if damage_action else 1)
        return lines

    def step(self):
        """Resolve one queued actor; dead actors skip their action."""
        self.sound_cue = None
        self.player_hit = False
        self.enemy_action_visual = None
        self.player_skill_visual = None
        self.last_skill_cured_count = 0
        self.status_visual_events = []
        self.status_messages = []
        if self.outcome or not self.queue:
            return []
        _, states, decision = self.prepare_turn()
        side, action = self.queue.popleft()
        self.turn_plan = None
        unit = self.party[action.actor] if side == 'party' else self.enemies[action]
        if side == 'enemy' and action not in self.enemy_turn_progress:
            unit.guarding = False
        if not unit.alive:
            clear_statuses(unit)
            lines = []
        elif decision in ('sleep', 'paralyze'):
            name = self.status_definitions[decision].name
            lines = [f'{unit.name} は{name}中。' if decision == 'sleep' else f'{unit.name} は{name}で動けない！']
            self._status_event(unit, decision, 'control')
        elif decision == 'confusion':
            lines = self._confusion_action(unit, side)
        else:
            lines = self._party_action(action) if side == "party" else self._enemy_action(action)
        # A two-action enemy has one own turn: one control roll and one status
        # duration/poison tick. Player turns and normal enemies are unchanged.
        more_enemy_actions = (side == 'enemy' and unit.ai.get('actions_per_round', 1) == 2
                              and ('enemy', action) in self.queue)
        if more_enemy_actions:
            self.enemy_turn_progress[action] = (states, decision)
        else:
            lines.extend(self._finish_status_turn(unit, states))
            if side == 'enemy': self.enemy_turn_progress.pop(action, None)
        lines.extend(self.status_messages)
        if self.elysion_barrier_hint_pending:
            lines.extend(self.final_data['barrier_hint'])
            self.elysion_barrier_hint_pending = False
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

    def run_chance(self):
        allies = [c.agility for c in self.party if c.alive]
        foes = [e.agility for e in self.enemies if e.alive]
        if not allies or not foes:
            return self.run_settings["min"]
        difference = sum(allies) / len(allies) - sum(foes) / len(foes)
        rules = self.run_settings
        correction = max(-rules["agi_cap"], min(rules["agi_cap"], difference * rules["agi_factor"]))
        return max(rules["min"], min(rules["max"], rules["base"] + correction))

    def attempt_run(self):
        if self.boss:
            return ["YOU CANNOT ESCAPE!"]
        if self.outcome or self.queue:
            raise ValueError("行動中は逃走できません。")
        success = self.run_override if self.run_override is not None else self.rng.random() < self.run_chance()
        self.run_override = None
        if success:
            self.outcome = "ESCAPE"
            self.clear_effects()
            return ["逃走に成功した! 探索を続ける"]
        self.round += 1
        self.queue.extend(("enemy", i) for i, enemy in enumerate(self.enemies) if enemy.alive)
        return ["逃走失敗! 敵の攻撃を受ける"]

    def clear_effects(self):
        self.turn_plan = None
        keep_poison = self.persistent_poison and self.outcome in ('VICTORY', 'ESCAPE', 'DRAW')
        for unit in self.party + self.enemies:
            unit.effects.clear()
            clear_statuses(unit, preserve_poison=keep_poison and isinstance(unit, Character))
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
            if 'confusion' in active_statuses(actor):
                actions.append(Action(i, 'STATUS'))
                continue
            if self.can_use_amrita and not any(a.item_id == AMRITA_ITEM_ID for a in actions):
                actions.append(Action(i, 'ITEM', item_id=AMRITA_ITEM_ID))
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
                actions.append(Action(i, "GUARD"))
        return actions

    @property
    def can_use_amrita(self):
        return bool(self.is_elysion_battle and self.elysion_barrier_active and
                    self.final_progress is not None and self.final_progress.has_amrita and
                    not self.final_progress.amrita_power_spent)


class Session:
    def __init__(self, settings, skills, party, enemy_data, seed=None):
        self.settings, self.skills, self.party = settings, skills, party
        self.enemy_data = enemy_data
        self.rng = random.Random(seed)
        self.debug = False
        self.completed = self.wins = self.losses = self.draws = 0
        self.total_battles = 0  # Lifetime starts; excluded from final retry snapshots.
        self.battle = None
        self.settled = False
        self.results = []
        self.debug_pending = False
        self.field_pending = False
        self.discovered_skills = {
            skill_id for character in self.party for skill_id in character.skills
        }
        self.mastered_skills = set()
        for actor in self.party:
            actor.mastered_skills = self.mastered_skills
        self.treasure = Treasure()
        self.inventory = Inventory()
        self.pending_relearn = None

    def next_battle(self, enemies=None, recover=True, spark_multiplier=1.0, boss=False,
                    final_progress=None, final_data=None, persistent_poison=False):
        if self.pending_replacements:
            raise ValueError("先に技の入れ替えを決めてください。")
        if self.battle is not None and not self.settled:
            raise ValueError("Finish and settle the current battle first.")
        persistent_poison = persistent_poison and not recover and not (
            boss and enemies and any(e.id == LORD_OF_ELYSION_ID for e in enemies))
        for character in self.party:
            character.history.extend(ensure_attack(character, self.skills,
                                                    self.settings["skill_slots"],
                                                    self.discovered_skills))
            character.recover() if recover else character.reset_battle_state(preserve_poison=persistent_poison)
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
                enemies.append(Enemy.from_definition(row,
                                     name=f"{row['name']} {chr(65 + i)}", max_hp=hp,
                                     strength=row["str"] + power, intellect=row["int"] + power))
        if not enemies or not any(e.alive for e in enemies):
            raise ValueError("戦闘には生存する敵が必要です。")
        self.battle = Battle(self.party, enemies, self.skills,
                             self.settings["max_rounds"], self.rng,
                             self.settings["skill_slots"],
                             self.discovered_skills, self.mastered_skills,
                             self.inventory, boss=boss, final_progress=final_progress, final_data=final_data,
                             persistent_poison=persistent_poison)
        self.settled = False
        self.results = []
        self.total_battles += 1
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
                if self.debug:
                    detail = " ".join(f"{stat}+{growth_bonus(character, stat, self.settings):.0%}"
                                      for stat in ("HP", "STR", "AGI", "INT"))
                    self.results.append(f"DEBUG {character.name} {detail}")
                self.results.extend(grow_and_spark(character, self.skills, self.settings,
                                                   self.rng, self.completed, self.debug,
                                                   self.discovered_skills, self.spark_multiplier))
        elif outcome == "ESCAPE":
            self.results.append("逃走: 成長・閃き・報酬なし")
        else:
            if outcome == "DEFEAT":
                self.losses += 1
                if self.battle.is_elysion_battle:
                    self.results.extend(self.battle.final_data['defeat'])
                else:
                    self.results.append(f"未確定{CURRENCY_NAME}を{self.treasure.lose()}失った")
            else:
                self.draws += 1
            self.results.append("成長・閃きなし")
            for character in self.party:
                character.history.append(f"B{self.completed} {OUTCOMES[outcome]}: 成長なし")
        if self.battle.is_elysion_battle:
            self.results.append('旅の結末へ' if outcome == 'VICTORY' else '決戦前からの再挑戦を選べる')
        else:
            self.results.append("次戦でHP回復・技回数は持越" if self.auto_recover else "探索へ戻る")
        self.settled = True
        return self.results

    @property
    def pending_replacements(self):
        return [i for i, c in enumerate(self.party) if c.pending_skill is not None]

    def resolve_replacement(self, actor_index, slot=None):
        """Choose an old slot, or None to decline; never roll growth again."""
        if not self.settled and not self.debug_pending and not self.field_pending and self.pending_relearn is None:
            raise ValueError("戦闘結果を確定してください。")
        actor = self.party[actor_index]
        new_id = actor.pending_skill
        if new_id is None:
            raise ValueError("習得待ちの技がありません。")
        new = self.skills[new_id]
        relearn = self.pending_relearn == (actor_index, new_id)
        uses = actor.relearn_uses(new) if relearn else actor.next_max_uses(new)
        if slot is None:
            message = f"{actor.name} {new.name} の習得を見送った"
        else:
            if type(slot) is not int or not 0 <= slot < len(actor.skills):
                raise ValueError("無効な入れ替え枠です。")
            if relearn and self.treasure.banked < new.relearn_cost:
                raise ValueError(f"確定した{CURRENCY_NAME}が足りません。")
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
            self.field_pending = False
        return message

    def relearn_candidates(self):
        return [s for s in self.skills.values() if s.id in self.discovered_skills and s.can_relearn]

    def relearn(self, actor_index, skill_id):
        if self.pending_replacements or (self.battle and not self.settled):
            raise ValueError("戦闘・入れ替えを完了してください。")
        skill = self.skills[skill_id]
        if skill not in self.relearn_candidates():
            raise ValueError("未発見・再習得対象外の技です。")
        actor = self.party[actor_index]
        if skill_id in actor.skills:
            raise ValueError("すでに所持しています。残数の補充はできません。")
        if self.treasure.banked < skill.relearn_cost:
            raise ValueError(f"確定した{CURRENCY_NAME}が足りません。")
        if len(actor.skills) >= self.settings['skill_slots']:
            actor.pending_skill = skill_id
            self.pending_relearn = (actor_index, skill_id)
            return f"入れ替え確定時に{CURRENCY_NAME}を消費します"
        actor.learn(skill)
        actor.skill_uses[skill_id] = actor.relearn_uses(skill)
        self.treasure.banked -= skill.relearn_cost
        message = f"{actor.name} {skill.name} 再習得{actor.skill_uses[skill_id]}回 / {CURRENCY_NAME}-{skill.relearn_cost}"
        actor.history.append(message)
        return message

    def field_return(self, actor_index):
        if self.pending_replacements or (self.battle and not self.settled):
            raise ValueError("戦闘・入れ替えを完了してください。")
        actor = self.party[actor_index]
        skill = next((self.skills[s] for s in actor.skills if self.skills[s].effect == 'return' and self.skills[s].field_usable and actor.skill_uses.get(s, 0) > 0), None)
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
                lines.append(f"{skill.name} MASTERED! {skill.mastery_label}")
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
                    member.skill_uses[sid] = 1 if operation == "one" else member.max_uses(self.skills[sid])
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
        """Compatibility entry point for the existing healing UI/tools."""
        if self.skills[skill_id].effect != 'heal':
            return False, ["探索中は回復技だけ使えます"]
        result = self.field_use(actor_index, skill_id, target_index)
        return result.used, result.messages

    def field_use(self, actor_index, skill_id, target_index=0):
        """Heal/cure/return dispatcher; no battle usage/growth/cooldown gains.

        No-op heals/cures do not spend stock. Cure reports removed ailment count.
        The app owns the actual camp transition for a successful RETURN.
        """
        if self.pending_replacements or (self.battle and not self.settled):
            raise ValueError("戦闘・入れ替えを完了してください。")
        actor = self.party[actor_index]
        if not actor.alive or skill_id not in actor.skills or actor.skill_uses.get(skill_id, 0) <= 0:
            return FieldSkillResult(False, ["この技を使用できません"])
        skill = self.skills[skill_id]
        if not skill.field_usable:
            return FieldSkillResult(False, ["探索中は使用できません"])
        if skill.effect == 'return':
            return FieldSkillResult(True, self.field_return(actor_index), returned=True)
        if skill.effect not in ('heal', 'cure'):
            return FieldSkillResult(False, ["探索中は使用できません"])
        if skill.target == 'ally' and (not 0 <= target_index < len(self.party) or not self.party[target_index].alive):
            return FieldSkillResult(False, ["満タン・戦闘不能は消費なし"] if skill.effect == 'heal' else ["治療対象なし"])
        refs = target_refs(skill, actor_index, self.party, [], target_index)
        targets = [self.party[i] for _, i in refs]
        targets = [target for target in targets if target.hp < target.max_hp] if skill.effect == 'heal' else [
            target for target in targets if any(key in skill.cure_statuses for key in active_statuses(target))]
        if not targets:
            return FieldSkillResult(False, ["満タン・戦闘不能は消費なし"] if skill.effect == 'heal' else ["治療対象なし"])
        messages, cured_count = [], 0
        for target in targets:
            if skill.effect == 'heal':
                restored = min(target.max_hp - target.hp, skill.power(actor))
                target.hp += restored
                messages.append(f"{actor.name} {skill.name}: {target.name} HP +{restored}")
            else:
                cured_count += len(cure_statuses(target, skill.cure_statuses))
                messages.append(f"{actor.name} {skill.name}: {target.name} 状態異常を治療")
        actor.skill_uses[skill_id] -= 1
        if actor.skill_uses[skill_id] == 0:
            actor.forget(skill_id)
            messages.append(f"{skill.name} 使い切り消滅")
            if skill_id not in self.mastered_skills:
                self.discovered_skills.add(skill_id)
                self.mastered_skills.add(skill_id)
                messages.append(f"{actor.name} {skill.name} MASTERED! {skill.mastery_label}")
        messages.extend(ensure_attack(actor, self.skills,
                                      self.settings["skill_slots"],
                                      self.discovered_skills))
        actor.history.extend("探索: " + line for line in messages)
        return FieldSkillResult(True, messages, cured_count)
