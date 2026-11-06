# ALPHA SKILL BALANCE PHASE 5B-2【改訂版】完了報告

実施日：2026-11-01。対象：Skill Seekers!! ～深淵のアムリタ～。

## 実装範囲

|ID|性能の変更前→後|維持した倍率 / Uses / CD|説明文|
|---|---|---|---|
|power_up|持続3→4ターン|STR1.4 / 8 / 0|味方STR1.4倍。4ターン。|
|focus|持続3→4ターン|INT1.5 / 6 / 0|味方INT1.5倍。4ターン。|
|sanctuary|持続2→3ターン|被害0.55 / 2 / 4|味方全体の被害45%減。3ターン。|

性能数値の差分は上記3フィールドだけ。全62スキル・PHASE 5B-1の4攻撃技・戦いの歌・精神集中陣・鉄壁陣・SLOWの計算と期間・RETURNは維持した。スロウ系2技の説明だけを「敵1体／敵全体の行動順を遅くする。」へ変更。AGIの内部係数や使用ラウンドの説明は追加していない。

sleep_spell / nightmare / time_stop は説明文を含む全フィールドが受領時と完全一致。旧依頼に由来する不要な追加文言は受領時点で存在しなかった。睡眠成功率・持続・ダメージでの解除・ボス無効と既存表示を変更していない。

## 治療UI

|場所|案内|選択・消費|
|---|---|---|
|戦闘キュア・対象選択|選択中の味方に治療可能な異常がなければ「治療対象なし / 予約可」|健康な生存者も選択・予約できる|
|戦闘浄化の風・技詳細|生存者全員に治療可能な異常がなければ「治療対象なし / 予約可」|そのまま予約できる|
|探索キュア・対象選択|「治療対象なし / 消費なし」|無対象で使用してもUsesを減らさない|
|探索浄化の風・技詳細|「治療対象なし」|Aで使った際も既存の通知を表示し、Usesを減らさない|

判定は表示時の生存者とskill.cure_statusesの積集合を見るだけ。表示のために状態・乱数・行動予約を変更しない。治療実行、Uses/CD/成長、習熟、入替、訓練、セーブを扱うモデルは一切変更していない。

実行時は従来どおり再判定する。予約後に毒などを受ければ治療しUses1消費。実行前に解除済みなら行動を終え、Uses・成長を消費しない。CD0でも実行直後には内部的な待ち1が置かれ、ラウンド終了で消える既存仕様も維持した。

## 変更前後の比較

全結果を[比較表](SKILL_BALANCE_5B2_COMPARISON.md)、機械可読値を[JSON](skill_balance5b2_comparison.json)に保存。攻撃48行、防御512行、集中の単発5件。攻撃は3仕様、防御は4仕様をそれぞれ実エンジンで実行した。

STR/INT20、DEF0/16、2・3・4・5ターン。直接攻撃は物理パンチ／魔法火花（CD0）。自己強化は1人、味方強化は使用者と受け手の2人の合計ダメージを示す。強化は最初に1回だけ使用し、その失う攻撃1回も比較に含める。行動順は実際のbegin_round/stepで解決した。

|自己強化・DEF0・4T|直接攻撃のみ|旧|新|
|---|---:|---:|---:|
|力の鼓舞→パンチ|80|76|84|
|集中→火花|96|96|108|

自身への強化は使用直後に残り3となり、次の3回の攻撃に有効。旧仕様の有効攻撃2回から1回増える。味方がまだ行動していれば付与ラウンドにも有効で、既に行動済みなら翌ラウンドから恩恵を受ける。

INT20の集中時はファイア40→60、メテオ140→210、応急手当30→45、大回復90→135、ミラクル100→150（回復は1人あたり）。これらを新たに有効になる第4ラウンドで実使用し、終了後に集中が消えることも確認。計算式は変更なし。

### サンクチュアリの強さ

B5・B10・B15守護者3体・DEMON・LORDに加え、STR/INT40の統制敵を測定。物理／魔法×単体／全体×先行／後攻×GUARD有無×2/3/4/5Tを全掲載。各敵の能力値と行動回数を使い、指定攻撃を固定して反復する負荷試験である。自然AIが選ばない攻撃や2行動での全体技連打も含み、実戦の自然ローテーション・撃破率を測定したものではない。HP打切りを避けるため味方と敵のHPを検証内だけで増やした。LORDは障壁解除後。

|全体魔法・先行3T・GUARDなし|補助なし|鉄壁陣|旧サンクチュアリ|新サンクチュアリ|
|---|---:|---:|---:|---:|
|B5 / イビルナイト|143|98|101|81|
|B10 / サイクロプス|180|123|126|99|
|B15 / デーモンガード|48|36|32|24|
|B15 / キュクロープス|73|49|49|37|
|B15 / レッドドラゴン|258|180|180|143|
|DEMON|589|415|413|325|
|LORD OF ELYSION|360|253|250|196|

少ない方が合計HP被害が小さい。全512条件で新サンクチュアリは旧版と鉄壁陣以下の被害。先行3Tでは概ね45%軽減が続き、後攻では使用ラウンドの被害を軽減できず、有効な未来ラウンドは2回となる。

**強さの留意点：** GUARDとの積は0.55×0.5=0.275で、個々の攻撃は丸め前72.5%軽減となる。LORDの上記条件でGUARDも使うと、新版の被害109、同じGUARD配置の無補助195。全員が防御しない無補助360との比較では69.7%減。初手の使用者はサンクチュアリとGUARDを同時使用していない。全体攻撃が続く状況では強力だが、指定どおり軽減率・Uses・CDを追加調整していない。

## 検証

新規15件と既存666件、**計681件すべて成功（215.553秒）**。[全体ログ](skill_balance5b2_all_tests.txt)。初回は旧持続時間の固定期待値6箇所と、新規テストの実行直後CD確認で失敗した。既存テストは指定3スキルの持続期待値のみを修正し、モデル変更で失敗を回避していない。ログ末尾のSUSPEND failedは破損データ・一度きり消費失敗・容量不足を意図的に起こす既存テストの出力であり、最終判定はOK。

|依頼項目|確認根拠|
|---|---|
|1～15 補助スキル|test_skill_balance5b2：独立期待値による行動順・合計ダメージ、倍率、持続、上書き、物理／魔法のGUARD併用、実回復。既存test_support / test_player_skill_foundation / test_player_skill_rosterも回帰|
|16～25 治療|新規テストで4異常・単体／全体、健康時のキー／ゲームパッド予約、予約後付与、実行前解除、非消費、探索を確認。Web実入力でも確認|
|26～33 睡眠|全フィールド一致。既存test_alpha_ux01の7ボス×3技、test_statusesの確率境界・解除、既存無効表示／演出。新規でナイトメアのダメージ40と睡眠だけ無効を確認|
|34～41 SLOW・表示|新規実行で使用ラウンドのキュー不変、未来2ラウンドだけ行動順反転、4ラウンド目復帰、全体効果。説明と数値の一致・実フォント幅を検査|
|42～51 62技・5B-1・習熟・技操作|既存test_skill_balance5b1 / test_skill_uses / test_feedback / test_player_skill_roster / test_alpha_ux01など。大治癒の「初期2回」・次コピーのMASTEREDプレビューも維持|
|52～54 通常／中断／旧セーブ|受領前定義で作成したv1通常セーブと中断を現定義で復元。5補助技＋二段斬りのID・Uses・MASTERED保持、3補助技実行。中断2回目consume失敗。既存test_save / test_alpha_ux01 / test_skill_balance5b1で4攻撃技も回帰|
|55～61 探索・終盤|test_alpha_gameplay02 / test_alpha_encounter04 / test_finale / test_final_battle / test_final_presentation。配布Web payloadでもELEVATOR・遭遇・無音の守護者連戦・アムリタ・最終障壁／再挑戦／ENDINGを確認|
|62 PC|実Edgeのキーボード入力。別テスト用プロファイルとfixtureを使用|
|63 スマホ操作|Pixel7設定のEdgeタッチエミュレーションでHTML D-PAD/A/Bへ実touchStart/touchEnd。iOS／Android実機ではない|
|64 GKD操作|既存ゲームパッド／SELECTテスト・配布ZIPの全ゲームファイル一致とPython3.11構文。GKD実機未確認|
|65 音声|全.pyxres/.pyxpal、音楽データ、rpg/sound.pyの受領時SHA一致。音声正常／AudioContext利用不可の両方でWeb操作検証。聴感評価は未実施|
|66 ネイティブ|PC Python3.14.0 / Pyxel2.9.9で無画面の実エンジン・描画・入力を検証。GUIでの長時間プレイは未実施|

### UI・Web

実フォント幅は、力の鼓舞92px・集中92px・サンクチュアリ120px。「治療対象なし / 予約可」84px、「治療対象なし / 消費なし」92px。使用可能幅148pxに収まる。[ネイティブ描画検査](skill_balance5b2_native_ui.json)。スキル詳細・探索一覧は同じskill_detailsとJSONを参照する。TRAINING一覧・確認画面には既存どおり期間の固定表記がなく、回数・費用を維持。入替画面の所持技の期間表示はSkill.formulaから動的に生成される。ARCHIVEは既存どおり発見／習熟一覧で、性能説明を追加していない。

[通常音声](skill_balance5b2_browser_running.json)、[音声利用不可](skill_balance5b2_browser_unavailable.json)ともPC／タッチ成功、ページ例外なし。各条件で戦闘4件、探索2件、3種の説明を検証。戦闘fixtureでは、健康な時点で予約し、敵の確定毒攻撃後に発動して治療する経路も実入力で確認した。実プレイヤーのlocalStorageやファイルセーブは使っていない。

[キュア対象画面](screenshots/skill5b2_native_target.png)、[探索画面](screenshots/skill5b2_native_field.png)、[サンクチュアリ](screenshots/skill5b2_native_sanctuary.png)、[タッチ画面](screenshots/skill5b2_touch_emulation_running_target.png)を目視し、追加文言のはみ出し・重なりがないことを確認した。

## 保存・既存変更の保護

セーブ形式・ID・通常SAVE v1・中断の一度きり仕様は無変更。オートセーブ・任意破棄は追加していない。受領時の66ゲームファイルをスナップショットし、指定JSON差分と表示メソッド以外を保護。[照合記録](skill_balance5b2_preservation.json)。既存の多数の未コミット変更を保持し、Gitへのcommit/pushは行っていない。

作業中、こちらでは編集していないdata/enemies.jsonのボス名・会話変更を検出したため保持。受領時ハッシュと検出後ハッシュを両方記録し、変更はname / message / after_messageに限定され、能力・行動・報酬など他フィールドが元データと一致することを検証した。比較表・配布物には最新のユーザー側編集を含む。受領時から変更されていたPUBメッセージも保持している。5B-1の歴史的保護テストは、今回受領時の厳密な保護へ引き継いだ。

## 配布物と再現

既存手順で[Web dist/game.html](../dist/game.html)、[GKD通常版](packages/skill_seekers_gkd.zip)、[GKD診断版](packages/skill_seekers_gkd_diagnostic.zip)を更新。[配布照合](skill_balance5b2_packages.json)：Web66／GKD66／診断69エントリー、各65ゲームファイルが作業ツリーとバイト一致。Python3.11構文を検証し、SAVE・テスト用ランタイムは非同梱。

受領時の.venvは参照先Python314本体が存在せず起動不可だったため、公式Python3.14.0ポータブル版を.gitignore対象の.toolsへ配置し、既存Pyxel2.9.9を使った。ゲームの依存固定版は変更していない。検証環境での再現コマンド：

```powershell
.tools/python/python.exe -B -X utf8 -m unittest discover -s tests
.tools/python/python.exe -B -X utf8 tools/audit_skill_balance5b2.py
.tools/python/python.exe -B -X utf8 tools/verify_skill5b2_ui.py
.tools/python/python.exe -B -X utf8 tools/verify_web_build.py
.tools/python/python.exe -B -X utf8 tools/verify_skill_balance5b2_packages.py
.tools/python/python.exe -B -X utf8 tools/verify_browser_skill5b2.py --playwright-path .tools/browser --output verification/skill_balance5b2_browser_running.json
```

最後のコマンドに--disable-audioを加えると音声利用不可条件。環境のファイルACLとブラウザ起動制約により、今回ZIPの更新／照合とブラウザテストだけは権限を上げて実行した。外部公開はしていない。

iOS Safari実機、GKD Pixel2/plumOS実機、スマホ画面ロック、音声の聴感と長時間プレイは未確認。比較は統制条件の測定であり、実プレイヤーの採用率・勝率を示さない。
