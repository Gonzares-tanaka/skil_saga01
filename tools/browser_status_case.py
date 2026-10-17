"""Isolated fixture executed by Pyodide, not by the shipped game."""
import gc
import json
from collections import deque
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import pyxel
from rpg.dungeon_app import DungeonApp
from rpg.models import Enemy, Action
from rpg.enemy_actions import EnemyAction
from rpg.statuses import STATUS_IDS, apply_status, clear_statuses
from rpg.save import BrowserSaveBackend, make_save_data, apply_save_data


def run_cases():
    app = next(o for o in gc.get_objects() if isinstance(o, DungeonApp))
    app.start_new_game(); app.enter_camp(); app.opening_input_blocked = False
    app.begin_encounter()
    b = app.battle
    b.enemies = [Enemy.from_definition(app.session.enemy_data[0], max_hp=10000)]
    actor, enemy = b.party[0], b.enemies[0]
    results = []
    def fresh():
        for unit in b.party + b.enemies:
            unit.hp = unit.max_hp = 1000
            clear_statuses(unit); unit.effects.clear()
        b.outcome = None; b.turn_plan = None
    def turn(side, action=None):
        fast = bool(len(results) % 2)
        app.confirm = app.confirm_held = lambda: fast
        b.queue = deque([(side, action or (Action(0, 'GUARD') if side == 'party' else 0))])
        app.state = 'resolve'; app.delay = 0; app.pending.clear(); app.battle_visual().reset()
        app.apply_visual_action()
        hp = [c.hp for c in b.party] + [e.hp for e in b.enemies]
        phases = []
        for tick in range(100):
            if not app.battle_visual().active: break
            phases.append(app.battle_visual().phase)
            app.update(); app.draw()
        else: raise AssertionError('status animation stalled')
        assert hp == [c.hp for c in b.party] + [e.hp for e in b.enemies]
        return dict(ticks=tick, phases=sorted(set(phases)))
    with patch.object(pyxel, 'btnp', return_value=False), patch.object(pyxel, 'btn', return_value=False), \
         patch.object(pyxel, 'play', side_effect=RuntimeError('suspended')), \
         patch.object(pyxel, 'playm', side_effect=RuntimeError('suspended')), \
         patch.object(pyxel, 'play_pos', side_effect=RuntimeError('closed')):
        app.confirm = app.confirm_held = app.cancel = lambda: True
        app.direction = lambda horizontal=False: 1
        fresh(); apply_status(actor, 'poison')
        for _ in range(3): turn('party')
        assert actor.hp == 850 and not actor.statuses
        results.append('poison_3_ticks')
        fresh(); apply_status(actor, 'sleep'); apply_status(actor, 'poison')
        before = deepcopy(actor.skill_uses)
        event = turn('party', Action(0, 'SKILL', 0, actor.skills[0]))
        assert actor.skill_uses == before and actor.hp == 950 and 'sleep' not in actor.statuses
        assert 'status_effect' in event['phases'] and 'party_hit' in event['phases']
        results.append('sleep_skip_poison_wake')
        fresh(); apply_status(actor, 'paralyze')
        sid = actor.skills[0]; before = actor.skill_uses[sid]
        with patch.object(b.rng, 'random', return_value=0):
            turn('party', Action(0, 'SKILL', 0, sid))
        assert actor.skill_uses[sid] == before
        with patch.object(b.rng, 'random', return_value=.99):
            turn('party', Action(0, 'SKILL', 0, sid))
        assert actor.skill_uses.get(sid, 0) == before - 1
        results.append('paralyze_skip_and_act')
        fresh(); actor.strength = 100
        before = deepcopy((actor.skill_uses, actor.category_uses, actor.growth_points))
        apply_status(actor, 'confusion'); app.begin_input()
        assert app.actor_index == 1 and app.actions[0].kind == 'STATUS'
        for branch in ('enemy', 'ally', 'idle'):
            apply_status(actor, 'confusion')
            with patch.object(b.rng, 'choices', return_value=[branch]), \
                 patch.object(b.rng, 'choice', side_effect=lambda choices: choices[0]):
                turn('party', Action(0, 'SKILL', 0, actor.skills[0]))
        assert (actor.skill_uses, actor.category_uses, actor.growth_points) == before
        assert enemy.hp == 925 and b.party[1].hp == 925 and actor.hp == 1000
        results.append('confusion_no_uses_growth_or_self_attack')
        fresh(); apply_status(enemy, 'confusion')
        with patch.object(b.rng, 'choices', return_value=['ally']): turn('enemy')
        assert enemy.hp == 1000
        results.append('lone_enemy_confusion_idle')
        fresh(); apply_status(actor, 'poison'); apply_status(actor, 'sleep')
        actor.effects = {'weaken': (.85, 3), 'slow': (.8, 3)}
        b.inventory.counts['REMEDY'] = 1
        turn('party', Action(1, 'ITEM', 0, item_id='REMEDY'))
        assert not actor.statuses and b.inventory.counts['REMEDY'] == 0 and set(actor.effects) == {'weaken', 'slow'}
        results.append('remedy_statuses_only')
        fresh()
        for ident in STATUS_IDS:
            enemy.actions = [dict(id='status_test', weight=1)]
            b.enemy_actions['status_test'] = EnemyAction('status test', 'status', 'random_player', status_id=ident)
            clear_statuses(actor)
            with patch.object(b.rng, 'choice', return_value=actor): turn('enemy')
            assert ident in actor.statuses
        b.enemy_actions['status_test'] = replace(b.enemy_actions['attack'], status_id='poison', status_chance=100)
        clear_statuses(actor)
        with patch.object(b.rng, 'choice', return_value=actor): turn('enemy')
        assert actor.hp < 1000 and actor.statuses['poison'] == 3
        results.append('enemy_status_only_and_damage_status')
        fresh(); apply_status(actor, 'poison'); apply_status(enemy, 'sleep')
        b.run_override = True; b.queue.clear(); b.attempt_run()
        assert actor.statuses == {'poison': 3} and not enemy.statuses
        results.append('escape_preserves_poison_only')
        fresh(); actor.hp = 1
        apply_status(actor, 'poison'); apply_status(actor, 'sleep')
        turn('party')
        assert not actor.alive and not actor.statuses
        b.inventory.counts['PHOENIX ASH'] = 1
        assert b.inventory.use('PHOENIX ASH', actor)[0] and not actor.statuses
        results.append('poison_ko_revive_clear')
        # Serialize through the actual browser backend, in this isolated profile only.
        b.clear_effects(); app.enter_camp()
        saved = make_save_data(app)
        assert saved['save_version'] == 1 and 'statuses' not in json.dumps(saved)
        backend = BrowserSaveBackend(); backend.write(saved)
        apply_save_data(app, backend.read())
        assert not any(c.statuses for c in app.session.party)
        results.append('localStorage_save_load_schema1')
    return json.dumps(dict(cases=results, count=len(results), all_silent=True,
                           normal_and_fast_supported=True, save_version=1))


run_cases()
