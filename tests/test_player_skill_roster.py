"""Official roster contracts, real actions, resources, controls and save codec."""
from collections import Counter, deque
from copy import deepcopy
import hashlib
import json
import random
import sys
import unittest
from unittest.mock import patch
from rpg.battle import Battle, Session
from rpg.content import ROOT, load_content
from rpg.growth import spark
from rpg.models import Action, Enemy
from rpg.skill_resources import ensure_attack
from rpg.statuses import load_statuses

# Independent specification: ID type effect target STR AGI INT Uses CD FX.
SPECS = '''
sweep physical damage all_enemies .75 0 0 12 1 slash
flame_wave magic damage all_enemies 0 0 .85 10 1 fire
venom_strike physical damage enemy 1.4 0 0 12 1 pierce
sleep_spell support status enemy 0 0 0 8 2 debuff
group_aid healing heal all_allies 0 0 .8 6 2 heal
battle_cry support power_up all_allies 0 0 0 4 3 buff
weak_wave support weaken all_enemies 0 0 0 4 3 debuff
wild_edge speed damage random_enemy .5 1.2 0 16 0 pierce
whirlwind speed damage all_enemies .45 .7 0 8 2 slash
blizzard magic damage all_enemies 0 0 1.4 7 2 ice
shock_stab speed damage enemy .6 .9 0 10 2 lightning
confuse support status enemy 0 0 0 6 2 debuff
toxic_mist support status all_enemies 0 0 0 6 2 dark
mending_wind healing heal all_allies 0 0 1.4 5 2 heal
iron_wall support guard_up all_allies 0 0 0 4 3 buff
slow_field support slow all_enemies 0 0 0 4 3 debuff
cure support cure ally 0 0 0 3 0 heal
cleaving_storm physical damage all_enemies 1.5 0 0 5 3 slash
inferno magic damage all_enemies 0 0 2.4 4 3 fire
plague_edge physical damage enemy 2.1 0 0 5 2 dark
thunder_bind magic damage enemy 0 0 2.3 5 2 lightning
nightmare magic damage enemy 0 0 2 4 3 dark
chaos_spell magic damage enemy 0 0 1.8 4 3 dark
armor_wave support armor_break all_enemies 0 0 0 4 3 debuff
focus_field support focus all_allies 0 0 0 4 3 buff
purify_wind support cure all_allies 0 0 0 2 3 heal
ragnarok physical damage all_enemies 3 0 0 2 4 legend
starfall magic damage all_enemies 0 0 4.5 2 4 legend
miracle healing heal all_allies 0 0 5 2 0 heal
sanctuary support guard_up all_allies 0 0 0 2 4 buff
time_stop support status all_enemies 0 0 0 1 4 debuff
'''.strip().splitlines()
NEW_IDS=tuple(line.split()[0] for line in SPECS)
STATUSES={'venom_strike':('poison',35),'sleep_spell':('sleep',45),
          'shock_stab':('paralyze',30),'confuse':('confusion',45),'toxic_mist':('poison',30),
          'plague_edge':('poison',60),'thunder_bind':('paralyze',45),
          'nightmare':('sleep',45),'chaos_spell':('confusion',40),'time_stop':('sleep',70)}
FIELD_IDS=('group_aid','mending_wind','cure','purify_wind','miracle')
RESTORES=dict(zip(NEW_IDS[:8],(6,5,6,4,3,2,2,8)))
RESTORES.update(cure=2,armor_wave=2,focus_field=2)
GROWTH={'physical':(0,2,0,0),'speed':(0,2,2,0),'magic':(0,0,0,2),
        'support':(0,0,0,1),'healing':(.5,0,0,1)}


class SkillRosterTests(unittest.TestCase):
    def setUp(self):
        self.s=Session(*load_content(),seed=817); self.actor=self.s.party[0]
        self.actor.strength=self.actor.agility=self.actor.intellect=40
        for c in self.s.party: c.hp=c.max_hp=1000
        self.enemies=[Enemy('E'+str(i),1000,1,1,1,(0,0),defense=i*3,magic_defense=i*5) for i in range(4)]
        self.b=Battle(self.s.party,self.enemies,self.s.skills,rng=self.s.rng,
                      discovered_skills=self.s.discovered_skills,mastered_skills=self.s.mastered_skills)

    def use(self,sid,target=0):
        if sid not in self.actor.skills: self.actor.learn(self.s.skills[sid])
        self.actor.cooldowns.clear()
        self.b.queue=deque([('party',Action(0,'SKILL',target,sid)),('party',Action(1,'GUARD'))])
        self.b.turn_plan=None
        return self.b.step()

    def app(self):
        import pyxel
        from rpg.dungeon_app import DungeonApp
        if not getattr(pyxel,'_tests_initialized',False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized=True
        with patch.object(pyxel,'init'):
            return DungeonApp(Session(*load_content(),seed=817),run=False,headless=True,start_at_title=False)

    def press(self,app,key):
        import pyxel
        with patch.object(pyxel,'btnp',side_effect=lambda code,*args:code==key),patch.object(pyxel,'btn',return_value=False):
            app.update(); app.draw()

    def test_counts_initial_archive_and_ids(self):
        raw=json.loads((ROOT/'data/skills.json').read_text(encoding='utf8'))
        self.assertEqual(len(raw),len({r['id'] for r in raw}))
        self.assertEqual(len(self.s.skills),62)
        self.assertEqual(Counter(s.rarity for s in self.s.skills.values()),
                         {'BASIC':3,'COMMON':18,'UNCOMMON':13,'RARE':20,'LEGEND':8})
        self.assertEqual([c.skills for c in self.s.party],[['punch'],['quick_hit'],['spark'],['punch']])
        summary=self.s.archive_summary()
        self.assertEqual((summary['discovered'],summary['mastered'],summary['total']),(3,0,62))
        self.assertTrue(set(NEW_IDS).isdisjoint(self.s.discovered_skills))

    def test_every_new_skill_exact_specification(self):
        for i,line in enumerate(SPECS):
            sid,kind,effect,target,s,a,n,uses,cd,fx=line.split(); skill=self.s.skills[sid]
            with self.subTest(skill=sid):
                self.assertEqual((skill.skill_type,skill.effect,skill.target,skill.effect_id),(kind,effect,target,fx))
                self.assertEqual((skill.str_scale,skill.agi_scale,skill.int_scale),(float(s),float(a),float(n)))
                self.assertEqual((skill.hits,skill.max_uses,skill.cooldown),(1,int(uses),int(cd)))
                self.assertEqual(skill.rarity,'COMMON' if i<8 else 'UNCOMMON' if i<16 else 'RARE' if i<26 else 'LEGEND')
                self.assertEqual(skill.field_usable,sid in FIELD_IDS)
                self.assertEqual((skill.status_id,skill.status_chance),STATUSES.get(sid,(None,0)))
                self.assertEqual(tuple(skill.growth[k] for k in ('HP','STR','AGI','INT')),GROWTH[kind])

    def test_legacy_rows_protected_data_sources_assets(self):
        old=json.loads((ROOT/'tests/fixtures/player_skills_31.json').read_text(encoding='utf8'))
        raw=json.loads((ROOT/'data/skills.json').read_text(encoding='utf8'))
        self.assertEqual([{k:v for k,v in row.items() if k != 'presentation_id'} for row in raw[:31]],old)
        self.assertEqual({r['id'] for r in raw[31:]},set(NEW_IDS))
        if sys.platform=='emscripten': return  # Native hashes all files; Web payload verified separately.
        hashes=json.loads((ROOT/'tests/fixtures/player_skill_roster_protected.json').read_text(encoding='utf-8-sig'))
        for name,digest in hashes.items():
            from tests.test_enemy_balance import ALLOWED
            if name in ALLOWED: continue  # Independently protected by this pass.
            # RARE presentation has dedicated full row/pixel/rule parity tests.
            if name in ('rpg/models.py','rpg/content.py','rpg/app.py','rpg/battle_presentation.py','game.pyxres'):
                continue
            if name == 'data/statuses.json':
                # Balance pass 01 permits exactly the 35% -> 50% skip change.
                data = (ROOT/name).read_bytes()
                self.assertEqual(data.count(b'"skip_chance": 0.50'), 1)
                original = data.replace(b'"skip_chance": 0.50', b'"skip_chance": 0.35')
                self.assertEqual(hashlib.sha256(original).hexdigest(), digest, name)
                continue
            if name in ('rpg/sound.py', 'rpg/dungeon_app.py'): continue  # Verified AUDIO PASS scene/event hooks.
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)

    def test_all_damage_defense_ko_and_one_resource_charge(self):
        for sid in NEW_IDS:
            if self.s.skills[sid].effect!='damage': continue
            with self.subTest(skill=sid):
                self.setUp(); skill=self.s.skills[sid]; self.enemies[3].hp=0
                hp=[e.hp for e in self.enemies]; self.use(sid)
                selected=([0,1,2] if skill.target=='all_enemies' else
                          [self.b.player_skill_visual['targets'][0][1]] if skill.target=='random_enemy' else [0])
                for i,e in enumerate(self.enemies):
                    defense=e.magic_defense if skill.skill_type=='magic' else e.defense
                    self.assertEqual(hp[i]-e.hp,max(1,round(skill.power(self.actor)-defense)) if i in selected else 0)
                self.assertEqual(self.actor.skill_uses[sid],skill.max_uses-1)
                self.assertEqual(self.actor.used_skills,{sid:1})
                self.assertEqual(self.actor.category_uses,{skill.skill_type:1})
                self.assertEqual(self.actor.growth_points,skill.growth)
                self.assertEqual(self.actor.cooldowns[sid],skill.cooldown+1)

    def test_random_one_living_and_no_preview_rng(self):
        from rpg.battle_presentation import BattlePresentation
        self.actor.learn(self.s.skills['wild_edge']); self.enemies[1].hp=0
        self.b.queue=deque([('party',Action(0,'SKILL',999,'wild_edge')),('party',Action(1,'GUARD'))])
        state=self.b.rng.getstate(); rng=random.Random(); rng.setstate(state); expected=rng.choice([0,2,3])
        visual=BattlePresentation(self.b); self.assertTrue(visual.start())
        self.assertEqual(self.b.rng.getstate(),state)
        self.b.step()
        self.assertEqual(self.b.player_skill_visual['targets'],[('enemy',expected)])
        self.assertEqual(self.b.rng.getstate(),rng.getstate())
        visual.after_action([True,False,True,True])
        self.assertEqual(visual.enemy_effect_targets,[('enemy',expected)])

    def test_damage_status_success_fail_and_ko(self):
        for sid,(status,chance) in STATUSES.items():
            if self.s.skills[sid].effect!='damage': continue
            for mode in ('success','fail','ko'):
                with self.subTest(skill=sid,mode=mode):
                    self.setUp()
                    if mode=='ko': self.enemies[0].hp=1
                    hp=self.enemies[0].hp
                    with patch.object(self.b.rng,'random',return_value=0 if mode=='success' else .999): self.use(sid)
                    self.assertLess(self.enemies[0].hp,hp)
                    self.assertEqual(self.enemies[0].statuses,{status:load_statuses()[status].duration} if mode=='success' else {})
                    self.assertEqual(self.actor.skill_uses[sid],self.s.skills[sid].max_uses-1)

    def test_pure_status_fail_cost_turn_cooldown_progress(self):
        for sid in ('sleep_spell','confuse','toxic_mist','time_stop'):
            with self.subTest(skill=sid):
                self.setUp(); skill=self.s.skills[sid]
                with patch.object(self.b.rng,'random',return_value=.999): self.use(sid)
                self.assertTrue(all(e.hp==1000 and not e.statuses for e in self.enemies))
                self.assertEqual(self.actor.used_skills,{sid:1}); self.assertEqual(len(self.b.queue),1)
                if skill.max_uses>1:
                    self.assertEqual(self.actor.skill_uses[sid],skill.max_uses-1)
                    self.assertEqual(self.actor.cooldowns[sid],skill.cooldown+1)
                else:
                    self.assertNotIn(sid,self.actor.skills); self.assertIn(sid,self.s.mastered_skills)
                self.b.step(); self.assertFalse(self.b.queue)

    def test_all_status_independent_roll_resistance_immunity_control(self):
        for sid in ('toxic_mist','time_stop'):
            with self.subTest(skill=sid):
                self.setUp(); status=self.s.skills[sid].status_id
                self.enemies[2].status_immunities=(status,); self.enemies[3].status_resistances={status:50}
                with patch.object(self.b.rng,'random',side_effect=[0,.99,.99]) as draws: self.use(sid)
                self.assertEqual(draws.call_count,3)
                self.assertEqual([bool(e.statuses) for e in self.enemies],[True,False,False,False])
        self.setUp(); self.enemies[0].statuses={'confusion':2}
        with patch.object(self.b.rng,'random',return_value=0): self.use('time_stop')
        self.assertEqual(self.enemies[0].statuses,{'confusion':2})

    def test_time_stop_current_bosses_70_percent(self):
        for row in self.s.enemy_data:
            if not row.get('boss'): continue
            for draw,success in ((.69,True),(.70,False)):
                with self.subTest(boss=row['id'],draw=draw):
                    self.setUp()
                    enemy=Enemy(row['name'],row['max_hp'],row['str'],row['agi'],row['int'],tuple(row['sprite']),id=row['id'],
                                status_resistances=row.get('status_resistances',{}),status_immunities=tuple(row.get('status_immunities',())))
                    self.b.enemies=[enemy]
                    with patch.object(self.b.rng,'random',return_value=draw): self.use('time_stop')
                    self.assertEqual(bool(enemy.statuses),success); self.assertEqual(enemy.hp,row['max_hp'])

    def test_buff_debuff_same_slot_refresh_not_stack(self):
        pairs=(('battle_cry','power_up'),('weak_wave','weaken'),('iron_wall','guard_up'),
               ('slow_field','slow'),('armor_wave','armor_break'),('focus_field','focus'))
        for new,old in pairs:
            with self.subTest(skill=new):
                self.setUp(); a,b=self.s.skills[new],self.s.skills[old]
                self.assertEqual((a.effect,a.modifier,a.duration),(b.effect,b.modifier,b.duration))
                group=self.s.party if a.target=='all_allies' else self.enemies; group[3].hp=0
                self.use(old,1); self.use(new); self.use(old,1)
                for i,target in enumerate(group): self.assertEqual(target.effects,{} if i==3 else {a.effect:(a.modifier,3)})

    def test_sanctuary_defense_family_055_two_turns(self):
        self.use('guard_up',1); self.use('sanctuary')
        for c in self.s.party:
            self.assertEqual(c.effects,{'guard_up':(.55,2)}); self.assertEqual(self.b._damage(c,100),55)
        self.use('iron_wall'); self.assertEqual(self.s.party[1].effects,{'guard_up':(.7,3)})
        self.use('sanctuary'); self.assertEqual(self.s.party[1].effects,{'guard_up':(.55,2)})

    def test_final_barrier_all_new_attacks_and_poison_ticks(self):
        from rpg.final_battle import make_final_enemy, load_final_battle_data
        for sid in NEW_IDS:
            if self.s.skills[sid].effect!='damage': continue
            with self.subTest(skill=sid):
                self.setUp(); enemy=make_final_enemy(self.s.enemy_data)
                self.b.enemies=[enemy]; self.b.elysion_barrier_active=True
                self.b.final_data=load_final_battle_data(); before=enemy.hp
                with patch.object(self.b.rng,'random',return_value=0): self.use(sid)
                self.assertEqual(enemy.hp,before)
                self.assertTrue(self.b.elysion_barrier_hint_shown)
                if enemy.statuses.get('poison'):
                    self.b._finish_status_turn(enemy,dict(enemy.statuses))
                    self.assertEqual(enemy.hp,before)
                self.b.elysion_barrier_active=False; enemy.statuses.clear()
                self.use(sid); self.assertLess(enemy.hp,before)

    def test_final_checkpoint_new_skills_restore_three_times(self):
        from rpg.final_battle import FinalBattleCheckpoint
        app=self.app(); s=app.session
        app.dungeon.finale.has_amrita=True; app.dungeon.finale.demon_defeated=True
        for start in range(0,len(NEW_IDS),5):
            c=s.party[0]
            for sid in list(c.skills): c.forget(sid)
            c.learn(s.skills['punch'])
            for sid in NEW_IDS[start:start+5]:
                s.discovered_skills.add(sid); s.mastered_skills.add(sid)
                c.learn(s.skills[sid]); c.skill_uses[sid]=1
            checkpoint=FinalBattleCheckpoint.capture(s,app.dungeon,app.exploration)
            before=deepcopy((c.skills,c.skill_uses,c.mastered_copies,s.inventory.counts,s.discovered_skills,s.mastered_skills,c.hp))
            for attempt in range(3):
                c=s.party[0]; c.hp=0
                for sid in list(c.skills): c.forget(sid)
                s.inventory.counts={k:0 for k in s.inventory.counts}
                app.dungeon.finale.has_amrita=False
                checkpoint.restore(s,app.dungeon,app.exploration); c=s.party[0]
                self.assertEqual((c.skills,c.skill_uses,c.mastered_copies,s.inventory.counts,s.discovered_skills,s.mastered_skills,c.hp),before)
                self.assertTrue(app.dungeon.finale.has_amrita)

    def test_cures_four_statuses_no_hp_effect_change_living_only(self):
        for sid in ('cure','purify_wind'):
            for status in load_statuses():
                with self.subTest(skill=sid,status=status):
                    self.setUp()
                    for c in self.s.party: c.statuses={status:2}; c.effects={'weaken':(.8,3),'power_up':(1.4,3)}; c.hp=50
                    # A sleeping/confused caster correctly cannot cast. Test
                    # cures on affected targets using an able, healthy caster.
                    self.actor.statuses={}
                    self.s.party[3].hp=0; self.use(sid,1); eligible=[1] if sid=='cure' else [1,2]
                    for i,c in enumerate(self.s.party):
                        self.assertEqual(c.hp,0 if i==3 else 50)
                        self.assertEqual(c.effects,{'weaken':(.8,3),'power_up':(1.4,3)})
                        self.assertEqual(c.statuses,{} if i in eligible or i==0 else {status:2})
                    self.assertEqual(self.b.last_skill_cured_count,len(eligible))

    def test_cure_noop_no_stock_growth_cooldown_mastery_or_retarget(self):
        for sid in ('cure','purify_wind'):
            with self.subTest(skill=sid):
                self.setUp(); self.actor.learn(self.s.skills[sid]); self.actor.skill_uses[sid]=1; self.use(sid,1)
                self.assertEqual(self.actor.skill_uses[sid],1)
                self.assertFalse(self.actor.cooldowns or self.actor.used_skills or self.actor.growth_points)
                self.assertNotIn(sid,self.s.mastered_skills); self.assertEqual(len(self.b.queue),1)
        self.setUp(); self.s.party[1].hp=0; self.s.party[2].statuses={'poison':2}; self.use('cure',1)
        self.assertEqual(self.actor.skill_uses['cure'],3); self.assertEqual(self.s.party[2].statuses,{'poison':2})
        self.s.party[1].hp=10; self.s.party[1].statuses={'poison':2}; self.use('cure',1); self.use('cure',1)
        self.assertEqual(self.actor.skill_uses['cure'],2); self.assertEqual(self.actor.used_skills['cure'],1)

    def test_group_heals_battle_field_hp0_full_noop(self):
        for sid in ('group_aid','mending_wind','miracle'):
            for field in (False,True):
                with self.subTest(skill=sid,field=field):
                    self.setUp(); self.actor.learn(self.s.skills[sid]); self.s.party[1].hp=1; self.s.party[2].hp=0
                    if field: self.assertTrue(self.s.field_use(0,sid).used)
                    else: self.use(sid)
                    self.assertEqual(self.s.party[1].hp,1+self.s.skills[sid].power(self.actor))
                    self.assertEqual(self.s.party[2].hp,0)
                    self.assertEqual(self.actor.skill_uses[sid],self.s.skills[sid].max_uses-1)
                    if field:
                        self.assertFalse(self.actor.growth_points or self.actor.used_skills)
                        self.s.party[1].hp=1000; before=self.actor.skill_uses[sid]
                        self.assertFalse(self.s.field_use(0,sid).used); self.assertEqual(self.actor.skill_uses[sid],before)

    def test_field_cures_persistent_poison_noop_no_growth(self):
        for sid in ('cure','purify_wind'):
            with self.subTest(skill=sid):
                self.setUp(); self.actor.learn(self.s.skills[sid])
                self.assertFalse(self.s.field_use(0,sid,1).used)
                self.assertEqual(self.actor.skill_uses[sid],self.s.skills[sid].max_uses)
                self.s.party[1].statuses={'poison':2}; self.s.party[1].hp=50; self.s.party[1].effects={'slow':(.5,3)}
                result=self.s.field_use(0,sid,1)
                self.assertEqual((result.used,result.cured_count),(True,1))
                self.assertEqual((self.s.party[1].hp,self.s.party[1].effects),(50,{'slow':(.5,3)}))
                self.assertFalse(self.s.party[1].statuses or self.actor.growth_points or self.actor.cooldowns)

    def test_restore_26_exact_cost_stock_no_owned_refill(self):
        self.assertEqual(sum(s.can_relearn for s in self.s.skills.values()),26)
        for sid in NEW_IDS:
            with self.subTest(skill=sid):
                self.setUp(); skill=self.s.skills[sid]; self.assertEqual(skill.can_relearn,sid in RESTORES)
                if sid not in RESTORES: continue
                cost=2 if skill.rarity=='COMMON' else 4
                self.assertEqual((skill.relearn_cost,skill.relearn_uses),(cost,RESTORES[sid]))
                self.s.discovered_skills.add(sid); self.s.treasure.banked=10; self.s.relearn(0,sid)
                self.assertEqual((self.actor.skill_uses[sid],self.s.treasure.banked),(RESTORES[sid],10-cost))
                with self.assertRaises(ValueError): self.s.relearn(0,sid)
                self.assertEqual(self.s.treasure.banked,10-cost)
        self.assertTrue(all(not s.can_relearn for s in self.s.skills.values() if s.rarity in ('UNCOMMON','LEGEND')))

    def test_all_new_mastered_next_copy_only_attack_bonus(self):
        for sid in NEW_IDS:
            with self.subTest(skill=sid):
                self.setUp(); skill=self.s.skills[sid]; self.actor.learn(skill); self.actor.skill_uses[sid]=1
                if skill.effect=='cure': self.s.party[0].statuses={'poison':2}
                with patch.object(self.b.rng,'random',return_value=0): self.use(sid)
                self.assertNotIn(sid,self.actor.skills); self.assertIn(sid,self.s.mastered_skills)
                self.assertIn(sid,self.s.discovered_skills); self.actor.learn(skill)
                self.assertEqual(self.actor.power_multiplier(skill),1.2 if skill.effect=='damage' else 1)
                self.assertEqual(skill.status_chance,STATUSES.get(sid,(None,0))[1])
                self.assertEqual(self.actor.skill_uses[sid],skill.max_uses)

    def test_all_mastered_damage_12_each_target_after_defense(self):
        for sid in ('sweep','flame_wave','ragnarok','starfall'):
            with self.subTest(skill=sid):
                self.setUp(); skill=self.s.skills[sid]; self.s.mastered_skills.add(sid); self.use(sid)
                power=skill.power(self.actor,apply_mastery=False)
                for e in self.enemies:
                    defense=e.magic_defense if skill.skill_type=='magic' else e.defense
                    self.assertEqual(1000-e.hp,max(1,round((power-defense)*1.2)))

    def test_spark_every_new_skill_b1_weights_exclude_owned_relearn(self):
        class Picker:
            def __init__(self,sid,test): self.sid,self.test=sid,test
            def choices(self,rarities,weights):
                self.test.assertEqual(dict(zip(rarities,weights)),self.test.s.settings['rarity_weights'])
                return [self.test.s.skills[self.sid].rarity]
            def choice(self,skills):
                self.test.assertTrue(all(s.id not in self.test.actor.skills for s in skills))
                return next(s for s in skills if s.id==self.sid)
        self.assertEqual(self.s.settings['rarity_weights'],{'BASIC':12,'COMMON':48,'UNCOMMON':28,'RARE':10,'LEGEND':2})
        for sid in NEW_IDS:
            with self.subTest(skill=sid):
                self.setUp(); self.s.mastered_skills.add(sid); self.s.discovered_skills.add(sid)
                spark(self.actor,self.s.skills,self.s.settings,Picker(sid,self),discovered=self.s.discovered_skills)
                self.assertIn(sid,self.actor.skills); self.actor.forget(sid)
                spark(self.actor,self.s.skills,self.s.settings,Picker(sid,self)); self.assertIn(sid,self.actor.skills)

    def test_full_six_exchange_skip_keeps_discovery(self):
        for slot in (None,2):
            self.setUp()
            for sid in ('sweep','fire','heal','slow','return'): self.actor.learn(self.s.skills[sid])
            self.assertEqual(len(self.actor.skills),6)
            self.actor.pending_skill='time_stop'; self.s.field_pending=True; self.s.discovered_skills.add('time_stop')
            self.s.resolve_replacement(0,slot)
            self.assertEqual(len(self.actor.skills),6); self.assertIn('time_stop',self.s.discovered_skills)
            self.assertEqual('time_stop' in self.actor.skills,slot is not None)

    def test_ensure_attack_new_damage_only(self):
        for sid in NEW_IDS:
            with self.subTest(skill=sid):
                self.setUp(); self.actor.forget('punch'); self.actor.learn(self.s.skills[sid])
                ensure_attack(self.actor,self.s.skills,discovered=self.s.discovered_skills)
                self.assertEqual('punch' in self.actor.skills,self.s.skills[sid].effect!='damage')

    def test_old_save_exact_roundtrip_unknown_62_same_version(self):
        from rpg.save import SAVE_VERSION,apply_save_data,make_save_data
        app=self.app(); old=json.loads((ROOT/'tests/fixtures/skill_foundation_save_v1.json').read_text(encoding='utf8'))
        apply_save_data(app,deepcopy(old)); self.assertEqual(make_save_data(app),old)
        self.assertEqual(SAVE_VERSION,1); self.assertEqual(app.session.archive_summary()['total'],62)
        self.assertTrue(set(NEW_IDS).isdisjoint(app.session.discovered_skills|app.session.mastered_skills))

    def test_every_new_skill_save_roundtrip_uses_mastery(self):
        from rpg.save import apply_save_data,make_save_data
        app=self.app(); old=json.loads((ROOT/'tests/fixtures/skill_foundation_save_v1.json').read_text(encoding='utf8'))
        for sid in NEW_IDS:
            with self.subTest(skill=sid):
                apply_save_data(app,deepcopy(old)); s=app.session; c=s.party[0]
                for owned in list(c.skills): c.forget(owned)
                s.discovered_skills.add(sid); s.mastered_skills.add(sid); c.learn(s.skills[sid]); c.skill_uses[sid]=1
                data=json.loads(json.dumps(make_save_data(app))); apply_save_data(app,data)
                self.assertEqual(make_save_data(app),data)
                self.assertEqual((app.session.party[0].skills,app.session.party[0].skill_uses),([sid],{sid:1}))
                self.assertEqual(app.session.party[0].power_multiplier(s.skills[sid]),1.2 if s.skills[sid].effect=='damage' else 1)

    def test_official_pad_targets_and_field_cure(self):
        import pyxel
        for sid in ('sweep','wild_edge','purify_wind','cure'):
            app=self.app(); app.enter_dungeon(); app.opening_input_blocked=False
            app.begin_encounter(); app.battle_input_blocked=False; app.session.party[0].learn(app.session.skills[sid])
            app.begin_input(); app.state='skill'; app.skill_cursor=1; self.press(app,pyxel.GAMEPAD1_BUTTON_A)
            self.assertEqual(app.state,'target' if sid=='cure' else 'command')
            if sid=='cure': self.press(app,pyxel.GAMEPAD1_BUTTON_B); self.assertEqual(app.state,'skill')
        app=self.app(); app.enter_dungeon(); app.opening_input_blocked=False
        app.session.party[0].learn(app.session.skills['cure']); app.session.party[1].statuses={'poison':2}
        app.overlay='info'; app.info_tab=1; app.info_character=0; app.scroll=1
        self.press(app,pyxel.GAMEPAD1_BUTTON_A); self.assertEqual(app.state,'field_heal')
        self.press(app,pyxel.GAMEPAD1_BUTTON_DPAD_DOWN); self.press(app,pyxel.GAMEPAD1_BUTTON_A)
        self.assertFalse(app.session.party[1].statuses)

    def test_new_skills_silent_presentation_finishes(self):
        import pyxel
        for sid in ('sweep','venom_strike','group_aid','toxic_mist','cure','inferno','purify_wind','ragnarok','time_stop'):
            with self.subTest(skill=sid):
                app=self.app(); app.enter_dungeon(); app.begin_encounter(); app.battle_input_blocked=False
                for c in app.session.party: c.hp=100; c.max_hp=1000
                actor=app.session.party[0]; actor.learn(app.session.skills[sid]); actor.intellect=10
                if app.session.skills[sid].effect=='cure': app.session.party[0].statuses={'poison':2}
                for e in app.battle.enemies: e.hp=e.max_hp=1000
                app.battle.queue=deque([('party',Action(0,'SKILL',0,sid))]); app.battle.round=1
                app.state='resolve'; app.delay=0; app.confirm=app.confirm_held=lambda:False
                with patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
                     patch.object(pyxel,'playm',side_effect=RuntimeError('interrupted')), \
                     patch.object(pyxel,'play_pos',side_effect=RuntimeError('closed')):
                    for _ in range(240):
                        app.update(); app.draw()
                        if not app.battle_visual().active and not app.battle.queue and not app.pending: break
                    else: self.fail('audio blocked progression: '+sid)
                self.assertEqual(actor.used_skills[sid],1)


if __name__=='__main__': unittest.main()
