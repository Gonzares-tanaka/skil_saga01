# PHASE 6B-1：UI不具合修正・探索中クエスト確認・日本語表示

完了確認日：2026-11-04。前回監査のうち指定された6項目を実装。既存の未コミット変更を受領状態として保存し、過去版への復元は行っていない。Git commit／pushは未実施。

## 1. 変更ファイル

今回手を入れた既存ファイルは次のとおり。Git全体の既存差分とは区別する。

| ファイル | 今回の変更 |
|---|---|
| `rpg/dungeon_app.py` | 道具説明、B案内、クエスト参照画面、酒場見出し、予定威力、通常UIの日本語ラベル |
| `rpg/hub.py` | 内部の施設・メニュー識別子を維持したまま日本語表示ラベルを追加 |
| `rpg/app.py` | リターン使用不可時の案内をスキル表示名参照へ。ヘルプ見出しを日本語化 |
| `rpg/battle.py` | 使用可能なリターンがない場合のエラー文だけ表示名参照へ。ルール変更なし |
| `rpg/elevator.py` | システム解放案内の施設名を「パブ」「エレベーター」へ。配置・条件は変更なし |
| `data/skills.json` | `return`／`revive`の`name`だけを変更 |
| `README.md` | プレイヤー向け施設・メニュー名を統一。コード・ファイル名・内部IDは保持 |
| `dist/index.html` | 施設・探索メニューの案内を画面と一致させ、クエスト参照の説明を追加 |
| `tools/build_gkd.py` | 通常／診断ZIPに共通の日本語操作案内を同梱 |
| `tools/verify_quest_records_ui.py` | 長いユーザー編集本文を複数ページ読んでから受注／報酬確認する検証へ修正 |
| `tests/ui_phase6a_preservation.py`、`tests/rescue5c_preservation.py` | 過去の保護検証を今回の明示されたUI変更・2技の名前変更に対応。過去fixtureは書換えなし |
| `dist/game.html` | 現行ソース・同じ資源でWeb再ビルド |
| `verification/packages/skill_seekers_gkd.zip`、`skill_seekers_gkd_diagnostic.zip` | 通常版／診断版を更新 |
| `verification/gkd_diagnostic_package.json` | 既存の診断ZIPビルダーが生成する検証記録を更新 |

新規の実装検証ファイル：

- `tests/test_ui_phase6b1.py`：今回の15テスト。
- `tests/ui_phase6b1_preservation.py`：受領版のルール・文章・素材を保護。
- `tests/fixtures/ui_phase6b1_before.json`：変更前69ファイルのハッシュ、比較用ソース、62技定義。
- `tests/fixtures/ui_phase6b1_legacy_save.json`、`ui_phase6b1_legacy_suspend.json`：**変更前コードで生成したテスト用データ**。実プレイヤーのセーブではない。
- `tools/snapshot_ui6b1.py`、`verify_ui6b1.py`、`verify_browser_ui6b1.py`、`verify_ui6b1_packages.py`。
- [GKD日本語操作案内](GKD_PLAY_GUIDE_JA.txt)、本報告書、`ui6b1_*.json`／テストログ／比較画像。

## 2. ITEM説明の原因と修正

原因は`draw_items()`の説明が「羽根か、それ以外か」の2分岐だったこと。POTION・PHOENIX ASHまでREMEDY用説明に流れていた。

選択中のアイテムIDから説明を対応付けるよう修正した。カーソルを動かすたびに現在IDを読み直す。

| 内部ID | 現在の探索説明 |
|---|---|
| `POTION` | 味方1人のHPを回復する |
| `PHOENIX ASH` | 戦闘不能の味方1人を蘇生する |
| `REMEDY` | 味方の状態異常を治療する |
| `return_feather` | ダンジョンから帰還 / 1個消費 |

回復量や蘇生率を説明へ固定していない。最新`data/items.json`の性能をそのまま使用する。価格、個数、対象選択、使用可能条件、無効対象に消費しない処理は変更していない。POTIONのHP回復と灰の蘇生は実処理でも確認した。

## 3. Bボタン案内

操作の遷移先は変えていない。

| 画面 | 修正後の案内・動作 |
|---|---|
| 拠点最上位 | `D-PAD:選択 A:入る`。戻れないBの案内を削除。Bに新しい処理は追加しない |
| 施設内メニュー | `B:拠点へ`。既存どおり拠点へ |
| ショップ購入／パブ情報購入 | `B:戻る`。既存どおり各施設内メニューへ |
| スキル図鑑の集計・一覧 | `B:戻る`。既存どおり訓練場メニューへ |
| 再取得の人物選択 | `B:戻る`。既存どおり訓練場メニューへ |
| ギルドのセーブ結果／確認 | 施設へ戻る意味に合わせて`戻る`へ |
| 新しいクエスト確認 | `B:戻る`で探索メニュー。さらにBで探索へ |

## 4. 探索中クエスト確認

探索中の **B →「クエスト」→ A** で開く。既存6項目のインデックスは維持し、7番目にクエストを追加した。中断は従来どおり6番目。表示行間だけ13px→11pxへ調整し、7行と下部案内が160×120に収まる。

画面は`menu`上の読取専用`field_quest`オーバーレイ。`active_quest`からその都度以下だけを読む。

- 種類とLv：例「調査 Lv3」
- 対象階：例「対象：B14F」
- 現在数／必要数：例「進捗：1/3」
- 達成時：「拠点に戻って報告」
- 未受注時：「受注中のクエストはありません」

地点の`points`、座標、討伐対象の隠れた位置、最短経路、未探索の構造、イベントの答えは表示しない。放棄機能も追加していない。Aで勝手に受注や報告を行わず、Bで閉じる。

探索・調査・討伐×Lv1〜3、部分達成／完了／未受注、実際の調査後・全滅後の更新、画面の開閉で契約・進捗・ゲーム／フレーバーRNGが変わらないことをテストした。中断再開後のB14F 1/3も同じ画面から確認できる。

## 5. 酒場の見出し

共通イベントの帰り先`field_after`が`pub`の場合だけ、見出しを**「酒場の噂」**にする。その他の探索イベントの見出しは維持。

18件の噂本文、1 TRZ、gameplay 70%／flavor 30%、直前同文回避、読み終わって購入画面へ戻る流れ、保存項目は変更していない。`data/pub_messages.json`は受領版と完全一致。

## 6. 訓練場の予定威力

スキル再取得の確認画面で、支払い前に攻撃／吸収技の**予定威力**を表示する。

```python
skill.power(actor, next_copy=True)
```

6枠満杯時の入替画面と同じAPI。MASTERED済み攻撃の次コピーは1.2倍、未MASTEREDは通常。現在持っている通常コピーを描画だけで強化しない。表示対象は既存の攻撃判定と整合する`damage`／`drain`で、回復・補助へ無意味な攻撃値を出さない。

表示用に確認画面の下部だけ間隔を調整した。回数・価格・実際の取得処理は同じ。取消時のTRZ・所持技不変、満杯時の既存プレビュー、取得後の威力との一致を確認。

## 7. 施設名・メニュー名

`HUB_FACILITIES`と`HUB_MENUS`の英語識別子は維持し、日本語表示を別に定義した。施設画像は同じものを参照する。

| 識別子／旧表示 | 日本語表示 |
|---|---|
| GUILD | ギルド |
| TRAINING | 訓練場 |
| PUB | パブ |
| SHOP | ショップ |
| DUNGEON | ダンジョン |
| ELEVATOR | エレベーター |
| PARTY STATUS | パーティ |
| QUEST | クエスト |
| QUEST RECORD | クエスト記録 |
| HEAR A RUMOR | 噂を聞く |
| SKILL ARCHIVE | スキル図鑑 |
| RESTORE SKILL | スキル再取得 |
| BUY ITEM | 道具を買う |
| SAVE | セーブ |
| HELP | ヘルプ |

関連する拠点・施設・道具・クエスト・再取得の見出しも整合させた。README、Web公開ページ、GKD同梱の操作案内も更新。内部ID、ファイル名、コード例、開発ログや履歴資料を一括日本語置換する処理はゲームへ入れていない。

タイトル、TRZ、MASTERED、COMMON／UNCOMMON／RARE／LEGEND、HP／STR／AGI／INT、Uses、ボス名は今回の一括変更対象にしていない。初回拠点の本文はすでに日本語のため変更しない。隠された救済をヘルプへ追記していない。

## 8. リターン／リバイブ

内部IDは実定義で`return`／`revive`と確認した。`data/skills.json`の**nameの2値だけ**を「リターン」「リバイブ」へ変更。

ひらめき・所持技・能力画面・戦闘／探索の選択・入替・図鑑・再取得・MASTERED通知は既存の`skill.name`を参照する。探索メニューのリターンと使用不可案内も同じ表示名を参照するようにした。技名を「帰還」「蘇生」に変更していない。

能力／戦闘スキル選択／図鑑／訓練場／入替で2つの名前を描画検証。スキル名・MASTERED通知を生成する既存ルールと救済は回帰テストで維持確認。

## 9. 内部ID・性能

62技、ID、式、威力、Uses、CD、再取得価格、MASTERED仕様、成長・閃き率、PHASE 5B-1／5B-2／5Cの性能は変更なし。現在の62行が受領JSONと同一であることを、上記2つのnameだけ例外として比較した。

`rpg/models.py`、`rpg/skill_resources.py`、`rpg/growth.py`、`rpg/quests.py`、`rpg/exploration.py`、`rpg/save.py`、`rpg/suspend.py`、敵データ・行動データ等は受領版のハッシュと一致する。`rpg/battle.py`は使用不可時の表示文字列だけの差をAST比較した。

## 10. ユーザー編集文の保護

スキルdescription全件、酒場本文、クエスト依頼／お礼、ボス名／会話、導入、深層石碑、最終イベント／ENDINGのJSONを維持。今回の変更対象以外のデータを過去fixtureへ戻していない。

従来の検証ツールが「依頼・お礼は1ページ」と仮定していたため、ユーザーの長文に対して途中で受注済みと判断する失敗が出た。**ゲームの本文やページ送り処理は変更せず、検証側を実際のページ数に合わせた。** その後、通常27件とfallback9件で報告／一度だけの報酬／達成率を確認できた。

## 11. 幅とスクロール

既存の美咲BDFと実`text_width()`で確認。画像／パレット／フォントの追加変更はない。

- 6文字48pxの「エレベーター」は右下で矢印文字を付けず、既存の選択枠をカーソルとして使う。文字はx110〜157、選択枠だけ2px拡張。左5施設や64×64施設絵の位置は維持。
- 施設内メニューは既存84px枠内。ヘッダー／フッター／道具説明／クエスト確認／予定威力も160×120内で描画確認。
- 長いスキル説明の148×8px窓、両端の待機、移動速度、選択時の先頭復帰、キー操作は維持。`rpg/text.py`と`App.skill_details()`を変更していない。
- 変更前12画面、変更後14画面を実Pyxelで取得。ブラウザのPC／タッチでも表示と操作を確認。

比較例：

| 対象 | 変更前 | 変更後 |
|---|---|---|
| 拠点 | [前](screenshots/ui6b1_before_hub.png) | [後](screenshots/ui6b1_after_hub.png) |
| パブ | [前](screenshots/ui6b1_before_pub.png) | [後](screenshots/ui6b1_after_pub.png) |
| 訓練場 | [前](screenshots/ui6b1_before_training.png) | [後](screenshots/ui6b1_after_training.png) |
| POTION説明 | [前](screenshots/ui6b1_before_potion.png) | [後](screenshots/ui6b1_after_potion.png) |
| 再取得予定威力 | [前](screenshots/ui6b1_before_preview_mastered.png) | [後](screenshots/ui6b1_after_preview_mastered.png) |
| リターン | [前](screenshots/ui6b1_before_return.png) | [後](screenshots/ui6b1_after_return.png) |
| リバイブ | [前](screenshots/ui6b1_before_revive.png) | [後](screenshots/ui6b1_after_revive.png) |

新しいクエスト画面：[進捗1/3](screenshots/ui6b1_after_quest_partial.png)、[達成・帰還待ち](screenshots/ui6b1_after_quest_return.png)。

## 12. 通常SAVE・中断互換性

形式・バージョン・保存先を変更していない。既存のセーブファイルを消去していない。

変更前コードで作ったテスト用SAVEから、`return` Uses2／`revive` Uses1、MASTERED、banked37 TRZ、調査Lv3・B14F 1/3、デーモン撃破・アムリタ・右隣エレベーターを保持して復元できた。技名は新しい定義で表示される。テスト用の旧中断スナップショットも完全復元し、実バックエンドの一度きり消費も確認。

Webは隔離プロファイルでIndexedDBへ中断→ページ再読込→「中断から」→正確な状態復元→再度クエスト確認に成功。同じ中断が何度も使えるようにはしていない。

既に保存された成長履歴などの過去メッセージは書換えないため、過去の英語名が履歴内に残る場合がある。現所持技の名前と保存履歴の文章を区別し、ユーザーの履歴を勝手に移行しない。

## 13. 自動検証

全件結果は末尾の最終確認に記録する。[全件ログ](ui6b1_all_tests.txt)。追加15件は既に成功し、名称確認を戦闘と入替にも拡張して再検証した。

配布Web payloadの検証：

- B5／B10の通常遭遇、B15通常遭遇なし、音声障害時の進行。
- QUEST通常27件＋fallback9件、お礼、繰返し回数と固有達成率、二重報酬なし。9,527回の文字描画が画面内。
- 同じSessionでB10→B11〜B15→守護者→泉→デーモン→アムリタ→拠点施設／保留→再帰還→献上→最終戦→ENDING。
- 最終戦の5種類の実全滅・再挑戦A〜Eで復元を確認。最終部分101,948回の文字描画が画面内。

ログ：[Web payload](ui6b1_web_payload.txt)、[QUEST記録](ui6b1_web_quest_records_ui.json)、[最終章](ui6b1_web_final_chapter.json)。進行用パーティ・資源を用意した状態検証であり、自然育成での難易度測定ではない。

## 14. PC・Webタッチ・GKD

| 環境 | 確認内容・結果 |
|---|---|
| PC Python／実Pyxelヘッドレス | キーボード相当／D-PAD/A/B、各画面・旧SAVE／中断・描画領域を自動検証 |
| PC Web・隔離Edge／Pyodide | 日本語名、道具説明、クエスト進捗／帰還待ち、中断再開、予定威力、噂の料金／復帰に成功。pageerror 0 |
| タッチエミュレーション・Pixel7設定／Edge | 実タッチイベントのD-PAD/A/Bだけで同じ操作に成功。pageerror 0 |
| 上記2条件×音声使用不可 | AudioContext.suspend＋resume失敗＋visibility／focus等のイベント後も同じ操作に成功。pageerror 0 |
| GKD Pixel2対応 | 全ゲームソースのPython3.11構文を検査。通常ZIPと診断ZIPのゲーム65ファイルがWeb／現ソースと一致。入力マッピング・SELECT終了・ランチャーは維持 |
| iPhone Safari／GKD実機 | 今回未確認。エミュレーションを実機成功として扱わない |

Web結果：[通常音声](ui6b1_browser_running.json)、[音声使用不可](ui6b1_browser_unavailable.json)。既存の音声終了を待たない設計を維持し、今回も音声復旧をUI進行条件にしていない。

## 15. B15エレベーター

デーモン(11,0)の**右隣(12,0)**、Bank1 (120,8)、8×8を維持。デーモン撃破フラグ／ボス撃破記録による出現条件、アムリタ所持、旧左位置中断の退出互換も変えていない。B1〜B15のTilemapを含む全`.pyxres`／`.pyxpal`は受領ハッシュと一致する。

## 16. 更新配布物

- [Webゲーム](../dist/game.html)、[Web案内ページ](../dist/index.html)
- [GKD通常版ZIP](packages/skill_seekers_gkd.zip)
- [GKD診断版ZIP](packages/skill_seekers_gkd_diagnostic.zip)
- 両ZIPに同じ`PLAY_GUIDE_JA.txt`を同梱。

65ゲームファイルが3形式で完全一致、セーブ／キャッシュを含まないことを確認。[配布物・保護照合](ui6b1_packages.json)。GKDの更新は既存フォルダへの上書き・結合で行い、`save/`を削除しない。GitHubへはまだpushしていない。

## 17. 実機未確認事項

iPhone Safari実機での文字サイズ・縦横レイアウト・画面ロック復帰、GKD実機での小画面の読みやすさ・SELECT終了・実コントローラー／睡眠復帰は未確認。現物でのテストを推奨する。今回の実AudioContext停止試験はSafariの`interrupted`状態そのものの観測ではない。

## 18. 既知の問題とセルフレビュー

現行ゲームの新たな進行不能は、今回の確認範囲では検出していない。旧保存履歴の英語名、内部識別子や開発文書の英語は意図して保持する。全噂の既読管理、G08のネタバレ時期、クエスト任意放棄、マップ変更など、今回指定外の監査候補には手を入れていない。

セルフレビューでは、クエスト画面が契約やRNGへ書込まないこと、オーバーレイを閉じて元の探索へ戻れること、Bの処理自体は変えていないこと、予定威力で所持コピーを強化しないこと、全文スクロールと画面境界、旧データ互換を確認した。

### 最終確認

- **全自動テスト734件成功、失敗0・エラー0、451.319秒。** 受領時719件＋今回15件。実セーブを含めない一時コピーで実行した。[ログ](ui6b1_all_tests.txt)。
- 追加15件は、戦闘・入替での2つの技名確認を拡張した後にも再実行し、15/15成功（12.969秒）。
- WebのPC／タッチ×通常音声／音声使用不可の4ケースが成功。クエスト表示と中断復元、道具説明、ラベル、再取得確認、噂購入の入力を検証。各ケースのpageerrorは0。
- **長文スクロールのWeb回帰もPC／タッチの2ケース成功。** 音声使用不可の条件で全文の先頭→末尾、選択・再オープン時のリセット、戦闘・状態画面のA/B、B15右隣へ歩行→中断→一度だけ再開→帰還→献上確認まで通過。[結果](ui6b1_scroll_browser_unavailable.json)。
- 更新済みWeb payloadで通常27件＋fallback9件のQUEST記録、B10→ENDING、実全滅・再挑戦A〜Eが成功。[ログ](ui6b1_web_payload.txt)。
- 変更前後・Webの比較画像は計62枚。いずれも実描画／ブラウザキャプチャで、ゲーム素材の編集ではない。
- 最終配布物照合：Web／GKD通常／GKD診断の65ゲームファイルが完全一致。Python3.11構文、セーブ非同梱、両ZIPの日本語操作案内を確認。受領した実セーブ`rpg/save/save.json`は同じハッシュを保持。
- 全資源・音声・マップ・ユーザー編集本文と62技の性能は保護検査を通過。変更データは2つのスキル表示名だけ。空白不備のdiffチェックも通過。
- iPhone Safari／GKD Pixel2の**実機は未確認**。Git commit／pushは行っていない。
