"""Historical PASS03 configuration remains available for honest comparisons."""
import json
import unittest
from rpg.content import ROOT


class Encounter03BaselineTests(unittest.TestCase):
    def test_received_pass03_probabilities_and_grace_are_archived(self):
        before = json.loads((ROOT/'tests/fixtures/alpha_encounter04_before.json').read_text(encoding='utf8'))
        self.assertEqual(before['settings']['encounter_rates'], [.14,.12,.11])
        self.assertEqual(before['settings']['post_battle_safe_steps'], 6)
        self.assertIn('self.rng.random() < chance',before['legacy_move'])
