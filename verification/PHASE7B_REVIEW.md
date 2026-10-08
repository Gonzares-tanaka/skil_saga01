# Phase 7B：ブラウザlocalStorage SAVE / LOAD

確認日：2026-10-08。Phase 7Aの共通SaveDataを変更せず、保存媒体としてBrowserSaveBackendを追加しました。

PCブラウザの確認は実際のMicrosoft Edgeをheadlessで起動し、配布用`dist/index.html` / `dist/game.html`をHTTP配信して行っています。HTML内のPyxel / Pyodide / WASM / localStorageを実際に動かしたテストです。スマートフォンの確認は、同じブラウザのPixel 7エミュレーションとタッチイベントを使用しています。実機Android / iOS Safariでの確認ではありません。

## 1. BrowserSaveBackendの場所

`rpg/save.py`の`BrowserSaveBackend`です。ゲームUIやSaveData変換を作り直していません。

## 2. 共通インターフェース

両バックエンドとも`read()` / `write(data)` / `available`を提供し、同じSaveManagerから扱います。BrowserSaveBackendには`exists()`もあります。既存FileSaveBackendへ不要な変更は加えていません。

## 3. バックエンド選択

`rpg/save.py`の`default_backend()`だけで選びます。画面ごとのブラウザ判定は追加していません。

## 4. ブラウザ判定と実ランタイム

`sys.platform == 'emscripten'`ならBrowserSaveBackend、それ以外のPC PythonではFileSaveBackendです。実Web版でもこの値とクラス名を確認しました。

配布HTMLが読み込むのは[公式Pyxel 2.9.9のランタイム](https://cdn.jsdelivr.net/gh/kitao/pyxel@2.9.9/wasm/pyxel.js)です。そのコード内のPyodide 314.0.4とWASM版Pyxelを使用します。既存音声状態表示でも使っている`js`モジュールから`window.localStorage`へ直接接続し、新しい独自JSブリッジは追加しません。[Pyodideの型変換仕様](https://pyodide.org/en/stable/usage/type-conversions.html)に従い、文字列を受け渡します。getItemの未保存時nullは、現行版のjsnullと旧版のNoneの両方を未保存として扱います。

## 5. localStorageキー

`BROWSER_SAVE_KEY = 'skill_seekers_save_v1'`を`rpg/save.py`に一箇所だけ定義しました。SaveData内の`save_version = 1`とは別の定数です。日時付きURLクエリや端末情報はキーに含めません。

## 6. JSON保存

Phase 7Aと同じ`make_save_data()`の全データを`json.dumps(ensure_ascii=False, indent=2, allow_nan=False)`でJSON文字列にしてsetItemします。LOADはgetItem → json.loads → 既存の検証 → apply_save_dataの順です。別スキーマ、ブラウザだけの項目削減、pickleはありません。

## 7. SAVE成功判定

同期APIのsetItemが例外なしで完了した後だけ、既存UIが「セーブしました。」を表示します。保存失敗時は成功表示を出しません。音声、Promise待ち、チャンネル終了待ちは保存処理にありません。

## 8. localStorage例外

localStorageプロパティの取得自体、getItem、setItemのすべてを例外処理の対象にしています。実ブラウザでQuotaExceededErrorを注入したSAVE、SecurityErrorを注入したREADを確認しました。単体テストではgetItem自体の失敗も確認しています。元の保存とゲーム状態を保ち、既存の失敗画面から戻れます。仮想ファイル保存へのフォールバックはありません。

## 9. SAVEなし

キーがない場合はNoSaveErrorとして「セーブデータがありません」を表示します。空文字の保存は「保存なし」でなく破損JSONとして扱います。起動時にlocalStorageへアクセスしないため、アクセスできない環境でもNEW GAMEを開始できます。

## 10. 壊れたSAVE

壊れたJSON、重要キー欠損、型不正、配列ルートなどは既存検証とエラーハンドラーで拒否します。LOAD失敗時は削除・自動上書きをしません。現在のゲーム状態も途中適用しません。

## 11. 未知save_version

999やboolはPhase 7Aの`migrate_save_data()`で拒否します。この関数とバージョンは変更していません。将来の移行処理を追加する入口も同じです。

## 12. PCブラウザSAVE

Edgeの実Pyxel Web上でNEW GAME → INTRO → HUB → GUILD → SAVE → はいをキーボードから操作し、localStorageに共通SaveDataが保存されました。日本語の成長履歴も文字化けなく往復しました。ブラウザ仮想FSに`save/save.json`は作られていません。

## 13. PCブラウザLOAD

ページ再読み込み後にCONTINUEから正常復元しました。タブを閉じて同じURLを再表示した場合と、同じ隔離プロファイルでEdgeのブラウザプロセスを閉じて再起動した場合も復元できました。通常HUB開始で、INTRO / HUB PREVIEW / HUB INTROは再表示されません。

## 14. PCブラウザ再SAVE

LOAD後、ゲームと同じSession / Battleで3戦を解決し、QUEST進捗とTRZを更新して再SAVEしました。TRZ22、戦闘回数131、調査進捗2を含む最新SaveDataが、タブ再表示後に一致しました。戦闘の準備能力値は検証専用で、ゲームの敵・バランスデータは変更していません。

## 15. スマートフォンブラウザSAVE

Pixel 7相当の画面・タッチ環境を使ったChromiumエミュレーションで、十字キー・A/BからSAVE成功を確認しました。実機スマートフォンの確認は未実施です。

## 16. スマートフォンブラウザLOAD

同じエミュレーションで再読み込み・タブ再表示・ブラウザプロセス再起動後のCONTINUEを確認しました。実機のSafari / Chromeの保存保持設定は未確認です。

## 17. スマートフォン操作

既存のHTMLボタンへ実際のタッチイベントを送り、選択・確認・取消・エラーからBで戻る・CONTINUEを操作しました。プレイ用の新しいボタンや文字入力は追加していません。保存成功画面のスクリーンショットでも文字と操作ボタンの表示を確認しました。

## 18. PARTY

HP / MAX HP / STR / AGI / INT / 成長タイプ / 名前 / sprite / 成長履歴を含む全SaveDataが保存前後で一致しました。

## 19. SKILL / Uses

技構成・順番・現在Uses・最大Uses・所持コピーの強化フラグを復元しました。初回保存でpunch17 / fire2 / return2を確認しています。共通のデータ復元処理は変更していません。

## 20. DISCOVERED / MASTERED

共通の両集合とmastered_copyを復元します。再取得時1.2倍の既存ルールを変更せず、復元時に再習得処理を呼びません。全SaveData比較と共通単体テストが成功しました。

## 21. ITEM

POTION2 / PHOENIX ASH7 / REMEDY9が保存前後で一致しました。上限9は既存検証のままです。

## 22. TRZ

初回保存17 → LOAD17で、初期3は加算されません。再SAVE後は22を復元しました。UNBANKEDは保存せず0で始まります。NEW GAME後の明示的な上書き保存では3に戻ります。

## 23. TOTAL BATTLES

128 → LOAD128 → 3戦 → 再SAVE131を確認しました。加算ルール、最終戦再挑戦時の累計を巻き戻さない仕様は変更していません。

## 24. QUEST RECORD

探索5 / 調査3 / 討伐2を保持しました。CLEARの更新ルールは変更していません。

## 25. completed_quest_ids

固有達成済み3件を保持しました。通常27件を分母とする既存UI計算を維持し、Web配布物からの27/27・100%回帰テストも成功しました。fallback9件は対象外です。

## 26. active_quest / flavor_id

調査Lv2、同じ対象階、必要数、途中進捗1、`investigate_l2_01`を復元しました。依頼人・依頼文も同じIDから一致します。再SAVEで進捗2を復元しました。座標はPhase 7Aの既存安全地点再構築に任せ、保存していません。全3種×3Lvの共通単体テストも成功しました。

## 27. ダンジョン進行

撃破済み4 / 9 / 14（内部0始まり）とストーリーフラグが一致しました。B5 / B10による階層・QUEST Lv解放は既存ロジックを使用します。全54ファイルを変更前ハッシュと比較し、許可した保存モジュールと読込エラー表示以外のゲームコード・データ・画像・音声・マップに差分がないことを確認しました。

## 28. アムリタ

has_amrita=Trueを保持しました。通常ITEM外のKEY ITEMのままです。LOAD直後は献上確認を出さず、外へ出て帰還すると既存の確認が出ます。「後で」で通常HUBへ戻れました。最終イベント開始・最終撃破・力消費フラグも共通スキーマで保存・検証されます。

## 29. FINAL BATTLE CHECKPOINT

通常SaveDataに含めず、Session用の既存処理を維持します。実Edgeとタッチエミュレーションでロードオブエリシオン戦 → 全滅 → Aで再挑戦を実施し、HP・Uses・ITEM・アムリタ・バリアが復元されました。この間localStorageの内容は変わりません。

Web配布物をPC Pythonで動かす既存の最終章通し検証でも、B10 → ENDINGと、全滅再挑戦5ケースが通過しました。最終戦のチェックポイントファイルは変更していません。

## 30. PC Python回帰

FileSaveBackendと共通変換・検証・SaveManagerのASTがPhase 7Aから同一であることを確認しました。実ファイルへのGUILD SAVE、別Pythonプロセス起動後のCONTINUE、再SAVE、原子的置換失敗時の元ファイル保持が成功しました。PC Pythonでは`js`をimportしません。

全unittestは215件成功です。保存専用10件、PC保存UI、GUILD4項目、RETURN、QUEST27件、最終章を含みます。証跡は`save_ui.json`、`web_payload_save_ui.json`、`web_pre_save_ui.json`、`web_quest_records_ui.json`、`web_final_chapter.json`です。

## 31. README / 配布物

READMEにPCファイル保存・両ブラウザのlocalStorage保存、GUILDとCONTINUEの操作、1スロット、サイトデータ削除、プライベートモード、同期なしを記載しました。公開入口`dist/index.html`の「ブラウザを閉じると失われる」説明も更新しました。`dist/game.html`は再生成済みです。

ビルドが`rpg/save/`などの作業用保存を拾う経路を確認したため、`tools/build_web.py`で`save`ディレクトリを除外しました。ユーザーの既存ファイルは変更・削除していません。配布アーカイブに`/save/`がないことを検証しています。

## 32. Phase 7Cへ残す確認

GKD Pixel 2の実機でFileSaveBackendの相対パス、書き込み権限、一時ファイル置換、終了・再起動後の復元を確認してください。GKD専用処理は追加していません。PCブラウザ・スマートフォン側でも、実機Android Chrome / iOS Safariの通常モードで保存・再表示と画面ロック復帰の最終確認が残っています。

## 33. 既知の問題・確認限界

- テスト範囲内で進行停止・データ復元異常は見つかっていません。
- スマートフォン実機・iOS Safari / WebKit・GKD Pixel 2は未確認です。エミュレーション成功を実機成功とは扱っていません。
- 音声APIが例外になる状態でもSAVE / LOADと最終戦再挑戦が進行しました。音声処理・Web Audio復帰ガードは変更していません。実機の自動ロック → 復帰は今回再現していません。
- 保存は端末・ブラウザ・オリジンごとです。サイトデータ削除、プライベートモード、設定によって保持できない場合があります。[localStorageの保存範囲と制限](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)を参照してください。
- Phase 7Aと同じく、QUEST座標と乱数内部状態は保存しません。現行データと矛盾する保存は自動補正せず拒否します。

## 指定36ケース

| CASE | 内容 | 結果 |
|---|---|---|
| 1 | PCブラウザNEW GAME → GUILD SAVE | 実Edgeで成功 |
| 2 | Reload → CONTINUE | 実Edgeで成功 |
| 3 | LOAD後通常HUB | 成功 |
| 4 | 初回演出を再表示しない | 成功 |
| 5 | TRZ17一致 | 成功 |
| 6 | 初期3の再加算なし | 成功 |
| 7 | TOTAL BATTLES一致 | 128、再SAVE131で成功 |
| 8 | PARTY一致 | 全SaveData比較で成功 |
| 9 | SKILL / Uses / DISCOVERED / MASTERED | 成功 |
| 10 | ITEM一致 | 2 / 7 / 9で成功 |
| 11 | QUEST RECORD一致 | CLEAR5 / 3 / 2で成功 |
| 12 | completed_quest_ids一致 | 固有3件で成功。27件UIも回帰成功 |
| 13 | active_quest一致 | 調査Lv2・途中進捗で成功 |
| 14 | flavor_id一致 | 再抽選なし、依頼人・本文も一致 |
| 15 | ダンジョン解放一致 | 撃破階4 / 9 / 14一致 |
| 16 | 数戦・QUEST進捗後に再SAVE | 3戦、TRZ22、調査進捗2で成功 |
| 17 | スマートフォンD-PAD / A / B SAVE | タッチエミュレーション成功。実機未確認 |
| 18 | スマートフォンReload → CONTINUE | エミュレーション成功。実機未確認 |
| 19 | スマートフォン主要データ一致 | エミュレーションの全SaveData比較で成功 |
| 20 | タッチUI維持 | エミュレーション操作・画像確認成功 |
| 21 | SAVEなし | 正しいメッセージ、Bでタイトル復帰 |
| 22 | 壊れたJSON | 安全に拒否、元データ保持 |
| 23 | version999 | 安全に拒否、元データ保持 |
| 24 | 重要キー欠損 | 安全に拒否、元データ保持 |
| 25 | localStorage利用不可・例外 | 実ブラウザのQuota / Security例外注入で成功 |
| 26 | 失敗時に成功を表示しない | 成功。元の保存も保持 |
| 27 | アムリタ所持保持 | 成功 |
| 28 | LOAD直後は献上確認なし | 成功 |
| 29 | 外から再帰還で献上確認 | 成功 |
| 30 | CHECKPOINTは保存対象外 | 成功。共通スキーマ変更なし |
| 31 | CHECKPOINT復元・再戦 | 実Edge・タッチエミュレーション成功。既存5ケースも通過 |
| 32 | PC PythonファイルSAVE | 成功 |
| 33 | PC Python別プロセスCONTINUE | 成功 |
| 34 | PC PythonでlocalStorageへアクセスしない | 遅延importと環境分離テスト成功 |
| 35 | Browser → BrowserSaveBackend | 実WASMのemscriptenで確認 |
| 36 | PC Python → FileSaveBackend | 単体・実ファイルUI検証で確認 |

追加で、NEW GAMEを選択しただけでは保存を変更せず、GUILDで明示SAVEすると上書きされること、無音時SAVE / LOAD、ブラウザプロセス再起動後の保存保持も検証しています。

## 再実行手順・証跡

プロジェクトのPython環境で次を実行します。Playwrightは検証時だけ必要で、ゲーム本体の依存には加えていません。

```powershell
python -m unittest discover -s tests
python tools/build_web.py
python tools/verify_web_build.py --save-ui --pre-save-ui --quest-records --final-chapter
python -m pip install playwright
python tools/verify_browser_save.py --channel msedge
```

Edgeがない環境では`python -m playwright install chromium`の後、`--channel msedge`を省略します。検証は隔離した一時ブラウザプロファイル・保存先を使い、通常のブラウザプロファイルや既存セーブへは触れません。

- 実ブラウザ：`verification/browser_save.json`
- 保存・スキーマ・資産保全：`verification/phase7b_preservation.json`
- 実画面：`verification/screenshots/browser_save_desktop.png` / `browser_save_mobile_emulation.png`

失敗注入テストで出る`SAVE failed` / `LOAD failed`は意図した開発ログです。テスト全体のPASSを確認してください。
