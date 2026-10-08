"""Real Pyxel UI: all nine quests, pad-only input, silence and editable assets."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import tomllib
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.battle import Session
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.quests import QUEST_TYPES, QUEST_SYMBOLS, spawn_candidates
from rpg.text import FONT_HEIGHT, text_width
from rpg.tiles import FLOOR_TILES, TILE_QUEST

A,B=pyxel.GAMEPAD1_BUTTON_A,pyxel.GAMEPAD1_BUTTON_B
DIRECTIONS={(0,-1):pyxel.GAMEPAD1_BUTTON_DPAD_UP,(0,1):pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,
            (-1,0):pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,(1,0):pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT}
DOWN,RIGHT=DIRECTIONS[(0,1)],DIRECTIONS[(1,0)]


def main():
    app= DungeonApp(Session(*load_content(),seed=37),run=False,headless=True,start_at_title=False)
    rows,texts,blits,shots,rendered_flavors=[],[],[],[],[]
    output=ROOT/'verification/screenshots'
    output.mkdir(parents=True,exist_ok=True)
    original_text,original_blt=pyxel.text,pyxel.blt

    def bounded(x,y,value,color,font=None):
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        texts.append((app.state,value))
        original_text(x,y,value,color,font)

    def blt(*args,**kwargs):
        blits.append(args)
        original_blt(*args,**kwargs)

    def press(button=None):
        assert button is None or button in (A,B,*DIRECTIONS.values())
        with patch.object(pyxel,'btnp',side_effect=lambda key,*a:key==button),patch.object(pyxel,'btn',return_value=False):
            app.update()
        app.draw()

    def shot(name):
        path=output/('phase6d_'+name+'.png')
        app.draw()
        pyxel.screenshot(str(path),scale=4)
        shots.append(path.relative_to(ROOT).as_posix())

    def advance():
        for _ in range(3000):
            if app.state in ('resolve','battle_transition','amrita_effect','result','field_event'):
                press(A)
            elif app.state=='replace':
                press(B); press(A); press(A)
            else:
                if app.state=='command' and app.battle_input_blocked:
                    press()  # A fresh press is required after encounter animation.
                return
        raise AssertionError(('State failed to advance',app.state))

    def combat():
        advance()
        for _ in range(120):
            if app.state!='command':
                break
            while app.state=='command':
                actor=app.actor
                available=[sid for sid in actor.skills if actor.skill_uses[sid]>0
                           and not actor.cooldowns.get(sid,0) and app.session.skills[sid].effect=='damage']
                if not available:
                    press(DOWN); press(A)
                    continue
                sid=max(available,key=lambda k:app.session.skills[k].power(actor))
                press(A)
                for _ in range(actor.skills.index(sid)):
                    press(DOWN)
                press(A)
                assert app.state=='target'
                press(A)
            advance()
        assert app.battle.outcome=='VICTORY'

    def arrive(point):
        d=app.dungeon
        d.floor=app.exploration.active['target_floor']-1
        dx,dy=next(delta for delta in DIRECTIONS
                   if d.can_enter(d.floor,point[0]-delta[0],point[1]-delta[1])
                   and d.tile(d.floor,point[0]-delta[0],point[1]-delta[1]) in FLOOR_TILES|{TILE_QUEST})
        d.x,d.y=point[0]-dx,point[1]-dy  # Disclosed adjacent-position fixture.
        app.state='explore'
        app.draw()
        bank,u,v=QUEST_SYMBOLS[app.exploration.active['type']]
        assert any(args[2:7]==(bank,u,v,8,8) for args in blits)
        press(DIRECTIONS[(dx,dy)])

    with (patch.object(pyxel,'text',side_effect=bounded),patch.object(pyxel,'blt',side_effect=blt),
          patch.object(pyxel,'play',side_effect=RuntimeError('suspended')),
          patch.object(pyxel,'playm',side_effect=RuntimeError('interrupted')),
          patch.object(pyxel,'stop',side_effect=RuntimeError('closed')),
           patch.object(pyxel,'play_pos',side_effect=RuntimeError('suspended'))):
        # Lv selection and cancellation never generate a quest. Only boss clears
        # unlock the next band; B returns to the same selected Lv.
        for gates, unlocked in (((), (1,)), ((4,), (1,2)), ((4,9), (1,2,3))):
            app.start_new_game()
            app.enter_camp()
            press()
            e = app.exploration
            app.dungeon.defeated_bosses.update(gates)
            press(DOWN); press(DOWN); press(A); press(A)
            assert app.state == 'quest_board'
            rng = app.session.rng.getstate()
            for level in (1,2,3):
                assert app.quest_cursor == level - 1
                press(A)
                assert not e.active and app.session.rng.getstate() == rng
                if level in unlocked:
                    assert app.state == 'quest_type'
                    shot('level'+str(level)+'_types')
                    press(DOWN); press(B)
                    assert app.state == 'quest_board' and app.quest_cursor == level - 1
                else:
                    assert app.state == 'quest_board'
                    assert f"B{(level-1)*5}F" in app.notice
                    shot('level'+str(level)+'_locked')
                if level < 3:
                    press(DOWN)
            press(B)
            assert app.state == 'facility' and not e.active

        for kind in QUEST_TYPES:
            for level in (1,2,3):
                app.start_new_game()
                app.enter_camp()
                press()
                s,d,e=app.session,app.dungeon,app.exploration
                initial_bank = s.treasure.banked
                d.defeated_bosses.update((4,9))
                for c in s.party:
                    c.hp=c.max_hp=500
                    c.strength=c.intellect=c.agility=60
                s.party[0].learn(s.skills['return'])
                press(DOWN); press(DOWN); press(A); press(A)
                assert app.state=='quest_board' and not e.active
                for _ in range(level-1):
                    press(DOWN)
                press(A)
                assert app.state=='quest_type' and not e.active
                for _ in range(QUEST_TYPES.index(kind)):
                    press(DOWN)
                rng, bank, last_flavor = s.rng.getstate(), s.treasure.banked, e.last_flavor_id
                press(A)
                assert app.state=='quest_preview' and not e.active
                assert e.pending_quest and not e.visible_points()
                shot(kind+str(level)+'_preview')
                press(DOWN); press(A)  # Explicit "do not accept".
                assert app.state=='quest_type' and not e.active and not e.pending_quest
                assert s.rng.getstate()==rng and s.treasure.banked==bank and e.last_flavor_id==last_flavor
                press(A); press(B)  # B declines as well.
                assert app.state=='quest_type' and not e.active and not e.pending_quest
                assert s.rng.getstate()==rng and s.treasure.banked==bank
                press(A)
                assert app.state=='quest_preview' and not e.active
                offer=deepcopy(e.pending_quest)
                offered_flavor=deepcopy(e.quest_flavor(e.pending_quest))
                press(A)  # Accept exactly the displayed offer.
                q=e.active_quest
                assert q==offer and e.quest_flavor()==offered_flavor and not e.pending_quest
                assert (q['type'],q['level'])==(kind,level)
                before,rng=deepcopy(q),s.rng.getstate()
                flavor, flavor_rng = deepcopy(e.quest_flavor()), e.flavor_rng.getstate()
                press(A)
                assert q==before and s.rng.getstate()==rng
                shot(kind+str(level)+'_accepted')
                press(B); press(A)  # Close and reopen the actual PUB board.
                assert app.state=='quest_board' and q==before
                assert e.quest_flavor()==flavor and e.flavor_rng.getstate()==flavor_rng
                press(B); press(B)
                assert app.state=='camp'
                press(DOWN); press(DOWN); press(A)
                advance()
                assert app.state=='explore'
                flags=d.finale.snapshot()
                for point in list(q['points']):
                    arrive(point)
                    if kind=='hunt':
                        assert app.battle_kind=='quest_hunt' and not app.battle.boss
                        assert len(app.battle.enemies)==1
                        advance()
                        if level==1:
                            # RUN keeps the target. A starts a fresh hunt at its marker.
                            app.battle.run_override=True
                            press(DOWN); press(RIGHT); press(A)
                            advance()
                            assert not e.surveyed and e.hunt_here() and app.state=='explore'
                            press(A)
                        combat()
                    else:
                        advance()
                        progress=q['progress']
                        press(A)
                        assert q['progress']==progress
                    assert d.finale.snapshot()==flags
                    assert s.treasure.banked==initial_bank
                    assert e.quest_flavor()==flavor
                assert e.surveyed
                app.state='quest_board'
                app.draw()
                shot(kind+str(level)+'_completed')
                app.state='explore'
                s.treasure.unbanked=3
                press(B)
                for _ in range(3):
                    press(DOWN)
                press(A); press(A)
                assert app.state=='quest_thanks' and e.active_quest
                assert e.quest_clear_counts==dict.fromkeys(QUEST_TYPES,0) and not e.completed_quest_ids
                assert s.treasure.banked==initial_bank+3
                shot(kind+str(level)+'_thanks')
                press(A)
                assert app.state=='quest_reward' and not e.active_quest
                assert e.quest_clear_counts[kind]==1 and e.completed_quest_ids==[q['flavor_id']]
                assert s.treasure.banked==initial_bank+q['reward']+3 and s.treasure.unbanked==0
                shot(kind+str(level)+'_return')
                press(A)
                assert app.state=='camp'
                rows.append(dict(type=kind,level=level,target_floor=q['target_floor'],
                    required_count=q['required_count'],reward=q['reward'],return_via_RETURN=True,
                     single_contract=True,selected_level_then_type=True,preview_accept_decline=True,
                     flavor_id=q['flavor_id'],requester=flavor['requester'],flavor_stable=True,
                     pad_only=True,silent=True,paid_once=True))

        # Actual ordinary all-KO after a completed quest: no reward, still active.
        e.accept(1,quest_type='investigate')
        for point in e.active['points']:
            arrive(point)
            advance()
        assert e.surveyed
        bank=s.treasure.banked
        s.treasure.unbanked=7
        d.floor=0
        d.x,d.y=d.find(0,(5,0))
        for c in s.party:
            c.hp=1
        app.begin_encounter()
        for _ in range(15):
            if app.state!='command':
                break
            while app.state=='command':
                press(DOWN); press(A)
            advance()
        assert app.battle.outcome=='DEFEAT' and app.state=='camp'
        assert e.active and not e.surveyed and e.active['progress']==0
        assert s.treasure.banked==bank and s.treasure.unbanked==0

        # Currency screens render the actual labels, rather than only source matches.
        currency_states=('camp','shop','pub','field_return','relearn_character','relearn_list','relearn_confirm','menu')
        app.relearn_cursor=0
        app.relearn_skill='punch'
        for state in currency_states:
            app.state=state
            app.draw()
            shot('currency_'+state)
        app.state='explore'
        app.overlay='help'
        app.draw()
        app.overlay=None
        for state in currency_states:
            assert any(st==state and 'TRZ' in value for st,value in texts),state
        assert not any('TREASURE' in value or ('宝' in value and '宝箱' not in value and '秘宝' not in value)
                       for _,value in texts),texts[-50:]

        # Draw all 27 authored variants plus each type/Lv fallback. ID assignment
        # here is a rendering fixture; actual random choice is covered by units.
        for kind in QUEST_TYPES:
            for level in (1,2,3):
                e.active=None
                e.accept(level,quest_type=kind)
                app.state,app.quest_flavor_page='quest_board',0
                for flavor in e.flavor_data['texts'][kind][str(level)]:
                    e.active['flavor_id']=flavor['id']
                    pages=app.quest_flavor_pages()
                    assert len(pages)==1,(flavor['id'],pages)
                    start=len(texts)
                    app.draw()
                    displayed=[value for _,value in texts[start:]]
                    assert all(line in displayed for line in pages[0])
                    assert '― '+flavor['requester'] in displayed
                    assert any('TRZ' in line for line in displayed)
                    rendered_flavors.append(flavor['id'])
                e.active['flavor_id']='removed_flavor'
                assert e.quest_flavor()==e.flavor_data['fallbacks'][kind][str(level)]
                app.draw()
        shot('flavor_fallback')

        # Long edited Japanese text is wrapped, then paged without losing text.
        e.active=None
        e.accept(2,quest_type='investigate')
        flavor=e.quest_flavor()
        long_lines=['地下の古い石壁に残る文字を調べて記録してほしい。'*9,
                    '', '離れた場所の痕跡とも比べてみたい。'*5]
        with patch.dict(flavor,lines=long_lines):
            pages=app.quest_flavor_pages()
            assert len(pages)>1
            app.quest_flavor_page=0
            before,rng,flavor_rng=deepcopy(e.active),s.rng.getstate(),e.flavor_rng.getstate()
            for page in pages:
                start=len(texts)
                app.draw()
                displayed=[value for _,value in texts[start:]]
                assert all(line in displayed for line in page)
                assert any(line.startswith('対象 B') for line in displayed)
                assert any(line.startswith('報酬 ') and 'TRZ' in line for line in displayed)
                if app.quest_flavor_page==0:
                    shot('flavor_long_first')
                press(A)
            assert app.quest_flavor_page==0 and e.active==before
            assert s.rng.getstate()==rng and e.flavor_rng.getstate()==flavor_rng

        # Before accepting a long offer, A reads all pages and never activates it.
        e.active=None
        offer=e.preview_quest(2,'investigate')
        app.state,app.quest_flavor_page,app.quest_offer_cursor='quest_preview',0,0
        with patch.dict(e.quest_flavor(offer),lines=long_lines):
            pages=app.quest_flavor_pages(offer)
            rng=s.rng.getstate()
            for _ in range(len(pages)-1):
                press(A)
                assert not e.active and s.rng.getstate()==rng
            shot('preview_long_last')
            start=len(texts)
            app.draw()
            displayed=[value for _,value in texts[start:]]
            assert '>受注する' in displayed and ' 受注しない' in displayed
            press(DOWN); press(A)
            assert app.state=='quest_type' and not e.active and not e.pending_quest
            assert s.rng.getstate()==rng

        # Persist an edited sprite to a temporary .pyxres, reload and draw it.
        app.state='explore'
        e.active=None
        e.accept(1)
        d.floor,d.x,d.y=e.target
        try:
            with tempfile.TemporaryDirectory(prefix='quest_editor_') as temp:
                for kind,(bank,u,v) in QUEST_SYMBOLS.items():
                    pyxel.load(str(ROOT/'game.pyxres'),exclude_tilemaps=True,exclude_sounds=True,exclude_musics=True)
                    changed=(pyxel.images[bank].pget(u,v)+1)%4
                    pyxel.images[bank].pset(u,v,changed)
                    path=Path(temp)/'edited.pyxres'
                    pyxel.save(str(path))
                    pyxel.load(str(ROOT/'game.pyxres'),exclude_tilemaps=True,exclude_sounds=True,exclude_musics=True)
                    assert pyxel.images[bank].pget(u,v)!=changed
                    pyxel.load(str(path),exclude_tilemaps=True,exclude_sounds=True,exclude_musics=True)
                    assert pyxel.images[bank].pget(u,v)==changed
                    e.active['type']=kind
                    blits.clear()
                    app.draw()
                    assert any(args[2:7]==(bank,u,v,8,8) for args in blits)
        finally:
            pyxel.load(str(ROOT/'game.pyxres'),exclude_tilemaps=True,exclude_sounds=True,exclude_musics=True)
        pixels=[bytes(pyxel.images[bank].pget(u+x,v+y) for y in range(8) for x in range(8))
                for bank,u,v in QUEST_SYMBOLS.values()]
        assert all(any(p) for p in pixels) and len(set(pixels))==3

    baseline_path=ROOT/'verification/backups/phase6d/game.pyxres'
    preserved=None
    if baseline_path.exists():
        def resource(path):
            with zipfile.ZipFile(path) as z:
                return tomllib.loads(z.read('pyxel_resource.toml').decode('utf-8'))
        original,current=resource(baseline_path),resource(ROOT/'game.pyxres')
        assert all(current[k]==original[k] for k in original if k!='images')
        assert current['images'][0]==original['images'][0] and current['images'][2:]==original['images'][2:]
        for y in range(256):
            for x in range(256):
                if y<8 and x>=232:
                    continue
                def pixel(image):
                    rows=image['data']
                    return rows[y][x] if y<len(rows) and x<len(rows[y]) else 0
                assert pixel(current['images'][1])==pixel(original['images'][1]),(x,y)
        preserved=True
    result=dict(quests=rows,boss_unlocks_and_selection_cancel=True,
                preview_accept_decline_and_B_all_nine=True,long_preview_read_before_decision=True,
                rendered_flavor_ids=rendered_flavors,flavor_fallback_all_nine=True,
                long_japanese_flavor_paging=True,flavor_reopen_and_progress_stable=True,
                actual_normal_defeat_keeps_contract_resets_progress=True,
                 actual_hunt_RUN_keeps_target=True,all_currency_screens_TRZ=True,
                 thanks_then_reward_and_records_all_nine=True,
                symbols=QUEST_SYMBOLS,sprite_edit_save_reload=True,existing_resource_content_preserved=preserved,
                safe_candidates_per_floor=[len(spawn_candidates(d,f)) for f in range(15)],
                bounded_text_calls=len(texts),physical_smartphone_tested=False,
                limitations=['Prepared party and adjacent-position fixtures; not natural balance.',
                             'Headless desktop Pyxel; browser WASM and phone require separate confirmation.'],screenshots=shots)
    (ROOT/'verification/phase6d_ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: nine quests via PUB/pad/RETURN, 27 flavors/fallbacks/paging, silent hunt/RUN/death, TRZ, editable assets;',len(texts),'bounded text calls')


if __name__=='__main__':
    main()
