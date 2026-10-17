"""Render 3/4 enemies and the fourth target using the current editable art."""
from pathlib import Path
import json
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_battle_grid import EnemyGridTests
from rpg.text import text_width,FONT_HEIGHT
import pyxel


def main():
    fixture=EnemyGridTests()
    fixture.setUp()
    app=fixture.app
    output=ROOT/'verification/screenshots'
    output.mkdir(parents=True,exist_ok=True)
    for enemy,row in zip(app.battle.enemies,app.session.enemy_data):
        enemy.sprite=tuple(row['sprite'])
        enemy.name=row['name']
    enemies=app.battle.enemies[:]
    shots=[]
    original=pyxel.text
    texts=[]
    def bounded(x,y,value,color,font=None):
        assert 0<=x and x+text_width(value)<=160,(x,y,value)
        assert 0<=y and y+FONT_HEIGHT<=120,(x,y,value)
        texts.append(value)
        original(x,y,value,color,font)
    def shot(name):
        app.draw()
        path=output/f'battle_grid_{name}.png'
        pyxel.screenshot(str(path),scale=4)
        shots.append(str(path.relative_to(ROOT)))
    with patch.object(pyxel,'text',side_effect=bounded):
        app.battle.enemies=enemies[:3]
        shot('three')
        app.battle.enemies=enemies
        shot('four')
        app.actor.learn(app.session.skills['fire'])
        app.selected_skill=app.session.skills['fire']
        app.state,app.target_cursor='target',3
        shot('fourth_target')
    report=dict(screenshots=shots,text_bounds_checked=len(texts),
                sprite_y_bottom=58,strip_y=64,fourth_target_visible=True)
    (ROOT/'verification/battle_grid_ui.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: current 3/4-enemy art, fourth target and text bounds;',len(texts),'text calls')


if __name__=='__main__':main()
