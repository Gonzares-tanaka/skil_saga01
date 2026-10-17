"""Deterministic pre/post visual trace; test-only, never part of distribution."""
import hashlib
import json
from unittest.mock import Mock, patch
import pyxel
from rpg.battle_presentation import BattlePresentation


def rare_trace(battle):
    visual = BattlePresentation(battle)
    assert visual.start()
    trace = []
    while visual.active:
        surface = Mock()
        with patch.object(pyxel, 'text') as text:
            visual.draw_effect(surface)
        trace.append((visual.phase, visual.frame,
                      [visual.actor_offset(i) for i in range(4)], visual.shake_offset(),
                      [visual.target_flashing('enemy', i) for i in range(len(battle.enemies))],
                      [(call[0], call.args, call.kwargs) for call in surface.mock_calls],
                      [call.args[:4] for call in text.call_args_list]))
        if visual.advance() == 'apply':
            before = [enemy.alive for enemy in battle.enemies]
            hp = [actor.hp for actor in battle.party]
            battle.step(); visual.after_action(before, hp)
        assert len(trace) < 80
    return hashlib.sha256(json.dumps(trace, separators=(',', ':')).encode()).hexdigest()
