# PHASE 6B-1 クエスト再受注クラッシュ修正

調査日：2026-11-05。対象は、この依頼の開始時に存在した未コミット変更を含む作業ツリー。

## 1. PC版での再現

再現した。NEW GAME → パブで討伐Lv1受注 → 対象敵との戦闘で勝利 → 安全帰還 → お礼・報酬 → パブで討伐Lv1再受注、という順序で発生した。

headlessのupdate/drawだけでなく、**通常の可視Pyxelウィンドウ**でも同じ例外を取得した。ウィンドウ検証はゲームパッド相当の入力をプログラムから与え、各フレームで実際のupdate/draw/flipを実行した。人間が物理キーを操作したテストではない。

移動だけはテストを短縮するため、実際に生成されたQUEST地点・B1入口へ座標を移すフィクスチャを使用した。通常探索の全経路を歩いたという意味ではない。討伐の敵・能力・HP・勝敗は変更せず、既存UIからSKILL/GUARDを選び、実際に戦闘・結果・報告・再受注を行った。

証跡：

- [修正前の通常ウィンドウ状態・入力記録](quest_reaccept_before_native.json)
- [修正前の完全なトレースバック](quest_reaccept_before_native_trace.txt)
- [修正後の通常ウィンドウ状態・入力記録](quest_reaccept_after_native.json)
- [修正後の画面](quest_reaccept_after_native.png)

## 2. 例外とスタックトレース

例外は `ValueError: 討伐対象はいません。`。PC通常ウィンドウで取得した完全なスタックトレースを上記TXTへ保存した。呼び出し経路は以下。

```text
tools/verify_quest_reaccept.py:27 main
  → tests/quest_reaccept_flow.py:86 accept
  → tests/quest_reaccept_flow.py:51 tick
  → rpg/dungeon_app.py:787 update                 # 修正前
  → rpg/dungeon_app.py:774 observe_hunt_goal       # 修正前
  → rpg/exploration.py:235 hunt_victory
ValueError: 討伐対象はいません。
```

例外直前のPC状態：

| 項目 | 値 |
|---|---|
| 画面 | `quest_board` / overlayなし |
| 前回戦闘 | `battle_kind='quest_hunt'`, `outcome='VICTORY'` |
| 戦闘清算 | `session.settled=True` |
| 新しい依頼 | 討伐Lv1 / `hunt_l1_02` / B2F / 地点(18,20) / 敵bat |
| 新しい進捗 | 0 / 未完了 |
| 仮受注データ | `pending_quest=None`（受注確定済み） |
| 前の達成記録 | `hunt_l1_01`、討伐クリア回数1 |
| BANKED TRZ | 7 = 初期3 + 報酬4 |
| 現在位置 | B1F (3,2)、拠点帰還後 |

## 3. 根本原因の場所

`rpg/dungeon_app.py` の `observe_hunt_goal()`（現在768行目、条件は770～771行目）。例外を送出した場所は `rpg/exploration.py` の `hunt_victory()`（233～235行目）。

`DungeonApp.update()` は毎フレーム、画面の入力処理より前に討伐勝利を監視する。討伐戦を清算して探索・拠点へ帰った後も、直前の `battle` と `battle_kind` は保持される。

修正前の監視条件は「討伐戦・勝利・現在受注中の依頼が未完了」だけで、**その勝利が既に清算済みかを確認していなかった**。新しい依頼を受けた次の更新で、前回の勝利を新しい依頼の勝利として処理した。現在位置は新しい討伐地点ではないため、`hunt_victory()` の妥当性チェックで停止した。

また、新しい依頼の討伐地点にいた場合は、例外にならず、まだ倒していない新依頼を達成扱いにする可能性もあった。この条件も回帰テストへ追加した。

## 4. 初回と再受注で異なる理由

初回は前回の討伐勝利が存在しない。初回撃破後も旧依頼が完了済みの間は `not q['completed']` がFalseになる。報告でactive_questが解除された後も判定対象がない。

再受注で新しい未完了依頼が設定された瞬間だけ、残っていた旧勝利と新依頼が誤って結び付く。新しい依頼が探索・調査でも同様で、抽選済み3件が尽きたこと自体は原因ではない。

受注可能判定・flavor抽選・安全地点生成・履歴・報酬確定・QUEST確認UIは原因ではなかった。受注確定処理は正常に完了し、仮受注データの解除・乱数状態の確定も済んでいた。

## 5. 暗転の原因

受注確定時に暗転する専用演出はない。未捕捉のPython例外によるゲーム処理の終了が原因。Webでは同じ例外で更新が停止した。GKDの暗転そのものは直接観測していないため、ランチャーへ戻る際の表示などの詳細は実機未確認。

## 6. PCとGKDの共通性

該当箇所はPC/GKD/Webで共通の `DungeonApp`。ハードウェア性能・GKDランチャー・音声待機処理に依存しないゲームロジックの不具合だった。PCと修正前Webでは実際の同一例外を取得した。

GKD実機のPython例外ログは今回取得していない。ユーザーが報告したGKD症状は同じ操作順・共通コードと整合するが、実機で原因と修正結果を確認済みとは扱わない。

## 7. 変更したファイルと内容

### ゲーム本体

`rpg/dungeon_app.py` の監視条件に **`not self.session.settled`** を追加しただけ。コメントも追加した。

```python
if (self.battle_kind == 'quest_hunt' and self.battle and
        self.battle.outcome == 'VICTORY' and not self.session.settled and q and not q['completed']):
    self.hunt_goal_lines = self.exploration.hunt_victory()
```

現在の戦闘で勝利した直後、清算前に達成を記録する既存順序は維持した。清算済み勝利は新依頼へ適用しない。例外の握りつぶし・履歴初期化・再受注禁止・セーブ項目追加は行っていない。

### テスト・検証用

| ファイル | 内容 |
|---|---|
| `tests/test_quest_reaccept.py` | 再受注・7種別組み合わせ・5回連続・全固有達成後・SAVE/LOAD・中断・古い勝利の誤達成を検証する6テスト |
| `tests/quest_reaccept_flow.py` | NEW GAMEから実際の更新・描画・入力・戦闘を通す共通ドライバー。保存先は一時ディレクトリ |
| `tests/fixtures/quest_reaccept_before.json` | 作業開始時の66ファイルのハッシュと修正前ソース。実セーブはハッシュのみ |
| `tests/quest_reaccept_preservation.py` | ゲームソースのAST差分を上記条件追加だけに限定、他データ・アセットのハッシュを照合 |
| `tests/ui_phase6b1_preservation.py` | 最新の厳密な保護検証へ接続。古いスナップショットは書き換えていない |
| `tests/test_persistent_poison.py` | 演出を省略するfinishフィクスチャに、実際と同じ「討伐達成判定→清算」の順序を追加。毒・安全帰還・達成の既存アサーションは維持 |
| `tools/snapshot_quest_reaccept.py` | 作業開始状態の読み取り・スナップショット取得 |
| `tools/verify_quest_reaccept.py` | 可視ウィンドウ/headlessの再現・状態・完全な例外記録 |
| `tools/verify_browser_quest_reaccept.py` | 配布HTMLを実ブラウザで操作、修正前・修正後・タッチ・音声不可を検証 |
| `tools/verify_quest_reaccept_packages.py` | Web/GKD通常/GKD診断の65ファイル一致、Python 3.11構文・実セーブ保護を検証 |
| `verification/quest_reaccept_*` と本書 | 検証結果・画面・ログ |

恒久的な診断フックはゲーム本体へ追加していない。Web検証ツールの例外記録フックは隔離ブラウザ内だけに存在し、例外は必ず再送出する。

## 8. NEW GAME再現条件の修正結果

正常。PC通常ウィンドウで2回の討伐を連続して受注・撃破・報告。最後はHUB、討伐回数2、固有ID2件、BANKED TRZ 11、active_questなし。清算済みの旧戦闘を保持したままでも正常に進むことを確認した。

新規回帰テストは修正前コードで同じValueErrorによって失敗し、条件追加後に成功した。

## 9. 討伐から探索への切り替え

次の7通りを、それぞれNEW GAMEから実際の前依頼達成・報告後に確認した。次依頼は有効になり、進捗0、前の履歴・クリア回数・所持TRZは受注前と同じ。

| 前回達成 | 次回受注 | 結果 |
|---|---|---|
| 討伐Lv1 | 討伐Lv1 | 成功 |
| 討伐Lv1 | 探索Lv1 | 成功 |
| 討伐Lv1 | 調査Lv1 | 成功 |
| 探索Lv1 | 討伐Lv1 | 成功 |
| 探索Lv1 | 探索Lv1 | 成功 |
| 調査Lv1 | 討伐Lv1 | 成功 |
| 調査Lv1 | 調査Lv1 | 成功 |

Webでも、討伐を2回報告後に探索Lv1を受注し、進捗0のまま正常に継続できた。

## 10. 全固有依頼達成後と繰り返し

討伐Lv1を5回連続クリアし、固有ID全3件・クリア回数5を確認。全3件を達成しても再受注・再クリアが可能。その後の探索Lv1受注・クリアも成功。

報酬合計は初期3 + 各依頼の定義済み報酬の合計と一致。報告後に更新を繰り返しても追加支払いは発生しない。固有IDの重複も発生しない。

## 11. セーブ互換性

セーブ・中断のコードと形式を変更していない。旧通常セーブ、旧中断データを用いる既存互換テストを維持。

新テストでは、実際のGUILDのSAVE画面から隔離ファイルへ保存 → CONTINUE → 討伐再受注・報告 → 探索へ切り替え → 中断保存・消費・復元 → QUEST進捗表示 → 探索報告 → 再SAVEまで確認した。中断復元後のデータは保存直前と一致し、再SAVEのクリア回数は探索1・調査0・討伐2。

実際の `rpg/save/save.json` は読み取りハッシュのみ使用し、開始時から不変。検証用バックエンド・ブラウザプロファイルは隔離した。通常ZIP・診断ZIP・Web埋め込みにユーザーセーブは同梱していない。

## 12. 全自動テスト

**最終全件実行：740件成功、失敗0・エラー0、321.019秒。** 実セーブを含めない新しい隔離コピーで実行した。従来734件に新規6件を追加。

初回全件実行は740件中1件失敗（既存の毒継続テストの省略フィクスチャ）。本体の実際の順序と異なり、達成監視より先に清算していたため。そのフィクスチャを実ゲームの順序へ合わせ、毒継続17テストは成功した。ゲーム本体の修正範囲は拡大していない。

- [最終全件ログ](quest_reaccept_all_tests.txt)
- [初回全件ログ](quest_reaccept_first_tests.txt)
- [配布Webペイロード回帰ログ](quest_reaccept_web_payload.txt)

配布Webに埋め込まれたソースもPC Python/Pyxelで実行し、全27依頼のお礼・記録（fallback9件も含む）、SAVE/CONTINUE、B10→ENDING・実際の全滅再挑戦5ケースの既存回帰を確認した。これは実ブラウザテストとは別の検証。

## 13. PC UI操作結果

通常の可視ウィンドウで、修正前の再現・例外取得、修正後の2周継続を実施。1節の入力自動化・移動フィクスチャという範囲制限がある。

以前の単純な受注テストは、実際の討伐勝利オブジェクトを残したまま報告・再受注する順序を通らないため、この問題を捉えられなかった。今回のテストは旧battleのVICTORYとsettled=Trueが残っていること自体も確認する。

## 14. Webブラウザ結果

Microsoft Edgeの実Pyxel/Pyodide実行環境、隔離ブラウザプロファイルで確認した。キーボードは実際のkeydown/up、タッチは実際のD-PAD/A/BのDOMボタンへタッチイベントを送った。移動と戦闘コマンドのカーソル位置には検証用フィクスチャを使用し、勝敗・報告・再受注結果は変更していない。

| 条件 | NEW GAME→討伐報告→再受注→再報告→探索受注 |
|---|---|
| 修正前Web / PCキーボード | 同じValueErrorを再現 |
| 修正後Web / PCキーボード / 通常AudioContext | 成功 |
| 修正後Web / タッチ端末エミュレーション / 通常AudioContext | 成功 |
| 修正後Web / PCキーボード / AudioContext suspend・resume失敗 | 成功 |
| 修正後Web / タッチ端末エミュレーション / AudioContext suspend・resume失敗 | 成功 |

音声不可検証では実際のAudioContextをsuspendし、resumeを失敗させ、visibilitychange/blur/focus/pageshowを送信した。音声終了をゲーム進行条件にする変更は一切行っていない。通常条件でも自動検証のブラウザ出力はmuteしており、聴感評価はしていない。

証跡：[修正前](quest_reaccept_browser_before.json) / [修正後・通常](quest_reaccept_browser_running.json) / [修正後・音声不可](quest_reaccept_browser_unavailable.json)。タッチはPixel 7設定のChromium系エミュレーションで、iOS Safari実機テストではない。

## 15. GKD向け検証と未確認事項

通常ZIP・診断ZIP・Webのゲームソース／JSON／アセット65ファイルを現在の作業ツリーとバイト単位で照合し、一致した。両GKD版に同じ修正が含まれる。

各パッケージの全Pythonソースを `ast.parse(feature_version=(3,11))` で検査し、Python 3.11構文互換を確認した。これはGKD上のPython 3.11.7／Pyxel 2.9.9で実行したという意味ではない。**GKD Pixel 2実機およびiOS Safari実機は未確認**。ユーザーの実機で討伐Lv1を1回報告後、もう一度受注・撃破・報告する最終確認が必要。

証跡：[パッケージ照合](quest_reaccept_packages.json)。

## 16. 更新した配布物と変更保護

- `dist/game.html`
- `verification/packages/skill_seekers_gkd.zip`（通常版、67エントリ）
- `verification/packages/skill_seekers_gkd_diagnostic.zip`（診断版、70エントリ）

取得時の66ファイルを照合し、ゲーム本体で変わったのは `rpg/dungeon_app.py` だけ。そこもAST比較で監視条件の追加以外に変更がないことを検証した。

全62スキルの性能・Uses/CD・MASTERED・救済演出・敵/AI・エンカウント・QUEST抽選/報酬/解放・セーブ形式・BGM/SE・マップ/画像・各ユーザー編集文・最終戦/ENDINGを維持。B15エレベーターも右隣(12,0)、Bank1(120,8)、8×8のまま。既存PHASE 6B-1のQUEST確認・日本語表記・長文スクロール・施設UIも維持。

Git commit / pushは行っていない。

## 17. 残る問題・追加確認

- このクラッシュと旧勝利による誤達成について、確認したPC/Webの条件では再発なし。
- ユーザーが持つ「固有依頼全件クリア済み」の実セーブは未提供のため、そのファイル自体の再現はしていない。同条件はNEW GAMEから作成し検証した。
- GKD実機・iOS Safari実機の最終操作確認と、公開GitHub Pagesへの配備後のキャッシュ更新確認は未実施。ローカルWeb配布物を実ブラウザで検証したもので、公開URLが更新済みという意味ではない。
- 検証の移動フィクスチャ、PC入力自動化、タッチエミュレーション、Python 3.11構文検査の範囲を、実機での通しプレイと区別する。

再検証例（プロジェクト直下）：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_quest_reaccept.py --window --label after_native
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_quest_reaccept.py --playwright-path .tools/browser
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_quest_reaccept.py --playwright-path .tools/browser --disable-audio
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_quest_reaccept_packages.py
```

全テストは実セーブをコピーしない一時作業ツリーで `python -B -X utf8 -m unittest discover -s tests` 相当を実行した。通常ウィンドウ・ブラウザの検証ツールも実セーブは使用しない。
