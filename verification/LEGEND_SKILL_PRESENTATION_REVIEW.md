# LEGEND SKILL PRESENTATION PHASE 確認報告

LEGEND 8技に個別の演出を追加しました。RARE 6系統・通常技の演出と、技の性能・戦闘ルール・音声対策・SAVEを維持しています。素材は既存 `game.pyxres` の空き領域へ追加し、Pyxel Editorで編集できます。

本報告の「変更前」は今回のLEGEND作業開始時点です。PARALYZE 50%およびRARE演出実装後の状態を `tests/fixtures/legend_presentation_before.json` に記録して比較しました。以前からの作業ツリーの変更は保持しています。

## 指定46項目

### 1. 今回の変更ファイル

| 区分 | ファイル | 内容 |
|---|---|---|
| ゲーム | `rpg/legend_skill_presentation.py`（新規） | 8専用ID、素材座標、固定Frame・blt中心の描画 |
| ゲーム | `rpg/battle_presentation.py` | LEGEND子状態、Charge→Main→Result→Afterglowの接続とreset |
| ゲーム | `rpg/app.py` | 既存メッセージ枠内のLEGEND技名強調 |
| ゲーム | `rpg/content.py` | rarityに対応した任意presentation_idの検証 |
| 静的データ | `data/skills.json` | LEGEND 8行へpresentation_idのみ追加 |
| 資材 | `game.pyxres` | Image Bank 0の未使用領域へ24フレーム追加 |
| 素材原稿・取込み | `tools/art/legend_effects.svg`, `tools/import_pixel_svg.py`, `tools/add_legend_skill_assets.py`（新規） | 整数グリッドの原稿と一度限りの取込み。ゲーム起動・ビルド時は実行しない |
| 自動テスト | `tests/test_legend_skill_presentation.py`, `tests/legend_presentation_helpers.py`, `tests/fixtures/legend_presentation_before.json`（新規） | 26テスト、性能160比較、RARE20技の描画トレース比較 |
| 既存テスト | `tests/test_rare_skill_presentation.py` | 後続LEGENDメタデータ・空き領域追加を許容し、RARE比較を継続 |
| 検証 | `tools/verify_legend_skill_presentation.py`, `tools/browser_legend_skill_case.py`, `tools/verify_legend_distribution.py`（新規） | 実描画・戦闘状況・Pyodide・配布物検証 |
| 既存検証 | `tools/verify_rare_distribution.py` | RARE行に限定してマッピングを照合 |
| 案内 | `README.md`, 本報告 | 編集場所と確認結果 |
| 配布 | `dist/game.html`, `verification/packages/skill_seekers_gkd.zip`, `verification/packages/skill_seekers_gkd_diagnostic.zip` | 最新ゲームを再生成 |
| 検証記録 | `verification/legend_presentation.json`, `legend_presentation_all_tests.txt`, `legend_presentation_browser.json`, `legend_presentation_freeze.json`, `legend_presentation_packages.json`, `legend_web_build.txt` | 最終結果。診断版ビルドは既存 `gkd_diagnostic_package.json` も更新 |

`verification/screenshots/legend/` に素材一覧と124枚の描画画像を保存しました。途中の `legend_presentation_focused_tests.txt` は最終全体試験以前の記録です。最終件数は全体試験ログを参照してください。

プレイヤーの可変データである `save/` は静的ファイルのハッシュ監査から除外しました。`rpg/save.py` は引き続き保護対象です。セーブの削除・上書き・復元は行っていません。

### 2～3. LEGEND総数・専用ID

LEGENDは8技、8個の専用ID、未割当0です。RARE以下へのLEGEND ID誤割当も0です。

| Skill ID | 表示名 | Presentation ID |
|---|---|---|
| seven_slash | 七連斬 | legend_seven_slash |
| meteor | メテオ | legend_meteor |
| full_heal | 大治癒 | legend_full_heal |
| ragnarok | ラグナロク | legend_ragnarok |
| starfall | スターフォール | legend_starfall |
| miracle | ミラクル | legend_miracle |
| sanctuary | サンクチュアリ | legend_sanctuary |
| time_stop | 時の停止 | legend_time_stop |

### 4～11. 各技の演出

| 項目 | 技 | 実装した表示 |
|---|---|---|
| 4 | 七連斬 | 短いCharge後、向きを変えた斬撃を2Frameずつ6回、専用Finishを2Frame。Finishの対象Flashと小さなShake、結果・残光 |
| 5 | メテオ | 対象周辺の予兆、敵陣上方から8Frameで落下、4FrameのImpact、対象Flash・Shake、爆発余韻 |
| 6 | 大治癒 | 大きなRingと包む光、固定3個の光粒が上昇、短い回復Pulse・余韻。既存計算式を使い、状態治療は追加しない |
| 7 | ラグナロク | 敵陣を横断する2本の大型Slash帯、全対象へ同時Impact、対象Flash・Shake |
| 8 | スターフォール | 固定4個の星が上側から斜めに落下、全対象へ同時Impact、対象Flash・Shake |
| 9 | ミラクル | 生存者へ同一FrameでRing・光柱・光粒を表示し、Party側に大回復の光と余韻。HP0は対象外 |
| 10 | サンクチュアリ | Party側のRingとShield、短い防御Pulse。余韻終了で専用表示を消し、通常のBUFF表示に戻る |
| 11 | 時の停止 | 円形Clock Glyphの針をMain 4Frame目から保持し、敵陣へ1回の短いPulse。その後、成功した対象だけ既存SLEEP演出 |

### 12～15. 技名・Charge・Flash・Shake

12. ChargeとMain中のみ、既存メッセージパネル内に枠・`LEGEND`・技名を表示します。新たな確認入力や名前表示待ちはありません。

13. Chargeは6Frame。Mainは七連斬14Frame、他7技12Frame。Result4Frame、Afterglow4Frameです。既存の踏み込み4Frame・戻り3Frameを含む基本合計は七連斬35Frame（30FPSで約1.17秒）、他技33Frame（約1.10秒）。既存の成功Status表示6Frameなどは別途発生し、今回の通常条件の時の停止は39Frameでした。RAREの基本合計23Frameに対し、約0.33～0.40秒の特別な間を追加しています。

14. ダメージ4技の対象FlashはMain最後の連続2Frameだけ。時の停止はMain 4～5Frame目の1回だけです。全面を白く塗る処理や高速点滅ループはありません。回復・防御は資材内の光とRing、サンクチュアリの1Frame枠Pulseで表現します。

15. ダメージ4技のResult冒頭3Frameだけ `(2,0) → (-2,1) → (1,-1)` pxを使用し、その後0へ戻します。メッセージ枠・技名・ステータスUIは揺らしません。

### 16～21. 全体表示とGameplay分離

16. 全体技は同一Phase・同一Frameで対象を描きます。ラグナロクの帯とスターフォールの4星は敵陣全体で1組だけです。ミラクルは生存者のみ同時表示します。

17. 対象1・2・3・4体でCharge/Main/Result/Afterglowの長さが完全一致する自動テストを実施しました。対象ごとの長い演出Queueは作りません。Damageは既存処理で各対象へ1回、Uses・Cooldown・Growthは技使用1回分です。

18. 時の停止は時計画像の参照先を保持するだけです。毎FrameのApp.update、keyboard.update、Presentation Timer、状態機械は動き続けます。`sleep`・`wait`・pauseループ・音声待ちは追加していません。次Commandへ戻ることも実Appで確認しました。

19. MainのFrame Timerで既存 `Battle.step()` を1回呼び、各EnemyのSLEEP Chance・Resistance・Immunity・Control排他を従来どおり判定します。Legend Result/Afterglowの後、既存 `status_visual_events` に入った成功対象だけSLEEP Feedbackを表示します。成功・耐性失敗・免疫・既存PARALYZEの4対象混在、および全失敗を確認しました。

20. 七連斬はVisual7斬撃、Gameplayは合算PowerによるDamage・防御計算1回です。個別7回のDamageに変更していません。結果の数値も1件です。

21. スターフォールは対象数によらずVisual4星。星の描画はDamageを呼びません。全体Magic Damageは既存Logicで各Enemyへ1回です。

Gameplayの呼出しは既存の一度限りの `apply` イベントに接続しています。画像・音声の完了通知は進行条件にせず、各PhaseにFrame上限と既存2秒のwall timeoutを適用します。timeoutを強制した場合も1回だけ処理して解除されます。通常のA連打では固定Frameを維持します。

### 22～28. 資材・編集座標

22. 追加領域はImage Bank 0の `x=0..191, y=128..255`。追加前に全pixelが0であることと、Tilemapから参照されていないことを確認しました。巨大配列・埋込み画像・実行時のpixel生成はありません。整数グリッド・既存の緑系Palette index 0～3を使い、ぼかし・AA・半透明・Gradientはありません。

23. 使用Image Bankは **0** です。

24. 左上座標は次表です。各技の3Frameは横並びです。

| 専用素材 | Frame 0 | Frame 1 | Frame 2 |
|---|---|---|---|
| 七連斬 | (0,128) | (32,128) | (64,128) |
| メテオ | (96,128) | (128,128) | (160,128) |
| 大治癒 | (0,160) | (32,160) | (64,160) |
| ラグナロク | (96,160) | (128,160) | (160,160) |
| スターフォール | (0,192) | (32,192) | (64,192) |
| ミラクル | (96,192) | (128,192) | (160,192) |
| サンクチュアリ | (0,224) | (32,224) | (64,224) |
| 時の停止 | (96,224) | (128,224) | (160,224) |

25. 1Frameは **32×32 px**。光粒や星はこの領域から小さく切り出して使います。

26. 各技 **3素材Frame、計24Frame**。素材Frame数と、七連斬のVisual7斬撃・StarfallのVisual4星・表示時間は別です。

27. RAREはImage Bank 1の `x=0..191, y=96..191` をそのまま保持しました。全Imageの新規領域以外のpixel、全Tilemap、Sound・Musicを変更前ハッシュと照合し一致しています。

28. `pyxel edit game.pyxres` のImage Bank 0で表のセルを描き直し、保存できます。対応は `LEGEND_SPRITES` に集約しています。[素材一覧](screenshots/legend/asset_sheet.png)も参照できます。編集後は既存のWeb/GKDビルドを実行してください。`add_legend_skill_assets.py` は初回取込み記録で、再実行不要です。占有セルがある場合は上書きを拒否します。

### 29～38. 性能・既存仕様・SAVE回帰

29. 8技×5seed×4条件（通常・MASTERED・残りUses1・PARALYZE）＝**160比較、全一致**。メッセージ、全Unitデータ、RNG状態、Outcome、Queue、道具、MASTERED・発見済みSkill、resource/status event、Sound cueを照合しました。8行の静的性能データもpresentation_id以外は完全一致。Power、Damage、Heal、BUFF、Chance/Duration、Uses/max Uses、Cooldown、Target、hits、Growth、Spark、Rarity、RESTOREを変更していません。

30. RARE moduleは作業開始時のハッシュと一致。20技全てのPhase/Frame・offset・Shake・Flash・blt/clip・数値描画トレースも一致しました。BASIC/COMMON/UNCOMMONは既存Phase・素材を使う回帰テストが成功しています。

31. Skill総数 **62**。BASIC3、COMMON18、UNCOMMON13、RARE20、LEGEND8を維持しています。

32. Spark処理・Weightを変更していません。**LEGEND Weight 2** を維持。全技のB1抽選・Weight・所持除外・再取得テストを含め、全体試験が成功しました。

33. B1からLEGEND取得可能な既存仕様を維持しています。自然Sparkを待つ検証はせず、検証用Partyへ8技を付与しました。正式Rosterや確率を変更するDEBUG改変はありません。

34. SAVE schemaを変更していません。presentation_idは静的Skill Dataのみで、演出状態はSAVEに入りません。`rpg/save.py` の変更前ハッシュも一致。

35. **save_version = 1** のままです。

36. 旧Save fixtureのLOAD→再保存が完全一致。PC/touch両Pyodideでそれぞれ、直接LOADとlocalStorage backend経由の2往復を確認しました。診断版もsaveを同梱しません。

37. Persistent Poisonの持ち越し・歩行でtickしないこと・階移動・討伐帰還・KO/復活・SAVE・Final Battleを含む既存回帰テストが成功しました。

38. **PARALYZE行動失敗50%、既存3 Actor Turn** を維持し、Chance・Uses・Growth等のテストが成功しました。CURE・REMEDYも既存回帰とブラウザ10 Statusケースで確認しました。

### 39～43. Audio・Freeze・自動試験・Browser

39. `rpg/sound.py` と既存音声資材を保持。nativeはチャンネル別再生で **playm回避を維持**。Web側の既存経路も維持し、新SEは追加していません。音声通常・停止・例外の各条件で8技が完了します。診断の設定・launcher・コードも一致しています。

40. Battle開始Freeze Regressionは **26,400開始中26,400成功**。固定敵編成、通常抽選、Audio normal/off/failed、Transition bypassで描画とD-PAD/A/Bを確認しました。Windows nativeでの回帰試験であり、Pixel2実機での測定ではありません。[記録](legend_presentation_freeze.json)

41. 全自動テスト **511 / 511成功**（136.849秒）。今回追加は26テストです。[最終ログ](legend_presentation_all_tests.txt)。別途、実描画65戦闘条件・124画像、38,821テキスト座標、63保護ファイル、8技連続80戦で子状態・参照の蓄積なし、Final Retry3回の8技/Uses復元と新規演出stateクリアを確認しました。[描画記録](legend_presentation.json)

42. PC Browserは **Edge Chromium / 実Pyodide 36 / 36成功**。Legend24テスト＋Status10ケース＋旧SAVE2往復。実キーボードDown/Z/X、全8技描画、性能160比較、RARE20描画比較、80連続戦闘を確認。AudioContext suspended・resume拒否でも完了し、pageerror0です。

43. Touch Browserは **Edge Chromium Pixel7タッチエミュレーション / 実Pyodide 36 / 36成功**。同一検証に加え、D-PAD/A/B pointer入力を確認し、pageerror0。スマートフォン実機・iOS Safari・実画面ロックは未確認です。[PC/Touch記録](legend_presentation_browser.json)

### 44～46. 配布物・既知の制限

44. 全体511テスト成功後に **`dist/game.html` を再生成**。埋込み63entry中ゲーム62ファイルが現在のソース・データ・資材と一致。62技/Legend8/Rare20・PARALYZE50を確認し、SAVE/cache/testsを含めません。この更新版を上記PC/touch試験で実行しました。

45. Pixel2通常版 **`verification/packages/skill_seekers_gkd.zip` 更新済み**。63entry・ゲーム62ファイル一致。診断版 **`verification/packages/skill_seekers_gkd_diagnostic.zip` 更新済み**。66entry・同じゲーム62ファイル一致。Python3.11構文互換を検証しました。[配布監査](legend_presentation_packages.json)

| ZIP | SHA-256 |
|---|---|
| 通常版 | `56bdca075730a2bad796d0b63aebe306b533ce31a5a18cea93300fc7d505333d` |
| 診断版 | `741eeb75e3ff2f464f9aeeb7f326e04b2cd8179b730b4eef51d2362d7947cd63` |

両ZIPはsaveを含みません。GKDへコピー更新するときは既存の `save/` を残してください。今回の作業では本体への転送や公開は行っていません。

46. 自動検証で残る不具合はありません。**GKD Pixel2実機の速度・視認性・音声デバイス、スマートフォン実機/iOS Safariは未確認**です。負荷検証は固定Sprite・80連続戦での参照解放までであり、Pixel2のFPSやメモリ使用量の実測ではありません。既存のプロジェクト `.venv` は参照先Python314がなく起動できないため、作業では既存の `C:\temp\mypyxel\adventure_test\.venv-verify\Scripts\python.exe`（Python3.12.14 / Pyxel2.9.9）を使用しました。

## 必須CASE 1～79の対応

全CASEは自動検証に対応しています。BattleのBoss描画は、正式Enemy定義を使った合成高HP条件で演出を最後まで観察したものです。自然進行の全Boss攻略や実機確認を示すものではありません。

| CASE | 確認内容 | 検証根拠・結果 |
|---|---|---|
| 1～4 | Legend8・全専用ID・未割当0・誤割当0 | `test_exact_eight_dedicated_ids_and_sixty_two_roster` / ID検証、成功 |
| 5～9 | 七連斬使用・連撃・Visual多Hit・Damage合算1回・性能一致 | `test_seven_visible_strokes_but_single_damage_defense_and_number` / 160比較 / 実描画、成功 |
| 10～14 | Meteor使用・上方落下・Impact・Shake・性能一致 | `test_meteor_falls_from_above_then_impact_and_two_pixel_shake` / 160比較 / 実描画、成功 |
| 15～18 | 大治癒・専用豪華表示・Heal一致・治療なし | `test_full_heal_matches_formula_and_never_cures_status` / 実描画 / 固定Frame比較、成功 |
| 19～23 | Ragnarok使用・全敵・定時間・個別Damage・Uses1 | `test_ragnarok_and_starfall_damage_once_per_target_resources_once` / 対象1～4体Timer / 実描画、成功 |
| 24～27 | Starfall使用・複数星・Projectile/Damage分離・全敵Damage | 上記Damage試験＋ `test_starfall_has_four_fixed_projectiles_independent_of_target_count`、成功 |
| 28～32 | Miracle使用・同時表示・生存者Heal・蘇生なし・量一致 | `test_miracle_simultaneous_living_heal_no_revival_or_cure` / 160比較 / 実描画、成功 |
| 33～37 | Sanctuary使用・Party Barrier・倍率・Guard family・残留なし | `test_sanctuary_preserves_point_fifty_five_guard_family_and_no_residual_art` / 実描画、成功 |
| 38～47 | Time stop使用・停止風・update継続・各敵Sleep・成功Feedback・失敗/耐性/免疫/排他・Uses1 | Clock保持試験、混在/全失敗試験、実App keyboard更新・Command復帰、成功 |
| 48～52 | A連打・高速送り・最低Frame・State維持・次Command | `test_all_eight_real_updates_fast_input_exactly_once_and_minimum_frames` / Command・Victory・実Browser入力、成功 |
| 53～57 | Audio通常/停止/失敗・native playm回避・Freeze | 8技Audio試験 / 既存GKD音声テスト / 26,400開始、成功 |
| 58 | 通常戦 | 全8技の実App描画、成功 |
| 59 | HUNT | 実QUEST HUNT構築・Starfall演出、成功 |
| 60 | B5 Boss | 正式guardian定義×8技、成功 |
| 61 | B10 Boss | 正式skill_keeper定義×8技、成功 |
| 62 | B15守護者 | 正式sentinel_armor/speed/mind各定義×8技、成功 |
| 63 | Demon | 正式depth_lord定義×8技、成功 |
| 64 | Lord of Elysion | 正式定義×8技（演出観察はBarrier解除条件）と既存Final barrier/Amritaテスト、成功 |
| 65 | Final Retry | 8技を付与したCheckpointで3回の実再挑戦・Uses/roster/state復元、成功 |
| 66～68 | Skill62・Legend8・Rare20 | Roster Counter / Web・両ZIP監査、成功 |
| 69 | Legend性能一致 | 160比較＋静的8技Data差分、成功 |
| 70 | Rare演出維持 | 20技全描画トレース・Rare module/素材ハッシュ、成功 |
| 71 | Common維持 | 既存Phase/素材回帰＋静的Skill Data一致、成功 |
| 72～73 | Enemy・Map維持 | 静的Enemy/Mapファイル保護ハッシュ・全Tilemap一致、成功 |
| 74～75 | Save/Load・旧Save | 既存Save試験・新Legend schema試験・両Browser旧Save2往復、成功 |
| 76 | Persistent Poison | 既存持ち越し回帰一式、成功 |
| 77 | Paralyze50% | 既存Balance回帰一式・配布Data一致、成功 |
| 78～79 | Cure・Remedy | 既存Roster・Status・Persistent Poison回帰／両Browser Status10ケース、成功 |

## 再検証

ゲームの通常起動・Editor保存後には素材取込みを実行しません。自動試験は使用可能なPython環境で次を実行できます。

```text
python -m unittest discover -s tests
python tools/verify_legend_skill_presentation.py
python tools/verify_legend_distribution.py
python tools/verify_paralyze_freeze.py --output verification/legend_presentation_freeze.json
python tools/verify_browser_statuses.py --fixture tools/browser_legend_skill_case.py --base-fixture tools/browser_status_case.py --unit-fixture tests/test_legend_skill_presentation.py --extra-fixture tests/fixtures/legend_presentation_before.json --extra-fixture tests/fixtures/rare_presentation_before.json --extra-fixture tests/test_rare_skill_presentation.py --extra-fixture tests/legend_presentation_helpers.py --save-fixture tests/fixtures/skill_foundation_save_v1.json --expected-count 36 --output verification/legend_presentation_browser.json
```

Browser検証はPlaywright・Edgeと公式Pyxel/Pyodide配信へのアクセスが必要です。
