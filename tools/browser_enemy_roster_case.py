"""Extra real-data roster cases in isolated browser profiles; no shipped hooks."""
# The driver prepends the existing status fixture, without its final invocation.
# This keeps all ten shared status/silent-audio regression cases active.
base_results=json.loads(run_cases())


def roster_cases():
    from rpg.battle import Battle
    from rpg.enemy_actions import load_enemy_actions
    from rpg.quests import spawn_candidates
    app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
    rows={r['id']:r for r in app.session.enemy_data}
    assert len(rows)==25 and sum(not r.get('boss') for r in rows.values())==18
    definitions=load_enemy_actions(); results=[]
    actions=[('poison_snake','poison_bite','poison'),('ghost','confusion_touch','confusion'),
             ('mummy','paralyze_grab','paralyze'),('dark_wisp','sleep_spell','sleep'),
             ('warlock','sleep_spell','sleep')]
    with patch.object(pyxel,'btnp',return_value=False),patch.object(pyxel,'btn',return_value=False), \
         patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
         patch.object(pyxel,'playm',side_effect=RuntimeError('suspended')), \
         patch.object(pyxel,'play_pos',side_effect=RuntimeError('closed')):
        for ident,action,status in actions:
            for success in (True,False):
                for actor in app.session.party:
                    actor.hp=actor.max_hp=1000; clear_statuses(actor); actor.effects.clear()
                enemy=Enemy.from_definition(rows[ident],max_hp=10000)
                enemy.actions=[dict(id=action,weight=1)]
                b=Battle(app.session.party,[enemy],app.session.skills,rng=app.session.rng,
                         inventory=app.session.inventory)
                app.battle=b; app.session.battle=b; app.session.settled=False
                b.queue=deque([('enemy',0)]); app.state='resolve'
                app.delay=0; app.pending.clear(); app.battle_visual().reset()
                app.confirm=app.confirm_held=lambda:False
                with patch.object(b.rng,'random',return_value=0 if success else .99), \
                     patch.object(b.rng,'choice',return_value=b.party[0]):
                    app.apply_visual_action()
                assert (status in b.party[0].statuses)==success
                if action=='sleep_spell': assert b.party[0].hp==1000
                phases=set(); hp=[c.hp for c in b.party]
                for tick in range(100):
                    if not app.battle_visual().active: break
                    phases.add(app.battle_visual().phase); app.update(); app.draw()
                else: raise AssertionError('enemy status effect stalled')
                assert hp==[c.hp for c in b.party]
                if success: assert 'status_effect' in phases
                b.clear_effects()
        results.append('real_new_enemy_actions_success_failure_silent_fx')
        app.enter_camp(); app.dungeon.defeated_bosses.update((4,9))
        backend=BrowserSaveBackend()
        newfloors={'horn_rabbit':2,'poison_snake':6,'blood_bat':7,'ghost':9,
                   'mummy':12,'dark_wisp':11,'warlock':15}
        for ident,floor in newfloors.items():
            e,d=app.exploration,app.dungeon; e.active=None
            q=e.make_quest((floor-1)//5+1,quest_type='hunt')
            source=floor-1 if 'enemy_ids' in d.settings['floors'][floor-1] else floor-2
            q.update(target_floor=floor,points=[list(spawn_candidates(d,floor-1)[0])],
                     hunt_source_floor=source+1,hunt_enemy_id=ident)
            e.activate_quest(q); saved=make_save_data(app)
            assert saved['save_version']==1
            backend.write(saved); apply_save_data(app,backend.read())
            e,d=app.exploration,app.dungeon
            assert e.active['hunt_enemy_id']==ident
            d.floor=floor-1; d.x,d.y=e.active['points'][0]
            enemy,=e.make_hunt_enemy()
            assert enemy.id==ident and enemy.actions==rows[ident]['actions']
        results.append('all_7_new_hunts_localStorage_same_id_schema1')
        # Boss-only B15 retains no random encounters but uses B14 for HUNT.
        assert 'enemy_ids' not in app.dungeon.settings['floors'][14]
        assert app.exploration.active['hunt_source_floor']==14
        assert app.exploration.active['hunt_enemy_id']=='warlock'
        results.append('B15_hunt_B14_fallback_no_random_table')
        assert rows['sentinel_mind']['sprite']==[160,16]
        for row in rows.values():
            if row.get('boss'): assert not row.get('actions')
        results.append('bosses_unchanged_fallback_dragon_reserved')
    return results


base_results['cases'].extend(roster_cases())
base_results['count']=len(base_results['cases'])
json.dumps(base_results)
