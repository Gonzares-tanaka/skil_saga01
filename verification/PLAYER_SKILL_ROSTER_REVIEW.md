# PLAYER SKILL ROSTER EXPANSION 検証報告

実装日: 2026-10-12。既存31技のデータを維持し、指定31技を追加。プレイヤーのセーブにはアクセスせず、合成セーブと隔離ブラウザのみ使用。

## 1–2. 総数とRarity

| Rarity | 既存 | 追加 | 合計 |
|---|---:|---:|---:|
| BASIC | 3 | 0 | 3 |
| COMMON | 10 | 8 | 18 |
| UNCOMMON | 5 | 8 | 13 |
| RARE | 10 | 10 | 20 |
| LEGEND | 3 | 5 | 8 |
| TOTAL | 31 | 31 | 62 |

## 3–6. 新規31技の全定義

Status Chanceは0–100の百分率。Damage + Statusは既存データ形式の`effect: damage`と`status_id/status_chance`の組み合わせ。Status Cureは`effect: cure`。指定BUFFは対応する既存effectを共有する。Scalingは防御・魔防・既存BUFF等を適用する前の式。全技hits=1。

### 3. COMMON 追加8技

| skill_id / name | type / effect / target | Scaling または modifier / duration | Status / Chance | Uses / CD | effect_id | field | RESTORE Cost / Uses | MASTERED報酬 |
|---|---|---|---|---|---|---|---|---|
| `sweep` / なぎ払い | physical / damage / all_enemies | STR ×0.75 | — | 12 / 1 | slash | 不可 | 2 / 6 | 再取得Damage ×1.2 |
| `flame_wave` / 火炎波 | magic / damage / all_enemies | INT ×0.85 | — | 10 / 1 | fire | 不可 | 2 / 5 | 再取得Damage ×1.2 |
| `venom_strike` / 毒撃 | physical / damage / enemy | STR ×1.4 | POISON / 35% | 12 / 1 | pierce | 不可 | 2 / 6 | 再取得Damage ×1.2 |
| `sleep_spell` / スリープ | support / status / enemy | Damageなし | SLEEP / 45% | 8 / 2 | debuff | 不可 | 2 / 4 | 記録のみ |
| `group_aid` / 応急陣 | healing / heal / all_allies | INT ×0.8 | — | 6 / 2 | heal | 可 | 2 / 3 | 記録のみ |
| `battle_cry` / 戦いの歌 | support / power_up / all_allies | ×1.4 / 3ラウンド | — | 4 / 3 | buff | 不可 | 2 / 2 | 記録のみ |
| `weak_wave` / 衰弱波 | support / weaken / all_enemies | ×0.8 / 3ラウンド | — | 4 / 3 | debuff | 不可 | 2 / 2 | 記録のみ |
| `wild_edge` / 乱れ突き | speed / damage / random_enemy | STR ×0.5 + AGI ×1.2 | — | 16 / 0 | pierce | 不可 | 2 / 8 | 再取得Damage ×1.2 |

### 4. UNCOMMON 追加8技

| skill_id / name | type / effect / target | Scaling または modifier / duration | Status / Chance | Uses / CD | effect_id | field | RESTORE Cost / Uses | MASTERED報酬 |
|---|---|---|---|---|---|---|---|---|
| `whirlwind` / 旋風斬 | speed / damage / all_enemies | STR ×0.45 + AGI ×0.7 | — | 8 / 2 | slash | 不可 | 不可 | 再取得Damage ×1.2 |
| `blizzard` / ブリザード | magic / damage / all_enemies | INT ×1.4 | — | 7 / 2 | ice | 不可 | 不可 | 再取得Damage ×1.2 |
| `shock_stab` / 痺れ突き | speed / damage / enemy | STR ×0.6 + AGI ×0.9 | PARALYZE / 30% | 10 / 2 | lightning | 不可 | 不可 | 再取得Damage ×1.2 |
| `confuse` / コンフューズ | support / status / enemy | Damageなし | CONFUSION / 45% | 6 / 2 | debuff | 不可 | 不可 | 記録のみ |
| `toxic_mist` / 毒霧 | support / status / all_enemies | Damageなし | POISON / 30% | 6 / 2 | dark | 不可 | 不可 | 記録のみ |
| `mending_wind` / 癒しの風 | healing / heal / all_allies | INT ×1.4 | — | 5 / 2 | heal | 可 | 不可 | 記録のみ |
| `iron_wall` / 鉄壁陣 | support / guard_up / all_allies | ×0.7 / 3ラウンド | — | 4 / 3 | buff | 不可 | 不可 | 記録のみ |
| `slow_field` / スロウフィールド | support / slow / all_enemies | ×0.5 / 3ラウンド | — | 4 / 3 | debuff | 不可 | 不可 | 記録のみ |

### 5. RARE 追加10技

| skill_id / name | type / effect / target | Scaling または modifier / duration | Status / Chance | Uses / CD | effect_id | field | RESTORE Cost / Uses | MASTERED報酬 |
|---|---|---|---|---|---|---|---|---|
| `cure` / キュア | support / cure / ally | 4状態異常解除 / HP回復なし | 4状態解除 | 3 / 0 | heal | 可 | 4 / 2 | 記録のみ |
| `cleaving_storm` / 烈風乱舞 | physical / damage / all_enemies | STR ×1.5 | — | 5 / 3 | slash | 不可 | 不可 | 再取得Damage ×1.2 |
| `inferno` / インフェルノ | magic / damage / all_enemies | INT ×2.4 | — | 4 / 3 | fire | 不可 | 不可 | 再取得Damage ×1.2 |
| `plague_edge` / 毒牙斬 | physical / damage / enemy | STR ×2.1 | POISON / 60% | 5 / 2 | dark | 不可 | 不可 | 再取得Damage ×1.2 |
| `thunder_bind` / 雷縛 | magic / damage / enemy | INT ×2.3 | PARALYZE / 45% | 5 / 2 | lightning | 不可 | 不可 | 再取得Damage ×1.2 |
| `nightmare` / ナイトメア | magic / damage / enemy | INT ×2 | SLEEP / 45% | 4 / 3 | dark | 不可 | 不可 | 再取得Damage ×1.2 |
| `chaos_spell` / カオス | magic / damage / enemy | INT ×1.8 | CONFUSION / 40% | 4 / 3 | dark | 不可 | 不可 | 再取得Damage ×1.2 |
| `armor_wave` / 装甲崩壊 | support / armor_break / all_enemies | ×0.7 / 3ラウンド | — | 4 / 3 | debuff | 不可 | 4 / 2 | 記録のみ |
| `focus_field` / 精神集中陣 | support / focus / all_allies | ×1.5 / 3ラウンド | — | 4 / 3 | buff | 不可 | 4 / 2 | 記録のみ |
| `purify_wind` / 浄化の風 | support / cure / all_allies | 4状態異常解除 / HP回復なし | 4状態解除 | 2 / 3 | heal | 可 | 不可 | 記録のみ |

### 6. LEGEND 追加5技

| skill_id / name | type / effect / target | Scaling または modifier / duration | Status / Chance | Uses / CD | effect_id | field | RESTORE Cost / Uses | MASTERED報酬 |
|---|---|---|---|---|---|---|---|---|
| `ragnarok` / ラグナロク | physical / damage / all_enemies | STR ×3 | — | 2 / 4 | legend | 不可 | 不可 | 再取得Damage ×1.2 |
| `starfall` / スターフォール | magic / damage / all_enemies | INT ×4.5 | — | 2 / 4 | legend | 不可 | 不可 | 再取得Damage ×1.2 |
| `miracle` / ミラクル | healing / heal / all_allies | INT ×5 | — | 2 / 0 | heal | 可 | 不可 | 記録のみ |
| `sanctuary` / サンクチュアリ | support / guard_up / all_allies | ×0.55 / 2ラウンド | — | 2 / 4 | buff | 不可 | 不可 | 記録のみ |
| `time_stop` / 時の停止 | support / status / all_enemies | Damageなし | SLEEP / 70% | 1 / 4 | debuff | 不可 | 不可 | 記録のみ |

## 7. 個別Growth Point

既存同カテゴリの保守的な値を採用。カテゴリ成長率は変更なし。対象人数にかかわらず使用1回分のみ加算。探索使用は加算なし。

| skill_id | HP | STR | AGI | INT |
|---|---:|---:|---:|---:|
| `sweep` | 0 | 2 | 0 | 0 |
| `flame_wave` | 0 | 0 | 0 | 2 |
| `venom_strike` | 0 | 2 | 0 | 0 |
| `sleep_spell` | 0 | 0 | 0 | 1 |
| `group_aid` | 0.5 | 0 | 0 | 1 |
| `battle_cry` | 0 | 0 | 0 | 1 |
| `weak_wave` | 0 | 0 | 0 | 1 |
| `wild_edge` | 0 | 2 | 2 | 0 |
| `whirlwind` | 0 | 2 | 2 | 0 |
| `blizzard` | 0 | 0 | 0 | 2 |
| `shock_stab` | 0 | 2 | 2 | 0 |
| `confuse` | 0 | 0 | 0 | 1 |
| `toxic_mist` | 0 | 0 | 0 | 1 |
| `mending_wind` | 0.5 | 0 | 0 | 1 |
| `iron_wall` | 0 | 0 | 0 | 1 |
| `slow_field` | 0 | 0 | 0 | 1 |
| `cure` | 0 | 0 | 0 | 1 |
| `cleaving_storm` | 0 | 2 | 0 | 0 |
| `inferno` | 0 | 0 | 0 | 2 |
| `plague_edge` | 0 | 2 | 0 | 0 |
| `thunder_bind` | 0 | 0 | 0 | 2 |
| `nightmare` | 0 | 0 | 0 | 2 |
| `chaos_spell` | 0 | 0 | 0 | 2 |
| `armor_wave` | 0 | 0 | 0 | 1 |
| `focus_field` | 0 | 0 | 0 | 1 |
| `purify_wind` | 0 | 0 | 0 | 1 |
| `ragnarok` | 0 | 2 | 0 | 0 |
| `starfall` | 0 | 0 | 0 | 2 |
| `miracle` | 0.5 | 0 | 0 | 1 |
| `sanctuary` | 0 | 0 | 0 | 1 |
| `time_stop` | 0 | 0 | 0 | 1 |
## 8. 全体Skill処理

全ての追加Damage技について、敵個別DEF/MDEF、KO除外、Uses −1、Cooldown 1回、Growth 1回を確認。全体Healは生存者のみ。全体Cureも生存者のみ。

## 9. random_enemy

乱れ突きは実行時に生存Enemyを1体抽選。描画準備はRNGを進めず、実際の対象へ演出を表示。

## 10. PLAYER Status

4純Statusと6 Damage + Statusを正式データで検証。全体Statusは敵ごとに独立判定。耐性・無効化・制御状態排他・既存Durationを通す。

## 11. Damage + Status

Damage後に生存者のみStatus判定。失敗してもDamageは残り、Usesは1。KO時には状態異常が残らない。

## 12. Cure

キュア/浄化の風は4状態異常を治療、HP・BUFF/DEBUFFを維持。戦闘中の治療対象なしは実行失敗メッセージを出し、Uses・Cooldown・Growth・MASTEREDを消費/登録しない。その順番の行動は終了。選んだ相手がKOなら別人へ自動転送しない。

## 13. Persistent Poison

探索で毒を治療。治療対象なしは非消費。歩行ダメージや状態持続等は未変更。

## 14. BATTLE CRY / POWER UP

同じpower_up枠へ×1.4/3ラウンドを再適用。累積なし。

## 15. WEAK WAVE / WEAKEN

同じweaken枠へ×0.8/3ラウンドを再適用。累積なし。

## 16. IRON WALL / GUARD UP

同じguard_up枠へ×0.7/3ラウンドを再適用。累積なし。

## 17. SLOW FIELD / SLOW

同じslow枠へ×0.5/3ラウンドを再適用。累積なし。

## 18. ARMOR WAVE / ARMOR BREAK

同じarmor_break枠へ×0.7/3ラウンドを再適用。累積なし。

## 19. FOCUS FIELD / FOCUS

同じfocus枠へ×1.5/3ラウンドを再適用。累積なし。

## 20. SANCTUARY / GUARD UP

guard_up枠を×0.55/2ラウンドへ更新。実際の被害100→55を確認。×0.385にはならない。後からGUARD UP/IRON WALLを使うと、既存の最終再適用仕様どおり×0.7/3ラウンドに更新。

## 21. RESTORE対象総数

既存15 + COMMON追加8 + RARE追加3 = 26。UNCOMMON全13、LEGEND全8は不可。所持中のUses補充不可。

## 22. CURE RESTORE

Cost 4 BANKED TRZ、Uses 2/3。装甲崩壊と精神集中陣もCost 4、Uses 2/4。

## 23. Archive分母

62。全62技のArchive一覧と詳細文字の画面内収まりを検証。

## 24. 初期DISCOVERED

3/62、MASTERED 0/62。初期習得技はpunch / quick_hit / spark / punchを維持。新技はUnknown。

## 25. Spark候補数

全62技を対象に、現在所持だけ除外。初期ロウの候補は61。忘れた技・DISCOVERED/MASTERED済み技も未所持なら再候補。6枠FULL時は交換/見送りを維持し、見送ってもDISCOVEREDを保持。技宝箱は同じspark関数を使い、Chance/Weightを変更しない。

## 26. Rarity Weight

BASIC 12 / COMMON 48 / UNCOMMON 28 / RARE 10 / LEGEND 2。settings.jsonのハッシュ一致を確認。

## 27. B1 LEGEND

Floor制限なし。指定の抽選結果を返すテストRNGで、新規31技それぞれが初期Sessionへ取得可能であることを確認。TIME STOP等5LEGENDを含む。自然抽選では従来の低確率。

## 28. MASTERED

新規31技それぞれを使い切ってMASTERED登録→再取得を確認。15 Damage技のみコピーへ×1.2。全体技も各Targetの防御減算後へ1.2を適用し、対象数による倍率増加なし。Status Chanceは不変。その他は記録のみ。

## 29. ensure_attack

新規Damage/Damage + Status全15技を攻撃として認識。その他16技だけではPUNCH救済が入る。

## 30. 旧SAVE互換

31技時代の合成version 1セーブをLOAD→SAVEし、全JSONが一致。既存D/Mを保持、新技Unknown、分母のみ62。プレイヤーのセーブは使用していない。

## 31. 新技SAVE / LOAD

31技すべてを所持・Uses 1・MASTERED再取得状態でJSON往復し、ID・Uses・コピー補正を復元。実ブラウザlocalStorageでも旧セーブとsweepの新セーブが完全一致。

## 32. save_version

1のまま。rpg/save.pyを含む保護ファイルのハッシュ一致によりschema変更なし。新技セーブを旧31技プログラムへ戻してLOADする逆互換は保証しない。

## 33. 既存31技の前後比較

追加直前のBattleと744条件（31技×3seed×4状態×2MASTERED）のスナップショットが完全一致。探索Heal16条件も一致。既存31行全フィールド一致。従来基盤比較も744条件・20勝利の成長/閃き・旧RESTORE15技で成功。個別成長率・技バランスの変更は0。

## 34. Enemy / Encounter回帰

敵定義・Action・Boss耐性・遭遇表・ITEM・QUEST・成長率・マップ・画像/音声等58ファイルのハッシュ一致。B5/B10通常遭遇あり、B15なしをWeb埋込み検証で確認。

## 35. Final Battle回帰

同一SessionでB10→守護者3連戦→泉→デーモン→アムリタ→献上後で→施設→再帰還→献上→バリア解除→ENDINGを確認。実全滅A–Eの5回再挑戦、HP/Uses/ITEM/アムリタ/バリア復元、通常全滅処理を確認。新規31技も6枠以内のセットに分けCheckpointで3回ずつ復元。追加攻撃15技はバリア中0、解除後Damageあり。毒の継続Damageもバリア中0。

## 36. TIME STOPと現行Boss

現行のB5/B10/B15デーモン、守護者3体、ロードオブエリシオンの計7Bossは、SLEEP耐性・Immunity定義なし。成功率70%で既存SLEEP（2ターン）を付与する。69%のテスト抽選で成功、70%の抽選値で失敗。制御異常が既に別種類なら排他で失敗。通常Damageによる睡眠解除などは既存どおり。最終ボスのバリアはダメージを防ぐがStatus免疫は追加せず、TIME STOPも効く。能力/AI/耐性の調整なし。

## 37. 自動テスト

全443テスト成功。追加Rosterは27テスト（各技/状態のsubTestを含む）。旧技744比較等の専用検証はこの件数とは別。初回に旧31件/探索5技を前提とした2テストが失敗したため、仕様変更に合わせて期待値を更新し全体を再実行。検証コードの対象なし描画・文字コード指定も修正済み。

## 38. PC Python

Python 3.14.7 / Pyxel 2.9.9、headless実描画・D-pad/A/Bシミュレーション・全テスト・最終章通し成功。GUI実プレイによる自然成長バランス試験ではない。

## 39. PC Browser

隔離Edge Chromiumの実Pyodideで正式Roster27テスト成功。実キーボードDown/Z/Xで全体技選択→Targetスキップ→B取り消しまで成功。

## 40. Touch Browser

隔離Edge ChromiumのPixel 7タッチエミュレーションで27テスト成功。HTML D-PAD/A/Bへ実touchStart/endを送り同じ操作を確認。iOS Safari/スマホ実機/Pixel2実機は未確認。

## 41. Audio停止時

実Web AudioContextをsuspendedにし、resumeを失敗させた状態でDesktop/Touchの戦闘検証成功。さらに9代表技をPyxel play/playm/play_pos例外で240更新以内に演出完了。visibilitychange/blur/focus/pageshowイベントも送出。物理画面ロック/実iOS interrupted状態は再現未実施。音声安全性の既存コードは未変更。

## 42. Web版更新

dist/game.htmlを現行ソース・62技データから再ビルド。埋込みPython/JSON/全pyxres・パレットと作業ファイルが一致。既存D-pad/A/B、無音最終戦再挑戦、ENDINGも検証。dist/index.htmlは今回の変更なし。GitHubへのpushは未実施。

## 43. Pixel2 ZIP

verification/packages/skill_seekers_gkd.zipを更新。61エントリ。全ソース/データ/素材が現行ファイルと一致。rpg 31モジュール＋main.pyのPython 3.11構文検証成功。save/・テスト・キャッシュなし。ランチャーは既存のまま。実機Python 3.11.7/Pyxel 2.9.9での確認はユーザー側で必要。

## 44. pyxres変更なし

ゲーム・area2・area3・素材・BGM等、全既存pyxresとpyxpalをハッシュ比較して一致。演出は既存effect_idを使用。

## 45. 既知の問題と確認限界

進行不能・クラッシュ等の未解決問題は今回の検証範囲では見つからない。62技の自然プレイでのバランスは未評価。SANCTUARYを後から弱い防御BUFFで上書きする挙動は既存更新仕様の維持。治療対象なしCUREはUses非消費だがその行動の順番は消費。実Safariの画面ロック・GKD実機は未確認。比較用の直前Battleバックアップはローカルverification/backups/配下でGit対象外。複製環境では該当専用比較スクリプトにそのバックアップが必要。全体unitテストはversioned fixtureを使う。

## 検証ファイル

- `tests/test_player_skill_roster.py`（27テスト、31技をsubTestで検証）
- `tests/fixtures/player_skills_31.json`（追加前の31技の全定義）
- `tests/fixtures/player_skill_roster_protected.json`（保護58ファイルの変更前ハッシュ）
- `verification/skill_roster.json`（744比較・画面内文字・SAVE）
- `verification/skill_roster_browser.json`（実Web Desktop/Touch・音声停止・localStorage）
- `verification/skill_roster_package.json`（Pixel2内容・Python 3.11構文）
- `verification/final_chapter.json` / `verification/web_final_chapter.json`（終盤回帰）

## 必須CASEの対応

| CASE | 主な検証 |
|---|---|
| 1–8 | counts_initial_archive_and_ids / every_new_skill_exact_specification / legacy_rows_protected_data_sources_assets |
| 9–29 | all_damage_defense / random_one_living / damage_status / pure_status / group_heals / buff_debuff_same_slot |
| 30–46 | cures_four_statuses / cure_noop / field_cures / all_damage / buff_debuff_same_slot |
| 47–56 | all_damage / group_heals / sanctuary / all_status_independent / time_stop_current_bosses |
| 57–71 | pure_status_fail / damage_status / all_damage_defense_ko_and_one_resource_charge |
| 72–88 | group_heals_battle_field_hp0_full_noop / restore_26_exact_cost_stock_no_owned_refill / legacy comparator |
| 89–106 | all_new_mastered / all_mastered_damage / spark_every_new_skill_b1_weights_exclude_owned_relearn |
| 107–122 | counts_initial_archive / all_new_mastered / full_six_exchange_skip / ensure_attack |
| 123–134 | old_save_exact_roundtrip / every_new_skill_save_roundtrip / protected_data_sources_assets |

すべてのデータ編集は新規31技のみ。既存31技・SAVE・Enemy・Map・ITEM・Growth・QUESTの定義は維持。
