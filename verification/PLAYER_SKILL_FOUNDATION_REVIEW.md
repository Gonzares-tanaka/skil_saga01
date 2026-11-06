# PLAYER SKILL SYSTEM EXPANSION FOUNDATION

正式PLAYER Skillを31種類のまま維持し、全体・ランダム対象、状態異常、治療、探索使用、明示データによるRESTORE判定を追加した。CURE等の正式Skill、テストSkill、画像・音声素材は本番データへ追加していない。

## 指定45項目の完了報告

1. **変更したファイル**: ゲーム側は`rpg/models.py`、`rpg/content.py`、`rpg/battle.py`、`rpg/statuses.py`、`rpg/app.py`、`rpg/dungeon_app.py`、`rpg/labels.py`、`rpg/battle_presentation.py`。追加は`rpg/skill_targets.py`。検証側は`tests/test_player_skill_foundation.py`、旧セーブfixture、`tools/verify_skill_foundation.py`、`tools/browser_skill_foundation_case.py`、ブラウザ検証driver、旧敵棚卸しテストの保護範囲指定。README・本報告・結果JSON、`dist/game.html`、GKD ZIPも更新した。変更前コード・ハッシュは`verification/backups/skill_foundation/`へ保管した。
2. **Skillの追加field**: `status_id=None`、`status_chance=0`、`cure_statuses=()`、`field_usable=None`。field_usable省略時は旧heal/returnをTrue、その他をFalseへ解決する。既存skills.jsonを編集せず互換を維持した。
3. **正式Target**: enemy / ally / self / all_enemies / all_allies / random_enemy。効果との不正な組み合わせも検証する。
4. **all_enemies**: 発動時の生存Enemy参照一覧へ同じSkill効果を適用。KOを除外する。
5. **all_allies**: 生存Partyの参照一覧へ適用。HP0は含めず、全体REVIVEはvalidationで拒否する。
6. **random_enemy**: 発動時にBattleの既存rng.choiceで生存Enemyを1体選ぶ。演出プレビューは乱数を引かず、実際に選んだ対象を発動後に表示する。
7. **Uses**: 対象ループ外で1回だけ減算する。
8. **Cooldown**: 対象ループ外で従来どおりcooldown+1を1回設定し、ラウンド終了時に減算する。
9. **Growth**: used_skills / category_uses / growth_pointsは対象数にかかわらず1使用分。
10. **Statusデータ構造**: status_idは既存statuses.jsonのID、status_chanceは百分率。damage/drainへのOptional情報とpure statusに対応する。
11. **pure Status**: effect=statusで共通Battle.apply_statusへ渡す。HPダメージ処理を呼ばない。
12. **Damage＋Status**: 従来の合算Powerで対象別ダメージ→対象が生存しているときだけ付与判定。KOした対象へは付与しない。
13. **Chance表現**: EnemyActionと同じ0～100。35＝35%。bool・非数値・範囲外・NaN等を拒否する。
14. **Resistance / Immunity**: 既存apply_statusへ接続し、Enemyの耐性・無効化を通す。
15. **Control排他**: 既存のparalyze/sleep/confusion排他、poison共存、同Status持続更新をそのまま再利用する。
16. **Cureデータ構造**: effect=cureとcure_statuses配列。healとは別の内部効果。
17. **Cure指定**: 既存4IDから1つ以上を選ぶ配列。未知ID・重複・空配列・cure以外への設定は拒否する。
18. **戻り値／解除数**: 共通cure_statusesは解除IDのtupleを返す。戦闘last_skill_cured_countと探索FieldSkillResult.cured_countで0/成功を確認できる。HP、別管理のeffects、KOの状態を変更しない。
19. **all_allies Cure**: 生存者ごとに指定Statusを解除し、解除数を合計する。Usesは1回分。
20. **Field Usable**: bool属性。探索用にheal/cure/returnのみ許可する。既存の探索可能5技は完全一致、他の既存26技は不可。
21. **Field Dispatcher**: Session.field_use→heal/cure/return。既存field_healは互換wrapper、RETURNの使用者選択と既存field_returnも維持。UIは単体の回復/治療で対象選択、自分/全体では選択省略。RETURNの成功後は既存帰還処理へ接続する。
22. **Persistent Poison**: 共通statusesから指定IDだけを除去するため、探索に残った毒の残りtickも除去できる。探索使用による毒tick・戦闘成長加算はない。
23. **探索Heal回帰**: 4技×負傷/満タン/KO/最後の1回＝16条件で、変更前とメッセージ・HP・Uses・MASTERED等が一致。
24. **RETURN回帰**: 最大3、消費1、使い切りMASTERED、RESTORE残1を維持。共通Dispatcher、D-PAD/A/Bによる帰還、TRZ確定、旧セーブ・終盤の帰還も確認した。
25. **RESTORE現在構造**: DISCOVERED、非所持、確定TRZ、枠入れ替え等の既存条件を維持。can_relearnは明示cost/usesの有無で判定する。
26. **データ駆動化**: 実施した。Rarityや既存6効果のホワイトリストへ依存しない。無効なcost/usesのペアはcontent validationで拒否する。
27. **既存15技一致**: can_relearn、cost、再取得Usesが変更前と一致。テスト用RARE Cureは明示cost/usesにより再取得可能、その他既存技が新たに対象になることはない。
28. **Archive**: 正式総数31。未発見表示・D/M・総数からの分母計算を維持。
29. **Spark候補**: 本番全定義31。各キャラの所持除外等は従来どおり。テストSkillは本番JSON・Web/GKD配布物に含めない。
30. **Rarity**: BASIC3 / COMMON10 / UNCOMMON5 / RARE10 / LEGEND3の5段階を維持。
31. **Spark weight**: 12 / 48 / 28 / 10 / 2。基本15%、DEBUG95%、B1～B15の倍率を変更していない。LEGENDはB1から候補。
32. **既存31技性能比較**: 31技×3seed×4状態×通常/MASTEREDコピー＝744条件で、変更前Battleとログ・HP・効果・Uses・Cooldown・成長・習熟・行動queue・乱数状態が一致。個別Power、formula、mastery_label、RESTOREも比較した。20勝利のseed付き成長・閃き結果も一致。
33. **DISCOVERED**: 初期技、閃き時点、満杯で拒否した新技の記録、共有記録を維持。既存回帰と旧SAVE復元に成功。
34. **MASTERED**: Uses0で消滅・記録、捨てるだけでは未習熟、再取得damage/drainコピーのみ1.2、累積なしを維持。Status/Cureは記録のみ。
35. **ensure_attack**: 変更なし。status/cureを攻撃技と誤判定せず、攻撃技なしでパンチ30回を救済取得する。
36. **SAVE互換**: 変更前に生成したschema1 fixtureをPCで読み込み→再生成した全JSONが一致。PCブラウザ/タッチブラウザでも隔離localStorageへ書き込み→読み込み→全JSON一致。実プレイヤーのSAVEは読まず、書き換えていない。
37. **save_version**: 1のまま。rpg/save.pyと保存schemaは変更していない。
38. **自動テスト**: 416/416成功（既存385＋新規31テストメソッド）。必須95ケースは下表の検証へ対応。別途744比較、16探索比較、旧SAVE、保護ハッシュ、実ブラウザ各31テストを実施。
39. **PC Python**: Python3.14.7 / Pyxel2.9.9。全テスト・実headless描画・Archiveの文字幅検証・既存終盤通し検証に成功。B10→ENDING、最終戦5回の実全滅と再挑戦も成功。
40. **PC Browser**: Edge Chromiumの実Pyodideで新規31テスト成功。実キーボードDown/Z/Xで全体Skill選択→個別Target省略→Bキャンセルを確認。旧SAVEのlocalStorage復元一致、ブラウザ例外なし。
41. **Touch / Smartphone Browser**: Pixel7タッチエミュレーションの実Pyodideで31テスト成功。HTML D-PAD/A/Bに実touchStart/touchEndを送り、選択・決定・キャンセルを確認。iOS Safari・スマートフォン・GKD Pixel2の実機は未確認。
42. **Audio停止**: PC描画検証でplay/playm/play_posを例外化。実ブラウザはAudioContextをsuspendedへ移しresumeを拒否、visibilitychange/blur/focus/pageshowも発行。全体技、Status成功/失敗、Cure、演出、旧SAVE、入力が進行。音声終了待ちを追加していない。実端末の画面ロックは未確認。
43. **pyxres**: 変更なし。マップ・素材・音声を含む保護50ファイルのSHA-256一致を確認。
44. **正式新Skill**: 追加なし。skills.jsonそのものも変更前とバイト単位で一致。テスト用定義はunit fixture／検証メモリ内のみ。
45. **既知の問題／確認範囲**: 今回のテストでは重大な進行不能を確認していない。実iOS Safari、画面ロック、GKD実機は未確認。正式CURE・全体技・新素材・専用演出は次工程。戦闘Cureは対象Statusなしでも1Uses消費、探索Cureは解除0なら未消費とする暫定基盤で、正式Skill追加時にUI仕様を確定する。自動戦闘AIへの新しい補助/治療判断は今回追加していない。

## 必須CASE 1～95の対応

| CASE | 実施した検証 |
|---|---|
| 1～10 | 正式JSON保護ハッシュ、件数31/Rarity内訳、744比較、個別定義照合。 |
| 11～15 | 744比較、16探索比較、従来BUFF/DEBUFF・REVIVE・有限RETURNテスト。 |
| 16～20 | 全体物理4敵・KO除外・個別DEF/GUARD/装甲低下、合算hits、Uses/Cooldown/成長1回。 |
| 21 | 全体魔法で4敵それぞれのMDEFを減算。 |
| 22～23 | 生存者全体Heal、HP0除外。 |
| 24～26 | random_enemyは1生存敵のみ、KO除外、previewでRNG不変。3自動Targetをpad選択し個別Target画面を省略。 |
| 27～33 | pure Statusの4ID・成功/失敗・ダメージ0・毒本人tickの持続、既存Visual。 |
| 34～38 | Control排他、毒共存、再付与refresh、耐性・無効化。 |
| 39～44 | 物理＋毒/魔法＋混乱、DEF/MDEF、Damage後生存判定、KO付与なし、Uses/成長1回。 |
| 45～48 | 全体毒、個別確率判定、個別耐性、成功と失敗の混在、KO/無効化で判定除外。 |
| 49～59 | 4状態の個別治療、複数/指定部分のみ治療、WEAKEN/ARMOR BREAK/SLOWとHP不変、解除0、KOを治療しない。 |
| 60～63 | 全体Cure、3生存者と1KO、生存者の指定状態解除、消費1回。 |
| 64～69 | 旧4Healの16条件比較、有限RETURN、既存探索可能5技の一致、他26技は不可。 |
| 70～72 | 単体/全体/自分の探索Cure、残留毒解除、成長/Cooldown加算なし、pad対象選択・Bキャンセル。 |
| 73～77 | 旧RESTORE15技・cost/uses一致、新たな旧対象なし、fixture RARE Cureを明示データで再取得。 |
| 78～81 | Archive31、本番JSON31、5Rarity/weight/階層倍率保護、B1 LEGENDの旧テスト、20勝利比較。 |
| 82～87 | 変更前のsynthetic SAVEをPC/Webで復元、fire7回・return2回・D/M等の全JSON一致、schema1/rpg/save.py保護。 |
| 88～90 | status/cureしかない構成でパンチ30取得、攻撃判定はdamage/drainのまま。 |
| 91～95 | 全体敵/味方の既存effect描画、Status成功Visual・失敗進行、音声例外時の演出完了、実Webのsuspended/resume拒否でも31テストと実操作成功。 |

## 配布・実行記録

- `dist/game.html`は更新済み。埋込みコード/素材照合、B5/B10通常遭遇・B15通常遭遇なし、既存pad、無音の守護者/最終戦/ENDING検証成功。
- `verification/packages/skill_seekers_gkd.zip`は更新済み。61エントリ、現行ソースと全件一致、SAVE/テストfixtureを同梱しない。更新時は本体のsave/を残す。
- GKD向けPython3.11構文確認は別JSONへ記録する。構文・内容検証は実機動作確認を意味しない。

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_skill_foundation.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_final_chapter.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_web.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_web_build.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_statuses.py --playwright-path verification/backups/quest_spawn/browser_deps --fixture tools/browser_skill_foundation_case.py --unit-fixture tests/test_player_skill_foundation.py --save-fixture tests/fixtures/skill_foundation_save_v1.json --expected-count 31 --output verification/skill_foundation_browser.json
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd.py
```

結果: `verification/skill_foundation.json`、`verification/skill_foundation_browser.json`、`verification/skill_foundation_package.json`。終盤回帰は`verification/final_chapter.json`。
