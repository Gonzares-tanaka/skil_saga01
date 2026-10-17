"""Render editable presentation assets and compare all protected resources."""
from collections import deque
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyxel
from rpg.battle import Session
from rpg.content import load_content
from rpg.dungeon_app import DungeonApp
from rpg.models import Action
from rpg.battle_presentation import EFFECT_IDS, ASSET_BANK, dungeon_floor_color
from rpg.text import FONT_HEIGHT, text_width


def main():
    backup = ROOT / 'verification/backups/battle_presentation'
    baseline = json.loads((backup / 'baseline.json').read_text(encoding='utf-8'))
    allowed = {'game.pyxres', 'data/skills.json', 'rpg/models.py', 'rpg/app.py', 'rpg/dungeon_app.py',
               'rpg/battle_presentation.py', 'rpg/sound.py', 'assets/battle_music.pyxres'}
    for name, digest in baseline.items():
        if name not in allowed:
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    old = json.loads((backup/'skills.json').read_text(encoding='utf-8'))
    new = json.loads((ROOT/'data/skills.json').read_text(encoding='utf-8'))
    assert [{k:v for k,v in row.items() if k != 'effect_id'} for row in new] == old
    pyxel.init(160,120,headless=True)
    def capture():
        images = [tuple(bank.pget(x,y) for y in range(256) for x in range(256)) for bank in pyxel.images]
        maps = [tuple(bank.pget(x,y) for y in range(256) for x in range(256)) for bank in pyxel.tilemaps]
        sounds = [(list(s.notes), list(s.tones), list(s.volumes), list(s.effects), s.speed) for s in pyxel.sounds]
        music = [[list(seq) for seq in m.seqs] for m in pyxel.musics]
        return images,maps,sounds,music
    pyxel.load(str(backup/'game.pyxres'))
    before = capture()
    pyxel.load(str(ROOT/'game.pyxres'))
    after = capture()
    assert before[1:] == after[1:], 'Tilemaps/sound/music changed'
    assert before[0][:2] == after[0][:2], 'Existing Image 0/1 changed'
    changed = []
    for n,(a,b) in enumerate(zip(before[0][2],after[0][2])):
        if a == b:
            continue
        x,y = n%256,n//256
        assert (240 <= x < 256 and y < 16 or 192 <= x < 224 and y < 8
                or 192 <= x < 240 and 32 <= y < 224
                or 160 <= y < 208 and any(u <= x < u+32 for u in (0,64,128))
                or 0 <= x < 96 and 208 <= y < 256), (x,y)
        changed.append((x,y))
    assert changed
    with patch.object(pyxel,'init'):
        app = DungeonApp(Session(*load_content(),seed=193),run=False,headless=True,start_at_title=False)
    output = ROOT/'verification/screenshots'
    output.mkdir(parents=True,exist_ok=True)
    shots,texts = [],[]
    original_text = pyxel.text
    def bounded(x,y,value,color,font=None):
        assert 0 <= x and x+text_width(value) <= 160, (x,y,value)
        assert 0 <= y and y+FONT_HEIGHT <= 120, (x,y,value)
        texts.append(value)
        original_text(x,y,value,color,font)
    def shot(name):
        app.draw()
        path = output/f'battle_presentation_{name}.png'
        pyxel.screenshot(str(path),scale=4)
        shots.append(str(path.relative_to(ROOT)))
    with patch.object(pyxel,'text',side_effect=bounded):
        for floor in (0,5,10):
            app.dungeon.floor = floor
            app.session.settled = True  # Independent area render fixtures.
            app.begin_encounter()
            assert app.battle_background_area == floor//5+1
            shot(f'area{floor//5+1}')
        app.session.party[1].hp = 0
        app.session.party[0].statuses = ['poison','paralyze','sleep']
        shot('ko_and_status')
        app.session.party[1].hp = app.session.party[1].max_hp
        app.state = 'resolve'
        b = app.battle
        b.queue = deque([('party',Action(0,'SKILL',0,'punch'))])
        v = app.battle_visual()
        assert v.start()
        v.frame = 2
        shot('step')
        v.enter('skill_effect')
        for effect in EFFECT_IDS:
            v.effect = effect
            v.frame = 4
            shot(effect)
        b.enemies[0].hp = 0
        v.after_action([True]*len(b.enemies))
        v.frame = 4
        shot('death_blink')
        v.frame = 16
        shot('death_sink')
        v.reset()
        app.state,b.outcome = 'result','VICTORY'
        app.fanfare_started_at = None
        a,c = app.session.party[:2]
        app.set_result_pages(['勝利！',f'{a.name} HP +4',f'{a.name} INT +1',f'{c.name} STR +1'])
        for i in range(len(app.growth_result_pages)):
            app.result_page = i
            shot(f'result_{i}')
        assert not any('ファンファーレ再生中' in line for line in texts)
    report = dict(protected_files_unchanged=True,skill_rule_fields_unchanged=True,
                  tilemaps_images_0_1_sound_music_unchanged=True,
                  image2_only_reserved_regions_changed=True, changed_pixels=len(changed),
                  text_bounds_checked=len(texts),screenshots=shots)
    (ROOT/'verification/battle_presentation_ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: protected rules, maps, existing sprites/music; UI bounds and '+str(len(shots))+' screenshots')


if __name__ == '__main__':
    main()
