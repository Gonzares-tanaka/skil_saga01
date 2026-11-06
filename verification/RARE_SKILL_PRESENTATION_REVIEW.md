# RARE SKILL PRESENTATION PHASE

実施日: 2026-10-14

RARE 20技へ6共通Familyの戦闘演出を追加した。技性能と既存`effect_id`は維持。
`rpg/battle.py`、状態異常ロジック、SAVE、成長・閃き、Enemy、Boss、Map、音声処理は無変更。
開始時点の未コミット変更と、前PhaseのPARALYZE 50%を保持した。

## 変更ファイル

- `data/skills.json`: RARE 20行へ任意の`presentation_id`のみ追加
- `rpg/models.py`: 静的Skill定義へOptionalフィールド追加
- `rpg/content.py`: 6 ID・RARE限定の検証
- `rpg/rare_skill_presentation.py`: Family、素材座標、固定タイマー
- `rpg/battle_presentation.py`: RARE導入・効果・既存結果の表示、軽いShake、既存Status Feedbackへの接続
- `rpg/app.py`: 対象Spriteだけの短いPalette Flash
- `game.pyxres`: 空のImage Bank 1領域へ6 Family×3 Frameを追加
- `tools/art/rare_effects.svg`, `tools/add_rare_skill_assets.py`: 静的原画と一度だけのインポート。起動・配布buildから呼ばない
- `tests/test_rare_skill_presentation.py`, `tests/fixtures/rare_presentation_before.json`: 26追加テスト、開始時点の技定義・画像/Map/音声ハッシュ
- `tests/test_player_skill_roster.py`, `tests/test_enemy_roster.py`: 今回の演出変更に対応。性能・旧Asset保全は専用試験で継続検証
- `tools/verify_rare_skill_presentation.py`, `tools/browser_rare_skill_case.py`, `tools/verify_rare_distribution.py`
- `tools/verify_paralyze_freeze.py`: 出力先を任意指定できるようにし、ROOT基準の絶対パスにする。既存試行内容は維持
- `README.md`, 本報告、`verification/rare_presentation*.json`, `rare_presentation_all_tests.txt`, `rare_web_build.txt`
- `dist/game.html`, `verification/packages/skill_seekers_gkd.zip`, `skill_seekers_gkd_diagnostic.zip`, `verification/gkd_diagnostic_package.json`
- 実描画画像: `verification/screenshots/rare/`。このディレクトリは従来どおりGit対象外

## Family割当と編集素材

`Skill.presentation_id: str | None = None`。技の`effect`、`effect_id`と分離した静的データ。
未知IDはデータ検証で拒否し、描画側も未設定・未知ID・RARE以外を既存演出へ安全にfallbackする。
SAVEへは保存しない。RARE以外の42技へ新フィールドを追加していない。

すべてImage Bank **1**、**32×32**、**3 Frame**。座標は各Frameの左上。

| Presentation ID | 対象Skill | Frame座標 |
|---|---|---|
| rare_impact | heavy_break | (0,96), (32,96), (64,96) |
| rare_slash | triple_slash, rapid_edge, cleaving_storm, plague_edge | (96,96), (128,96), (160,96) |
| rare_magic | flare, inferno, thunder_bind | (0,128), (32,128), (64,128) |
| rare_dark | drain, nightmare, chaos_spell | (96,128), (128,128), (160,128) |
| rare_heal | heal, renew, revive, cure, purify_wind | (0,160), (32,160), (64,160) |
| rare_support | armor_break, focus, armor_wave, focus_field | (96,160), (128,160), (160,160) |

合計20、未割当0、Family数6、素材Frame数18。
[素材シート](screenshots/rare/asset_sheet.png)は実際の`.pyxres`から書き出したもの。
初回監査で領域全体が色0、Mapから未参照であることを確認してから取り込んだ。
既存画像全3 Bankは追加領域を色0に戻したハッシュが開始前と一致。全Tilemap・Sound・Musicも一致。

## 指定52項目の報告

| # | 項目 | 結果 |
|---|---|---|
| 1 | 変更ファイル一覧 | 上記。既存の制作中変更は保持。 |
| 2 | Skill総数 | 62。追加・削除なし。 |
| 3 | RARE総数 | 20。Rarity内訳も維持。 |
| 4 | データ構造 | SkillのOptional `presentation_id`。静的定義のみ、Gameplay/SAVEから独立。 |
| 5 | 新規ID | rare_impact / rare_slash / rare_magic / rare_dark / rare_heal / rare_support。 |
| 6 | IMPACT対象 | heavy_break。 |
| 7 | SLASH対象 | triple_slash / rapid_edge / cleaving_storm / plague_edge。 |
| 8 | MAGIC対象 | flare / inferno / thunder_bind。 |
| 9 | DARK対象 | drain / nightmare / chaos_spell。 |
| 10 | HEAL対象 | heal / renew / revive / cure / purify_wind。 |
| 11 | SUPPORT対象 | armor_break / focus / armor_wave / focus_field。 |
| 12 | 20技全割当 | 20/20、未割当0、RARE以外の割当0。自動検証。 |
| 13 | .pyxres変更 | game.pyxresの空領域へ6種類・18Frame追加。他のリソースファイルは無変更。 |
| 14 | Image Bank | 1。 |
| 15 | Asset座標 | 上記表。領域x=0～191、y=96～191。 |
| 16 | Frame Size | 全Family 32×32。元素overlayは既存16×16素材。 |
| 17 | Frame数 | 各3Frame、計18。 |
| 18 | 既存Asset上書き | なし。全旧Pixel、全Map、Sound/Musicのハッシュ一致。 |
| 19 | IMPACT概要 | 拡張する衝撃輪→星形Impact→破片の短い余韻。対象Flash 2Frame、1pixel Shake 3Frame。 |
| 20 | SLASH概要 | 太い斜めの軌跡→逆方向を重ねた交差斬撃→細い残像。演出上の複数軌跡はDamage回数を増やさない。 |
| 21 | MAGIC概要 | 使用者へRune集中、その後対象へ拡張Ring。既存fire/lightningを重ね、属性を維持。 |
| 22 | DARK概要 | 暗い外周と渦が3Frameで内側へ収縮。DRAINには同じHEAL素材の小片が対象→使用者へ戻る短い表現。 |
| 23 | HEAL概要 | 明るい光、Ring、上へ動く光粒。CURE/PURIFYはHP数値を増やさず既存治療Feedbackへ接続。 |
| 24 | SUPPORT概要 | 共通の幾何Symbol/Ring/Aura。上向き／下向きの動きを共有素材で表現。 |
| 25 | BUFF / DEBUFF区別 | focus系は通常向き＋上へ移動、armor系は上下反転＋下へ移動。 |
| 26 | 全体表示 | 1つのphase/frameから全対象へblt。対象別の待機キューを作らない。 |
| 27 | 時間非直列化 | 1対象と4対象でRARE導入4、効果9、結果3Frameが同一。対象数でUses/Growth/Cooldownを増やさない。 |
| 28 | Damage + Status順 | RARE攻撃→実行時点の既存Damage/Status解決→Damage数値→成功Statusの既存Feedback。詳細は下記。 |
| 29 | Status成功 | Battleの既存`status_visual_events`だけを使い、rare_feedbackの後にstatus_effect。 |
| 30 | Status失敗 | RARE攻撃とDamageは正常表示。Status Feedbackは出さない。4技すべて成功/失敗を試験。 |
| 31 | Damage KO | 既存ルールが付与を拒否。Status Feedbackなし、既存KO/Victory表示へ進む。 |
| 32 | 多段Gameplay | hitsを合算Powerへ使う既存処理を維持。triple_slash/rapid_edgeはDamage/DEF計算各1回。全体技は対象ごとに各1回。 |
| 33 | RARE20性能比較 | 全62行の新フィールドを除いた定義が完全一致。20技×3Seed×4条件=240比較で結果・状態・RNG・Uses/CD・Growth・MASTERED等が一致。 |
| 34 | COMMON / UNCOMMON | BASIC含め定義・素材無変更。既存skill_effect 9Frameを維持する試験成功。 |
| 35 | LEGEND | 8技すべて既存演出・定義のまま。RAREに全画面Flash/長時間停止/大Shakeを導入せず、次Phaseの余地を残す。 |
| 36 | SAVE schema | 無変更。新フィールドをSAVEへ含めない試験成功。 |
| 37 | save_version | 1のまま。 |
| 38 | Archive / Spark | 62技、BASIC3 / COMMON18 / UNCOMMON13 / RARE20 / LEGEND8。既存発見・習熟・再取得・閃きの回帰成功。 |
| 39 | Persistent Poison | 既存全テスト成功、実装/定義のハッシュ一致。探索持ち越し・歩行Damageなしを維持。 |
| 40 | PARALYZE 50% | 前Phaseの定義と共通判定を維持。固定Seed各10,000回・50%境界・PLAYER/Enemyの回帰成功。 |
| 41 | Battle進行 | RARE20技を実update/drawで使用、1回だけ解決。Command、Victory、既存RUNへ正常進行。100全体RARE戦闘で残存Visual/Target配列なし。 |
| 42 | Boss回帰 | 既存Boss回帰成功。guardian＋heavy_breakの実描画・継続も確認。 |
| 43 | Final Battle回帰 | 最終戦・Retry・Amritaの既存テスト成功。Lordへのinferno（Barrierあり）/chaos_spell（解除後）の実描画・進行も確認。 |
| 44 | Audio停止 | 通常・停止・API例外すべてでRARE進行。Audio完了を待たない。 |
| 45 | native playm回避 | rpg/sound.pyのハッシュ一致。チャンネル別play()の既存テスト成功。nativeへplaymを追加していない。 |
| 46 | Freeze Regression | 既存FORCED/identity_checks/run_trialsを再使用し26,400/26,400成功。通常・音声停止・音声例外・演出bypass・D-pad/A/Bを含む。 |
| 47 | 自動テスト | 485/485成功（既存459＋追加26）、失敗/エラー/skipなし。Webケース・開始ストレス試行は別集計。 |
| 48 | PC Browser | Edge Chromiumの実Pyodideで36/36成功（RARE24＋既存Status10＋旧SAVE2）。実ArrowDown/Z/XでRARE全体技の選択・確定・取消も成功。ページエラー0。 |
| 49 | Touch Browser | Pixel7設定のTouchエミュレーション、実Pyodideで36/36成功。同じRARE選択・確定・取消をD-pad/A/Bのpointer入力で確認。ページエラー0。実機は未確認。 |
| 50 | Web更新 | dist/game.html再生成。62エントリ・61ゲームファイルが現ソースと一致、20技Mapping・PARALYZE 50%を内包。 |
| 51 | Pixel2 ZIP更新 | 通常ZIP62エントリ、診断ZIP65エントリ。ゲーム61件一致、Python3.11構文確認、SAVE/cache/tests除外。診断コード/config/launcherを保持。 |
| 52 | 既知の問題 | このPhase由来の既知ゲーム不具合なし。GKD/Touch実機・画面ロックの実測は未実施。プロジェクト.venvは参照先Python欠落のため別の既存環境で検証。 |

## 解決と表示の分離

既存`Battle.step()`は**Damage→生存確認→Status付与判定→ターン終了→勝敗判定**を同じ実行時点に一度だけ行う。
今回もその処理・順序を変更していない。表示だけをRARE攻撃→解決済みHP差分の数値→成功したStatus Feedbackへ分ける。
Status判定を描画からやり直したり、Feedback終了までルール・勝敗判定を保留したりしない。
純粋なCURE/PURIFYはHP差分なし、解除された対象/Statusのイベントだけを後段へ渡す。

時間は本人の踏み込み4→RARE導入4→RARE効果9→結果表示3→戻り3の標準23Frame、約0.77秒。
通常の標準16Frameに対して約0.23秒追加。既存Status Feedback6Frame、KO/反撃等は必要時のみ追加。
A長押し・連打でこの最低Frame数を飛ばさない。全phaseに既存のwall-clock timeoutも適用し、音声/描画完了通知への依存を作っていない。

RARE描画は固定Spriteのbltが中心。最大4対象、MAGICでも最大12 blt/効果frame。
巨大なSprite配列・動的Pixel生成・無制限Particle・画像コピーをゲームへ追加していない。
静的SVG原画の初回インポート後は、Pyxel Editorで直接素材を変更できる。
100回の全体RARE使用後、弱参照で残るBattlePresentationは現在の1個のみ、Target/Status/HP配列はresetで空。

## 必須CASE 1–85の対応

| CASE | 主な検証 |
|---|---|
| 1–4 | exact_roster_mapping / all_sixty_two_skill_rows |
| 5–8 | 全20技描画 / impact_shake_and_target_flash / Command進行 |
| 9–14 | multislash_damage_and_defense / all_target_duration / 全20技描画 |
| 15–20 | fire_lightning_identity / all_target_blits / 全20技描画 |
| 21–24 | 全20技描画 / heal_renew_revive_and_drain / 240性能比較 |
| 25–34 | cures_dont_heal / heal_renew_revive_and_drain / 全体表示・時間比較 |
| 35–42 | support_up_and_down / support_modifier_duration_and_refresh / 240性能比較 |
| 43–49 | damage_then_successful_status / failed_status / damage_ko |
| 50–58 | all_target_blits / all_target_duration / 240性能比較 |
| 59–65 | real_draws / Command・Victory進行 / 既存RUN・Boss・最終戦・Retry / Boss実描画 |
| 66–68 | real_draws_spam_minimum_frames / wall_timeout |
| 69–73 | stopped_and_failed_audio / GKD既存テスト / 26,400開始 |
| 74–85 | 定義全比較・保全ハッシュ / Roster・Save・旧Save・Persistent Poison・PARALYZE・治療の既存回帰 |

## 証跡と再実行

- `tests/fixtures/rare_presentation_before.json`: 開始時点の全62技、保全ハッシュ
- `verification/rare_presentation_all_tests.txt`: 485件の全試験ログ
- `verification/rare_presentation.json`: 69描画画像、9,686件の文字範囲検査、保全60ファイル、Boss描画
- `verification/rare_presentation_freeze.json`: 26,400開始の回帰結果
- `verification/rare_presentation_packages.json`: 全配布ソース照合、ZIPハッシュ
- `verification/rare_presentation_browser.json`: PC/Touch各36件、実入力、音声suspended、旧SAVE/localStorage、エラー0

実行環境: Windows / Python3.12.14 / Pyxel2.9.9。
使用Python: `C:\temp\mypyxel\adventure_test\.venv-verify\Scripts\python.exe`。

```powershell
python -m unittest discover -s tests -v
python tools/verify_rare_skill_presentation.py
python tools/verify_paralyze_freeze.py --output verification/rare_presentation_freeze.json
python tools/build_web.py
python tools/build_gkd.py
python tools/build_gkd_diagnostic.py
python tools/verify_rare_distribution.py
python tools/verify_browser_statuses.py --fixture tools/browser_rare_skill_case.py --base-fixture tools/browser_status_case.py --unit-fixture tests/test_rare_skill_presentation.py --extra-fixture tests/fixtures/rare_presentation_before.json --save-fixture tests/fixtures/skill_foundation_save_v1.json --expected-count 36 --output verification/rare_presentation_browser.json
```

通常ZIP SHA-256: `8f29ddeaa8de79e2e3b4b4b5f4853e66835a275f242a43f07920e8dc3f3eedd2`

診断ZIP SHA-256: `270fb48f4c4113b12af911b100274101077a188f157192e6f8e03884be22cc71`

コミット・Push・公開デプロイは実施していない。
Pixel2へは既存フォルダへ上書き/結合し、既存`save/`を保持する。配布物にSAVE削除処理を追加していない。
