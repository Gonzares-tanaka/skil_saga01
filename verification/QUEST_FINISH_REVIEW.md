# QUEST仕上げ 実装・検証報告

通常固有QUEST **27件（探索9・調査9・討伐9）**を固定対象とし、お礼イベント、累計CLEAR、固有達成履歴、GUILDのQUEST RECORD、未達成優先抽選を実装しました。汎用fallback9件はコンプリート対象外です。

## 指定された26項目の報告

| # | 項目 | 実装・確認結果 |
|---|---|---|
| 1 | complete_linesを追加したファイル | `data/quest_flavors.json`。既存の`id / requester / lines`に`complete_lines`を追加。 |
| 2 | 通常27件 | 全27件に固有の2～3行のお礼を追加。元の人・物・痕跡、研究内容、討伐の被害軽減へ対応。Lv3調査も本編の核心を確定しない表現。 |
| 3 | fallback9件 | 全9件に種別・Lv別の汎用のお礼を追加。通常候補には混ぜない。 |
| 4 | 安全帰還のお礼 | `DungeonApp.enter_camp(returned=True)`から`quest_thanks`へ。入口・RETURNが同じ経路を使用。元の`requester`と`complete_lines`を参照。 |
| 5 | 処理順 | 目的達成 → 安全帰還 → お礼（A） → 報酬画面 → Aで通常HUB。お礼の最後のAで報酬・記録更新・受注解除を一括実行し、更新済みの報酬画面へ移る。未確定TRZの確保とHP回復は既存どおり帰還時。 |
| 6 | quest_clear_counts | `Exploration`内の`{"explore": 0, "investigate": 0, "hunt": 0}`。通常dict。 |
| 7 | completed_quest_ids | `Exploration`内の重複しない通常IDのlist。初期値`[]`。 |
| 8 | CLEAR加算 | 安全帰還後、お礼を読み終えた正式完了時に該当種別のみ+1。ダンジョン内の目的達成時は加算しない。 |
| 9 | 二重加算防止 | `finalize_quest_completion()`に集約。安全帰還済み・有効な受注・目的達成を検査し、処理後に受注と`completion_ready`を解除。同じ呼び出しを繰り返しても無処理。 |
| 10 | fallback除外 | `rpg/quests.py`の固定`QUEST_COMPLETION_IDS`に含まれ、実際に同じ通常フレーバーへ解決できるIDだけ登録。`*_default`、欠損、未知、別カテゴリ・LvのIDは登録しない。集計も固定IDとの積集合を使用。 |
| 11 | 探索の分母 | 9。 |
| 12 | 調査の分母 | 9。 |
| 13 | 討伐の分母 | 9。 |
| 14 | TOTALの分母 | 27。fallbackを含めた36にはしない。27/27は100%。 |
| 15 | QUEST RECORD追加場所 | `rpg/hub.py`のGUILDメニュー。PARTY STATUS / QUEST RECORD / HELP。描画・操作は`rpg/dungeon_app.py`。 |
| 16 | 表示内容 | 種別、再クリア込みのCLEAR、固有達成数、整数％、TOTAL達成数・％。全達成時はCOMPLETE!。BでGUILDへ戻る。追加報酬なし。 |
| 17 | 未達成優先 | 選択したTYPE+Lvの通常3件に未達成があれば、その候補から選択。全達成後は通常候補へ戻す。既存の直前受注ID回避と独立した文章用乱数を維持。 |
| 18 | NEW GAME初期化 | 既存の新規`Exploration`生成でdictを全種別0、listを空へ初期化。お礼画面のページ・領収データも初期化。 |
| 19 | 将来SAVEするデータ | `quest_clear_counts`と`completed_quest_ids`。JSONへ直接保存できるdict/list。今回SAVE/LOADは追加していない。 |
| 20 | hunt_l1_03 | 「入口近くをうろつく魔物が」→「浅い階層をうろつく魔物が」。 |
| 21 | hunt_l2_03 | 「魔力の強い魔物が現れた。」→「危険な魔物が現れた。」。 |
| 22 | 既存QUEST回帰 | 全9カテゴリのPUB選択・プレビュー・辞退・受注・現地達成・RETURNを確認。討伐の実戦・RUN・無音・全滅、既存TRZ処理を維持。旧バックエンドの即時報告APIは互換用に残し、ゲームUIは必ずお礼付き遅延完了を使用。 |
| 23 | PC確認 | Python 3.13.7 / Pyxel 2.9.9、headlessの実Pyxelで全202ユニットテスト成功。GUILD、帰還、27通常+9汎用のお礼・記録画面を仮想D-PAD/A/Bで描画・操作。画面外描画を検出する検査と主要スクリーンショットの目視確認を実施。通常のウィンドウでの手動操作確認は未実施。 |
| 24 | Web確認 | `dist/game.html`再生成済み。埋め込みZIPのコード・JSON・資源が現行ファイルと一致することを検査。抽出した配布ペイロードを実Pyxelで実行し、QUEST9カテゴリ、27件達成、9汎用、GUILD、無音操作を確認。加えてB10→ENDING・実際の5連続全滅/再挑戦が成功。ブラウザ上の実ランタイム実機確認とは区別する。 |
| 25 | スマートフォン確認 | D-PAD/A/Bだけで新画面の全操作が完結することを自動検証。既存HTMLの6ボタン・AudioContext復帰コードの存在も検査。iOS/Android実機・画面ロック復帰の直接試験は未実施。 |
| 26 | 既知の問題 | 検証範囲内で新たな進行不能・二重報酬・記録不整合は検出なし。SAVE未実装なので終了時に記録は消える。ブラウザ/スマートフォン実機確認は残る。既存B15は安全な候補が1地点のため調査Lv3はB11～B14から選ぶ仕様を維持。 |

既存のNEW GAME初期3 TRZは変更していません。今回3 TRZを追加で付与する処理はなく、既存の初期値をそのまま維持しています。

## 必須CASE 1～28

下表の「成功」は自動検証での結果です。全27件のお礼UI検証では目的達成フラグを設定するfixtureを使用し、現地接触・実戦・RETURNは別の9カテゴリ通し検証で確認しています。自然育成バランスや実機ブラウザを検証したという意味ではありません。

| CASE | 確認結果 | 主な証跡 |
|---|---|---|
| 1 | 成功：通常27件の同一依頼人・対応お礼 → 報酬 → HUB。 | `verify_quest_records_ui.py` |
| 2 | 成功：investigate_l2_01の歴史研究者が古代水脈・論文についてお礼。 | 同ツール、専用thanks/reward画像 |
| 3 | 成功：達成後全滅でもお礼・報酬・CLEAR・固有ID更新なし。受注を残して進捗リセット。 | `test_quest_completion.py`、QUEST UI、Phase 6D実戦全滅 |
| 4 | 成功：9カテゴリで実際のRETURN操作から同じお礼・報酬・記録。 | `verify_phase6d_ui.py` |
| 5 | 成功：探索正式完了で探索のみ0→1。 | completionユニット/UI |
| 6 | 成功：同一ID再クリアで探索1→2、固有IDは1件。 | completionユニット |
| 7 | 成功：調査正式完了で調査のみ+1。 | completionユニット/UI |
| 8 | 成功：討伐正式完了で討伐のみ+1。 | completionユニット/UI |
| 9 | 成功：再帰還・GUILD出入り・完了API再呼び出しで二重加算・二重報酬なし。 | completionユニット/UI |
| 10 | 成功：初期各0/9、TOTAL0/27。 | initial画像、completionユニット |
| 11 | 成功：explore_l1_01初達成で探索1/9、TOTAL1/27。 | 同一IDテスト |
| 12 | 成功：再達成でも固有1/9のまま。 | 同一IDテスト |
| 13 | 成功：探索9/9・100%。 | explore_complete画像、UI |
| 14 | 成功：全27/27・100%・COMPLETE!。 | all_complete画像、UI |
| 15 | 成功：汎用/未知IDはCLEARのみ増加し、固有数不変・分母27。 | completionユニット/UI |
| 16 | 成功：調査Lv2で01達成済みの場合、候補は02・03のみ。 | 抽選候補を直接確認するユニットテスト |
| 17 | 成功：調査Lv2全達成後、直前IDなしなら3候補すべてへ戻る。 | 同ユニットテスト |
| 18 | 成功：通常27件の抽選でfallbackが出ない。候補欠損時のみfallback。 | 27件順次達成・既存フレーバーテスト |
| 19 | 成功：GUILD→QUEST RECORD。 | GUILD/UI |
| 20 | 成功：BでGUILDへ戻る。 | GUILD/UI |
| 21 | 成功：各種CLEAR・固有数・整数％、TOTALを検査。 | completionユニット/UI |
| 22 | 成功：新UIで9,005回の文字描画を実フォント幅・160×120内検査。主要画面の目視も実施。 | quest_records_ui.json、画像 |
| 23 | 成功：PARTY STATUS・HELP・B帰還が正常。 | GUILD/UI |
| 24 | 成功：通常探索9・調査9・討伐9＝27。 | 固定カタログテスト、保存前後データ比較 |
| 25 | 成功：汎用9件は固定カタログから除外。欠損・別LvIDも固有登録なし。 | completionユニット/UI |
| 26 | 成功：通常27件すべてに2～3行のお礼あり。 | データテスト・全件描画 |
| 27 | 成功：fallback9件すべてにお礼あり、表示可能。 | データテスト・全件描画 |
| 28 | 成功：既存通常27件のID・依頼人はすべて同一。既存依頼文の変更は指定2件のみ。 | quest_finish_preservation.json |

## 変更範囲・回帰確認

作業開始時の52ファイルをSHA-256で比較し、本体で変更したのは`rpg/dungeon_app.py`、`rpg/exploration.py`、`rpg/hub.py`、`rpg/quests.py`、`data/quest_flavors.json`のみです。

- B1～B15を格納する全`.pyxres`、パレット、画像、BGM/SE資源は変更なし。
- 敵、スキル、QUEST報酬・階層条件、ショップ/PUB価格、成長率のJSONは変更なし。
- 通常戦闘、全滅、RETURN、デーモン、アムリタ、ロードオブエリシオン、FINAL BATTLE CHECKPOINTの本体コードは変更なし。
- 既存の検証スクリプトで「達成帰還→即return_result」を期待していた箇所を、新しい「quest_thanks→quest_reward」へ更新。最初の最終章回帰検証はこの旧前提で停止しましたが、前提更新後にB10→ENDINGと5連続全滅/復元が成功しています。
- 音声APIのplay/playm/stop/play_posが例外を返しても、追加したお礼・記録画面は待機せず操作できます。AudioContext/HTML復帰処理自体は変更していません。
- 既存のバックエンド`completed`（Lv完了の旧set）と新しい`completed_quest_ids`は別用途として維持。最終戦チェックポイント復元を3回行っても新規QUEST履歴が変化しないことを確認しました。

## 実行した検証と証跡

- 全ユニットテスト：**202件成功**（うちQUEST関連26件）。
- `tools/verify_phase6d_ui.py`：9カテゴリの受注・現地達成・RETURN、討伐実戦/RUN/全滅、無音、TRZを確認。8,070回の画面内文字検査。
- `tools/verify_feedback_ui.py`：QUEST、帰還、全滅、宝箱・泉・MASTERED回帰成功。
- `tools/verify_hub_ui.py`：拠点5施設、GUILD STATUS/RECORD/HELP成功。
- `tools/verify_quest_records_ui.py`：通常27件・汎用9件の帰還UI、100%、再クリア、NEW GAME初期化、無音、D-PAD/A/B成功。
- `tools/build_web.py`：現行本体・データ・資源を`dist/game.html`へ再格納。
- `tools/verify_web_build.py --phase6d --quest-records`：配布ペイロード一致検査と同じQUEST UI検証が成功。
- `tools/verify_web_build.py --final-chapter`：配布ペイロードでB10→ENDING、5連続全滅/再挑戦、通常全滅隔離を確認。最終戦部分46,492回の画面内文字検査。
- `git diff --check`：空白エラーなし。

JSON証跡：`quest_records_ui.json`、`web_quest_records_ui.json`、`phase6d_ui.json`、`web_phase6d_ui.json`、`web_final_chapter.json`、`quest_finish_preservation.json`。

スクリーンショット：`verification/screenshots/quest_record_*.png`。このフォルダは既存設定でGit対象外です。

再検証コマンド（利用可能なPython環境で実行）：

```bash
python -m unittest discover -s tests
python tools/verify_quest_records_ui.py
python tools/verify_phase6d_ui.py
python tools/build_web.py
python tools/verify_web_build.py --phase6d --quest-records --final-chapter
```
