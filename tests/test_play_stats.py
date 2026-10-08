"""Battle starts are durable play statistics, independent of settled outcomes."""
import json
import unittest

from rpg.battle import Session
from rpg.content import load_content
from rpg.models import Action, Enemy


class PlayStatsTests(unittest.TestCase):
    def session(self):
        return Session(*load_content(), seed=71)

    def test_initial_value_and_failed_starts_do_not_count(self):
        s = self.session()
        self.assertEqual(s.total_battles, 0)
        self.assertEqual(json.loads(json.dumps({'total_battles': s.total_battles})), {'total_battles': 0})
        with self.assertRaises(ValueError):
            s.next_battle([])
        self.assertEqual(s.total_battles, 0)
        s.next_battle()
        self.assertEqual(s.total_battles, 1)
        with self.assertRaises(ValueError):
            s.next_battle()
        self.assertEqual(s.total_battles, 1)

    def test_rounds_settlement_escape_defeat_and_draw_never_add_again(self):
        s = self.session()
        for count, outcome in enumerate(('ESCAPE', 'DEFEAT', 'DRAW'), 1):
            battle = s.next_battle([Enemy('試験', 9999, 1, 1, 1, (0, 0))])
            self.assertEqual(s.total_battles, count)
            for _ in range(3):
                battle.begin_round([Action(i, 'GUARD') for i in range(4)])
                while battle.queue:
                    battle.step()
                self.assertEqual(s.total_battles, count)
            battle.outcome = outcome  # Settlement fixture, not a balance adjustment.
            s.settle()
            s.settle()
            self.assertEqual(s.total_battles, count)

    def test_counter_does_not_change_enemies_rng_actions_or_balance(self):
        first, second = self.session(), self.session()
        second.total_battles = 10000
        left, right = first.next_battle(), second.next_battle()
        self.assertEqual([vars(e) for e in left.enemies], [vars(e) for e in right.enemies])
        self.assertEqual(first.rng.getstate(), second.rng.getstate())
        for battle in (left, right):
            battle.begin_round(battle.auto_actions())
            while battle.queue:
                battle.step()
        self.assertEqual([vars(c) for c in first.party], [vars(c) for c in second.party])
        self.assertEqual(first.rng.getstate(), second.rng.getstate())
        self.assertEqual((first.total_battles, second.total_battles), (1, 10001))


if __name__ == '__main__':
    unittest.main()
