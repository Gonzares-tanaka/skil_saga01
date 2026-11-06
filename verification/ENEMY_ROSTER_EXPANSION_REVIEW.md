# Enemy Roster Expansion Phase 確認報告

2026-10-12。ゲーム実装の変更は `data/enemies.json`、`data/enemy_actions.json`、`data/dungeon.json` の3ファイルのみ。既存の共通処理へデータを追加した。README、テスト・検証ツール、WebとGKDの配布物は更新した。

## 指定46項目

1. **通常Enemy総数**: 18種類（既存11＋新規7）。
2. **全enemy_id数**: 25種類。ボス7種類。重複なし。表示名をID判定へ使用していない。
3. **horn_rabbit**: HP24 / STR6 / DEF0 / AGI15 / INT2 / MDEF0。attack90、double_attack10。RABBIT(208,16)。
4. **poison_snake**: HP58 / STR13 / DEF2 / AGI17 / INT4 / MDEF2。attack75、poison_bite25。SNAKE(128,16)。
5. **blood_bat**: HP52 / STR15 / DEF1 / AGI24 / INT5 / MDEF2。attack75、double_attack25。BAT(16,16)。
6. **ghost**: HP56 / STR8 / DEF4 / AGI16 / INT20 / MDEF12。attack20、magic60、confusion_touch20。GHOST(176,16)。
7. **mummy**: HP86 / STR18 / DEF8 / AGI6 / INT10 / MDEF8。attack65、heavy_attack15、paralyze_grab20。MUMMY(224,16)。
8. **dark_wisp**: HP60 / STR6 / DEF3 / AGI18 / INT24 / MDEF12。magic65、area_magic20、sleep_spell15。WISP(48,16)。
9. **warlock**: HP68 / STR8 / DEF5 / AGI14 / INT27 / MDEF10。magic45、power_up15、weaken15、armor_break10、slow10、sleep_spell5。MAGE(96,16)。
10. **poison_bite**: 単体物理0.90倍、ダメージ後に生存者へ毒45%。既存 `Battle.apply_status` を利用。
11. **confusion_touch**: 単体魔法0.85倍、混乱35%。既存の混乱専用行動・Uses非消費・40/40/20抽選・制御状態排他を維持。
12. **paralyze_grab**: 単体物理0.85倍、マヒ35%。マヒ中の行動失敗率35%とリソース非消費を維持。
13. **sleep_spell**: 生存者からランダム1人、ダメージなし、睡眠45%。失敗でもターン終了し、magicへfallbackしない。
14. **状態Action weight**: 毒蛇25、ゴースト20、ミイラ20、ダークウィスプ15、ウォーロック5。それぞれ総weight100。
15. **付与成功率**: 毒45%、混乱35%、マヒ35%、睡眠45%。行動選択と別抽選。未付与・無耐性の対象への1行動あたり理論成功率は順に11.25%、7%、7%、6.75%、2.25%。
16. **B1**: slime6 / bat3 / goblin1。
17. **B2**: slime2 / bat2 / goblin4 / wisp2 / horn_rabbit1。
18. **B3**: goblin2 / wisp2 / skeleton3 / mage2 / horn_rabbit2。
19. **B4**: golem5 / skeleton3 / mage4 / wisp1。
20. **B5**: B4の通常テーブルを既存処理で参照。guardianボスは別。
21. **B6**: iron_golem4 / skeleton2 / mage2 / poison_snake2。
22. **B7**: berserker4 / iron_golem3 / wisp1 / poison_snake2 / blood_bat2。
23. **B8**: assassin4 / stone_beast3 / mage2 / blood_bat2。
24. **B9**: iron_golem2 / berserker2 / assassin2 / stone_beast2 / poison_snake2 / blood_bat2 / ghost1。
25. **B10**: B9の通常テーブルを既存処理で参照。skill_keeperボスは別。
26. **B11**: iron_golem3 / berserker3 / mage2 / ghost2 / dark_wisp2。
27. **B12**: assassin3 / stone_beast3 / mage2 / ghost2 / mummy2。
28. **B13**: stone_beast3 / berserker3 / iron_golem2 / mummy3 / dark_wisp2 / warlock1。
29. **B14**: assassin3 / berserker2 / stone_beast2 / ghost2 / mummy2 / dark_wisp2 / warlock2。
30. **B15**: 通常ランダム遭遇なし。QUEST、守護者3連戦、HPのみの泉、デーモンを維持。Web配布内容でB15遭遇禁止も検証済み。
31. **HUNT反映**: 対象階の通常テーブルを既存 `Exploration.make_quest` で再利用。B15はB14を使用。新規全7種を生成・保存・復元・戦闘生成して確認。HP倍率・STR補正・DEF+1・状態成功率を変更していない。
32. **HUNT SAVE/LOAD**: 新規全7IDでJSON往復および読込後の敵生成に成功。ブラウザでは隔離プロファイルのlocalStorageを利用する実保存・読込で確認。
33. **旧SAVE互換**: 更新前の敵・階層データから51通りのHUNT付きschema1セーブを生成し、現在データでLOAD。同じhunt_enemy_idとhunt_source_floorを維持。プレイヤーの実セーブは読み書きしていない。
34. **既存11体の能力**: 敵レコード全体が更新前と一致。HP/STR/DEF/AGI/INT/MDEFを変更していない。
35. **既存Action weight**: 既存レコードと共通11Action定義が一致。変更していない。
36. **Boss**: 7体のレコード・AI・倍率・画像・戦闘ロジックが一致。状態異常行動を割り当てていない。守護者3はDRAGON(160,16)のまま。
37. **PLAYER Skill**: 新規追加なし。skills.json、成長、閃き処理もハッシュ一致。
38. **Status回帰**: 既存35テストと新規敵からの実付与を確認。毒tick・自然解除、制御状態排他、マヒ／混乱のUses/ITEM非消費、睡眠の通常ダメージ／毒起床、KO解除・戦闘終了解除・最終戦復元を維持。
39. **REMEDY回帰**: 新規敵が与えた毒・睡眠を治療。他の状態は既存4状態テストを維持。WEAKEN/ARMOR BREAK/SLOWは残る。ITEM性能・価格を変更していない。
40. **自動テスト**: 全368テスト成功（従来357＋新規11）。旧Enemy Actionテストの全敵数を25に更新し、旧11体とボスの割当を引き続き検証する。
41. **Encounter Simulation**: B1～B14各3,000戦、計42,000遭遇。指定外なし、全候補出現、ID/weight長一致、正のweight。実際の7敵行動を各10,000ターン、計70,000ターン検証。結果は次の表を参照。
42. **PC Python**: Python3.14.7 / Pyxel2.9.9のheadless描画・全テスト・最終章通しテストに成功。GUIで自然進行する手動難易度テストは実施していない。
43. **PC Browser**: Edge Chromiumで実際のPyxel/Pyodideを起動。4新規Actionの成功／失敗、演出、7種HUNTのlocalStorage SAVE/LOAD、従来状態異常の計14ケース群を確認。
44. **Smartphone Browser**: Edge ChromiumのPixel7タッチエミュレーションで同じ14ケース群を確認。iOS Safari・スマートフォン実機では未実施。既存D-PAD/A/BのWeb入力と終盤操作の回帰も確認。
45. **audio freeze回帰**: 実AudioContextをsuspendedにし、resumeを拒否させ、visibilitychange/blur/focus/pageshowを発行。Pyxel音声再生と再生位置取得が失敗する状態でも敵の状態異常演出・進行・保存読込が終了。音声待ちロジックを追加していない。実画面ロックは未実施。
46. **既知の問題・確認範囲**: 重大な進行不能・クラッシュは確認されていない。数値は指定のテスト初期値で、自然進行の難易度・REMEDY需要は今後の実機プレイで評価する。指定のAREA3テーブルにpoison_snakeはないため、通常遭遇で毒を使う敵はAREA2に限定される。毒蛇を独自にAREA3へ追加していない。iOSとGKD実機は未確認。

## 二段階抽選の実測

無状態・生存・無耐性の対象を毎ターン用意し、敵の本来のAction一覧で実際の `Battle.step` を実行。HP等の初期化は検証用の隔離された戦闘内だけで行う。頻度テストは難易度評価ではない。

| 敵 / Action | Action選択 / 10,000 | 付与成功 | Action中の成功率 | 全行動での成功率 |
|---|---:|---:|---:|---:|
| horn_rabbit / double_attack | 991 | — | — | — |
| blood_bat / double_attack | 2,524 | — | — | — |
| poison_snake / poison_bite | 2,524 | 1,159 | 45.92% | 11.59% |
| ghost / confusion_touch | 2,010 | 716 | 35.62% | 7.16% |
| mummy / paralyze_grab | 2,010 | 716 | 35.62% | 7.16% |
| dark_wisp / sleep_spell | 1,566 | 718 | 45.85% | 7.18% |
| warlock / sleep_spell | 476 | 207 | 43.49% | 2.07% |

## 必須CASE 1～64対応

| CASE | 確認と結果 |
|---|---|
| 1～4 | 18通常/25全ID、ID重複なし、7種の正しいID、表示名変更でもID・Action維持。新規テスト成功。 |
| 5～12 | 指定7Spriteを既存Bank0から読み取り、画像が空でないことを確認。DRAGONは守護者3専用のまま。画像ファイルは完全一致。 |
| 13～16 | B1の変更なし、B2/B3ツノウサギ、連撃10%、AREA1全Actionに状態異常なし。 |
| 17～21 | B6蛇、実際の毒の牙、物理0.90倍、毒成功/失敗、3tickと自然解除、味方アイコンと短い表示、REMEDY。 |
| 22～25 | B9ゴースト、実際の混乱の接触、混乱分岐とUses/ITEM/カテゴリ/成長記録非消費。 |
| 26～29 | AREA3ミイラ、実際のマヒのつかみ、skip時Uses/ITEM非消費。 |
| 30～34 | ダークウィスプ/ウォーロックの睡眠成功/失敗、無ダメージ、通常/毒で起床、REMEDY、自然解除。 |
| 35～39 | B11～B14の指定候補を多数回実抽選。制御状態排他を実際の敵行動で確認。 |
| 40～43 | B15通常遭遇なし、守護者3連戦/泉/デーモンの通し進行、B15 HUNTのウォーロック生成・保存復元。 |
| 44～49 | 新規全7種HUNT、Action/Status引継ぎ、HP/STR/DEF補正、JSONとブラウザ保存読込、同一ID維持。 |
| 50～52 | 旧データから51HUNTセーブを現在データでLOAD、ID/元階維持、save_version=1。 |
| 53～54 | 既存11体の全レコード・Action weight・既存共通Action11定義が完全一致。 |
| 55～60 | B5/B10ボス・守護者・デーモン・ロードオブエリシオン・5回全滅再挑戦の既存通し確認に成功。 |
| 61～64 | 結果処理・閃き・REMEDY・RUNの全テスト回帰に成功。 |

## 描画・マップ・配布物

- 55ファイルのハッシュ一致。全rpgコード、既存マップ・画像・パレット・音声・成長/アイテム/セーブ/クエスト定義を維持。
- 新規7体の2×2配置、および4状態の付与表示を6スクリーンショットで確認。96文字描画呼出しで160×120画面内に収まることを確認。既存Icon/Effectを使用。
- 終盤通し: 同一SessionでB10→B15守護者3連戦→泉→デーモン→献上→最終戦→ENDING。5回の実全滅・再挑戦も成功。D-PAD/A/B操作、音声完全失敗でも進行。最終章84,236文字描画呼出しに収まりを確認。
- `dist/game.html`更新。埋込み全ソース・JSON・素材の現行ファイルとの一致、B5/B10通常遭遇、B15通常遭遇禁止、ゲームパッド、無音最終戦・ENDINGを確認。
- `verification/packages/skill_seekers_gkd.zip`更新。60エントリ、全ゲームファイルと一致、save/を同梱しない。GKDは既存save/を残してゲームファイルを上書き更新する。通常プレイの状態異常は今回から自然発生する。
- GKDのPython3.11向け構文確認は30個のrpgモジュールすべて成功。パッケージ確認の結果は `verification/enemy_roster_package.json` に記録。

## 再実行と成果物

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_enemy_roster.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_final_chapter.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_web.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_web_build.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_statuses.py --playwright-path verification/backups/quest_spawn/browser_deps --fixture tools/browser_enemy_roster_case.py --base-fixture tools/browser_status_case.py --expected-count 14 --output verification/enemy_roster_browser.json
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd.py
```

抽選・保護確認: `verification/enemy_roster.json`。実ブラウザ: `verification/enemy_roster_browser.json`。終盤: `verification/final_chapter.json`。更新前のテスト用定義: `tests/fixtures/enemy_roster_before.json`。実セーブの内容は含めない。
