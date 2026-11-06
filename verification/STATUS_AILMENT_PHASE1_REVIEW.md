# Status Ailment System Phase 1

確認日: 2026-10-12。毒・マヒ・睡眠・混乱を、PLAYER/Enemy共通の戦闘限定システムとして追加。既存のeffectsとは別に保持し、現行Enemy/PLAYER Skillへは割り当てていない。

## 完了報告（指定45項目）

1. **定義ファイル**: `data/statuses.json`。poison/paralyze/sleep/confusionの固定IDをキーとし、name、duration、icon_id、固有数値を保持。ローダーは`rpg/statuses.py`。
2. **保持構造**: Character/Enemyの`statuses: dict[str,int]`。例`{'poison':3,'sleep':2}`。既存BUFF/DEBUFFの`effects`とは別。残り数はラウンド数ではなく本人ターン数。
3. **付与API**: `rpg.statuses.apply_status(target,status_id,chance=100,rng=None,definitions=None)`。Battle内は`battle.apply_status`を使うとメッセージと表示イベントも記録。表示名で条件分岐しない。
4. **status_chance**: 0～100の百分率。0は失敗、100は耐性がなければ確定。中間はrng.randomで1回抽選。KO・未知ID・別制御状態・immunityは抽選前に拒否。EnemyActionの省略値は100。
5. **耐性拡張**: `status_resistances={'poison':50}`なら付与率を半分、`status_immunities=('sleep',)`なら無効。欠落や不正な耐性値は0扱い。Enemy.from_definitionは将来の同名データもコピー可能。全既存敵・ボスへの耐性割り当てはなし。
6. **毒率**: 最大HP×0.05を整数切り捨て、最低1。通常のDEF/MDEF/GUARD、能力補正を通さない。最終ボスの既存バリアだけは維持して遮断。
7. **毒duration**: 3tick。再付与は3へ戻るだけで割合は積み上がらない。
8. **毒タイミング**: 本人の通常／阻害／混乱行動後に1tick。その後durationを減らす。別人のターン、ラウンド境界ではtickしない。KO済みにはtickしない。
9. **マヒ失敗率**: 35%。`statuses.json`のskip_chance=0.35で編集可能。
10. **マヒduration**: 3本人ターン。成功／失敗どちらでも1減る。
11. **Uses未消費**: Battle.prepare_turnで実行直前の制御判定を1回だけキャッシュ。失敗なら_party_action/_enemy_actionを呼ばないためUses・ITEM・使用記録を消費しない。許可時は既存行動をそのまま実行。演出の事前確認でも再抽選しない。
12. **睡眠duration**: 2本人ターン。本人の行動をskipし、Uses/ITEM未消費。本人ターン2回で自然解除。
13. **Damage起床**: 共通damage_hpによる実HP減少で即時解除。物理・魔法・全体・連撃・反撃は既存_damageから同じHP減少経路へ接続。0減少では起床しない。本人ターンより前に起床すれば元の入力済み行動を実行可能。
14. **毒起床**: 毒も同じHP減少経路を使う。POISON＋SLEEPならその本人ターンの行動はskip→毒で起床→次の本人ターンから行動可能。
15. **混乱duration**: 2本人ターン。攻撃でも何もしなくても減算。
16. **混乱倍率**: STR×0.75。既存の物理攻撃補正・被ダメージ計算を再利用。新Skillではなく専用処理。
17. **PLAYER抽選**: 生存敵40%、別の生存味方40%、何もしない20%。本人は除外。他の味方がいない場合の味方攻撃枠は何もしない。混乱中はコマンド選択を自動で省く。
18. **Enemy抽選**: 同じAPIで生存PLAYER40%、別の生存Enemy40%、何もしない20%。単独Enemyの味方攻撃枠は何もしない。味方撃破でも通常VICTORY判定へ進む。
19. **Uses/成長**: _party_actionを呼ばず、Skill Uses、ITEM、used_skills、category_uses、growth_points、MASTEREDを更新しない。混乱攻撃を閃き用使用カテゴリへ登録しない。通常の戦後ランダム成長自体は既存仕様のまま。
20. **制御排他**: paralyze/sleep/confusionのいずれか1つだけ。別の制御状態を追加しようとすると失敗。poisonは併用可能。
21. **refresh**: 同一状態は標準durationへ更新し、倍率・効果量を累積しない。全制御状態の組み合わせとrefreshをテスト。
22. **REMEDY**: Inventory.useへ治療を実装。戦闘ITEM一覧・対象選択・予約個数の処理へ接続。使用者の1行動を消費し、成功時のみ1個消費。治療対象が行動前に既に治っていれば無駄に消費しない。
23. **治療対象**: 生存PLAYERのpoison/paralyze/sleep/confusionを1個で全解除。POISON＋Controlの2状態も全解除。
24. **治療しない効果**: effectsにあるWEAKEN/ARMOR BREAK/SLOW/POWER UP/FOCUS/GUARD UP等。HP0は使用不可。状態なしは「今は治す状態異常がありません」で未消費。
25. **アイコン座標**: game.pyxres Image Bank 2、各8×8。poison(192,0)、paralyze(200,0)、sleep(208,0)は既存素材。confusion(224,0)の「?」だけ未使用セルに追加。透過色0、既存4色。Pyxel editorで編集可能。
26. **PLAYER描画**: Sprite左のX=82＋演出オフセット、Y=13+16×index+3。最大2個横並び。地面と同じ色に埋もれないよう暗い下地で表示。HP0はKO Sprite優先。
27. **Enemy描画**: Sprite左9pxの位置へ最大2個を縦並び。2×2配置の隣の敵や背景帯を避ける。最終ボスは専用48×48画像のboundsを基準に表示。死亡中はアイコンを表示しない。
28. **KO clear**: damage_hpでHP0となった時点で全Statusを解除。Enemyも同じ。REVIVE/PHOENIX ASHは状態なしで復帰。
29. **戦闘終了clear**: 既存Battle.clear_effectsへStatus clearを追加。VICTORY/DEFEAT/DRAW/settleで一括解除。回復・次の戦闘開始もCharacter.reset_battle_stateで解除。
30. **RUN clear**: 成功時の既存clear_effects経路で解除。逃走率・ボス逃走不可・失敗時の既存敵ターン処理は変更なし。
31. **Final Retry clear**: 最終戦のcheckpointコードは変更していない。終了時解除＋新戦闘開始時resetにより一時状態を持ち越さない。状態を付与して敗北・再挑戦を3回繰り返し、毎回Statusなし、アムリタあり、バリアありを確認。
32. **Enemy Action接続**: EnemyActionへstatus_id/status_chanceを追加。physical/magicへ付けるとダメージ処理後に生存対象へ1回付与。type='status'はダメージなしで付与。1対象への連撃で状態を何度も抽選しない。DEBUG/TESTでdamage＋poison、status-onlyの4状態を検証。
33. **既存Enemy未割り当て**: data/enemies.jsonとdata/enemy_actions.jsonは変更前ハッシュと一致。11通常敵・7ボスのactions/weightはそのまま。
34. **PLAYER Skill追加なし**: data/skills.json、Skillクラスの仕様、成長率のデータを保持。
35. **CURSE保留**: 共通API・データは4IDのみ受け付ける。以前のcurse/weak予約アイコンは素材を保持しただけで、呪いのルールはなし。
36. **即死保留**: INSTANT DEATH、PETRIFY/SILENCE/BLINDなど追加状態は実装していない。
37. **SAVE**: rpg/save.pyがハッシュ一致、SAVE_VERSION=1を維持。Status・耐性フィールドは既存SaveDataに追加しない。実ブラウザでlocalStorageの書き込み・復元後にStatusがないことを確認。
38. **weight不変**: 敵行動の抽選重みと既存選択手順を維持。状態異常なしの通常11行動×15seedと全7ボス×15seed、計270パターンの全状態・メッセージ・乱数が旧コードと一致。
39. **敵能力不変**: 全18敵の能力・固定ID・画像・出現テーブル・HUNT補正を保持。48既存ファイルが変更前ハッシュと一致。
40. **自動テスト**: 最終の全357件成功、82.522秒。今回35件を追加。既存の「蘇生後に架空の状態が残る」描画テスト1件は新しいKO clear仕様に合わせて更新。
41. **PC Python**: Windows/Python 3.14.7/Pyxel 2.9.9の実エンジンをheadlessで確認。9枚のUI描画、文字境界、状態のフレーム演出、REMEDY対象、DEBUGを確認。B10→ENDING、5種類の実全滅再挑戦も成功。
42. **PC Browser**: 実Edge Chromium/Pyodideで10グループの状態・治療・KO・逃走・localStorage復元を検証。入力連打でも演出中は二重stepせず、音声使用不能でも完了。JSエラーなし。
43. **Smartphone Browser**: Edge ChromiumのPixel 7タッチ端末エミュレーションで同じ10グループ成功。物理スマートフォン/iOS Safariの実機確認ではない。
44. **audio freeze**: 両ブラウザの実AudioContextをsuspendedにし、resumeも意図的に失敗させた。Pythonのplay/playm/play_posも失敗させた状態で進行。visibilitychange/blur/focus/pageshowも通知。新Status演出は6フレーム・最大2秒のタイマーのみ。
45. **既知の問題／限界**: 進行不能・状態持ち越し・二重消費は検出されなかった。既存Enemyへ未割り当てなので通常プレイでの発生頻度・ボス耐性の体感評価は未実施。iOS Safari実機の画面ロックとPixel2実機の今回の演出確認は未実施。

## 必須ケースの結果

| CASE | 結果・検証 |
|---|---|
| 1～6 | 毒付与、アイコン、5%・最低1、3tick、KO/DEFEAT/VICTORYと戦闘終了解除を確認 |
| 7～11 | マヒ付与、失敗/成功、Uses/ITEM未消費、本人3ターン。敵側でも同じ阻害/自然解除 |
| 12～18 | 睡眠skip、2本人ターン、Uses未消費、物理/魔法/共通damage起床、順番前の起床、毒起床を確認 |
| 19～26 | 混乱コマンド選択の自動省略、Uses/ITEM/成長記録なし、敵/別味方/idle、自分・死亡者除外、2本人ターンを確認 |
| 27～29 | 敵の3分岐、敵同士の攻撃、単独Enemyのidle fallbackを確認 |
| 30～33 | 制御状態の全組み合わせ排他、同一refresh、POISONとの併用を確認 |
| 34～42 | 各状態・2状態をREMEDY1個で治療、effectsは保持、状態なしとKOは未消費。入力段階でも対象を絞る |
| 43～45 | 共通ダメージKOでStatus clear、毒KOも通常反応→KO、PHOENIX ASH/REVIVE後は状態なし |
| 46～48 | RUN成功、VICTORY、通常全滅、最終戦3回再挑戦で残存なし |
| Enemy Action連携 | TEST-only状態行動とダメージ＋毒を実行。通常敵のファイルは変更なし |
| 49～55 | 4アイコン、POISON＋Control、敵側2個、KO優先を実描画とテストで確認 |
| 56～60 | 通常戦闘、heavy/double/area、敵GUARDの既存テスト成功。状態なし270パターンも一致 |
| 61～63 | HUNT生成・SAVE/LOAD、B5/B10の通常遭遇とボス戦の既存テスト成功 |
| 64～67 | 同Sessionの守護者3連戦→泉→デーモン→アムリタ→最終戦→ENDING、5敗北経路からの再挑戦を確認 |
| 68～69 | RESULT・閃き・入れ替え、既存SAVE/LOADテスト成功。Web埋込み終盤も成功 |

## 状態・表示の補足

- 状態判定は、演出前のprepare_turnと実行stepで同じ結果を使う。演出フレームを増やしても制御確率・damage・Usesを再評価しない。
- 混乱中の予約は内部Action(kind='STATUS')。治療が先に成功して混乱が消えた場合はGUARDへ戻り、意図しないSkill消費を避ける。
- 毒tick、阻害、付与、起床に短いStatus表示を使う。HP減少・Enemy撃破・KOは既存reaction/death/RESULTの経路を使用。メッセージの1行待ち時間と早送りは変更なし。
- RUNは従来のパーティ逃走コマンドを維持。失敗時に新しいPLAYER本人ターンや追加の毒tickを作っていない。
- ダンジョン毒沼は従来の探索ダメージのまま。新しい戦闘中POISONとは別で、探索へStatusを持ち越さない。

## 素材・配布・確認限界

- Image Bank 2の(224,0)から8×8だけを追加。Image 0/1、全Tilemap、既存Image 2、Sound/Musicを内容比較して保持を確認。
- dist/game.htmlを再生成し、全rpg・JSON・素材と埋込み内容の一致を確認。
- Pixel2 ZIPを最新60エントリへ更新。rpg/data/game.pyxresの一致、SAVE除外、全30ゲームモジュールのPython 3.11構文互換を確認。
- 実SAVEは読み書きしていない。PCテストは一時ファイル、実ブラウザは隔離したプロファイルのlocalStorageのみ使用。
- PC GUIの手動通しプレイ、iOS Safari実機、実画面ロック、GKD Pixel2実機は今回の確認に含まれない。

## 実行方法と記録

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_status_system.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_final_chapter.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_web.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_web_build.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_statuses.py --playwright-path verification/backups/quest_spawn/browser_deps
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd.py
```

詳細: status_preservation.json、statuses_browser.json、status_package.json、final_chapter.json。描画: screenshots/status_*.png。
