"""Permit only the requested display labels, two rumors and UI label lookups."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from rpg.content import ROOT

NAMES={'POTION':'ポーション','PHOENIX ASH':'不死鳥の灰','REMEDY':'妖精のしずく',
       'return_feather':'帰還の羽根'}
HINTS={'POTION':'味方1人のHPを回復する','PHOENIX ASH':'戦闘不能の味方1人を蘇生する',
       'REMEDY':'味方の状態異常を治療する','return_feather':'ダンジョンから帰還 / 1個消費'}
RUMORS={6:'ダンジョンの深淵で迷ったら、左手を頼りに進め。',
        7:'アムリタには、まだ知られぬ力があるらしい。'}


@lru_cache(maxsize=1)
def baseline():
    return json.loads((ROOT/'tests/fixtures/ui_phase6b2_before.json').read_text(encoding='utf8'))


def expected_sources():
    result=dict(baseline()['sources'])
    def replace(name,old,new):
        assert result[name].count(old)==1,(name,old)
        result[name]=result[name].replace(old,new,1)
    result['rpg/items.py']+='''
    def description(self, item):
        return {
            'POTION': '味方1人のHPを回復する',
            'PHOENIX ASH': '戦闘不能の味方1人を蘇生する',
            'REMEDY': '味方の状態異常を治療する',
            RETURN_FEATHER: 'ダンジョンから帰還 / 1個消費',
        }[item]
'''
    replace('rpg/app.py',"                    name = self.battle.skills[action.skill_id].name if action.kind == 'SKILL' else action.item_id",
        "                    name = self.battle.skills[action.skill_id].name if action.kind == 'SKILL' else action.item_id\n                    if action.kind == 'ITEM' and action.item_id != AMRITA_ITEM_ID:\n                        name = self.session.inventory.label(action.item_id)")
    replace('rpg/app.py','            label = self.selected_item or f"{self.selected_skill.name} 残{self.actor.skill_uses[self.selected_skill.id]}"',
        '            label = self.selected_item or f"{self.selected_skill.name} 残{self.actor.skill_uses[self.selected_skill.id]}"\n            if self.selected_item:\n                label = self.session.inventory.label(self.selected_item)')
    replace('rpg/app.py',"                label = f'{item} x{remaining}'",
        "                label = f'{self.session.inventory.label(item)} x{remaining}'")
    replace('rpg/app.py','''        else:
            text(8, 78, "POTION: 生存者のHP回復", 2, 36)
            text(8, 90, "ASH: 戦闘不能を25%で蘇生", 2, 36)''',
        '''        elif options:
            text(8, 78, self.session.inventory.description(options[self.item_cursor]), 2, 36)''')
    replace('rpg/battle.py','            return [f"{actor.name} {action.item_id}", message]',
        '            return [f"{actor.name} {self.inventory.label(action.item_id)}", message]')
    replace('rpg/dungeon.py','            return "", f"{kind} は満杯。宝箱は残した"',
        '            return "", f"{self.inventory.label(kind)} は満杯。宝箱は残した"')
    replace('rpg/dungeon.py','            message = f"{kind} を{amount}個入手"',
        '            message = f"{self.inventory.label(kind)} を{amount}個入手"')
    replace('rpg/dungeon_app.py',"""        hint = {
            'POTION': '味方1人のHPを回復する',
            'PHOENIX ASH': '戦闘不能の味方1人を蘇生する',
            'REMEDY': '味方の状態異常を治療する',
            RETURN_FEATHER: 'ダンジョンから帰還 / 1個消費',
        }[ITEMS[self.item_kind_cursor]]""",
        '        hint = self.session.inventory.description(ITEMS[self.item_kind_cursor])')
    replace('rpg/dungeon_app.py','        self.title(item + " / 誰に使う?")',
        '        self.title(self.session.inventory.label(item) + " / 誰に使う?")')
    replace('rpg/dungeon_app.py','        labels = {"TREASURE": CURRENCY_NAME, "POTION": "薬",',
        '''        labels = {"TREASURE": CURRENCY_NAME, "POTION": self.session.inventory.label('POTION'),''')
    replace('rpg/dungeon_app.py','                          ("灰を1個取得", "ash"), ("薬を1個取得", "potion"),',
        '''                          (self.session.inventory.label('PHOENIX ASH') + "を1個取得", "ash"),
                          (self.session.inventory.label('POTION') + "を1個取得", "potion"),''')
    for item,old in (('PHOENIX ASH','灰'),('POTION','薬')):
        replace('rpg/dungeon_app.py',f'            self.tell("{old} +1" if self.session.inventory.add("{item}") else "{old}は満杯")',
            f"            label = self.session.inventory.label('{item}')\n"+
            f'            self.tell(label + " +1" if self.session.inventory.add("{item}") else label + "は満杯")')
    return result


def expected_items():
    items=deepcopy(baseline()['items'])
    for key in ('POTION','PHOENIX ASH','REMEDY'):items['items'][key]['name']=NAMES[key]
    return items


def expected_rumors():
    rumors=deepcopy(baseline()['rumors'])
    for index,value in RUMORS.items():rumors['gameplay'][index]=value
    return rumors


def assert_preserved(case):
    if (ROOT/'tests/fixtures/phase7_before.json').exists():
        from tests.phase7_preservation import assert_preserved as assert_phase7_preserved
        return assert_phase7_preserved(case)
    sources=expected_sources()
    for name,digest in baseline()['hashes'].items():
        if 'save' in Path(name).parts:continue # Final package check protects actual saves.
        if name in sources:
            case.assertEqual((ROOT/name).read_text(encoding='utf8'),sources[name],name)
        elif name=='data/items.json':
            case.assertEqual(json.loads((ROOT/name).read_text(encoding='utf8')),expected_items())
        elif name=='data/pub_messages.json':
            case.assertEqual(json.loads((ROOT/name).read_text(encoding='utf8')),expected_rumors())
        else:case.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
