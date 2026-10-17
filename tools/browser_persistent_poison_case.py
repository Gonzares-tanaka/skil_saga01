"""Real dungeon poison lifecycle and touch/pad UI in isolated Pyodide profiles."""
# The driver prepends browser_status_case.py without its last invocation.
base_results=json.loads(run_cases())


def persistence_cases():
    from rpg.content import load_content
    from rpg.models import Action
    from rpg.tiles import FLOOR_TILES,TILE_HEAL_POINT
    app=next(o for o in gc.get_objects() if isinstance(o,DungeonApp))
    results=[]
    def press(key):
        with patch.object(pyxel,'btnp',side_effect=lambda code,*args:code==key), \
             patch.object(pyxel,'btn',return_value=False): app.update(); app.draw()
    def finish(outcome):
        b=app.battle; b.queue.clear(); b.outcome=outcome; b.turn_plan=None
        b.clear_effects(); app.session.settle()
        for c in app.session.party: c.pending_skill=None
        app.fanfare_started_at=app.fanfare_start_frame=None
        app.state='result'; app.finish_results()
    def turn(index=0):
        b=app.battle; b.turn_plan=None; b.queue=deque([('party',Action(index,'GUARD'))])
        app.state='resolve'; app.delay=0; app.pending.clear(); app.battle_visual().reset()
        app.confirm=app.confirm_held=lambda:False
        app.apply_visual_action()
        for _ in range(100):
            if not app.battle_visual().active: break
            app.update(); app.draw()
        else: raise AssertionError('poison visual stopped progress')
    with patch.object(pyxel,'play',side_effect=RuntimeError('suspended')), \
         patch.object(pyxel,'playm',side_effect=RuntimeError('suspended')), \
         patch.object(pyxel,'play_pos',side_effect=RuntimeError('closed')):
        app.start_new_game(); app.enter_camp(); app.opening_input_blocked=False
        app.enter_dungeon(); app.dungeon.debug_floor(5); app.dungeon.defeated_bosses.update((4,9))
        # Restore actual pad input handlers, changed by the base animation fixture.
        app.confirm= lambda: app.pressed(pyxel.KEY_Z,pyxel.KEY_RETURN,pyxel.KEY_SPACE,pyxel.GAMEPAD1_BUTTON_A)
        app.cancel= lambda: app.pressed(pyxel.KEY_X,pyxel.KEY_ESCAPE,pyxel.GAMEPAD1_BUTTON_B)
        from rpg.app import App
        app.direction=App.direction.__get__(app)
        actor=app.session.party[0]
        for c in app.session.party: c.hp=c.max_hp=1000
        app.begin_encounter(); b=app.battle
        apply_status(actor,'poison'); apply_status(actor,'sleep'); actor.statuses['poison']=2
        finish('VICTORY')
        assert app.state=='explore' and actor.statuses=={'poison':2}
        app.begin_encounter(); assert actor.statuses=={'poison':2}
        hp=actor.hp; maximum=actor.max_hp; turn()
        assert actor.hp==hp-max(1,int(maximum*.05)) and actor.statuses=={'poison':1}
        finish('VICTORY'); assert actor.statuses=={'poison':1}
        results.append('victory_remaining_ticks_next_battle_tick')
        # RUN plus other statuses clears only control and enemies.
        app.begin_encounter(); apply_status(actor,'confusion')
        for enemy in app.battle.enemies: apply_status(enemy,'poison')
        app.battle.run_override=True; app.battle.attempt_run()
        assert actor.statuses=={'poison':1} and not any(e.statuses for e in app.battle.enemies)
        finish('ESCAPE'); results.append('escape_poison_only')
        # No tick on 100 safe ground steps, waiting, stairs or entry to B15.
        d=app.dungeon; floor=d.floor
        pair=next(((x,y),(x+1,y)) for y in range(d.map_bounds(floor)[1]) for x in range(d.map_bounds(floor)[0]-1)
                  if d.tile(floor,x,y) in FLOOR_TILES and d.tile(floor,x+1,y) in FLOOR_TILES)
        d.x,d.y=pair[0]; hp=actor.hp
        app.confirm=App.confirm.__get__(app); app.cancel=App.cancel.__get__(app)
        with patch.object(d.rng,'random',return_value=1):
            for _ in range(50):
                press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT); press(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)
            for _ in range(100): press(None)
        assert actor.hp==hp and actor.statuses=={'poison':1}
        app.handle_event(*d.change_floor(6)); assert actor.hp==hp and actor.statuses=={'poison':1}
        d.floor=13; app.handle_event(*d.change_floor(14))
        assert actor.statuses=={'poison':1} and 'enemy_ids' not in d.settings['floors'][14]
        results.append('100_steps_wait_stairs_B15_no_tick')
        # B15 HP-only spring and potion keep poison and Uses.
        app.state='explore'; actor.hp=20; d.x,d.y=d.positions(14,TILE_HEAL_POINT)[0]
        uses=deepcopy(actor.skill_uses); counts=deepcopy(app.session.inventory.counts)
        app.handle_event(*d.interact())
        assert actor.hp==actor.max_hp and actor.statuses=={'poison':1}
        assert actor.skill_uses==uses and app.session.inventory.counts==counts
        actor.hp=20; app.session.inventory.counts['POTION']=1
        app.session.inventory.use('POTION',actor)
        assert actor.hp==50 and actor.statuses=={'poison':1}
        results.append('spring_potion_HP_only')
        # D-PAD/A/B only, including a no-status target that cannot spend.
        app.state='explore'; app.overlay=None; app.session.inventory.counts['REMEDY']=2
        press(pyxel.GAMEPAD1_BUTTON_B)
        for _ in range(2): press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        press(pyxel.GAMEPAD1_BUTTON_A)
        for _ in range(2): press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        press(pyxel.GAMEPAD1_BUTTON_A); assert app.state=='item_target'
        press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN); press(pyxel.GAMEPAD1_BUTTON_A)
        assert app.session.inventory.counts['REMEDY']==2
        press(pyxel.GAMEPAD1_BUTTON_DPAD_UP); press(pyxel.GAMEPAD1_BUTTON_A)
        assert not actor.statuses and actor.hp==50 and app.session.inventory.counts['REMEDY']==1
        results.append('pad_field_remedy_no_waste_HP_unchanged')
        # Re-poison, then RETURN secures TRZ and clears all. SAVE remains schema1.
        apply_status(actor,'poison'); actor.statuses['poison']=2
        if 'return' not in actor.skills: actor.learn(app.session.skills['return'])
        app.session.discovered_skills.add('return')
        actor.skill_uses['return']=2
        app.session.treasure.banked,app.session.treasure.unbanked=3,7
        app.open_return_skill(); press(pyxel.GAMEPAD1_BUTTON_A)
        assert not any(c.statuses for c in app.session.party)
        assert (app.session.treasure.banked,app.session.treasure.unbanked)==(10,0)
        assert actor.skill_uses['return']==1
        saved=make_save_data(app); assert saved['save_version']==1 and 'statuses' not in json.dumps(saved)
        backend=BrowserSaveBackend(); backend.write(saved); apply_save_data(app,backend.read())
        assert not any(c.statuses for c in app.session.party)
        results.append('RETURN_cure_bank_localStorage_schema1')
    return results


base_results['cases'].extend(persistence_cases())
base_results['count']=len(base_results['cases'])
json.dumps(base_results)
