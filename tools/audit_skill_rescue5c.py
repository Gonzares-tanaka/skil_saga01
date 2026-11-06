"""Compare old/new rescue on the unchanged 5A character model; no game writes."""
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.audit_skill_balance5b1 import models
from rpg.battle import Battle
from rpg.content import load_content
from rpg.models import Enemy
from rpg.skill_resources import RESCUE_SKILLS


def damage(actor,enemy,skill,mastered,cap):
    c,e=deepcopy(actor),deepcopy(enemy)
    c.mastered_copies={skill.id} if mastered else set()
    if not cap:e.hp=e.max_hp=100000
    b=Battle([c],[e],{skill.id:skill},rng=random.Random(5111))
    b.elysion_barrier_active=False
    hp=e.hp;b._skill_target_effect(c,skill,e)
    d=hp-e.hp
    defense=enemy.magic_defense if skill.skill_type=='magic' else enemy.defense
    expected=max(1,round(max(1,skill.power(c,apply_mastery=False)-defense)*(1.2 if mastered else 1)))
    if cap:expected=min(enemy.max_hp,expected)
    assert d==expected,(skill.id,actor.party_id,d,expected)
    return d


def main():
    _,skills,_,rows=load_content()
    data={r['id']:r for r in rows}
    enemies=[]
    for sid,scale in (('slime',.9),('iron_golem',1),('ghost',1.45),('lord_of_elysion',1)):
        row=data[sid];enemies.append(Enemy.from_definition(row,max_hp=round(row['max_hp']*scale)))
    records=[]
    stages=models()
    for stage,n,party in stages:
        for c in party:
            for e in enemies:
                r=dict(stage=stage,wins=n,name=c.name,party_id=c.party_id,
                    stats=[c.strength,c.agility,c.intellect],enemy=e.name,enemy_id=e.id,
                    hp=e.max_hp,defense=e.defense,magic_defense=e.magic_defense)
                for version,sid in (('before','punch'),('after',RESCUE_SKILLS[c.party_id][0])):
                    skill=skills[sid]
                    normal=damage(c,e,skill,False,False)
                    mastered=damage(c,e,skill,True,False)
                    remaining=e.max_hp-normal*skill.max_uses
                    chain_hits=(math.ceil(e.max_hp/normal) if remaining<=0
                                else skill.max_uses+math.ceil(remaining/mastered))
                    r[version]=dict(id=sid,name=skill.name,uses=skill.max_uses,cd=skill.cooldown,
                        normal=normal,mastered=mastered,
                        capped_normal=damage(c,e,skill,False,True),
                        capped_mastered=damage(c,e,skill,True,True),
                        normal_total=normal*skill.max_uses,mastered_total=mastered*skill.max_uses,
                        normal_hits=math.ceil(e.max_hp/normal),mastered_hits=math.ceil(e.max_hp/mastered),
                        chain_hits=chain_hits,chain_copies=math.ceil(chain_hits/skill.max_uses))
                r['normal_change_percent']=(r['after']['normal']/r['before']['normal']-1)*100
                records.append(r)
    output=dict(seed=5111,rows=records,actual_damage_probes=len(records)*8,
        party_model=[dict(stage=stage,wins=n,name=c.name,strength=c.strength,
            agility=c.agility,intellect=c.intellect) for stage,n,party in stages for c in party])
    (ROOT/'verification/skill_rescue5c_comparison.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# PHASE 5C 救済技の変更前後比較','',
        'PHASE 5Aと同じ初期値/20勝/50勝の統制モデル。毎勝利で初期技3回分の成長寄与を固定した期待値を丸めたもので、実セーブ・実測到達能力ではない。新救済を使い続けた場合の成長予測ではない。',
        '序盤B1スライム（HP倍率0.9）、中盤B6アイアンゴーレム（1.0）、終盤B14ゴースト（1.45）、ロードオブエリシオン（1.0・障壁解除後）。敵数値は今回受領した現行データ。',
        '全段階×4人×4敵=48行。変更前/後×通常/M×HP制限あり/なし=384回、実エンジン処理と式を照合。固定seed5111（技ダメージに威力乱数はない）。',
        '', '|段階|人物|STR|AGI|INT|','|---|---|---:|---:|---:|']
    for c in output['party_model']:lines.append(f"|{c['stage']}|{c['name']}|{c['strength']}|{c['agility']}|{c['intellect']}|")
    lines+=['', '## 読み方','',
        '- 全セルは従来のパンチ → 新救済（ロウ/カイ/セン=火花、ミオ=パンチ）。Mは既習熟コピー。',
        '- 通常/MダメージはDEF/MDEF適用後で、敵HP上限だけを外した値。実HP列は敵HPで切り詰めた実際の減少量。',
        '- 総量は1コピーの初期Usesを使い切る場合。同条件の新しい敵を毎回攻撃する仮定で、敵1体のHPを超えて削れる意味ではない。',
        '- 必要回数N/Mはそれぞれ同じ威力のまま単独で倒す仮定のceil(HP/ダメージ)。N継続は初コピーを未習熟で使用し、使い切った後はMの新コピーとなる仕様まで反映。',
        '- 敵の攻撃、味方3人、回復、状態異常、ターン上限、逃走は含めない。多くの終盤条件は1コピーで倒せず、救済は勝利保証にならない。',
        '- 物理パンチはDEF、魔法火花はMDEFを参照するため、適性が低くても高DEF/低MDEFの敵では火花が有利になる場合がある。性能は補正しない。','']
    for stage,_,_ in stages:
        lines += [f'## {stage}', '',
            '|人物|敵 HP/DEF/MDEF|新技|Uses|CD|通常|M|通常増減%|実HP N|実HP M|総量N|総量M|必要回数N|必要回数M|N継続回数|N継続コピー数|',
            '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for r in records:
            if r['stage']!=stage:continue
            def pair(key):return f"{r['before'][key]} → {r['after'][key]}"
            lines.append('|'+ '|'.join([r['name'],f"{r['enemy']} {r['hp']}/{r['defense']}/{r['magic_defense']}",r['after']['name'],
                *[pair(k) for k in ('uses','cd','normal','mastered')],f"{r['normal_change_percent']:+.2f}",
                *[pair(k) for k in ('capped_normal','capped_mastered','normal_total','mastered_total','normal_hits','mastered_hits','chain_hits','chain_copies')]])+'|')
        lines.append('')
    (ROOT/'verification/SKILL_RESCUE_5C_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('PASS: 48 rows, 384 real damage/analytical matches')
    for r in records:
        if r['stage']=='終盤' and r['enemy_id'] in ('ghost','lord_of_elysion'):
            print(r['name'],r['enemy'],'normal',r['before']['normal'],'->',r['after']['normal'],
                'M',r['before']['mastered'],'->',r['after']['mastered'],'hits',r['after']['normal_hits'])


if __name__=='__main__':main()
