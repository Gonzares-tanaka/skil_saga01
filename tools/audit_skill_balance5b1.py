"""Read-only deterministic 5A-model comparisons; write verification reports only."""
from copy import deepcopy
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rpg.battle import Battle
from rpg.content import load_content
from rpg.growth import growth_bonus
from rpg.models import Enemy, Skill

IDS = ('punch','power_strike','double_slash','triple_slash',
       'quick_hit','wild_edge','rapid_edge','seven_slash')
STAGES = (('序盤',0),('中盤',20),('終盤',50))


def models():
    settings,skills,party,enemies = load_content()
    answer = []
    for stage,n in STAGES:
        chars = []
        for original,sid in zip(party,('punch','quick_hit','spark','punch')):
            c = deepcopy(original)
            c.growth_points = {stat:3*v for stat,v in skills[sid].growth.items()}
            c.category_uses = {skills[sid].skill_type:3}
            rates = settings['growth_rates'][c.growth_type]
            for stat,attr in (('STR','strength'),('AGI','agility'),('INT','intellect')):
                setattr(c,attr,round(getattr(original,attr)+n*min(1,rates[stat]+growth_bonus(c,stat,settings))))
            hp_gain = sum(settings['hp_gain'])/2
            c.max_hp = round(original.max_hp+n*min(1,rates['HP']+growth_bonus(c,'HP',settings))*hp_gain)
            c.recover()
            chars.append(c)
        answer.append((stage,n,chars))
    return answer


def main():
    settings,current,_,rows = load_content()
    old = {r['id']:Skill(**r) for r in json.loads(
        (ROOT/'tests/fixtures/skill_balance5b1_before.json').read_text(encoding='utf8'))['skills']}
    definitions = {r['id']:r for r in rows}
    enemies = []
    for sid,scale,label in (('slime',.9,'低DEF B1'),('iron_golem',1,'高DEF B6'),
                           ('ghost',1.45,'終盤通常 B14'),('lord_of_elysion',1,'最終ボス・障壁解除後')):
        row = definitions[sid]
        e = Enemy.from_definition(row,max_hp=max(1,round(row['max_hp']*scale)))
        enemies.append((label,e))
    records,probes = [],0
    stages = models()
    for stage,n,chars in stages:
        for c in chars:
            for label,enemy in enemies:
                for sid in IDS:
                    record = dict(stage=stage,wins=n,character=c.name,stats=[c.strength,c.agility,c.intellect],
                        enemy_id=enemy.id,enemy=enemy.name,enemy_hp=enemy.max_hp,defense=enemy.defense,
                        skill_id=sid,skill=current[sid].name,uses=current[sid].max_uses,cd=current[sid].cooldown)
                    for version,skill in (('before',old[sid]),('after',current[sid])):
                        for mastered in (False,True):
                            actor = deepcopy(c)
                            actor.mastered_skills = {sid} if mastered else set()
                            actor.mastered_copies = {sid} if mastered else set()
                            target = deepcopy(enemy)
                            target.hp = target.max_hp = 100000
                            battle = Battle([actor], [target], {sid:skill},rng=random.Random(501))
                            battle.elysion_barrier_active = False
                            battle._skill_target_effect(actor,skill,target)
                            raw = 100000-target.hp
                            analytical = max(1,round(max(1,round(max(1,
                                skill.power(actor,apply_mastery=False)-enemy.defense)))*(1.2 if mastered else 1)))
                            assert raw==analytical,(record,raw,analytical)
                            # Second call uses the real enemy HP to expose overkill caps.
                            target = deepcopy(enemy)
                            battle.enemies = [target]
                            battle._skill_target_effect(actor,skill,target)
                            capped = enemy.max_hp-target.hp
                            assert capped==min(enemy.max_hp,raw)
                            probes += 2
                            key = version+('_mastered' if mastered else '_normal')
                            record[key] = dict(raw=raw,capped=capped,uses_total=raw*skill.max_uses,
                                capped_uses_total=capped*skill.max_uses,
                                cd_sustained=raw/(skill.cooldown+1),
                                finite8_total=raw*min(skill.max_uses,1+7//(skill.cooldown+1)),
                                finite20_total=raw*min(skill.max_uses,1+19//(skill.cooldown+1)))
                    for mode in ('normal','mastered'):
                        a,b=record['before_'+mode]['raw'],record['after_'+mode]['raw']
                        record['change_'+mode+'_percent']=(b/a-1)*100
                    records.append(record)
    data = dict(records=records,real_damage_probes=probes,
        analytical_matches=probes//2,seed=501,
        characters=[dict(stage=stage,wins=n,name=c.name,hp=c.max_hp,
            strength=c.strength,agility=c.agility,intellect=c.intellect)
            for stage,n,chars in stages for c in chars])
    (ROOT/'verification/skill_balance5b1_comparison.json').write_text(
        json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# PHASE 5B-1 全条件ダメージ比較','',
        'PHASE 5Aと同じ統制モデル。序盤=初期値、中盤=20勝、終盤=50勝。各勝利で初期技を3回使用した育成寄与を固定した期待値を丸めたもの。実セーブ・実測到達能力ではない。',
        '全段階×4人×4敵×8技=384行、通常/M・変更前/後=1,536組、実ダメージ処理3,072回。乱数シード501（対象技のダメージ自体は決定的）。',
        '敵は実データ。B1スライムHP倍率0.9、B6アイアンゴーレム1.0、B14ゴースト1.45、LORD OF ELYSION1.0。DEFは倍率なし。状態異常・強化・防御なし、最終ボス障壁なし。',
        '', '## 能力値モデル','', '|段階|人物|HP|STR|AGI|INT|','|---|---|---:|---:|---:|---:|']
    for c in data['characters']:
        lines.append(f"|{c['stage']}|{c['name']}|{c['hp']}|{c['strength']}|{c['agility']}|{c['intellect']}|")
    lines += ['', '## 読み方','',
        '- 各セルは変更前 → 変更後。MはMASTERED再取得したコピー。増減率はHP上限なしの実ダメージから算出。',
        '- 通常/Mの未切詰ダメージはDEF・習熟補正後で、敵のHP上限のみ外した値。実HP列は敵HPで上限処理した値。',
        '- 総量=未切詰ダメージ×初期Uses。毎回同条件の新しい対象へ当てる想定。単一の敵のHPを超えて削れるという意味ではない。',
        '- CD持続=1回ダメージ/(CD+1)。他の行動・他の技でCD間を埋めた分は含めない。Uses無限の理論値であり、1ターンあたりのこの技の寄与。',
        '- 8T/20T=1T目使用、CD中はGUARD、Usesを補充しない場合の累計通常ダメージ。有限回数の継続能力を別に評価。',
        '- 非変更4技も同じ式・同じ実処理で検証。MASTEREDはDEF適用後x1.2、Python round。プレビューの「威力」はDEF控除前でダメージとは異なる。', '']
    for stage,n,_ in stages:
        for label,enemy in enemies:
            lines += [f'## {stage} / {label} {enemy.name} HP{enemy.max_hp} DEF{enemy.defense}', '',
                '|人物|技|Uses/CD|通常|M|通常増減%|M増減%|実HP 通常|実HP M|総量 通常|総量 M|CD持続 通常|CD持続 M|8T通常累計|20T通常累計|',
                '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
            for r in records:
                if r['stage']!=stage or r['enemy_id']!=enemy.id: continue
                def pair(mode,key,precision=None):
                    vals=[r[v+'_'+mode][key] for v in ('before','after')]
                    if precision is not None: vals=[f'{v:.{precision}f}' for v in vals]
                    return ' → '.join(map(str,vals))
                lines.append('|'+ '|'.join([r['character'],r['skill'],f"{r['uses']}/{r['cd']}",
                    pair('normal','raw'),pair('mastered','raw'),f"{r['change_normal_percent']:+.2f}",f"{r['change_mastered_percent']:+.2f}",
                    pair('normal','capped'),pair('mastered','capped'),pair('normal','uses_total'),pair('mastered','uses_total'),
                    pair('normal','cd_sustained',2),pair('mastered','cd_sustained',2),
                    pair('normal','finite8_total'),pair('normal','finite20_total')])+'|')
            lines.append('')
    (ROOT/'verification/SKILL_BALANCE_5B1_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('PASS: 384 rows / 1536 analytical matches /',probes,'real damage probes')
    for r in records:
        if r['stage']=='終盤' and r['character']==stages[-1][2][1].name and r['enemy_id']=='lord_of_elysion':
            print(r['skill_id'],r['before_normal']['raw'],'->',r['after_normal']['raw'],
                  'M',r['before_mastered']['raw'],'->',r['after_mastered']['raw'])


if __name__=='__main__': main()
