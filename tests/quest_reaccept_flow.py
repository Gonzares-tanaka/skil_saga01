"""Actual update/draw input flows. Only travel position is a disclosed fixture."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.save import FileSaveBackend
from rpg.suspend import FileSuspendBackend

A,B=pyxel.GAMEPAD1_BUTTON_A,pyxel.GAMEPAD1_BUTTON_B
DOWN,UP=pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,pyxel.GAMEPAD1_BUTTON_DPAD_UP


class QuestFlow:
    def __init__(self,seed=303,window=False):
        self.temp=tempfile.TemporaryDirectory(prefix='quest-reaccept-save-')
        self.directory=Path(self.temp.name)
        self.window=window
        self.inputs=[];self.stages=[];self.last_before=None
        if getattr(pyxel,'_tests_initialized',False):
            with patch.object(pyxel,'init'):
                self.a=self.create(seed,True)
        else:
            self.a=self.create(seed,not window)
            pyxel._tests_initialized=True

    def create(self,seed,headless):
        return DungeonApp(Session(*load_content(),seed=seed),run=False,headless=headless,
                          save_backend=FileSaveBackend(self.directory/'save.json'),
                          suspend_backend=FileSuspendBackend(self.directory/'suspend.json'))

    def close(self):self.temp.cleanup()

    def snapshot(self):
        a=self.a;e=a.exploration;b=a.battle
        return dict(state=a.state,overlay=a.overlay,battle_kind=a.battle_kind,
            battle_outcome=b.outcome if b else None,settled=a.session.settled,
            active=deepcopy(e.active),pending=deepcopy(e.pending_quest),
            clears=dict(e.quest_clear_counts),completed_ids=list(e.completed_quest_ids),
            banked=a.session.treasure.banked,completion_ready=e.completion_ready,
            location=[a.dungeon.floor+1,a.dungeon.x,a.dungeon.y])

    def tick(self,key=None):
        self.last_before=self.snapshot()
        self.inputs.append(dict(state=self.a.state,key=key))
        with patch.object(pyxel,'btn',return_value=False),patch.object(pyxel,'btnp',
                side_effect=lambda k,*args:k==key):
            self.a.update()
        self.a.draw()
        if self.window:pyxel.flip()

    def mark(self,name):self.stages.append(dict(stage=name,**self.snapshot()))

    def new_game(self):
        for _ in range(20):
            self.tick()
            if self.a.suspend_job is None:break
        assert self.a.state=='title'
        self.tick(A)
        for _ in range(300):
            if self.a.state=='camp':break
            self.tick(None if self.a.opening_input_blocked else A)
        assert self.a.state=='camp'
        self.mark('NEW_GAME_HUB')

    def accept(self,kind,level=1):
        a=self.a
        assert a.state=='camp',self.snapshot()
        # Return always selects GUILD; select PUB with real menu inputs.
        while a.camp_cursor!=2:self.tick(DOWN)
        self.tick(A);self.tick(A)
        assert a.state=='quest_board'
        for _ in range(level-1):self.tick(DOWN)
        self.tick(A)
        for _ in range(('explore','investigate','hunt').index(kind)):self.tick(DOWN)
        self.tick(A)
        assert a.state=='quest_preview'
        offer=deepcopy(a.exploration.pending_quest)
        while a.quest_flavor_page+1<len(a.quest_flavor_pages(offer)):self.tick(A)
        self.tick(A)
        assert a.state=='quest_board' and a.exploration.active==offer
        self.mark('ACCEPTED_'+kind)
        self.tick()  # The first update after accept is part of the reproduction.
        self.tick(B);self.tick(B)
        assert a.state=='camp'
        return offer

    def settle_screens(self):
        a=self.a
        for _ in range(6000):
            if a.overlay=='rescue':self.tick(None if a.rescue_input_blocked else A)
            elif a.state=='replace':
                self.tick(B);self.tick(A);self.tick(A)
            elif a.state in ('resolve','result','field_event','battle_transition'):
                self.tick(None if a.battle_input_blocked else A)
            else:return
        raise AssertionError(('Unfinished battle UI',self.snapshot()))

    def win_hunt(self):
        a=self.a
        self.settle_screens()
        for _ in range(100):
            if a.state!='command':break
            self.tick() # Release encounter/notification input before selecting.
            if a.state!='command':self.settle_screens();continue
            while a.state=='command':
                actor=a.actor
                choices=[sid for sid in actor.skills if actor.skill_uses.get(sid,0)>0
                         and not actor.cooldowns.get(sid,0)
                         and a.session.skills[sid].effect in ('damage','drain')]
                if not choices:
                    a.cursor=2 # Existing GUARD action, only UI cursor setup.
                    self.tick(A);continue
                sid=max(choices,key=lambda v:a.session.skills[v].power(actor))
                a.cursor=0;self.tick(A)
                while a.skill_cursor!=actor.skills.index(sid):self.tick(DOWN)
                self.tick(A)
                if a.state=='target':self.tick(A)
            self.settle_screens()
        assert a.battle.outcome=='VICTORY',self.snapshot()
        self.settle_screens();assert a.state=='explore',self.snapshot()

    def complete(self):
        a=self.a;e=a.exploration;q=deepcopy(e.active)
        assert a.state=='camp'
        while a.camp_cursor!=4:self.tick(DOWN)
        self.tick(A);self.settle_screens()
        for point in q['points']:
            # The fixture skips ordinary travel/battles, but uses the actual
            # target, A interaction, real hunt combat and complete result UI.
            a.dungeon.floor=q['target_floor']-1;a.dungeon.x,a.dungeon.y=point
            self.tick(A)
            if q['type']=='hunt':self.win_hunt()
            else:self.settle_screens()
        assert e.surveyed
        self.mark('OBJECTIVE_COMPLETE')
        # Travel fixture to the B1 entrance; A triggers ordinary safe return.
        from rpg.tiles import TILE_ENTRANCE
        a.dungeon.floor=0;a.dungeon.x,a.dungeon.y=a.dungeon.find(0,TILE_ENTRANCE)
        self.tick(A)
        assert a.state=='quest_thanks'
        bank=a.session.treasure.banked;clears=e.quest_clear_counts[q['type']]
        for _ in range(len(a.quest_thanks_pages())):self.tick(A)
        assert a.state=='quest_reward' and e.active is None
        assert a.session.treasure.banked==bank+q['reward']
        assert e.quest_clear_counts[q['type']]==clears+1
        self.tick(A);assert a.state=='camp'
        self.mark('REPORTED_'+q['type'])
        return q
