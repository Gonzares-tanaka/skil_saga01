"""Completion records are independent of the per-final-battle retry snapshot."""
from dataclasses import dataclass
from functools import lru_cache
import json
import uuid
import zipfile
import tomllib
from .content import ROOT
from .enemy_actions import EnemyAction,validate_enemy_action_lists
from .models import Enemy

POSTGAME_RESOURCE=ROOT/'assets/postgame.pyxres'
DRAGON_ID='ancient_dragon'


@dataclass
class CompletionRecords:
    run_id: str | None = None
    main_game_cleared: bool = False
    ancient_dragon_defeated: bool = False
    ancient_dragon_best_turns: int | None = None
    ancient_dragon_victories: int = 0

    @classmethod
    def new_game(cls):return cls(run_id=uuid.uuid4().hex)

    def snapshot(self):return dict(vars(self))

    def dragon_victory(self,turns):
        if not self.main_game_cleared or type(turns) is not int or turns<1:
            raise ValueError('クリア済みの実戦ターン数が必要です。')
        self.ancient_dragon_defeated=True
        self.ancient_dragon_victories+=1
        best=self.ancient_dragon_best_turns
        self.ancient_dragon_best_turns=turns if best is None else min(best,turns)

    def merge(self,other):
        if self.run_id is None or self.run_id!=other.run_id:return
        self.main_game_cleared |= other.main_game_cleared
        self.ancient_dragon_defeated |= other.ancient_dragon_defeated
        self.ancient_dragon_victories=max(self.ancient_dragon_victories,other.ancient_dragon_victories)
        values=[n for n in (self.ancient_dragon_best_turns,other.ancient_dragon_best_turns) if n is not None]
        self.ancient_dragon_best_turns=min(values) if values else None


@lru_cache(maxsize=1)
def load_postgame_data():
    data=json.loads((ROOT/'data/postgame.json').read_text(encoding='utf8'))
    definitions={k:EnemyAction(**row) for k,row in data['actions'].items()}
    validate_enemy_action_lists([data['enemy']],definitions)
    if data['enemy']['id']!=DRAGON_ID or data['dragon_floor'] not in (13,14):
        raise ValueError('postgame.json: 竜のID・階層が不正です。')
    if (len(data['dragon_point'])!=2 or any(type(n) is not int or n<0 for n in data['dragon_point'])
            or type(data['max_rounds']) is not int or data['max_rounds']<1):
        raise ValueError('postgame.json: 座標・最大ターンが不正です。')
    for key in ('warning','victory_lines','title_lines'):
        if not isinstance(data[key],list) or not data[key] or not all(isinstance(s,str) for s in data[key]):
            raise ValueError('postgame.json: 文章は配列です。')
    return data


def dragon_enemy(data):return Enemy.from_definition(data['enemy'])


def dragon_location(dungeon):
    data=load_postgame_data()
    return data['dragon_floor']-1,tuple(data['dragon_point'])


def dragon_here(dungeon):
    if not dungeon.completion.main_game_cleared:return False
    floor,point=dragon_location(dungeon)
    return dungeon.completion.main_game_cleared and dungeon.floor==floor and (dungeon.x,dungeon.y)==point


@lru_cache(maxsize=1)
def dragon_image():
    import pyxel
    with zipfile.ZipFile(POSTGAME_RESOURCE) as archive:
        row=tomllib.loads(archive.read('pyxel_resource.toml').decode('utf8'))['images'][0]
    image=pyxel.Image(row['width'],row['height'])
    for y,pixels in enumerate(row.get('data',[])):
        for x,color in enumerate(pixels):image.pset(x,y,color)
    return image


def dragon_bounds(x,y):
    _,_,w,h=load_postgame_data()['battle_sprite']
    return max(0,min(96-w,x+8-w//2)),max(12,min(64-h,y+8-h//2)),w,h


def draw_dragon(pyxel,x,y,sink=0):
    u,v,w,h=load_postgame_data()['battle_sprite']
    left,top,_,_=dragon_bounds(x,y)
    pyxel.blt(left,top+sink,dragon_image(),u,v,w,h,0)
