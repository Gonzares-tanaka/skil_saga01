"""One Session: B10 -> Amrita -> facilities -> five real defeats -> ENDING.

The disclosed B10 strong-party setup is inherited from verify_phase6a_ui.
Final-defeat fixtures change only party resources, never enemy rules or files.
After Amrita, all UI input is D-pad/A/B; no DEBUG progression shortcuts.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.final_battle import AMRITA_ITEM_ID, LORD_OF_ELYSION_ID
from rpg.text import FONT_HEIGHT, text_width
from rpg.tiles import TILE_ENTRANCE, FLOOR_TILES
from tools.verify_phase6a_ui import main as phase6a

A, B = pyxel.GAMEPAD1_BUTTON_A, pyxel.GAMEPAD1_BUTTON_B
DOWN, RIGHT = pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT
DIRECTIONS = {(0,-1):pyxel.GAMEPAD1_BUTTON_DPAD_UP,(0,1):DOWN,
              (-1,0):pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,(1,0):RIGHT}


def main():
    protected=list(ROOT.glob('*.pyxres'))+list(ROOT.glob('*.pyxpal'))+list((ROOT/'data').glob('*.json'))+list((ROOT/'rpg').glob('*.py'))+list((ROOT/'assets').glob('*.pyxres'))
    baseline={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    timeline, inputs, texts, failures, screenshots, facilities = [], [], [], [], [], []
    early_gates = []

    def observe(stage, app):
        f = app.dungeon.finale
        timeline.append(dict(stage=stage, state=app.state, floor=app.dungeon.floor+1,
                             total_battles=app.session.total_battles,
                             flags=f.snapshot(), barrier=(app.battle.elysion_barrier_active
                                 if app.battle and app.battle.is_elysion_battle else None)))
        if stage in ('B10_START', 'BEFORE_DEMON'):
            before = f.snapshot()
            assert not f.demon_defeated and not f.has_amrita and not f.can_offer_amrita
            for operation in (app.start_final_story, app.begin_final_battle):
                try:
                    operation()
                except ValueError:
                    pass
                else:
                    raise AssertionError('Final event accessible before demon victory')
            assert f.snapshot() == before
            early_gates.append(stage)
        if stage == 'B10_BATTLE':
            assert AMRITA_ITEM_ID not in app.battle_items() and not app.battle.can_use_amrita
        if stage == 'DEMON_VICTORY_AMRITA':
            assert f.demon_defeated and f.has_amrita
            assert AMRITA_ITEM_ID not in app.session.inventory.counts
        if stage == 'FIRST_AMRITA_OFFER':
            assert f.has_amrita and not f.final_event_started

    app, phase6a_result = phase6a(observer=observe)
    session_identity = id(app.session)
    s, d = app.session, app.dungeon
    assert app.state == 'camp' and d.finale.has_amrita and not s.debug
    output = ROOT/'verification/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    real_text = pyxel.text

    def bounded(x,y,value,color,font=None):
        assert 0 <= x and x + text_width(value) <= 160, (x,y,value)
        assert 0 <= y and y + FONT_HEIGHT <= 120, (x,y,value)
        texts.append(value)
        real_text(x,y,value,color,font)

    def press(button=None):
        assert button is None or button in (A,B,*DIRECTIONS.values())
        inputs.append(button)
        with patch.object(pyxel,'btnp',side_effect=lambda code,*args:code==button), \
             patch.object(pyxel,'btn',return_value=False):
            app.update()
        app.draw()

    def shot(name):
        app.draw()
        path = output/('final_chapter_'+name+'.png')
        pyxel.screenshot(str(path),scale=4)
        screenshots.append(str(path.relative_to(ROOT)))

    def checkpoint_state():
        return deepcopy(dict(party=[vars(c) for c in s.party], items=s.inventory.counts,
            treasure=vars(s.treasure), discovered=s.discovered_skills, mastered=s.mastered_skills,
            counts=(s.completed,s.wins,s.losses,s.draws), flags=d.finale.snapshot(),
            pending={k:getattr(s,k) for k in ('debug','debug_pending','field_pending','pending_relearn')},
            dungeon={k:getattr(d,k) for k in app.final_checkpoint.DUNGEON_FIELDS},
            exploration={k:getattr(app.exploration,k) for k in app.final_checkpoint.EXPLORATION_FIELDS},
            rng=s.rng.getstate()))

    def finish_result():
        for _ in range(600):
            if app.state not in ('result','replace'):
                return
            if app.state == 'replace':
                press(B); press(A); press(A)
            else:
                press(A)
        raise AssertionError('Results did not finish')

    def resolve():
        for _ in range(3000):
            if app.state not in ('resolve','amrita_effect','battle_transition'):
                return
            press(A)
        raise AssertionError('Resolution/effect did not finish')

    def skill(sid,target=0):
        actor=app.actor
        press(A)
        assert app.state=='skill',app.state
        for _ in range(actor.skills.index(sid)):
            press(DOWN)
        press(A)
        if app.state=='target':
            for _ in range([i for i,_ in app.targets()].index(target)):
                press(DOWN)
            press(A)

    def item(iid,target=0):
        press(RIGHT); press(A)
        assert app.state=='battle_item'
        for _ in range(app.battle_items().index(iid)):
            press(DOWN)
        press(A)
        if app.state=='target':
            for _ in range([i for i,_ in app.targets()].index(target)):
                press(DOWN)
            press(A)

    def round_with(specs=None):
        assert app.state=='command',app.state
        specs=specs or {}
        while app.state=='command':
            kind,value,target=specs.get(app.actor_index,('guard',None,0))
            if kind=='skill':
                skill(value,target)
            elif kind=='item':
                item(value,target)
            else:
                press(DOWN); press(A)
        resolve()

    def use_amrita():
        before_uses=[dict(c.skill_uses) for c in s.party]
        before_items=dict(s.inventory.counts)
        round_with({0:('item',AMRITA_ITEM_ID,0)})
        assert app.state=='command' and not app.battle.elysion_barrier_active
        assert d.finale.has_amrita and not d.finale.amrita_power_spent
        assert before_items==s.inventory.counts and before_uses==[c.skill_uses for c in s.party]
        observe('AMRITA_RELEASED',app)

    def spend_strong_skills():
        casts=0
        for sid in ('meteor','seven_slash'):
            while any(sid in c.skills for c in s.party):
                assert all(c.alive for c in s.party)
                if any(c.cooldowns.get(sid,0) for c in s.party if sid in c.skills):
                    round_with()
                    continue
                users=[i for i,c in enumerate(s.party) if sid in c.skills]
                round_with({i:('skill',sid,0) for i in users})
                casts+=len(users)
                assert app.state=='command','Boss ended before depletion fixture finished'
        assert 'meteor' in s.mastered_skills and 'seven_slash' in s.mastered_skills
        return casts

    def spend_items():
        before=dict(s.inventory.counts)
        for _ in range(7):
            s.party[0].hp=max(1,s.party[0].max_hp-90)  # Disclosed injury fixture.
            round_with({0:('item','POTION',0)})
        for _ in range(3):
            s.party[3].hp=0
            app.begin_input()  # Rebuild the living-actor order after fixture KO.
            round_with({0:('item','PHOENIX ASH',3)})
            assert s.party[3].alive
        assert s.inventory.counts['POTION']==before['POTION']-7
        assert s.inventory.counts['PHOENIX ASH']==before['PHOENIX ASH']-3
        return dict(POTION=7,PHOENIX_ASH=3)

    def fail_and_retry(case,casts=0,item_usage=None):
        starts_before_retry = s.total_battles
        # Enemy stats/policy stay original. One-HP party makes its real attacks
        # produce an all-KO outcome in a few turns rather than a 60-turn draw.
        for c in s.party:
            c.hp=1
        for _ in range(12):
            if app.state=='result':
                break
            round_with()
        assert app.battle.outcome=='DEFEAT' and app.state=='result'
        assert all(c.hp==0 for c in s.party) and d.finale.has_amrita
        observe('CASE_'+case+'_DEFEAT',app)
        shot('case_'+case+'_defeat')
        finish_result()
        assert app.state=='final_retry'
        press(A); press()
        assert app.final_checkpoint is checkpoint
        assert s.total_battles == starts_before_retry + 1
        assert checkpoint_state()==initial,case+' checkpoint mismatch'
        assert app.battle.elysion_barrier_active and d.finale.has_amrita
        assert not app.final_visual().active and app.final_visual().frame==0
        assert all(c.mastered_skills is s.mastered_skills for c in s.party)
        assert d.inventory is s.inventory and d.treasure is s.treasure and d.rng is s.rng
        assert app.exploration.session is s and app.exploration.dungeon is d
        row=dict(case=case,outcome='DEFEAT',strong_casts=casts,item_usage=item_usage or {},
                 complete_restore=True,key_retained=True,barrier_restored=True,
                 same_checkpoint=True,shared_references=True,
                 total_battles_before=starts_before_retry,total_battles_after=s.total_battles)
        failures.append(row)
        observe('CASE_'+case+'_RETRY',app)

    with (patch.object(pyxel,'text',side_effect=bounded),
          patch.object(pyxel,'play',side_effect=RuntimeError('suspended')),
          patch.object(pyxel,'playm',side_effect=RuntimeError('interrupted')),
          patch.object(pyxel,'play_pos',side_effect=RuntimeError('suspended')),
          patch.object(pyxel,'stop',side_effect=RuntimeError('closed'))):
        # Actual facilities after the first "Later"; no progression flags changed.
        for facility in range(4):
            while app.camp_cursor!=facility:
                press(DOWN)
            press(A)
            assert app.state=='facility'
            press(A)
            assert app.overlay=='info' if facility==0 else app.state in ('archive','quest_board','shop')
            if facility==3:
                stock=s.inventory.counts['POTION']
                funds=s.treasure.banked
                if stock<9 and funds>=s.inventory.data['items']['POTION']['price']:
                    press(A)
                    assert s.inventory.counts['POTION']==stock+1
            press(B); press(B)
            assert app.state=='camp' and d.finale.has_amrita and not d.finale.final_event_started
            facilities.append(('GUILD','TRAINING','PUB','SHOP')[facility])
        # Deterministic pre-checkpoint loadout/resources, not enemy balance edits.
        for c in s.party:
            for sid in ('fire','meteor','seven_slash'):
                if sid not in c.skills:
                    if len(c.skills)>=8:
                        old=next(k for k in reversed(c.skills) if k not in ('punch','quick_hit','spark','return','fire','meteor','seven_slash'))
                        c.forget(old)
                    c.learn(s.skills[sid])
                    s.discovered_skills.add(sid)
            for sid in ('meteor','seven_slash'):
                c.skill_uses[sid]=c.max_uses(s.skills[sid])
        s.inventory.counts={iid:9 for iid in s.inventory.counts}
        assert AMRITA_ITEM_ID not in s.inventory.counts and d.finale.has_amrita
        while app.camp_cursor!=4:
            press(DOWN)
        press(A)
        facilities.append('DUNGEON')
        assert app.state=='explore'
        entrance=d.find(0,TILE_ENTRANCE)
        assert (d.x,d.y)==entrance
        delta=next(delta for delta in DIRECTIONS if d.can_enter(0,d.x+delta[0],d.y+delta[1])
                   and d.tile(0,d.x+delta[0],d.y+delta[1]) in FLOOR_TILES)
        press(DIRECTIONS[delta]); press(DIRECTIONS[(-delta[0],-delta[1])])
        assert app.state=='return_result'
        press(A)
        assert app.state=='amrita_offer'
        observe('REENTRY_AMRITA_OFFER',app)
        shot('reentry_offer')
        press(A)
        assert app.state=='final_story' and d.finale.has_amrita and d.finale.final_event_started
        observe('YES_STORY_KEY_RETAINED',app)
        for _ in app.final_story_pages():
            press(A)
        press()
        assert app.state=='command' and app.battle.enemies[0].id==LORD_OF_ELYSION_ID
        assert app.battle.elysion_barrier_active and id(s)==session_identity
        checkpoint=app.final_checkpoint
        initial=checkpoint_state()
        observe('FINAL_BATTLE_START',app)
        fail_and_retry('A')
        # Physical BASIC, non-LEGEND magic, then all LEGEND uses, all blocked.
        hp=app.battle.enemies[0].hp
        basic=next(sid for sid in s.party[0].skills if s.skills[sid].rarity=='BASIC')
        hint_start=len(texts)
        round_with({0:('skill',basic,0)})
        round_with({0:('skill','fire',0)})
        casts=spend_strong_skills()
        assert app.battle.enemies[0].hp==hp and app.battle.elysion_barrier_hint_shown
        assert any('アムリタ' in line for line in texts[hint_start:])
        observe('PHYSICAL_MAGIC_LEGEND_BLOCKED_HINT',app)
        fail_and_retry('B',casts)
        fail_and_retry('C',item_usage=spend_items())
        use_amrita()
        fail_and_retry('D')
        use_amrita()
        # Lower only fixture party damage after capture so many high skills can
        # exhaust without killing the boss. Restore also checks these stats.
        for c in s.party:
            c.strength=c.intellect=3
        casts=spend_strong_skills()
        item_usage=spend_items()
        fail_and_retry('E',casts,item_usage)
        use_amrita()
        hp=app.battle.enemies[0].hp
        round_with({0:('skill',basic,0)})
        assert app.battle.enemies[0].hp<hp
        observe('NORMAL_DAMAGE_AFTER_RELEASE',app)
        for _ in range(40):
            if app.state=='result':
                break
            specs={}
            for i,c in enumerate(s.party):
                if not c.alive:
                    continue
                choices=[s.skills[sid] for sid in c.skills if c.skill_uses[sid]>0 and not c.cooldowns.get(sid,0)
                         and s.skills[sid].effect in ('damage','drain')]
                if choices:
                    specs[i]=('skill',max(choices,key=lambda skill:skill.power(c)).id,0)
            round_with(specs)
        assert app.battle.outcome=='VICTORY'
        finish_result()
        assert app.state=='ending' and app.final_checkpoint is None
        assert d.finale.lord_of_elysion_defeated and d.finale.amrita_power_spent and not d.finale.has_amrita
        observe('ENDING',app)
        shot('ending')
        ending_flags=d.finale.snapshot()
        # Both APIs and ordinary external re-entry refuse re-start after victory.
        for operation in (app.start_final_story,app.begin_final_battle):
            try:
                operation()
            except ValueError:
                pass
            else:
                raise AssertionError('Final event restarted after ENDING')
        for _ in app.final_ending_pages():
            press(A)
        assert app.state=='title'
        app.enter_camp(returned=True)
        press()  # Release TITLE's fresh-input gate before synthetic re-entry.
        press(A)
        assert app.state=='camp' and not d.finale.can_offer_amrita
        observe('POST_VICTORY_REENTRY_NO_OFFER',app)
        app.state='title'
        press(); press(A)
        assert app.state=='title_fade' and app.final_checkpoint is None
        assert not any(app.dungeon.finale.snapshot()[key] for key in
                       ('demon_defeated','has_amrita','final_event_started','lord_of_elysion_defeated','amrita_power_spent'))
        observe('NEW_GAME_FLAGS_RESET',app)

        # A stale final checkpoint must never restore an ordinary defeat.
        s,d=app.session,app.dungeon
        app.enter_camp()
        press()
        app.enter_dungeon()
        for c in s.party:
            c.max_hp=c.hp=200
            c.strength=c.intellect=3
            c.agility=50
        if 'fire' not in s.party[0].skills:
            s.party[0].learn(s.skills['fire'])
        s.inventory.counts['POTION']=3
        s.treasure.banked,s.treasure.unbanked=11,7
        app.final_checkpoint=checkpoint  # Deliberately stale fault fixture.
        app.begin_encounter()
        uses=s.party[0].skill_uses['fire']
        round_with({0:('skill','fire',0)})
        s.party[0].hp=100
        round_with({0:('item','POTION',0)})
        spent_uses=s.party[0].skill_uses['fire']
        assert spent_uses==uses-1 and s.inventory.counts['POTION']==2
        for c in s.party:
            c.hp=1
        app.begin_input()
        for _ in range(12):
            if app.state=='result':
                break
            round_with()
        assert app.battle.outcome=='DEFEAT'
        finish_result()
        assert app.state=='camp' and app.battle_kind=='normal'
        assert s.party[0].skill_uses['fire']==spent_uses and s.inventory.counts['POTION']==2
        assert s.treasure.banked==11 and s.treasure.unbanked==0
        assert all(c.hp==c.max_hp for c in s.party)
        assert not d.finale.has_amrita and not d.finale.final_event_started
        normal_defeat=dict(stale_final_checkpoint_not_applied=True,spent_uses_not_restored=True,
                          spent_items_not_restored=True,unbanked_lost=True,banked_kept=True,hp_recovered=True)
        observe('ORDINARY_DEFEAT_CHECKPOINT_ISOLATED',app)

    preserved={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in baseline.items()}
    assert all(preserved.values()),preserved
    result=dict(same_session_B10_to_ENDING=True,phase6a=phase6a_result,
                pre_demon_gates=early_gates,facilities_after_later=facilities,
                final_part_DPAD_A_B_only=True,final_pad_input_count=len(inputs),
                fully_silent_final_part=True,defeat_cases=failures,consecutive_actual_defeats=len(failures),
                ending_flags=ending_flags,post_victory_reentry_blocked=True,new_game_flags_reset=True,
                ordinary_defeat=normal_defeat,
                timeline=timeline,unchanged_files=preserved,bounded_final_text_calls=len(texts),
                screenshots=screenshots,physical_smartphone_tested=False,
                limitations=['Prepared B10 party and pre-checkpoint LEGEND/item fixture; not natural balance.',
                             'Party HP/damage injuries injected for actual defeats; enemy stats never changed.',
                             'Desktop headless Pyxel; real browser and phone handled separately.'])
    (ROOT/'verification/final_chapter.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: same Session B10 -> ENDING, 5 real all-KO retries A-E, pad-only final part;',len(texts),'bounded text calls')


if __name__=='__main__':
    main()
