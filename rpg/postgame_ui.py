"""Small ending/extra-boss state machine; audio never controls progression."""
from copy import copy,deepcopy
import json
import uuid
import pyxel
from .content import ROOT
from .postgame import (load_postgame_data,dragon_enemy,dragon_here,dragon_location,
                       dragon_image,CompletionRecords)
from .enemy_actions import EnemyAction
from .save import make_save_data,prepare_saved_game,read_completion,SaveError,NoSaveError
from .text import text,text_width,wrap_lines

POSTGAME_STATES=('credits','ending_end','extra_quest_title','extra_quest_story',
    'clear_save_error','dragon_warning','dragon_victory_story','dragon_title','dragon_result','completion_record')


def load_credits():
    data=json.loads((ROOT/'data/ending_credits.json').read_text(encoding='utf8'))
    for key in ('lines','extra_title','extra_lines'):
        if not isinstance(data.get(key),list) or not data[key] or not all(isinstance(s,str) for s in data[key]):
            raise ValueError('ending_credits.json: 文章は配列です。')
    for key,low,high in (('scroll_frames_per_pixel',1,30),('line_height',8,32),('end_frames',30,600)):
        if type(data.get(key)) is not int or not low<=data[key]<=high:
            raise ValueError('ending_credits.json: スクロール・表示時間が不正です。')
    return data


def centered(lines,top=None,gap=10):
    lines=wrap_lines(lines,38)
    y=(120-len(lines)*gap)//2 if top is None else top
    for i,line in enumerate(lines):
        text(max(0,(160-text_width(line))//2),y+i*gap,line,3,40)


class PostgameMixin:
    def init_postgame(self):
        self.credits_data=load_credits()
        self.postgame_data=load_postgame_data()
        self.completion_pending=None
        self.completion_error=''
        self.postgame_frame=0
        self.postgame_blocked=False
        self.ending_first=False
        self.postgame_page=0
        self.dragon_turns=0
        self.dragon_first=False
        self.dragon_new_record=False

    def postgame_state(self,state):
        self.state,self.overlay,self.notice_timer=state,None,0
        self.postgame_frame=0
        self.postgame_page=0
        self.postgame_blocked=True

    def clear_candidate(self,main):
        # Work on detached objects. A failed atomic write cannot destroy the
        # live battle, its checkpoint or the previously stored game.
        s,d,e=copy(self.session),copy(self.dungeon),copy(self.exploration)
        d.finale=deepcopy(d.finale);d.completion=deepcopy(d.completion)
        if main:
            if self.final_checkpoint is None:raise SaveError('決戦前の記録がありません')
            self.final_checkpoint.restore(s,d,e)
            f=d.finale
            f.has_amrita=True
            f.final_event_started=f.lord_of_elysion_defeated=f.amrita_power_spent=False
            d.completion.main_game_cleared=True
            if d.completion.run_id is None:d.completion.run_id=uuid.uuid4().hex
        else:
            s.party=deepcopy(s.party);s.inventory=deepcopy(s.inventory);s.treasure=deepcopy(s.treasure)
            s.treasure.secure()
            for actor in s.party:actor.recover()
            d.completion.dragon_victory(self.dragon_turns)
        proxy=copy(self)
        proxy.session,proxy.dungeon,proxy.exploration=s,d,e
        proxy.hub_intro_shown=True
        data=make_save_data(proxy)
        prepare_saved_game(proxy,data)
        return data

    def complete_main_game(self):
        self.ending_first=not self.dungeon.completion.main_game_cleared
        self.completion_pending=('main',self.clear_candidate(True))
        self.write_completion()

    def complete_dragon(self):
        record=self.dungeon.completion
        self.dragon_turns=self.battle.round
        self.dragon_first=not record.ancient_dragon_defeated
        self.dragon_new_record=record.ancient_dragon_best_turns is None or self.dragon_turns<record.ancient_dragon_best_turns
        self.completion_pending=('dragon',self.clear_candidate(False))
        self.write_completion()

    def write_completion(self):
        kind,data=self.completion_pending
        try:
            self.save_manager.backend.write(data)
        except Exception as error:
            self.completion_error=str(error)
            self.postgame_state('clear_save_error')
            return
        self.dungeon.completion=read_completion(data['completion'])
        self.completion_pending=None
        self.completion_error=''
        if kind=='main':
            self.final_checkpoint=None
            self.state,self.ending_page='ending',0
        else:self.postgame_state('dragon_victory_story' if self.dragon_first else 'dragon_result')

    def start_credits(self):
        self.postgame_state('credits')
        self.audio.play_bgm('bgm_credits')

    def ending_to_title(self):
        self.audio.stop_bgm()
        self.state,self.overlay,self.title_cursor='title',None,1
        self.opening_input_blocked=True
        self.sync_scene_audio()

    def dragon_warning(self):
        self.postgame_state('dragon_warning')
        self.final_choice=1 # Do not accidentally commit an unprepared fight.

    def begin_dragon_battle(self):
        if not dragon_here(self.dungeon):raise ValueError('竜はここにはいません。')
        self.postgame_blocked=False
        self.battle=self.session.next_battle([dragon_enemy(self.postgame_data)],recover=False,boss=True,persistent_poison=True)
        self.battle.enemy_actions.update({k:EnemyAction(**v) for k,v in self.postgame_data['actions'].items()})
        self.battle.max_rounds=self.postgame_data['max_rounds']
        self.battle_kind,self.battle_is_boss='dragon',True
        self.battle_background_area=3
        self.battle_position=self.dungeon.floor,self.dungeon.x,self.dungeon.y
        self.log=[self.postgame_data['enemy']['name']+'が現れた！']
        self.overlay=None;self.notice_timer=0
        self.fanfare_started_at=self.fanfare_start_frame=None
        self.final_checkpoint=None
        self.begin_input()
        self.battle_input_blocked=True
        self.audio.play_bgm('bgm_boss')

    def merge_saved_completion(self,prepared):
        # A stale suspend from this same adventure may not roll back records.
        try:stored=read_completion(self.save_manager.backend.read().get('completion'))
        except NoSaveError:return prepared
        except Exception as error:raise SaveError('クリア記録を照合できません') from error
        current=prepared[1].completion
        if stored.main_game_cleared and current.run_id is None:
            raise SaveError('クリア後は通常の「つづきから」で再開してください')
        if stored.run_id==current.run_id and stored.main_game_cleared and not current.main_game_cleared:
            raise SaveError('クリア前の中断です。「つづきから」で再開してください')
        current.merge(stored)
        return prepared

    def update_postgame(self):
        if self.state not in POSTGAME_STATES:return False
        state=self.state
        if state=='credits':
            self.postgame_frame+=1
            lines=wrap_lines(self.credits_data['lines'],38)
            end=(120+len(lines)*self.credits_data['line_height'])*self.credits_data['scroll_frames_per_pixel']
            if self.postgame_frame>=end or not self.ending_first and self.confirm():
                self.audio.stop_bgm();self.postgame_state('ending_end')
            return True
        if state=='ending_end':
            self.postgame_frame+=1
            if self.postgame_frame>=self.credits_data['end_frames']:
                if self.ending_first:self.postgame_state('extra_quest_title')
                else:self.ending_to_title()
            return True
        if self.postgame_blocked:
            from .dungeon_app import TRANSITION_INPUTS
            if not any(pyxel.btn(k) for k in TRANSITION_INPUTS):self.postgame_blocked=False
            return True
        confirm,cancel=self.confirm(),self.cancel()
        if state=='clear_save_error':
            if confirm:self.write_completion()
        elif state=='dragon_warning':
            pages=self.postgame_pages(self.postgame_data['warning'])
            if cancel:self.state='explore';self.opening_input_blocked=True
            elif self.postgame_page+1<len(pages):
                if confirm:self.postgame_page+=1
            else:
                self.final_choice=(self.final_choice+self.direction())%2
                if confirm:
                    if self.final_choice:self.state='explore';self.opening_input_blocked=True
                    else:self.begin_dragon_battle()
        elif state=='completion_record':
            if cancel:self.state='quest_record'
        elif state=='extra_quest_title':
            if confirm:self.postgame_state('extra_quest_story')
        elif state in ('extra_quest_story','dragon_victory_story'):
            lines=self.credits_data['extra_lines'] if state=='extra_quest_story' else self.postgame_data['victory_lines']
            pages=self.postgame_pages(lines)
            if confirm:
                if self.postgame_page+1<len(pages):self.postgame_page+=1
                elif state=='extra_quest_story':self.ending_to_title()
                else:self.postgame_state('dragon_title')
        elif state=='dragon_title':
            if confirm:self.postgame_state('dragon_result')
        elif state=='dragon_result' and confirm:
            self.battle=None
            self.battle_kind='normal'
            self.enter_camp(returned=True)
            self.camp_offer_pending=False
            if self.state=='amrita_offer':self.state='camp'
            self.opening_input_blocked=True
        return True

    def postgame_pages(self,lines):
        rows=wrap_lines(lines,36)
        return [rows[i:i+7] for i in range(0,len(rows),7)] or [['']]

    def draw_postgame(self):
        pyxel.cls(0)
        state=self.state
        if state=='credits':
            y=120-self.postgame_frame//self.credits_data['scroll_frames_per_pixel']
            for line in wrap_lines(self.credits_data['lines'],38):
                if 0<=y<=112:text((160-text_width(line))//2,y,line,3,40)
                y+=self.credits_data['line_height']
        elif state=='ending_end':
            glyphs=('11111/10000/10000/11110/10000/10000/11111',
                    '10001/11001/10101/10011/10001/10001/10001',
                    '11110/10001/10001/10001/10001/10001/11110')
            for i,glyph in enumerate(glyphs):
                for y,row in enumerate(glyph.split('/')):
                    for x,pixel in enumerate(row):
                        if pixel=='1':pyxel.rect(45+i*24+x*4,46+y*4,4,4,3)
        elif state=='extra_quest_title':centered(self.credits_data['extra_title']);self.footer('A:次へ')
        elif state=='clear_save_error':
            centered(['記録を保存できませんでした','クリア記録は未保存です','保存先の容量・権限を確認して','Aで再試行してください'])
            self.footer('A:保存を再試行')
        elif state=='dragon_warning':
            pages=self.postgame_pages(self.postgame_data['warning'])
            centered(pages[self.postgame_page],top=16)
            if self.postgame_page+1==len(pages):
                for i,label in enumerate(('挑む','準備し直す')):
                    value=('> ' if i==self.final_choice else '  ')+label
                    text((160-text_width(value))//2,87+i*10,value,3)
            self.footer('A:決定 B:戻る')
        elif state in ('extra_quest_story','dragon_victory_story'):
            lines=self.credits_data['extra_lines'] if state=='extra_quest_story' else self.postgame_data['victory_lines']
            centered(self.postgame_pages(lines)[self.postgame_page]);self.footer('A:次へ')
        elif state=='dragon_title':centered(self.postgame_data['title_lines']);self.footer('A:記録へ')
        elif state=='dragon_result':
            record=self.dungeon.completion
            centered(['ANCIENT DRAGON','DEFEATED!','',f'討伐ターン数 {self.dragon_turns}',
                'BEST RECORD',str(record.ancient_dragon_best_turns),
                'NEW RECORD!' if self.dragon_new_record else ''],top=18)
            self.footer('A:拠点へ帰還')
        elif state=='completion_record':
            record=self.dungeon.completion
            centered(['本編クリア：達成','', 'エンシェントドラゴン',
                '討伐：達成' if record.ancient_dragon_defeated else '討伐：未達成',
                f'最短討伐：{record.ancient_dragon_best_turns}ターン' if record.ancient_dragon_defeated else '',
                f'討伐回数：{record.ancient_dragon_victories}'])
            self.footer('B:クエスト記録へ')

    def draw_dragon_symbol(self,camera_x,camera_y):
        from .dungeon_app import MAP_X,MAP_Y,TILE_SIZE
        floor,(x,y)=dragon_location(self.dungeon)
        if self.dungeon.completion.main_game_cleared and self.dungeon.floor==floor:
            u,v,w,h=self.postgame_data['symbol']
            sx,sy=MAP_X+x*TILE_SIZE-camera_x,MAP_Y+y*TILE_SIZE-camera_y
            image=dragon_image()
            # A dark outline preserves the editable glyph on pale AREA3 floors.
            for iy in range(h):
                for ix in range(w):
                    if image.pget(u+ix,v+iy):
                        for dx,dy in ((0,-1),(0,1),(-1,0),(1,0)):
                            pyxel.pset(sx+ix+dx,sy+iy+dy,0)
            pyxel.blt(sx,sy,image,u,v,w,h,0)
