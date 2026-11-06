# Enemy Action System Phase 1

確認日: 2026-10-11

敵ごとのweight抽選と11種類の共通行動を追加。既存通常敵11体への割り当ては指示どおり。敵総数18、敵の固定ID・表示名・画像・基本能力は変更していない。ボス7体はactions未設定で従来挙動を維持。階層による特殊行動率の固定値やoverrideはない。

## 完了報告（指定41項目）

1. **定義ファイル**: `data/enemy_actions.json`。表示名、type、target、power、hits、modifier、duration、effect_idを保持。
2. **選択処理**: `rpg/enemy_actions.py`の`choose_enemy_action`。実行は`rpg/battle.py`の`Battle._enemy_action`。
3. **敵側データ**: `data/enemies.json`の`"actions":[{"id":"attack","weight":65},{"id":"heavy_attack","weight":35}]`形式。固定IDを持つ同じ敵定義からEnemy.actionsをコピーし、表示名による検索・条件分岐は行わない。
4. **抽選**: 使用可能な定義と正の有限weightを抽出し、`rng.choices`で1行動だけ選ぶ。相対weightなので合計100である必要はない。大きなweightの合計が溢れないよう最大値で正規化。抽選し直しループはない。
5. **fallback**: actions未設定／空、あるいは実行時に有効な候補がない場合、従来のmagic_chanceによるattack/magicへ戻る。従来の「生存対象抽選→magic抽選→ダメージ揺れ」の乱数順も維持。JSONの構造や参照の誤りは読み込み時に明示的なエラーとし、戦闘中の無効候補は除外する。
6. **attack**: 生存者からランダム1人、STR×既存の弱体補正×0.9～1.1。power=1.00、1hit。通常ダメージ処理を使用。
7. **magic**: 同じ対象選択でINTを参照。power=1.00、1hit。既存の魔法ダメージ処理を使用。
8. **heavy_attack**: 単体物理1.35倍、1hit。追加効果・反動はなし。
9. **double_attack**: 単体物理0.60倍×2hit。対象を最初に固定し、KOしたら残りhitを中止。別人へ移さない。キュー消費は1行動。
10. **area_attack**: 生存している味方全員へ物理0.55倍。各対象に既存ダメージ処理を適用。
11. **area_magic**: 生存している味方全員へ魔法0.50倍。既存11通常敵へは割り当てていない。
12. **Enemy GUARD**: 既存のguardingとダメージ計算を再利用。PLAYER GUARDとは解除タイミングだけ異なる。
13. **軽減率**: 敵側の初期被ダメージ倍率は0.50。enemy_actions.jsonのguard.modifierで編集可能。PLAYER GUARDの0.50倍は変更なし。
14. **持続**: guardを実行してから次の自身の行動開始まで。ラウンド境界では解除しない。次の自身の行動で解除してから行動を選ぶ。再度guardを選んだ場合は新しい1行動として防御する。戦闘終了／逃走では解除。
15. **power_up**: 自身の物理攻撃を1.20倍、duration=3。魔法攻撃は強化しない。基本STRは変えない。
16. **weaken**: 生存味方1人の攻撃ダメージを0.85倍、duration=3。既存effectsのweakenを使う。物理・魔法・プレイヤー反撃に適用し、回復量は減らさない。
17. **armor_break**: 生存味方1人にmodifier=0.85、duration=3。味方にはDEFがないため、物理被ダメージを1÷0.85（約1.176倍）として反映。魔法被害には適用しない。既存の敵へのARMOR BREAKは従来のDEF低下を維持。味方DEFの新能力値やSAVE項目は追加していない。
18. **slow**: 生存味方1人の行動速度を0.80倍、duration=3。既存battle_agility/effectsを利用し、既に決定した行動順は変えず次ラウンドから反映。
19. **重複**: 既存PLAYER Skillと同じeffects辞書を使い、同じ効果は上書きと期限更新。倍率を累乗して積み上げない。異なる効果は共存。duration=3には付与したラウンドを含み、ラウンド終了ごとに減算し、0で消える。戦闘終了時も一括解除。
20. **slime**: attack 100。
21. **bat**: attack 100。
22. **goblin**: attack 90 / heavy_attack 10。
23. **wisp**: attack 30 / magic 70。
24. **golem**: attack 85 / heavy_attack 15。
25. **skeleton**: attack 100。
26. **mage**: attack 20 / magic 80。
27. **iron_golem**: attack 75 / guard 25。
28. **berserker**: attack 65 / heavy_attack 35。
29. **assassin**: attack 70 / double_attack 30。
30. **stone_beast**: attack 65 / guard 20 / area_attack 15。
31. **ボス維持**: 全7体にactionsを割り当てず従来処理を使用。実装前後105回（7体×15seed）の行動ログ・HP減少・乱数状態ハッシュが一致。ボス固有フェーズAIは追加していない。守護者画像はKNIGHT→CYCLOPS→DRAGONを維持。最終戦の48×48描画、バリア、アムリタ、チェックポイントも維持。
32. **enemy_id**: 全18件の文字列を維持。Enemy.from_definitionで固定IDとactionsを保持。表示名変更テストも成功。
33. **SAVE**: SAVE_VERSION=1と現行schemaを維持。rpg/save.pyはハッシュ一致。敵行動、選択状態、アニメーションは保存しない。HUNT保存項目も同じ。
34. **状態異常**: POISON/PARALYZE/SLEEP/CURSE、持続ダメージ、行動不能、成功率・耐性は追加していない。REMEDYも変更していない。
35. **敵追加**: 新enemy_id・新敵・新画像なし。18件の定義を前後比較し、通常敵11件へのactions追加以外に差なし。
36. **自動テスト**: 最終コードで全310件成功。今回の敵行動専用24件を含む。専用ケースは下記参照。
37. **PC Python**: Windows/Pyxelの実エンジンを使うheadlessテストでダメージ・入力・描画・KO・RESULT・SAVEを確認。B10からENDINGまで同じSessionで進む統合テストも成功。
38. **PC Browser**: 実Edge Chromium/Pyodideの隔離プロファイルで全11行動、無音での全滅→拠点帰還を確認。ブラウザエラーなし。
39. **Smartphone Browser**: 実Edge Chromium/PyodideのPixel 7タッチ端末エミュレーションで同じ全11行動を確認。スマートフォン実機とiOS Safariの確認ではない。
40. **audio freeze**: 実ブラウザのAudioContextをsuspendedにし、resumeも意図的に失敗させた状態でPC/タッチ両方を検証。Pythonのplay/playm/play_posも使用不能にした状態で進行成功。visibilitychange/blur/focus/pageshowも通知。新行動は音声状態を参照せず、既存エフェクトはフレーム・最大2秒の期限で進む。
41. **既知の問題／限界**: 今回の機能に関する進行不能は検出されなかった。iOS Safari実機、実際の画面ロック、GKD Pixel2の確認は未実施。序盤の戦闘の体感と難易度は外部プレイテストが必要。全体魔法とBUFF/DEBUFFは基盤・テストのみで、現行敵には未割り当て。

## 必須ケースの確認

| CASE | 結果・主な検証 |
|---|---|
| 1～4 | fallbackの80パターンで旧式計算・対象・乱数一致。weight抽選、固定ID、名前独立性を専用テストで確認 |
| 5～7 | 強攻撃1.35倍、連撃同一対象2hit、初撃KOで他人へ移さないことを確認 |
| 8～10 | 全体物理／魔法の倍率、生存者のみへの適用、KO除外を確認 |
| 11～14 | 敵GUARDの半減・ラウンド跨ぎ・次行動での解除・終了時解除とPLAYER GUARD維持を確認 |
| 15～20 | 各BUFF/DEBUFFの実ダメージ／次ラウンド順序、期限切れ、上書き、異種共存、非累積を確認 |
| 21～25 | 指定11体の全weight、約65:35の10,000回抽選、JSONのweight／倍率変更による反映を確認 |
| 26～28 | slime/bat/skeletonは通常のみ、wisp/mageは既存魔法比率、goblin10%・golem15%だけ強攻撃。体感評価は未実施 |
| 29～33 | 7ボスの旧挙動105回一致、守護者3連戦→泉→デーモン→アムリタ→最終戦→ENDINGの通し検証、5種類の全滅再挑戦に成功 |
| 34～36 | 実際のHUNT生成とSAVE/LOADで、行動設定・固定ID・生成された能力・SaveDataが一致。Lv1 wisp／Lv2 iron_golem／Lv3 stone_beastの契約で確認 |
| 37～41 | 既存被弾・KO・撃破・RESULT・閃き・入れ替えテスト成功。特殊攻撃のKO表示順も専用ケースで確認 |
| 42 | 実ブラウザPC/タッチ相当で全11行動を音声使用不能にして確認。全滅しても正常帰還 |
| 43 | 実AudioContext suspend/resume失敗下で成功。実機iOSの画面ロックは未確認 |

## 検証の実行方法

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools\verify_final_chapter.py
.\.venv\Scripts\python.exe -B -X utf8 tools\build_web.py
.\.venv\Scripts\python.exe -B -X utf8 tools\verify_web_build.py
.\.venv\Scripts\python.exe -B -X utf8 tools\verify_browser_enemy_actions.py --playwright-path verification/backups/quest_spawn/browser_deps
```

- 最終ユニットテスト: 310件 / 81.279秒 / OK。
- 変更禁止の既存40ファイルはSHA-256一致。出現設定、Skill、成長、TRZ、HUNT、SAVE、イベント、最終戦チェックポイント、全マップ・画像・音声等を含む。
- データ保全: 全18敵のactions以外の全項目が一致。
- `verify_final_chapter.py`: Phase 6Aの310移動・22戦闘、同Session B10→ENDINGと5種類の実全滅からの再挑戦、表示境界検査成功。準備済みパーティを使う進行テストであり、自然育成のバランス評価ではない。
- Web最終パッケージのコード・JSON・画像・音声一致と、無音の終盤進行・最終戦再挑戦を確認。
- 実ブラウザの詳細: `verification/enemy_actions_browser.json`。
- データ保全・HUNTの詳細: `verification/enemy_actions_preservation.json`。
- 実ブラウザは隔離した一時プロファイルを使用し、ユーザーのブラウザSAVEや実セーブファイルは変更していない。

## セルフレビュー

既存被弾テストで、対象抽選を整数へ変えると従来の対象オブジェクトを返すテストと互換性がなくなることを検出。対象オブジェクトによる従来方式を維持し、描画位置だけを後から求める形へ修正した。特殊行動でKOした際は、効果表示→ノックバック→KO画像の順を保ち、途中でKO画像から通常画像へ戻らないよう補正した。

敵の効果表示は既存素材を使用する。連撃は実行hit数だけ反復し、全体行動は実際の対象だけに描く。演出はダメージを再計算せず、音声終了を待たない。新しいアニメーション素材は作成していない。
