"""Diagnostic-only entry point. Never imported by the normal game.

Packaged as diagnostic_main.py, launched instead of main.py only in the
separate diagnostic ZIP. Wrappers observe original methods and re-raise
game exceptions. No IDs, save codec, timers or combat rules are changed.
"""
import functools
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback

DEFAULT_CONFIG={'battle_start_audio':True,'skip_transition':False,'watchdog_seconds':20}
LOG_LIMIT=256*1024
STACK_LIMIT=64*1024


class Diagnostic:
    def __init__(self,root,config=None,watchdog=True):
        self.root=Path(root).resolve()
        self.config=dict(DEFAULT_CONFIG,**(config or {}))
        for key in ('battle_start_audio','skip_transition'):
            if type(self.config[key]) is not bool: raise ValueError(key+' must be true/false')
        if type(self.config['watchdog_seconds']) is not int or not 1<=self.config['watchdog_seconds']<=120:
            raise ValueError('watchdog_seconds must be 1..120')
        self.directory=self.root/'diagnostics'; self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'battle_start.jsonl'; self.file=None
        self.stack_path=self.directory/'python_stacks.log'
        self.sequence=self.frame=self.battle_number=0
        self.app=None; self.starting=False; self.update_previous=None
        self.first_draw=False; self.command_drawn=self.ready=False
        self.transition_started=self.transition_completed=False
        self.draw_scope=False; self.held=None; self.last_held_check=0
        self.replacements=[]; self.fault=None; self.stack_file=None
        self.last_watchdog=0; self.watchdog=watchdog; self.io_failed=False
        self.checkpoint('DIAGNOSTIC_START',config=self.config,python=sys.version,
                        pyxel=importlib.metadata.version('pyxel'),platform=sys.platform)
        if watchdog: self.start_watchdog()

    def snapshot(self):
        app=self.app; b=getattr(app,'battle',None); order=getattr(app,'order',[])
        pos=getattr(app,'actor_position',0)
        return dict(frame=self.frame,battle_number=self.battle_number,
                    floor=getattr(getattr(app,'dungeon',None),'floor',-1)+1,
                    state=getattr(app,'state',None),
                    presentation=getattr(getattr(app,'battle_presentation',None),'phase',None),
                    active_player=order[pos] if 0<=pos<len(order) else None,
                    actor_position=pos,input_lock=getattr(app,'battle_input_blocked',None),
                    opening_lock=getattr(app,'opening_input_blocked',None),
                    queue_length=len(b.queue) if b else 0,
                    message_queue_length=len(getattr(app,'pending',())),
                    enemy_count=len(b.enemies) if b else 0,
                    enemies=[dict(index=i,id=e.id,name=e.name,sprite=list(e.sprite)) for i,e in enumerate(b.enemies)] if b else [])

    def checkpoint(self,event,**extra):
        if self.io_failed: return
        self.sequence+=1
        row={**self.snapshot(),**extra,'seq':self.sequence,'event':event,'monotonic':round(time.monotonic(),3)}
        line=json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n'
        try:
            if self.file is None: self.file=self.path.open('a',encoding='utf8')
            if self.file.tell()+len(line.encode('utf8'))>LOG_LIMIT:
                self.file.close(); self.file=None
                os.replace(self.path,self.path.with_suffix('.jsonl.1'))
                self.file=self.path.open('w',encoding='utf8')
            self.file.write(line); self.file.flush()
            # Persist the last critical checkpoint before entering native audio
            # even if the device must be powered off. Not a per-frame fsync.
            if (event in ('COMMAND_READY','GAME_EXCEPTION','UNCAUGHT_EXCEPTION') or
                    event=='AUDIO_REQUEST' and extra.get('battle_start') and
                    extra.get('audio_api') in ('play','playm') and
                    extra.get('audio_args',[None])[0] in ('0','1')):
                os.fsync(self.file.fileno())
        except OSError as error:
            self.io_failed=True
            print('DIAGNOSTIC LOG ERROR:',repr(error),file=sys.stderr,flush=True)

    def start_watchdog(self):
        try:
            import faulthandler
            if self.stack_path.exists(): os.replace(self.stack_path,self.stack_path.with_suffix('.log.1'))
            self.stack_file=self.stack_path.open('w',encoding='utf8')
            faulthandler.enable(file=self.stack_file)
            self.fault=faulthandler
            self.checkpoint('WATCHDOG_ENABLED',seconds=self.config['watchdog_seconds'])
            self.heartbeat(force=True)
        except (ImportError,OSError,RuntimeError,ValueError) as error:
            self.checkpoint('WATCHDOG_UNAVAILABLE',error=repr(error))

    def heartbeat(self,force=False):
        if self.fault is None: return
        now=time.monotonic()
        if not force and now-self.last_watchdog<min(2,self.config['watchdog_seconds']/2): return
        self.fault.cancel_dump_traceback_later()
        if self.stack_path.stat().st_size>=STACK_LIMIT:
            self.checkpoint('WATCHDOG_STACK_LIMIT'); self.fault.disable(); self.fault=None
            return
        self.fault.dump_traceback_later(self.config['watchdog_seconds'],repeat=False,file=self.stack_file)
        self.last_watchdog=now

    def replace(self,obj,name,value):
        previous=vars(obj)[name]
        self.replacements.append((obj,name,previous)); setattr(obj,name,value)

    def install(self):
        import pyxel
        from rpg.app import App
        from rpg.dungeon_app import DungeonApp,TRANSITION_INPUTS
        from rpg.dungeon import Dungeon
        from rpg.battle import Session
        from rpg.models import Enemy
        from rpg.battle_presentation import enemy_position
        diag=self
        def observe(obj,name,before,after):
            original=getattr(obj,name)
            @functools.wraps(original)
            def wrapped(owner,*args,**kwargs):
                diag.checkpoint(before)
                try: result=original(owner,*args,**kwargs)
                except BaseException as error:
                    diag.checkpoint('GAME_EXCEPTION',method=name,error=repr(error)); raise
                extra={}
                if name in ('make_enemies','next_battle'):
                    enemies=result if name=='make_enemies' else result.enemies
                    extra=dict(enemy_count=len(enemies),enemies=[dict(index=i,id=e.id,name=e.name,sprite=list(e.sprite)) for i,e in enumerate(enemies)])
                diag.checkpoint(after,**extra); return result
            diag.replace(obj,name,wrapped)
        observe(Dungeon,'make_enemies','ENEMY_GROUP_GENERATION_BEGIN','ENEMY_GROUP_CREATED')
        observe(Session,'next_battle','BATTLE_OBJECT_BEGIN','BATTLE_OBJECT_CREATED')
        original_enemy=Enemy.from_definition
        def enemy_factory(cls,row,**overrides):
            diag.checkpoint('ENEMY_INSTANCE_BEGIN',enemy_id=row['id'],sprite=row['sprite'])
            result=original_enemy(row,**overrides)
            diag.checkpoint('ENEMY_INSTANCE_READY',enemy_id=result.id,sprite=list(result.sprite))
            return result
        self.replace(Enemy,'from_definition',classmethod(enemy_factory))
        original_encounter=DungeonApp.begin_encounter
        @functools.wraps(original_encounter)
        def encounter(app,boss=False,animate=False,guardian_index=None,quest_hunt=False):
            diag.app=app; diag.battle_number+=1; diag.starting=True
            diag.first_draw=True; diag.command_drawn=diag.ready=False
            diag.transition_started=diag.transition_completed=False; diag.held=None
            diag.heartbeat(force=True)
            diag.checkpoint('ENCOUNTER_DETECTED',boss=boss,animated=animate,quest_hunt=quest_hunt)
            if diag.config['skip_transition'] and animate and not boss:
                diag.checkpoint('TRANSITION_BYPASS_DIAGNOSTIC'); animate=False
            try:
                result=original_encounter(app,boss,animate,guardian_index,quest_hunt)
                diag.checkpoint('ENEMY_INSTANCES_READY')
                if app.state=='battle_transition' and not diag.transition_started:
                    diag.transition_started=True; diag.checkpoint('TRANSITION_BEGIN')
                return result
            except BaseException as error:
                diag.checkpoint('GAME_EXCEPTION',method='begin_encounter',error=repr(error)); raise
            finally: diag.starting=False
        self.replace(DungeonApp,'begin_encounter',encounter)
        original_input=App.begin_input
        def begin_input(app):
            diag.app=app; diag.checkpoint('BATTLE_STATE_BEGIN')
            result=original_input(app)
            diag.checkpoint('BATTLE_STATE_READY'); diag.checkpoint('ACTIVE_PLAYER_SELECTED')
            return result
        self.replace(App,'begin_input',begin_input)
        original_visual=App.battle_visual
        def visual(app):
            previous=getattr(app,'battle_presentation',None)
            result=original_visual(app)
            if result is not previous: diag.checkpoint('BATTLE_PRESENTATION_CREATED')
            return result
        self.replace(App,'battle_visual',visual)
        original_update=DungeonApp.update
        def update(app):
            diag.app=app; diag.frame+=1; diag.heartbeat()
            previous=app.state; lock=app.battle_input_blocked; diag.update_previous=previous
            if lock and previous=='command' and time.monotonic()-diag.last_held_check>.5:
                diag.checkpoint('INPUT_QUERY_BEGIN')
                held=[int(k) for k in TRANSITION_INPUTS if pyxel.btn(k)]
                if held!=diag.held: diag.checkpoint('INPUT_HELD',held_keys=held); diag.held=held
                diag.last_held_check=time.monotonic()
            try: result=original_update(app)
            except BaseException as error:
                diag.checkpoint('GAME_EXCEPTION',method='update',error=repr(error)); raise
            finally: diag.update_previous=None
            if previous!=app.state: diag.checkpoint('STATE_CHANGED',previous_state=previous)
            if previous=='battle_transition' and app.state=='command' and not diag.transition_completed:
                diag.transition_completed=True; diag.checkpoint('TRANSITION_COMPLETE')
            if lock and not app.battle_input_blocked: diag.checkpoint('INPUT_UNLOCKED')
            diag.check_ready(); return result
        self.replace(DungeonApp,'update',update)
        original_draw=App.draw_battle
        def draw(app):
            first=diag.first_draw
            if first: diag.checkpoint('BATTLE_DRAW_BEGIN'); diag.draw_scope=True
            try: result=original_draw(app)
            except BaseException as error:
                diag.checkpoint('GAME_EXCEPTION',method='draw_battle',error=repr(error)); raise
            finally: diag.draw_scope=False
            if first:
                diag.checkpoint('ENEMY_DRAW_COMPLETE'); diag.checkpoint('PARTY_DRAW_COMPLETE')
                diag.first_draw=False
            if app.state=='command' and not diag.command_drawn:
                diag.command_drawn=True; diag.checkpoint('COMMAND_MENU_CREATED'); diag.check_ready()
            return result
        self.replace(App,'draw_battle',draw)
        original_blt=pyxel.blt
        def blt(*args,**kwargs):
            kind=None; index=None
            if diag.draw_scope and len(args)>=7 and args[2]==0 and diag.app.battle:
                for i,e in enumerate(diag.app.battle.enemies):
                    if tuple(args[3:5])==tuple(e.sprite) and tuple(args[:2])==enemy_position(i,len(diag.app.battle.enemies)):
                        kind='ENEMY_SPRITE'; index=i; break
                if kind is None and args[0]==98: kind='PARTY_SPRITE'; index=(args[1]-13)//16
            if kind: diag.checkpoint(kind+'_BEGIN',instance_index=index)
            result=original_blt(*args,**kwargs)
            if kind: diag.checkpoint(kind+'_COMPLETE',instance_index=index)
            return result
        self.replace(pyxel,'blt',blt)
        for api in ('play','playm','stop','load'):
            original=getattr(pyxel,api)
            def make_audio(original,api):
                def audio(*args,**kwargs):
                    starting=(diag.starting or diag.update_previous=='battle_transition')
                    if diag.app and diag.app.state=='battle_transition' and not diag.transition_started:
                        diag.transition_started=True; diag.checkpoint('TRANSITION_BEGIN')
                    if api in ('play','playm') and diag.update_previous=='battle_transition' and diag.app.state=='command' and not diag.transition_completed:
                        diag.transition_completed=True; diag.checkpoint('TRANSITION_COMPLETE')
                    diag.checkpoint('AUDIO_REQUEST',audio_api=api,audio_args=[str(a) for a in args[:2]],battle_start=starting)
                    if starting and not diag.config['battle_start_audio'] and api in ('play','playm','stop'):
                        diag.checkpoint('AUDIO_SKIPPED_DIAGNOSTIC',audio_api=api); return None
                    try: result=original(*args,**kwargs)
                    except BaseException as error:
                        diag.checkpoint('AUDIO_EXCEPTION',audio_api=api,error=repr(error)); raise
                    diag.checkpoint('AUDIO_RETURN',audio_api=api); return result
                return audio
            self.replace(pyxel,api,make_audio(original,api))
        return self

    def check_ready(self):
        app=self.app
        if not self.ready and self.command_drawn and app.state=='command' and not app.battle_input_blocked and not app.opening_input_blocked:
            self.ready=True; self.checkpoint('COMMAND_READY')

    def close(self):
        for obj,name,previous in reversed(self.replacements): setattr(obj,name,previous)
        self.replacements.clear()
        if self.fault: self.fault.cancel_dump_traceback_later(); self.fault.disable()
        if self.stack_file: self.stack_file.close()
        if self.file: self.file.close()


def main():
    root=Path.cwd()
    path=root/'diagnostic_config.json'
    config=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    diag=Diagnostic(root,config).install()
    try:
        import main as game
        game.main()
    except BaseException as error:
        diag.checkpoint('UNCAUGHT_EXCEPTION',error=repr(error))
        if diag.stack_file:
            traceback.print_exc(file=diag.stack_file); diag.stack_file.flush()
        raise
    finally: diag.close()


if __name__=='__main__': main()
