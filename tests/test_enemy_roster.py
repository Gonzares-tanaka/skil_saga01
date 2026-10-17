"""Roster expansion, real shared status actions, encounter and saved-hunt contracts."""
from collections import deque, Counter
from copy import deepcopy
import json
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pyxel
from rpg.art import load_art
from rpg.battle import Battle, Session
from rpg.content import load_content, ROOT
from rpg.dungeon import Dungeon, load_dungeon_settings
from rpg.enemy_actions import choose_enemy_action, load_enemy_actions
from rpg.exploration import Exploration
from rpg.map_resources import load_maps
from rpg.models import Action, Enemy
from rpg.quests import spawn_candidates
from rpg.save import apply_save_data, make_save_data, SAVE_VERSION
from rpg.statuses import clear_statuses

NEW = {
    'horn_rabbit': ((29,6,0,15,2,0),(208,16), {'attack':90,'double_attack':10}),
    'poison_snake': ((70,14,2,17,4,2),(128,16), {'attack':75,'poison_bite':25}),
    'blood_bat': ((63,16,1,24,5,2),(16,16), {'attack':75,'double_attack':25}),
    'ghost': ((73,8,4,16,22,12),(176,16), {'attack':20,'magic':60,'confusion_touch':20}),
    'mummy': ((105,19,8,6,10,8),(224,16), {'attack':65,'heavy_attack':15,'paralyze_grab':20}),
    'dark_wisp': ((74,6,3,18,26,12),(48,16), {'magic':65,'area_magic':20,'sleep_spell':15}),
    'warlock': ((84,8,5,14,29,10),(96,16), {'magic':45,'power_up':15,'weaken':15,'armor_break':10,'slow':10,'sleep_spell':5}),
}
TABLES = [
    {'slime':6,'bat':3,'goblin':1},
    {'slime':2,'bat':2,'goblin':4,'wisp':2,'horn_rabbit':1},
    {'goblin':2,'wisp':2,'skeleton':3,'mage':2,'horn_rabbit':2},
    {'golem':5,'skeleton':3,'mage':4,'wisp':1},
    None,
    {'iron_golem':4,'skeleton':2,'mage':2,'poison_snake':2},
    {'berserker':4,'iron_golem':3,'wisp':1,'poison_snake':2,'blood_bat':2},
    {'assassin':4,'stone_beast':3,'mage':2,'blood_bat':2},
    {'iron_golem':2,'berserker':2,'assassin':2,'stone_beast':2,'poison_snake':2,'blood_bat':2,'ghost':1},
    None,
    {'iron_golem':3,'berserker':3,'mage':2,'ghost':2,'dark_wisp':2},
    {'assassin':3,'stone_beast':3,'mage':2,'ghost':2,'mummy':2},
    {'stone_beast':3,'berserker':3,'iron_golem':2,'mummy':3,'dark_wisp':2,'warlock':1},
    {'assassin':3,'berserker':2,'stone_beast':2,'ghost':2,'mummy':2,'dark_wisp':2,'warlock':2},
]
TABLES[4] = TABLES[3]
TABLES[9] = TABLES[8]
STATUS_ACTIONS = {'poison_bite':('poison',45,'physical_single',.90),
                  'confusion_touch':('confusion',35,'magic_single',.85),
                  'paralyze_grab':('paralyze',35,'physical_single',.85),
                  'sleep_spell':('sleep',45,'status',1)}


def hunt_on(app, floor, ident):
    e, d = app.exploration, app.dungeon
    e.active = None
    d.defeated_bosses.update((4,9))
    q = e.make_quest((floor-1)//5+1, quest_type='hunt')
    source = floor-1 if 'enemy_ids' in d.settings['floors'][floor-1] else floor-2
    q.update(target_floor=floor, points=[list(spawn_candidates(d,floor-1)[0])],
             hunt_source_floor=source+1, hunt_enemy_id=ident)
    e.activate_quest(q)
    d.floor = floor-1
    d.x, d.y = q['points'][0]
    return q


class EnemyRosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(pyxel, '_tests_initialized', False):
            pyxel.init(160,120,headless=True); pyxel._tests_initialized = True

    def setUp(self):
        load_art(pyxel)
        self.content = load_content()
        self.s = Session(*deepcopy(self.content), seed=817)
        self.d = Dungeon(load_maps(),self.s.enemy_data,load_dungeon_settings(),self.s.rng,
                         self.s.treasure,self.s.inventory)
        self.e = Exploration(self.s,self.d)
        self.app = SimpleNamespace(session=self.s,dungeon=self.d,exploration=self.e,
                                   initial_content=self.content,hub_intro_shown=True)
        self.rows = self.d.enemies
        self.defs = load_enemy_actions()

    def battle(self, ident, action):
        enemy = Enemy.from_definition(self.rows[ident], max_hp=10000)
        enemy.actions = [{'id':action,'weight':1}]
        for c in self.s.party:
            c.hp=c.max_hp=1000; c.statuses.clear(); c.effects.clear()
        return Battle(self.s.party,[enemy],self.s.skills,rng=self.s.rng,inventory=self.s.inventory)

    def turn(self,b,side='enemy',action=None, success=True):
        b.turn_plan=None
        b.queue=deque([(side,0 if side=='enemy' else (action or Action(0,'GUARD')))])
        with patch.object(b.rng,'choice',return_value=b.party[0]), \
             patch.object(b.rng,'random',return_value=0 if success else .999), \
             patch.object(b.rng,'uniform',return_value=1):
            return b.step()

    def test_exact_new_stats_ids_names_sprites_and_weights(self):
        self.assertEqual(len(self.rows),25)
        self.assertEqual(sum(not r.get('boss') for r in self.rows.values()),18)
        self.assertEqual(sum(bool(r.get('boss')) for r in self.rows.values()),7)
        for ident,(stats,sprite,weights) in NEW.items():
            row=self.rows[ident]; enemy=Enemy.from_definition(row)
            self.assertEqual(enemy.id,ident)
            self.assertEqual((enemy.max_hp,enemy.strength,enemy.defense,enemy.agility,enemy.intellect,enemy.magic_defense),stats)
            self.assertEqual(enemy.sprite,sprite)
            self.assertEqual({a['id']:a['weight'] for a in enemy.actions},weights)
            self.assertTrue(any(pyxel.images[0].pget(x,y) for x in range(sprite[0],sprite[0]+16) for y in range(16,32)))
            renamed=deepcopy(row); renamed['name']='renamed'
            self.assertEqual(Enemy.from_definition(renamed).id,ident)
            self.assertEqual(Enemy.from_definition(renamed).actions,enemy.actions)

    def test_all_floor_tables_and_area_restrictions(self):
        for floor,expected in enumerate(TABLES):
            row=self.d.settings['floors'][floor]
            if 'enemy_ids' not in row: row=self.d.settings['floors'][floor-1]
            self.assertEqual(len(row['enemy_ids']),len(row['weights']))
            self.assertEqual(dict(zip(row['enemy_ids'],row['weights'])),expected)
            self.assertTrue(all(w>0 for w in row['weights']))
            for ident in expected:
                for a in self.rows[ident]['actions']:
                    status=self.defs[a['id']].status_id
                    if floor<5: self.assertFalse(status)
                    if floor<10: self.assertNotIn(status,('sleep','paralyze'))
                    if floor<8: self.assertNotEqual(status,'confusion')
        self.assertNotIn('enemy_ids',self.d.settings['floors'][14])
        self.assertEqual(self.rows['sentinel_mind']['sprite'],[160,16])
        self.assertTrue(all(r.get('boss') or r['sprite']!=[160,16] for r in self.rows.values()))

    def test_encounter_sampling_all_candidates_and_scaling(self):
        for floor,expected in enumerate(TABLES):
            self.d.floor=floor; counts=Counter()
            profile=self.d.settings['floors'][floor if floor not in (4,9) else floor-1]
            for _ in range(400):
                for enemy in self.d.make_enemies():
                    counts[enemy.id]+=1; row=self.rows[enemy.id]
                    self.assertEqual(enemy.max_hp,max(1,round(row['max_hp']*profile['hp_scale'])))
                    self.assertEqual(enemy.strength,max(1,round(row['str']*profile['power_scale'])))
                    self.assertEqual(enemy.intellect,max(1,round(row['int']*profile['power_scale'])))
            self.assertEqual(set(counts),set(expected))

    def test_status_actions_success_failure_damage_and_no_sleep_fallback(self):
        for ident,action in (('poison_snake','poison_bite'),('ghost','confusion_touch'),
                             ('mummy','paralyze_grab'),('dark_wisp','sleep_spell'),('warlock','sleep_spell')):
            status,chance,kind,power=STATUS_ACTIONS[action]
            definition=self.defs[action]
            self.assertEqual((definition.status_id,definition.status_chance,definition.type,definition.power),
                             (status,chance,kind,power))
            for success in (False,True):
                b=self.battle(ident,action); actor=b.party[0]
                self.turn(b,success=success)
                self.assertEqual(status in actor.statuses,success)
                self.assertEqual(b.enemy_action_visual['action_id'],action)
                stat=b.enemies[0].intellect if kind.startswith('magic') else b.enemies[0].strength
                self.assertEqual(1000-actor.hp,0 if kind=='status' else round(stat*power))
                self.assertEqual(bool(b.status_visual_events),success)
                if success: self.assertEqual(b.status_visual_events[0]['target'][0],'party')
                self.assertFalse(b.queue)

    def test_real_poison_tick_expiry_and_remedy_preserves_debuffs(self):
        b=self.battle('poison_snake','poison_bite'); self.turn(b)
        hp=b.party[0].hp
        for _ in range(3): self.turn(b,'party')
        self.assertEqual(b.party[0].hp,hp-150)
        self.assertFalse(b.party[0].statuses)
        self.turn(b); b.party[0].effects={'weaken':(.85,3),'armor_break':(.85,3),'slow':(.8,3)}
        b.inventory.counts['REMEDY']=1
        self.turn(b,'party',Action(1,'ITEM',0,item_id='REMEDY'))
        self.assertFalse(b.party[0].statuses)
        self.assertEqual(b.inventory.counts['REMEDY'],0)
        self.assertEqual(set(b.party[0].effects),{'weaken','armor_break','slow'})

    def test_real_confusion_and_paralyze_never_spend_resources(self):
        for ident,action,status in (('ghost','confusion_touch','confusion'),('mummy','paralyze_grab','paralyze')):
            b=self.battle(ident,action); self.turn(b)
            actor=b.party[0]; before=deepcopy((actor.skill_uses,actor.category_uses,actor.growth_points))
            b.inventory.counts['POTION']=2
            with patch.object(b.rng,'choices',return_value=['idle']):
                self.turn(b,'party',Action(0,'SKILL',0,actor.skills[0]))
                self.turn(b,'party',Action(0,'ITEM',0,item_id='POTION'))
            self.assertEqual((actor.skill_uses,actor.category_uses,actor.growth_points),before)
            self.assertEqual(b.inventory.counts['POTION'],2)

    def test_real_sleep_damage_poison_and_remedy_wake(self):
        for wake in ('damage','poison','remedy','expiry'):
            b=self.battle('dark_wisp','sleep_spell'); self.turn(b)
            actor=b.party[0]
            before=deepcopy(actor.skill_uses)
            self.turn(b,'party',Action(0,'SKILL',0,actor.skills[0]))
            self.assertEqual(actor.skill_uses,before)
            if wake=='damage': b._damage(actor,1)
            elif wake=='poison':
                b.apply_status(actor,'poison'); self.turn(b,'party')
            elif wake=='remedy':
                b.inventory.counts['REMEDY']=1
                self.turn(b,'party',Action(1,'ITEM',0,item_id='REMEDY'))
            else: self.turn(b,'party')
            self.assertNotIn('sleep',actor.statuses)

    def test_control_exclusion_with_real_enemy_actions(self):
        b=self.battle('ghost','confusion_touch'); self.turn(b)
        enemy=b.enemies[0]
        for action in ('paralyze_grab','sleep_spell'):
            enemy.actions=[{'id':action,'weight':1}]; self.turn(b)
            self.assertEqual(set(b.party[0].statuses),{'confusion'})
        enemy.actions=[{'id':'poison_bite','weight':1}]; self.turn(b)
        self.assertEqual(set(b.party[0].statuses),{'confusion','poison'})

    def test_new_hunts_all_ids_scaling_actions_status_chance_and_save_load(self):
        floors={'horn_rabbit':2,'poison_snake':6,'blood_bat':7,'ghost':9,'mummy':12,'dark_wisp':11,'warlock':15}
        for ident,floor in floors.items():
            q=hunt_on(self.app,floor,ident); enemy,=self.e.make_hunt_enemy()
            row=self.rows[ident]; profile=self.d.settings['floors'][q['hunt_source_floor']-1]
            bonus=self.e.quest_data['hunt']
            self.assertEqual(enemy.id,ident)
            self.assertEqual(enemy.max_hp,round(row['max_hp']*profile['hp_scale']*bonus['hp_multiplier']))
            self.assertEqual(enemy.strength,round(row['str']*profile['power_scale'])+bonus['str_bonus'])
            self.assertEqual(enemy.defense,row.get('defense',0)+bonus['def_bonus'])
            self.assertEqual(enemy.actions,row['actions'])
            saved=json.loads(json.dumps(make_save_data(self.app)))
            self.assertEqual(saved['save_version'],1)
            apply_save_data(self.app,saved)
            self.s,self.d,self.e=self.app.session,self.app.dungeon,self.app.exploration
            self.assertEqual(self.e.active['hunt_enemy_id'],ident)
            self.d.floor=floor-1; self.d.x,self.d.y=self.e.active['points'][0]
            loaded,=self.e.make_hunt_enemy()
            self.assertEqual(loaded.id,ident)
            self.assertEqual(loaded.actions,enemy.actions)
            for a in loaded.actions:
                if self.defs[a['id']].status_id:
                    for actor in self.s.party:
                        actor.hp=actor.max_hp=1000; clear_statuses(actor)
                    b=Battle(self.s.party,[loaded],self.s.skills,rng=self.s.rng)
                    loaded.actions=[a]; self.turn(b)
                    self.assertEqual(b.enemy_action_visual['action_id'],a['id'])
                    self.assertIn(self.defs[a['id']].status_id,b.party[0].statuses)
                    clear_statuses(b.party[0])

    def test_old_hunt_table_members_remain_loadable_without_reroll(self):
        baseline=json.loads((ROOT/'tests/fixtures/enemy_roster_before.json').read_text(encoding='utf8'))
        oldcontent=deepcopy(self.content); oldcontent=list(oldcontent); oldcontent[3]=baseline['enemies']
        oldsession=Session(*oldcontent,seed=71)
        oldd= Dungeon(load_maps(),oldsession.enemy_data,baseline['dungeon'],oldsession.rng,
                      oldsession.treasure,oldsession.inventory)
        olde=Exploration(oldsession,oldd)
        oldapp=SimpleNamespace(session=oldsession,dungeon=oldd,exploration=olde,
                               initial_content=oldcontent,hub_intro_shown=True)
        for floor in range(1,16):
            profile=baseline['dungeon']['floors'][floor-1]
            if 'enemy_ids' not in profile: profile=baseline['dungeon']['floors'][floor-2]
            for ident in profile['enemy_ids']:
                hunt_on(oldapp,floor,ident)
                saved=make_save_data(oldapp)
                apply_save_data(self.app,json.loads(json.dumps(saved)))
                self.assertEqual(self.app.exploration.active['hunt_enemy_id'],ident)
                self.assertEqual(self.app.exploration.active['hunt_source_floor'],saved['active_quest']['hunt_source_floor'])
                self.assertEqual(SAVE_VERSION,1)

    def test_unchanged_existing_rows_actions_floor_parameters_and_source_assets(self):
        import hashlib
        baseline=json.loads((ROOT/'tests/fixtures/enemy_roster_before.json').read_text(encoding='utf8'))
        for old in baseline['enemies']:
            current = deepcopy(self.rows[old['id']])
            allowed = {'max_hp','str','int'} | ({'defense','actions','ai'} if old.get('boss') else set())
            self.assertEqual({k:v for k,v in current.items() if k not in allowed},
                             {k:v for k,v in old.items() if k not in allowed})
        raw=json.loads((ROOT/'data/enemy_actions.json').read_text(encoding='utf8'))
        for ident,old in baseline['actions'].items(): self.assertEqual(raw[ident],old)
        self.assertEqual(set(raw)-set(baseline['actions']),set(STATUS_ACTIONS))
        before,after=deepcopy(baseline['dungeon']),deepcopy(self.d.settings)
        for settings in (before,after):
            for row in settings['floors']:
                row.pop('enemy_ids',None); row.pop('weights',None)
        self.assertEqual(before,after)
        for name,digest in baseline['hashes'].items():
            from tests.test_enemy_balance import ALLOWED
            if name in ALLOWED: continue
            if name == 'game.pyxres':
                continue  # Dedicated RARE asset test preserves all old pixels/maps/audio.
            if name == 'data/statuses.json':
                # Balance pass 01 permits exactly the 35% -> 50% skip change.
                data = (ROOT/name).read_bytes()
                self.assertEqual(data.count(b'"skip_chance": 0.50'), 1)
                original = data.replace(b'"skip_chance": 0.50', b'"skip_chance": 0.35')
                self.assertEqual(hashlib.sha256(original).hexdigest(), digest, name)
                continue
            if name in ('data/enemies.json','data/enemy_actions.json','data/dungeon.json'): continue
            # Phase 1.5 intentionally changes status lifetime and its UI only.
            if name in ('rpg/statuses.py','rpg/models.py','rpg/battle.py','rpg/app.py','rpg/dungeon_app.py'): continue
            # Skill foundation intentionally extends target validation/labels/FX;
            # its own before/after checks retain every enemy, rule and asset hash.
            if name in ('rpg/content.py','rpg/labels.py','rpg/battle_presentation.py'): continue
            # The subsequent player roster appends 31 skills. Its separate
            # preservation test compares every original row and all other data.
            if name == 'data/skills.json': continue
            if name == 'rpg/sound.py': continue  # Native playm freeze investigation/fix.
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)


if __name__=='__main__': unittest.main()
