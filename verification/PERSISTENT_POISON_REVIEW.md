# Status Ailment Phase 1.5「Persistent Poison」検証報告

2026-10-12。変更対象は状態異常の戦闘境界と探索UI。数値バランス・画像・SAVE設計は変更していない。WebとGKD用ZIPを更新した。実セーブの読み書きはしていない。

## 指定33項目

1. **持ち越し実装場所**: `rpg/statuses.py`の`clear_statuses(target, preserve_poison=False)`へ、要求された場合だけ生存者の毒を残す処理を追加。`Character.statuses`を引き続き使用する。`rpg/battle.py`のBattleとSession、`rpg/dungeon_app.py`のダンジョン戦入口で接続。
2. **戦闘終了**: `Battle.clear_effects`がダンジョン戦のVICTORY/ESCAPE/DRAW時だけ味方の毒を保持。制御状態・BUFF/DEBUFF・敵の全状態は解除。引き分けも探索へ戻る既存フローなので毒を保持する。全滅は全解除。
3. **RUN**: 既存`attempt_run`→`clear_effects`を使用。成功時は毒だけ残す。RUN率・失敗時の敵行動・リソース処理は変更していない。
4. **次戦の引継ぎ**: `DungeonApp.begin_encounter`が`Session.next_battle(..., persistent_poison=True)`を指定。`Character.reset_battle_state(preserve_poison=True)`が毒だけ残し、残っていたマヒ・睡眠・混乱は安全に除去する。通常戦・HUNT・ボス・守護者すべて同じ入口。
5. **残りduration**: 既存dictの正の整数値をそのまま保持。終了時・開始時に3tickへ更新しない。毒の再付与は既存仕様どおり標準3tickへ更新。
6. **歩行ダメージなし**: 実D-PAD入力で安全な地面を100歩、追加200更新フレーム待機し、HPと残り2tickが不変。毒tickを探索updateへ追加していない。既存の毒沼・罠は別の探索ダメージで、仕様・コードを変更していない。
7. **階層移動**: B6→B7→B6、B14→B15→B14、落とし穴による入口戻りでHP・毒2tickを保持。`Dungeon.change_floor`は変更なし。
8. **探索REMEDY使用**: Bメニュー→道具→REMEDY→対象→A。生存者の毒を即治療、1個消費、HP・Uses不変。戦闘ターンの操作は行わない。
9. **ITEM Menu変更**: `DungeonApp.update`のitemsでREMEDYを拒否する分岐を除去。`ITEMS`共通一覧を使用し、item_targetの2種類限定参照も3種類対応へ変更。道具説明を探索の毒治療へ変更。
10. **対象選択**: 従来の4人一覧とD-PAD/A/Bを再利用。毒アイコンを名前の横へ表示。対象を確認して選べるよう、4人全員を表示する。
11. **毒なし対象**: 既存`Inventory.use`が「今は治す状態異常がありません」を返し、消費しない。HP0では「戦闘不能には使えません」。残数0の道具も消費・遷移しない。治療ロジックを毒専用に書き換えていない。
12. **探索UI**: 右側パーティーの名前横、ITEM対象一覧、能力STATUS画面へアイコンを追加。マップ主人公の頭上には追加していない。
13. **Status Icon**: Image Bank 2 `(192,0)` 8×8。既存`draw_status_icons`を再利用。新素材・色なし。KO対象のアイコン表示なし。
14. **Healing Spring**: HPのみ全回復の既存`Exploration.heal`を維持。B4/B15の実泉イベントで毒2tick・Uses・ITEM数が不変。
15. **POTION**: 既存30HP回復を維持。毒中のHP20→50、毒2tickのまま。毒を治療しない。
16. **KO**: 既存`damage_hp`が全状態を解除。毒tickでHP1→0→蘇生のケースでも毒を復活させない。
17. **RETURN**: 既存RETURN使用→`enter_camp(returned=True)`→`Character.recover`で全状態解除。RETURN1回消費、BANKED3/UNBANKED7→10/0を維持。
18. **通常帰還**: B1入口の退出イベントと直接の拠点到着で全員の状態異常を解除。既存HP回復・帰還処理をそのまま使用。
19. **Wipe**: BattleがDEFEATなら味方・敵の全状態解除。既存拠点復帰で再度全解除とHP回復。未確定TRZ喪失など既存全滅仕様を維持。
20. **Final Retry**: 最終戦はpersistent_poison対象外。Sessionでロードオブエリシオン戦への持ち越し指定を無効にする。`rpg/final_battle.py`はハッシュ一致、チェックポイント変更なし。従来の3回復元テストと通し確認の5回実全滅・再挑戦に成功。
21. **HUNT**: 毒蛇HUNTの実Actionで毒付与→勝利処理→完了進捗→探索で2tick維持→安全帰還で毒解除→QUEST完了。敵ID、HUNT補正、報酬、SAVEは変更していない。
22. **B15**: 毒の保持は階層に依存しない。通常遭遇の抽選は禁止のまま。守護者3戦の開始と各勝利間で毒2tickを保持する境界テスト、および通常の終盤通し進行を実施。泉では治療しない。
23. **Status基本値**: `data/statuses.json`完全一致。毒5%/最低1/3本人tick、マヒ35%/3本人ターン、睡眠2本人ターン、混乱0.75/40:40:20/2本人ターンを変更していない。
24. **Enemy Action**: `data/enemy_actions.json`と`data/enemies.json`完全一致。18通常/7ボス、全weight・倍率・status_chanceを維持。
25. **PLAYER Skill**: `data/skills.json`、成長・閃き処理が完全一致。CURE等の技追加なし。
26. **SAVE schema**: `rpg/save.py`完全一致。毒を保存するフィールドを追加していない。拠点帰還後に保存し、LOAD後は全員状態異常なし。
27. **save_version**: 1のまま。既存の旧HUNT付き51データ互換テストも成功。
28. **自動テスト**: 全385成功（既存368＋新規17）。新規は残りtick境界、実勝利、RUN、制御状態除去、100歩、階段、探索REMEDY、泉/POTION、KO、RETURN、通常帰還、Wipe、B15、HUNT、SAVE、最終戦への除外、描画を含む。
29. **PC Python**: Python3.14.7/Pyxel2.9.9で全テスト、headless描画、終盤通し進行。変更前Battleと330パターンのメッセージ・HP/状態/Usesなど・乱数状態が一致。ダンジョンでの戦闘境界以外の処理を維持。
30. **PC Browser**: Edge Chromiumの実Pyodideで従来10＋毒持ち越し6＝16ケース群を確認。次戦tick、RUN、100歩、階層、B15、泉/POTION、D-PAD/A/Bの探索REMEDY、RETURN、localStorage実保存・読込。
31. **Smartphone Browser**: 同じ16ケース群をPixel7タッチエミュレーションで確認。実iOS Safari、スマートフォン、GKD Pixel2は未確認。タッチエミュレーションは実機の代替確認としては扱わない。
32. **audio freeze回帰**: 実AudioContextをsuspendedにしresumeを拒否。visibilitychange/blur/focus/pageshowを発行し、Pyxelの再生・再生位置取得も失敗させる。毒tick・演出・次戦・探索REMEDY・RETURN・SAVE/LOADが進行。音声終了を待つ新処理は追加していない。実画面ロックは未確認。
33. **既知の問題・限界**: 重大な進行不能は今回の検証で確認されていない。自然進行でのリソース判断・難易度の評価は未実施。PC GUIの手動通しプレイ、iOS SafariとGKD実機、画面ロックは今後の確認対象。DEBUG全回復F7は既存の`recover()`を使用するため毒も解除する。通常の泉・POTIONでは解除しない。

## 必須CASE 1～78

| CASE | 検証内容・結果 |
|---|---|
| 1～7 | 付与3→本人ターン2→実際のSKILLで勝利→探索2→次戦2→tick1。成功。 |
| 8～12 | 本人ターンで1→0、自然解除し、その後勝利・探索でも毒なし。成功。 |
| 13～16 | RUN成功→探索で残り2保持→次戦2。成功。 |
| 17～20 | 毒＋マヒ/睡眠/混乱それぞれ勝利後は毒のみ。戦闘開始時に残った制御状態も除去。成功。 |
| 21～23 | 実D-PAD100歩＋待機、階段往復、B14/B15移動でHP/tick不変。成功。 |
| 24～29 | 探索ITEMからD-PAD/A/Bで対象選択→REMEDY1個→毒なし、HP/Uses不変。Bキャンセルも検証。 |
| 30～32 | 無状態/KO/残数0で未消費。成功。 |
| 33～36 | 実泉イベントでHP最大、毒2保持、UsesとITEMは補充なし。成功。 |
| 37～39 | POTION30回復、毒保持。成功。 |
| 40～43 | 毒tickでKO→状態なし→PHOENIX ASH蘇生→次戦も毒なし。従来REVIVE回帰も成功。 |
| 44～48 | RETURNのpad操作、1Uses消費、帰還で毒解除、未確定TRZ確定。成功。 |
| 49～50 | 通常の入口退出で全状態解除。成功。 |
| 51～53 | DEFEAT処理→拠点回復→全員状態なし。通常全滅回帰も成功。 |
| 54～58 | B14毒→B15、通常遭遇のRNGが呼ばれない、泉はHPのみ。成功。 |
| 59～64 | 毒蛇HUNT Action→毒付与→勝利/完了進捗→探索保持→帰還/QUEST完了→毒なし。成功。 |
| 65～68 | 旧schema1/HUNT互換、帰還後SAVE、LOAD状態なし、SAVE_VERSION1。成功。 |
| 69～76 | 戦闘の毒・マヒ・睡眠・混乱・REMEDY・敵状態・RUN・QUESTの既存テストすべて成功。 |
| 77～78 | B10からENDINGまでのpad操作、アムリタ・バリア・実全滅5回の再挑戦。正常。3回の状態異常復元テストも成功。 |

## 変更範囲・配布物

- 変更したゲームコード: `rpg/statuses.py`、`rpg/models.py`、`rpg/battle.py`、`rpg/dungeon_app.py`、`rpg/app.py`。
- 変更しない53ファイルのハッシュ一致。敵・Action・Status・Skill・出現テーブル・ITEM価格・マップ・全画像/パレット/音声・SAVE・最終戦チェックポイントを含む。
- 探索、メニュー、ITEM、対象選択、能力画面、次戦の6画像を確認。65文字描画呼出しが160×120内に収まり、毒アイコンも画面内・既存文字外へ配置。
- 終盤通し: B10→B15守護者3連戦→泉→デーモン→最終戦→ENDING。5回の実全滅と再挑戦、音声失敗時のpad操作、84,236文字描画呼出しに成功。
- `dist/game.html`更新。埋込み全コード・データ・素材一致、B5/B10通常遭遇、B15遭遇なし、ゲームパッド、無音最終戦/ENDINGを確認。
- `verification/packages/skill_seekers_gkd.zip`更新。既存本体の`save/`を残してゲームファイルを上書きする。
- ZIPは60エントリで全ゲームファイルと一致し、save/を同梱しない。rpgの30モジュールはGKDのPython3.11向け構文確認に成功。結果は`verification/persistent_poison_package.json`に記録。実機動作を確認したものではない。

## 実行方法と記録

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_persistent_poison.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_final_chapter.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_web.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_web_build.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_statuses.py --playwright-path verification/backups/quest_spawn/browser_deps --fixture tools/browser_persistent_poison_case.py --base-fixture tools/browser_status_case.py --expected-count 16 --output verification/persistent_poison_browser.json
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd.py
```

結果: `verification/persistent_poison.json`、`verification/persistent_poison_browser.json`、`verification/final_chapter.json`。描画: `verification/screenshots/persistent_poison_*.png`。
