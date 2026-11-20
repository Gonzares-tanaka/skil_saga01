"""Phase 9B: real settle/skill/spark paths and detached clear SAVE boundaries."""
from copy import deepcopy
from unittest.mock import patch

from tests.encounter_fixture import EncounterFixture
from tests import test_phase7 as phase7
from rpg.growth import spark
from rpg.models import Action
from rpg.save import make_save_data, prepare_saved_game, SaveError


class FinalVictorySaveTests(EncounterFixture):
    final_ready = phase7.Phase7Tests.final_ready
    credits_to_title = phase7.Phase7Tests.credits_to_title

    def ready(self, mastered=False):
        a=self.a;s=a.session;c=s.party[0]
        for sid in list(c.skills):c.forget(sid)
        if mastered:s.mastered_skills.add('triple_slash')
        for sid in ('power_strike','double_slash','triple_slash','fire','heal','counter'):
            c.learn(s.skills[sid]);s.discovered_skills.add(sid)
        c.skill_uses['triple_slash']=1
        c.skill_uses['fire']=3
        c.hp=31
        s.treasure.banked=9
        self.final_ready()
        self.before=deepcopy(make_save_data(a))
        self.checkpoint=deepcopy(a.final_checkpoint.session_state)
        return a,s,s.party[0]

    def settle(self, new_skill=None, slot=None):
        a=self.a;s=a.session
        # Deterministic growth and an exact new skill through the real spark API.
        # These are test-only RNG/offer fixtures, not production balance changes.
        def selected(actor, skills, settings, rng, allowed=None, discovered=None):
            if actor is s.party[0] and new_skill:
                return spark(actor,{new_skill:skills[new_skill]},settings,rng,discovered=discovered)
            return []
        a.battle.outcome='VICTORY'
        with patch.object(s.rng,'random',return_value=0),patch.object(s.rng,'randint',return_value=2), \
             patch('rpg.growth.spark',side_effect=selected):
            s.settle()
        for index in list(s.pending_replacements):s.resolve_replacement(index,slot)
        self.earned=deepcopy(make_save_data(a))

    def finish(self):
        with patch.object(self.a,'waiting_for_fanfare',return_value=False):self.a.finish_results()

    def assert_candidate(self, saved):
        for before,earned,after in zip(self.before['party'],self.earned['party'],saved['party']):
            for key in ('max_hp','strength','agility','intellect','history'):
                self.assertEqual(after[key],earned[key],key)
            self.assertEqual(after['hp'],before['hp'])
            self.assertEqual([x['skill_id'] for x in after['skills']],
                             [x['skill_id'] for x in earned['skills']])
            self.assertLessEqual(len(after['skills']),6)
            self.assertEqual(len(after['skills']),len({x['skill_id'] for x in after['skills']}))
        self.assertEqual(saved['mastered_skills'],self.earned['mastered_skills'])
        self.assertEqual(saved['discovered_skills'],self.earned['discovered_skills'])
        self.assertEqual(saved['items'],self.before['items'])
        self.assertEqual(saved['banked_trz'],self.before['banked_trz'])
        self.assertTrue(saved['story']['has_amrita'])
        self.assertFalse(saved['story']['amrita_power_spent'])
        self.assertFalse(saved['story']['final_event_started'])
        prepare_saved_game(self.a,saved) # Actual v1 validation, including Uses and copies.

    def test_growth_mastery_exhaustion_resources_continue_and_restart(self):
        a,s,c=self.ready()
        a.battle._party_action(Action(0,'SKILL',0,'triple_slash'))
        a.battle._party_action(Action(0,'SKILL',0,'fire'))
        self.assertNotIn('triple_slash',c.skills)
        self.assertIn('triple_slash',s.mastered_skills)
        c.hp=1;s.inventory.counts['POTION']=0;s.treasure.banked=0
        self.settle();self.finish()
        saved=a.save_manager.backend.read();self.assert_candidate(saved)
        self.assertGreater(saved['party'][0]['max_hp'],self.before['party'][0]['max_hp'])
        self.assertEqual({x['skill_id']:x['uses'] for x in saved['party'][0]['skills']}['fire'],3)
        self.assertNotIn('triple_slash',[x['skill_id'] for x in saved['party'][0]['skills']])
        self.credits_to_title();a.continue_game();self.tick()
        self.assertEqual(make_save_data(a),saved)
        # A new app instance, same isolated backend; no real player SAVE.
        from rpg.battle import Session
        from rpg.content import load_content
        from rpg.dungeon_app import DungeonApp
        import pyxel
        with patch.object(pyxel,'init'):
            restarted=DungeonApp(Session(*load_content(),seed=1),run=False,headless=True,
                save_backend=a.save_manager.backend,suspend_backend=self.backend)
        restarted.continue_game()
        self.assertEqual(make_save_data(restarted),saved)

    def test_full_six_replacement_survives_without_resurrecting_old_copy(self):
        a,s,c=self.ready()
        a.battle._party_action(Action(0,'SKILL',0,'fire'))
        self.settle('meteor',slot=0);self.finish()
        saved=a.save_manager.backend.read();self.assert_candidate(saved)
        ids=[x['skill_id'] for x in saved['party'][0]['skills']]
        self.assertEqual(len(ids),6);self.assertEqual(ids[0],'meteor')
        self.assertNotIn('power_strike',ids)
        meteor=next(x for x in saved['party'][0]['skills'] if x['skill_id']=='meteor')
        self.assertEqual(meteor['uses'],s.skills['meteor'].max_uses)
        self.assertIn('meteor',saved['discovered_skills'])

    def test_declined_spark_keeps_discovery_but_not_loadout(self):
        a,s,c=self.ready();self.settle('meteor',slot=None);self.finish()
        saved=a.save_manager.backend.read();self.assert_candidate(saved)
        self.assertIn('meteor',saved['discovered_skills'])
        self.assertNotIn('meteor',[x['skill_id'] for x in saved['party'][0]['skills']])

    def test_exhaust_then_same_id_spark_uses_new_copy_even_when_already_mastered(self):
        for previously_mastered in (False,True):
            with self.subTest(previously_mastered=previously_mastered):
                a,s,c=self.ready(mastered=previously_mastered)
                a.battle._party_action(Action(0,'SKILL',0,'triple_slash'))
                self.settle('triple_slash');self.finish()
                saved=a.save_manager.backend.read();self.assert_candidate(saved)
                copies=[x for x in saved['party'][0]['skills'] if x['skill_id']=='triple_slash']
                self.assertEqual(len(copies),1)
                self.assertEqual(copies[0]['uses'],s.skills['triple_slash'].max_uses)
                self.assertTrue(copies[0]['mastered_copy'])
                a.continue_game();self.tick()

    def test_party_wide_mastery_does_not_promote_an_existing_unmastered_copy(self):
        a,s,c=self.ready();other=s.party[1]
        other.learn(s.skills['triple_slash']);s.discovered_skills.add('triple_slash')
        # Capture this legal loadout as the checkpoint, then start the attempt.
        from rpg.final_battle import FinalBattleCheckpoint
        a.final_checkpoint=FinalBattleCheckpoint.capture(s,a.dungeon,a.exploration)
        self.before=deepcopy(make_save_data(a))
        a.battle._party_action(Action(0,'SKILL',0,'triple_slash'))
        self.settle();self.finish()
        saved=a.save_manager.backend.read()
        self.assertIn('triple_slash',saved['mastered_skills'])
        copy=next(x for x in saved['party'][1]['skills'] if x['skill_id']=='triple_slash')
        self.assertFalse(copy['mastered_copy'])

    def test_candidate_and_failed_save_retry_never_mutate_or_double_apply(self):
        a,s,c=self.ready();old=self.before;a.save_manager.backend.write(old)
        a.battle._party_action(Action(0,'SKILL',0,'triple_slash'))
        self.settle('meteor')
        live=deepcopy(make_save_data(a));rng=s.rng.getstate()
        first=a.clear_candidate(True);second=a.clear_candidate(True)
        # First clear run IDs are minted once per candidate, not gameplay rewards.
        first['completion']['run_id']=second['completion']['run_id']
        self.assertEqual(first,second)
        self.assertEqual(make_save_data(a),live);self.assertEqual(s.rng.getstate(),rng)
        with patch.object(a.save_manager.backend,'write',side_effect=SaveError('full disk')):self.finish()
        self.assertEqual(a.state,'clear_save_error');self.assertEqual(a.save_manager.backend.read(),old)
        pending=deepcopy(a.completion_pending[1]);self.assert_candidate(pending)
        for _ in range(2):
            with patch.object(a.save_manager.backend,'write',side_effect=SaveError('full disk')):a.write_completion()
            self.assertEqual(a.completion_pending[1],pending)
            self.assertEqual(a.save_manager.backend.read(),old)
        a.write_completion();self.assertEqual(a.state,'ending')
        self.assertEqual(a.save_manager.backend.read(),pending)
        a.continue_game();self.tick();self.assertEqual(make_save_data(a),pending)

    def test_three_defeats_restore_full_checkpoint_before_rewarded_win(self):
        a,s,c=self.ready();cp=deepcopy(a.final_checkpoint.session_state)
        for _ in range(3):
            s.party[0].hp=0;s.inventory.counts['POTION']=0;s.treasure.banked=0
            a.battle._party_action(Action(1,'ITEM',item_id='AMRITA'))
            a.battle.outcome='DEFEAT';s.settle();self.finish()
            a.final_checkpoint.restore(s,a.dungeon,a.exploration)
            self.assertEqual(s.party,cp['party'])
            self.assertEqual(s.inventory.counts,cp['inventory'].counts)
            self.assertEqual(s.treasure.banked,cp['treasure'].banked)
            self.assertTrue(a.dungeon.finale.has_amrita)
            a.begin_final_battle();self.assertTrue(a.battle.elysion_barrier_active)
        self.settle();self.finish();self.assert_candidate(a.save_manager.backend.read())

    def test_repeat_clear_preserves_dragon_quests_and_adds_each_new_growth_only_once(self):
        a,s,c=self.ready();self.settle();self.finish();a.continue_game();self.tick()
        a.dungeon.completion.dragon_victory(17)
        a.session.party[0].strength+=3 # prior postclear training fixture
        prior=a.session.party[0].strength
        for _ in range(3):
            self.final_ready();self.before=deepcopy(make_save_data(a))
            self.settle();earned=self.earned['party'][0]['strength']
            self.finish();saved=a.save_manager.backend.read();self.assert_candidate(saved)
            self.assertEqual(saved['completion']['ancient_dragon_best_turns'],17)
            self.assertEqual(saved['quest_clear_counts'],self.before['quest_clear_counts'])
            self.assertEqual(saved['party'][0]['strength'],earned)
            self.assertEqual(earned,prior+1)
            a.continue_game();self.tick();self.assertEqual(make_save_data(a),saved)
            prior=earned
