"""Reproducible support comparisons using actual round resolution, not new rules."""
from copy import deepcopy
from dataclasses import replace
import itertools
import json
from pathlib import Path
import random
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rpg.battle import Battle
from rpg.content import load_content
from rpg.models import Action, Enemy, Skill

BEFORE = ROOT/'tests/fixtures/skill_balance5b2_before.json'

def definitions():
    _, skills, party, enemies = load_content()
    old = {row['id']: Skill(**row) for row in json.loads(BEFORE.read_text(encoding='utf8'))['skills']}
    return skills, old, party, enemies

def ready(party, skills, ids):
    party = deepcopy(party)
    for c in party:
        for sid in list(c.skills): c.forget(sid)
        c.mastered_skills.clear()
        c.hp = c.max_hp = 100000
        c.strength = c.intellect = 20
        c.agility = 20
        for sid in ids: c.learn(skills[sid])
    return party

def resolve(battle, actions):
    battle.begin_round(actions)
    order = list(battle.queue)
    while battle.queue: battle.step()
    return order

def offense(sid, variant, defense, turns, timing, attack=None):
    skills, old, party, _ = definitions()
    attack = attack or ('punch' if sid == 'power_up' else 'spark')
    if variant == 'old': skills[sid] = old[sid]
    party = ready(party[:2] if timing != 'self' else party[:1], skills, (sid, attack))
    caster, attacker = party[0], party[-1]
    caster.agility = 30 if timing != 'ally_late' else 10
    enemy = Enemy('DEF probe',100000,1,1,1,(0,0),defense=defense,magic_defense=defense)
    b = Battle(party,[enemy],skills,rng=random.Random(5110))
    orders=[]
    with patch.object(b, '_enemy_action', return_value=[]):
        for turn in range(turns):
            actions = [Action(i,'SKILL',0,attack) for i in range(len(party))]
            if variant != 'none' and turn == 0:
                actions[0] = Action(0,'SKILL',len(party)-1,sid)
            orders.append(resolve(b,actions))
    return 100000-enemy.hp, orders

def defense(enemy_row, variant, turns, timing, guard, action_id):
    skills, old, party, _ = definitions()
    sid = 'iron_wall' if variant == 'iron' else 'sanctuary'
    if variant == 'old': skills[sid] = old[sid]
    party = ready(party,skills,('punch',sid))
    party[0].agility = enemy_row['agi']+100 if timing == 'early' else 0
    enemy = Enemy.from_definition(enemy_row)
    enemy.hp = enemy.max_hp = 100000
    b = Battle(party,[enemy],skills,rng=random.Random(5110),boss=True)
    b.elysion_barrier_active = False
    # Forced repeated attack profile preserves each boss's stats, power/hits and
    # actions/round. This isolates mitigation; it is not its natural AI rotation.
    with patch('rpg.battle.choose_enemy_action', return_value=action_id):
        for turn in range(turns):
            actions = [Action(i,'GUARD') if guard and (i or turn) else Action(i,'SKILL',0,'punch')
                       for i in range(4)]
            if variant != 'none' and turn == 0: actions[0] = Action(0,'SKILL',0,sid)
            resolve(b,actions)
    return sum(100000-c.hp for c in party)

def main():
    skills, old, party, enemies = definitions()
    offense_rows=[]
    for sid, df, timing, turns in itertools.product(('power_up','focus'),(0,16),('self','ally_early','ally_late'),(2,3,4,5)):
        values=[offense(sid,v,df,turns,timing)[0] for v in ('none','old','new')]
        offense_rows.append(dict(skill=sid,defense=df,timing=timing,turns=turns,
                                 none=values[0],old=values[1],new=values[2]))
    boss_ids = ('guardian','skill_keeper','sentinel_armor','sentinel_speed','sentinel_mind','depth_lord','lord_of_elysion')
    # Boss IDs are checked against data rather than inferred from display names.
    bosses=[r for r in enemies if r['id'] in boss_ids]
    assert len(bosses)==7, [r['id'] for r in bosses]
    generic=dict(enemies[0],id='controlled40',name='統制STR/INT40',str=40,int=40,agi=20,ai={})
    defense_rows=[]
    for row, action, timing, guard, turns in itertools.product([generic,*bosses],('attack','magic','area_attack','area_magic'),('early','late'),(False,True),(2,3,4,5)):
        values=[defense(row,v,turns,timing,guard,action) for v in ('none','iron','old','new')]
        assert values[3] <= values[2] and values[3] <= values[1], (row['id'],action,timing,guard,turns,values)
        defense_rows.append(dict(enemy=row['id'],name=row['name'],action=action,timing=timing,guard=guard,
                                 turns=turns,none=values[0],iron=values[1],old=values[2],new=values[3]))
    focus_rows=[]
    for sid in ('fire','meteor','first_aid','renew','miracle'):
        c=deepcopy(party[0]); c.intellect=20
        base=skills[sid].power(c)
        c.effects['focus']=(1.5,4)
        focused=skills[sid].power(c)
        assert focused==round(20*1.5*skills[sid].int_scale*skills[sid].hits)
        focus_rows.append(dict(skill=sid,base=base,focused=focused))
    report=dict(seed=5110,offense=offense_rows,defense=defense_rows,focus=focus_rows)
    (ROOT/'verification/skill_balance5b2_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# PHASE 5B-2 補助スキル比較表','',
           'seed5110、実際のbegin_round/stepで解決。強化は初回1回のみ、MASTEREDなし、HP打切りなし。',
           '攻撃：STR/INT20、物理punch / 魔法spark（CD0）。selfは1人、allyは2人の合計与ダメージ。',
           'ally_early/lateは強化対象より先/後に付与。無補助では同じ人数が毎回攻撃し、補助の1行動分を含めて比較する。',
           '防御：味方4人、HP各100000。敵能力・攻撃倍率・HIT・行動回数は実データ。指定攻撃を毎回固定する統制負荷試験で、自然AIによる実戦勝率の測定ではない。',
           'early/lateは使用者が敵より先/後。GUARDありは使用者以外が初手から、使用者は2手目から防御（使用と防御を同時に行わない）。',
           'B15は3守護者を個別掲載。LORDはアムリタで障壁解除後。全列は合計HP被害、小さいほど強い。',
           '使用ラウンド込みの減算、端数丸め、行動順決定、GUARD係数は現行エンジンそのまま。敵の能力を補正して調整を相殺する変更はない。','',
           '## 攻撃比較','','|技|DEF|付与順|T|直接攻撃のみ|旧|新|旧→新増分|','|---|---:|---|---:|---:|---:|---:|---:|']
    for r in offense_rows:
        lines.append(f"|{r['skill']}|{r['defense']}|{r['timing']}|{r['turns']}|{r['none']}|{r['old']}|{r['new']}|{r['new']-r['old']}|")
    lines += ['', '## 集中時の単発威力・回復（INT20、DEF前、回復は1人あたり）','',
              '|技|通常|集中中|','|---|---:|---:|']
    for r in focus_rows: lines.append(f"|{r['skill']}|{r['base']}|{r['focused']}|")
    lines += ['', '## 防御全条件','', '|敵|攻撃|順|GUARD|T|補助なし|鉄壁陣|旧聖域|新聖域|新の軽減量|新の軽減率|',
              '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in defense_rows:
        lines.append(f"|{r['name']}|{r['action']}|{r['timing']}|{'有' if r['guard'] else '無'}|{r['turns']}|{r['none']}|{r['iron']}|{r['old']}|{r['new']}|{r['none']-r['new']}|{100*(1-r['new']/r['none']):.1f}%|")
    (ROOT/'verification/SKILL_BALANCE_5B2_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(f'PASS: {len(offense_rows)} offense + {len(defense_rows)} defense rows, five focus probes')

if __name__ == '__main__': main()
