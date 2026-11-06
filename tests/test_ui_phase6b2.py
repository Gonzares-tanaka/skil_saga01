"""Japanese item labels across actual screens, unchanged effects and old saves."""
from copy import deepcopy
import json
from unittest.mock import patch
import pyxel
from tests.encounter_fixture import EncounterFixture
from tests.ui_phase6b2_preservation import NAMES,HINTS,baseline,assert_preserved
from rpg import app as base_ui,dungeon_app as ui
from rpg.content import ROOT
from rpg.items import ITEMS,Inventory
from rpg.models import Action
from rpg.save import prepare_saved_game
from rpg.statuses import apply_status
from rpg.text import text_width,fit


class UIPhase6B2Tests(EncounterFixture):
    def capture(self):
        lines=[];actual=base_ui.text;pixels=pyxel.text
        def record(x,y,value,color=3,width=None):
            value=str(value);lines.append((x,y,value,width))
            if any(name in value for name in NAMES.values()):
                budget=min(160-x,width*4 if width is not None else 160)
                self.assertLessEqual(text_width(value),budget,(x,y,value,budget))
                self.assertEqual(fit(value,budget),value)
            return actual(x,y,value,color,width)
        def bounded(x,y,value,color,selected_font=None):
            width=selected_font.text_width(value) if selected_font else len(value)*4
            self.assertTrue(0<=x and x+width<=160,(x,y,value,width))
            self.assertTrue(0<=y and y+8<=120,(x,y,value))
            if selected_font is None:return pixels(x,y,value,color)
            return pixels(x,y,value,color,selected_font)
        with patch.object(base_ui,'text',side_effect=record),patch.object(ui,'text',side_effect=record),patch.object(pyxel,'text',side_effect=bounded):
            self.a.draw()
        return lines

    def item_screens(self):
        a=self.a;inv=a.session.inventory
        inv.counts.update({sid:9 for sid in ITEMS});a.notice_timer=0;a.overlay=None
        a.state='shop';yield 'shop',None
        a.state='items'
        for i,sid in enumerate(ITEMS):
            a.item_kind_cursor=i;yield 'field_'+sid,sid
        a.state='item_target'
        for i,sid in enumerate(ITEMS[:3]):
            a.item_kind_cursor=i;yield 'field_target_'+sid,sid
        a.begin_encounter();a.session.party[0].hp=1;a.session.party[1].hp=0
        apply_status(a.session.party[2],'poison');a.notice_timer=0
        for i,sid in enumerate(ITEMS[:3]):
            a.state='battle_item';a.item_cursor=i;yield 'battle_'+sid,sid
            a.state='target';a.selected_item=sid;a.selected_skill=None;a.target_cursor=0
            yield 'battle_target_'+sid,sid
            a.selected_item=None

    def test_only_requested_labels_rumors_and_lookups_changed(self):
        assert_preserved(self)
        rumors=self.a.rumors
        self.assertEqual((len(rumors['gameplay']),len(rumors['flavor'])),(11,7))
        self.assertEqual(len(self.a.session.skills),62)

    def test_all_screens_show_full_shared_names_and_selected_effect_hint(self):
        bdf=(ROOT/'assets/fonts/misaki_gothic_2nd.bdf').read_text(encoding='utf8')
        for char in ''.join(NAMES.values()):self.assertIn('ENCODING '+str(ord(char))+'\n',bdf)
        for name,sid in self.item_screens():
            with self.subTest(screen=name):
                words=[row[2] for row in self.capture()]
                self.assertFalse(any(key in word for key in ITEMS[:3] for word in words),words)
                for label in (NAMES.values() if sid is None else (NAMES[sid],)):
                    self.assertTrue(any(label in word for word in words),(name,label,words))
                if name.startswith(('field_','battle_')) and '_target_' not in name:
                    self.assertIn(HINTS[sid],words)

    def test_effects_and_consumption_match_prechange_inventory(self):
        namespace={'__name__':'rpg._ui6b2_original_items','__package__':'rpg'}
        exec(baseline()['sources']['rpg/items.py'],namespace)
        OldInventory=namespace['Inventory']
        for item in ITEMS:
            for condition in ('healthy','damaged','dead','poisoned'):
                with self.subTest(item=item,condition=condition):
                    target=deepcopy(self.a.session.party[0]);target.recover()
                    if condition=='damaged':target.hp=1
                    elif condition=='dead':target.hp=0
                    elif condition=='poisoned':apply_status(target,'poison')
                    old_target=deepcopy(target)
                    current=Inventory();old=OldInventory(deepcopy(baseline()['items']))
                    current.counts[item]=old.counts[item]=2
                    self.assertEqual(current.use(item,target),old.use(item,old_target))
                    self.assertEqual((target.hp,target.statuses,current.counts),
                                     (old_target.hp,old_target.statuses,old.counts))

    def test_battle_chest_and_purchase_messages_use_names_without_economic_change(self):
        a=self.a;inv=a.session.inventory;a.begin_encounter();c=a.session.party[1]
        for item in ITEMS[:3]:
            c.recover()
            if item=='POTION':c.hp=1
            elif item=='PHOENIX ASH':c.hp=0
            else:apply_status(c,'poison')
            inv.counts[item]=2
            messages=a.battle._party_action(Action(0,'ITEM',1,item_id=item))
            self.assertIn(NAMES[item],messages[0]);self.assertEqual(inv.counts[item],1)
            self.assertIn(NAMES[item],a.dungeon.grant_chest(dict(kind=item,amount=2))[1])
            self.assertEqual(inv.counts[item],3)
            inv.counts[item]=9
            self.assertIn(NAMES[item],a.dungeon.grant_chest(dict(kind=item,amount=1))[1])
            self.assertEqual(inv.counts[item],9)
        for item in ITEMS:
            a.session.treasure.banked=20;inv.counts[item]=0
            ok,message=inv.buy(item,a.session.treasure)
            self.assertTrue(ok);self.assertIn(NAMES[item],message)
            self.assertEqual(inv.counts[item],1)
            self.assertEqual(a.session.treasure.banked,20-baseline()['items']['items'][item]['price'])

    def test_legacy_save_and_suspend_keep_ids_counts_and_display_new_names(self):
        old=json.loads((ROOT/'tests/fixtures/ui_phase6b1_legacy_save.json').read_text(encoding='utf8'))
        s,*_=prepare_saved_game(self.a,deepcopy(old))
        self.assertEqual(s.inventory.counts,old['items'])
        self.assertEqual([s.inventory.label(sid) for sid in ITEMS],list(NAMES.values()))
        saved=json.loads((ROOT/'tests/fixtures/ui_phase6b1_legacy_suspend.json').read_text(encoding='utf8'))
        s,*_=self.a.suspend_manager.prepare(self.a,json.dumps({**saved,'suspend_id':'1'*32}))
        self.assertEqual(s.inventory.counts,saved['game']['items'])
        self.assertEqual([s.inventory.label(sid) for sid in ITEMS],list(NAMES.values()))
