# Phase 7C：4環境のSAVE / LOAD統合確認

確認日：2026-10-09。PC・Edgeの試験範囲では、保存形式・ゲーム本体の変更が必要な不具合は見つかりませんでした。後のGKD実機バージョン追加調査ではPyxelのAPI非互換が判明しています。追加したのは検証・診断コードと説明・検証記録です。新しいゲーム機能、数値調整、マップ編集、依存バージョン変更は行っていません。

PC Pythonと実Edgeでは保存・終了／再読み込み・復元・進行・再保存が通りました。スマートフォンはEdgeのPixel 7タッチ模擬環境です。スマートフォン実機とGKD Pixel 2実機は利用できておらず、4環境すべての実機合格という判定にはしていません。

追記：ユーザーから対象スマートフォンは**iOS Safari**、GKDのOSは**plumOS**と確認できました。初回の実機診断ではPyxel 2.3.6でしたが、2026-10-10の更新後ログで**Python 3.11.7 / Pyxel 2.9.9 / aarch64**を確認しました。旧版とのバージョン差は解消しています。診断ログをゲーム本体の実機試験合格に置き換えていません。iOSのバージョンは未確認です。

## 指定37項目の完了報告

1. **現在のSaveData version：** `SAVE_VERSION = 1`を維持。不要な移行処理は追加していません。
2. **共通SaveData構造の変更：** なし。`make_save_data()`、`prepare_saved_game()`、`apply_save_data()`、`SaveManager`を両Backendで共用しています。
3. **PC Python backend：** `FileSaveBackend`。実Python 3.14.7 / Pyxel 2.9.9で確認。
4. **PC Browser backend：** `BrowserSaveBackend`。実Edge 154.0.4258.62、配布済みPyxel/Pyodideと実localStorageで確認。
5. **Smartphone Browser backend：** 同じ`BrowserSaveBackend`。スマートフォン専用SaveDataはありません。タッチ模擬環境で確認、実機未確認。
6. **GKD Pixel 2 backend：** ネイティブPythonでは`FileSaveBackend`を選ぶ設計。GKD専用の保存構造はありません。
7. **backend選択処理：** `rpg/save.py`の`default_backend()`一箇所。`sys.platform == 'emscripten'`だけBrowser、それ以外はFile。画面別の保存媒体分岐を増やしていません。
8. **PC Python保存先：** `DEFAULT_SAVE_PATH = Path('save') / 'save.json'`。実行時の作業ディレクトリ基準。`run.cmd`ではプロジェクト配下です。試験では別の一時ディレクトリを指定し、プレイヤーの保存ファイルには触れていません。
9. **GKD用保存先設定方法：** `DEFAULT_SAVE_PATH`を起動前に一箇所で設定、または既存の`FileSaveBackend(path)`を`DungeonApp(..., save_backend=...)`へ渡せます。SDカード・ユーザー領域の実パスと書き込み権限、ランチャーの作業ディレクトリは実機で確認が必要です。
10. **Browser localStorage key：** `skill_seekers_save_v1`。同一オリジン／ブラウザプロファイル内で使用し、URLクエリには依存しません。サイトデータ削除で消失し得ます。PC・スマートフォン・別ブラウザ間の自動同期はありません。
11. **PC Pythonテスト結果：** 全218件の自動テストが合格。別々の3プロセスで、GUILD SAVE → 完全終了 → TITLE CONTINUE → HUB → 1戦 → 再SAVE → 完全終了 → 再CONTINUEを確認。画面は実Pyxelのheadless更新・描画、入力は模擬D-PAD/A/Bです。通常の可視ウィンドウでの手動試験とは区別しています。
12. **PC Browserテスト結果：** 実localStorage保存、ページ再読み込み、CONTINUE、全SaveData一致、タブ閉鎖・再作成、ブラウザプロセス終了・再起動、再保存、ストレージ例外、最終戦再挑戦が合格。未処理pageerrorは0件。HTTPで配布済み`dist`を提供し、隔離プロファイルを使用しました。
13. **Smartphone Browserテスト結果：** 実EdgeのPixel 7エミュレーションとCDPタッチ入力で、既存D-PAD/A/BだけによるNEW GAME、SAVE確認・取り消し・完了、CONTINUE、LOAD後操作、再保存が合格。実Android Chrome／iOS Safariの結果ではありません。
14. **GKD Pixel 2実機テスト有無：** ゲーム本体の起動・SAVE / LOADは未実施。OSはplumOS（ユーザー申告）。更新後の実機診断ログによりPython 3.11.7 / Pyxel 2.9.9 / aarch64と実行パスを確認しました。
15. **GKDコード検証結果：** Linux相当の`sys.platform`でFile選択、`js`なしで保存コードを使用可能、Windows IME APIを呼び出さないことを確認。`pathlib`、`json`、`os.fsync`、置換による標準Python処理です。保存先作成・権限拒否・書き込み途中の例外の保護を試験しました。これはLinux実機やGKDの起動試験を代替しません。実機ログのPython 3.11.7 / Pyxel 2.9.9は現行の必要バージョンと一致しました。SDL・表示・音声・実コントローラー・ファイル保存の実動作は未確認です。
16. **TRZ SAVE / LOAD：** NEW GAMEは3 / 0。FileとBrowserの共通試験で21 → 21、既存試験で17 → 17。初期3の再加算なし。PC別プロセス試験では進行後22を再保存し22へ復元。通常の未確定TRZはLOAD後0。
17. **PARTY復元：** 4人のHP・最大HP・STR/AGI/INT・成長タイプ・名前・画像指定・成長履歴が全SaveData比較で一致。HPを減らしたcodec試験も一致。空の技構成も保持します。
18. **SKILL / Uses復元：** 固定`skill_id`、技順序、Uses、max_uses、MASTERED状態で取得した個体フラグが一致。PUNCH 17/30、RETURN 1/3、RAREのREVIVE 2/3を使用しました。指定例のRETURN 1/1へ性能を変更せず、実データの上限3を維持。技の表示名だけを試験用メモリ内で変更してもFile/Browser両方から同じIDで復元できました。
19. **DISCOVERED / MASTERED復元：** 共通集合と所持個体の`mastered_copy`を復元。MASTERED前から持つ技と、MASTERED後に再取得した技の区別を維持し、LOADによる誤強化を防ぐ既存試験も合格。
20. **ITEM復元：** POTION 2、PHOENIX ASH 7、REMEDY 9を復元。保存キーは現行の固定内部IDで、日本語表示とは別です。一部英語ラベルと同じ文字列でも、今後表示名を変更するときは内部IDを変更しない必要があります。アムリタはこの消耗品辞書に含まれません。
21. **TOTAL BATTLES復元：** 128で保存・復元、1戦開始で129、再保存・再起動後も129。加算ルールは変更していません。
22. **active_quest復元：** type、level、target_floor、progress、required_count、completed、reward、flavor_idが一致。討伐では固定`hunt_enemy_id`も一致。依頼人と依頼文は同じflavor_idから復元し再抽選しません。敵の表示名だけをメモリ内で変更しても復元可能。位置は既存仕様どおり安全候補へ再配置。
23. **completed_quest_ids復元：** 固有12件を欠損・重複なしで復元。通常27件のIDは変更していません。fallback9件は分母と固有達成数の対象外のまま。
24. **QUEST RECORD復元：** 探索CLEAR 5、調査CLEAR 3、討伐CLEAR 4、固有12/27を保存・復元。受注・お礼・報酬・重複達成・100%表示は既存回帰試験も合格。
25. **ダンジョン進行復元：** B5/B10/B15撃破記録と階層解放を復元。石碑既読・守護者撃破等の永続進行も対象。一時的な座標・泉・扉・スイッチ・敵HP・ターン・BUFF/GUARD・演出・UI状態は保存対象外。
26. **アムリタ状態復元：** `has_amrita=True`と関連進行フラグを復元。LOAD直後は通常HUBで献上確認を出さず、外へ出て再入場すると条件に従い表示。通常消耗品や未確定TRZとは独立。
27. **FINAL BATTLE CHECKPOINT分離：** 通常SAVEにcheckpointを含めず、LOAD後は`final_checkpoint is None`。最終戦開始後に別途セッション内checkpointを作成。実Edgeでも敗北・再挑戦を確認。配布埋込み本体のB10 → ENDING通し試験と連続5回の全滅復元（CASE A～E）も合格。
28. **SAVEなし時：** File・実BrowserともCONTINUEで安全に失敗メッセージ。ブラウザではストレージの存在確認失敗も処理し、仮想ファイルへ保存媒体を勝手に変更しません。
29. **不正SAVE時：** 不正JSON、途中破損、必要キー欠損、未知versionを拒否し、適用前のゲーム状態と保存原文を保持。BrowserのSecurityError等も安全に失敗。NEW GAMEだけで破損SAVEや既存SAVEを上書きしません。
30. **再SAVE / 上書き：** FileはUTF-8 JSONをtmpへ書き、flush/fsync後replace。作成・fsync・replaceの失敗でも旧保存内容を保持する試験が合格。BrowserはsetItem失敗をSAVE失敗と表示し、成功メッセージを出しません。進行後の再保存・再読込は最新データで一致。
31. **smartphone audio freeze回帰：** 実Edgeのデスクトップ／タッチ模擬双方で実SDL AudioContextをRUNNING → SUSPENDEDにし、`resume()`を拒否させ、CDPのfrozen → active後に探索操作・戦闘突入・勝利・探索復帰・保存を確認。勝利後もSUSPENDEDで、ファンファーレは既存タイムアウトで解放。未処理例外なし。実画面ロック、SafariのINTERRUPTED、CLOSEDの実端末挙動は未確認。詳細は下表。
32. **Windows固有パス・API：** 保存コードにWindows絶対パス、ドライブ固定、ユーザー名固定、Windows専用APIはありません。ゲーム全体では既存`rpg/keyboard.py`にIME対策の`ctypes.WinDLL(user32/imm32)`がありますが、win32以外では呼ばないガードを試験しました。「ゲーム全体にWindows APIがない」とは判定していません。
33. **README更新：** 4環境のBackend・保存先・実際の確認範囲、GKDの保存先設定と依存環境未確認、ブラウザサイトデータ削除・同期なし、本報告へのリンクを整理。
34. **今回修正した不具合：** ゲーム本体の修正はなし。GKDの旧Pyxel 2.3.6とのAPI非互換を調査・記録し、ユーザーが実機のPyxelを2.9.9へ更新したことを診断ログで確認しました。診断スクリプトのログが残らない弱点はrevision 2で改善し、ユーザーからログ出力成功の報告を受けました。旧版対応コードは追加していません。
35. **未確認事項：** 対象iOS SafariのOSバージョンと実機動作、実画面ロック・アプリ切替、Safari INTERRUPTED、plumOS上のGKDのゲーム起動・入力・性能・SD権限・更新後の動作。ヘッドレスEdgeではタブ切替後も`document.hidden=False`のため、実際の非表示遷移は検証できていません。
36. **既知の問題・制限：** GKDの旧Pyxel 2.3.6とのバージョン差は更新により解消しましたが、ゲーム本体の実機試験が完了するまでGKD対応確認済みとは扱いません。PC・Edge検証範囲では保存・復元の進行不能やデータ破損は見つかりませんでした。ローカル保存のみで端末間同期なし、サイトデータ削除で消失し得る既存仕様は維持。強制電源断時のSD媒体の永続性まで保証していません。固定IDや技能のmax_usesを将来変える場合、別途version移行判断が必要です。
37. **feature freeze判断：** 共通SaveData version 1、単一スロット、Backend境界、保存対象とLOAD先HUBの仕様はFIX可能です。追加機能のために設計を拡張する必要は見つかりません。ただし「4環境の実機で安定動作を確認済み」というリリース判定は、スマートフォン・GKDの実機試験が済むまで保留します。

## 必須テストMATRIX

PCは実Python・headless描画・模擬入力。Browserは実Edge・実Pyodide・実localStorage・隔離プロファイルです。スマートフォン欄の合格はタッチ模擬環境での結果であり、実機合格を意味しません。

### PC Python

| No. | 項目 | 結果 |
|---|---|---|
| 1 | NEW GAME | 合格：3 TRZ、戦闘0、固有記録0 |
| 2 | GUILD SAVE | 合格：確認と完了表示、JSON一致 |
| 3 | ゲーム完全終了 | 合格：保存プロセス終了後に別プロセス開始 |
| 4 | CONTINUE | 合格：TITLE操作で復元 |
| 5 | HUB開始 | 合格：INTRO・即時献上確認なし |
| 6 | TRZ復元 | 合格：21、再保存後22 |
| 7 | PARTY復元 | 合格：全データ一致 |
| 8 | SKILL Uses復元 | 合格：17/30、1/3、2/3等 |
| 9 | MASTERED / DISCOVERED | 合格：集合・個体状態一致 |
| 10 | ITEM復元 | 合格：2・7・9 |
| 11 | TOTAL BATTLES復元 | 合格：128 → 129 |
| 12 | QUEST復元 | 合格：調査Lv2、同じ文章と進捗 |
| 13 | QUEST RECORD復元 | 合格：5・3・4、12/27 |
| 14 | ダンジョン進行復元 | 合格：ボス・関連進行フラグ一致 |
| 15 | 再SAVE | 合格：1戦・進捗更新後に保存 |
| 16 | 再LOAD | 合格：3番目のプロセスで最新データ一致 |

### PC Browser

| No. | 項目 | 結果 |
|---|---|---|
| 1 | NEW GAME | 合格：3 TRZ、既存スロットは未上書き |
| 2 | GUILD SAVE | 合格：実localStorage |
| 3 | Reload | 合格：実ページ再読み込み |
| 4 | CONTINUE | 合格：TITLEから復元 |
| 5 | HUB開始 | 合格：導入なし |
| 6 | TRZ復元 | 合格：17、進行後の再保存も一致 |
| 7 | PARTY復元 | 合格：全SaveData一致 |
| 8 | SKILL Uses復元 | 合格：全SaveData一致 |
| 9 | QUEST復元 | 合格：同一flavor・進捗・依頼文 |
| 10 | TOTAL BATTLES復元 | 合格：128、追加3戦で131を復元 |
| 11 | 再SAVE | 合格：進行後の更新内容を保存 |
| 12 | 再Reload / LOAD | 合格：タブ・ブラウザ再起動も確認 |

### Smartphone Browser

| No. | 項目 | タッチ模擬環境の結果 | 実機 |
|---|---|---|---|
| 1 | NEW GAME | 合格 | 未実施 |
| 2 | GUILD SAVE | 合格 | 未実施 |
| 3 | Reload | 合格 | 未実施 |
| 4 | CONTINUE | 合格 | 未実施 |
| 5 | HUB開始 | 合格 | 未実施 |
| 6 | TRZ復元 | 合格：初期3の追加なし | 未実施 |
| 7 | PARTY復元 | 合格：全データ一致 | 未実施 |
| 8 | SKILL Uses復元 | 合格：全データ一致 | 未実施 |
| 9 | QUEST復元 | 合格：同一依頼 | 未実施 |
| 10 | TOTAL BATTLES復元 | 合格：128 → 131 | 未実施 |
| 11 | 十字キー / A / B | 合格：実タッチイベントで操作 | 未実施 |
| 12 | SAVE確認操作 | 合格：決定・取消・完了 | 未実施 |
| 13 | 画面ロック / 復帰 | 実画面ロック不可。CDPページfreeze/復帰の代替試験は合格 | 未実施 |
| 14 | audio停止でも進行 | 合格：実AudioContext suspended＋resume拒否 | 未実施 |
| 15 | 再SAVE | 合格：停止音声に依存せず保存 | 未実施 |

### GKD Pixel 2 Python

| No. | 必須実機項目 | 結果 |
|---|---|---|
| 1 | 起動 | 未実施 |
| 2 | NEW GAME | 未実施 |
| 3 | GUILD SAVE | 未実施 |
| 4 | アプリ終了 | 未実施 |
| 5 | 再起動 | 未実施 |
| 6 | CONTINUE | 未実施 |
| 7 | HUB開始 | 未実施 |
| 8 | TRZ復元 | 未実施 |
| 9 | PARTY復元 | 未実施 |
| 10 | SKILL Uses復元 | 未実施 |
| 11 | QUEST復元 | 未実施 |
| 12 | TOTAL BATTLES復元 | 未実施 |
| 13 | 再SAVE | 未実施 |

コード上はFileBackend共有、Windows絶対パスなし、保存先設定可能、標準Python API使用、Linux判定時にIME WinDLLを回避、既存の入力コードを変更していないことを確認しました。SDのファイルシステム・権限・ランチャー環境はこの確認に含みません。

## 音声・復帰試験の区別

| ケース | 実施内容と結果 |
|---|---|
| 実AudioContext停止 | デスクトップ／タッチ模擬双方でRUNNING → SUSPENDED |
| resume失敗 | 実コンテキストのresumeを拒否Promiseへ差し替え。例外を捕捉し操作継続 |
| ページ停止・復帰 | CDP `Page.setWebLifecycleState`のfrozen → activeを実行。復帰後フレーム進行 |
| 戦闘・勝利・探索復帰 | SUSPENDEDのまま合格。検証用メモリ内で敵HPを1にして戦闘経路を確認。本番数値は不変 |
| ファンファーレ | 音声終了が得られなくても既存4.5秒／150フレームの上限で待機解除。実Browserでもtimeoutを確認 |
| SAVE / LOAD | 音声API例外でも保存・復元可能。ストレージ処理は音声完了に依存しない |
| タブ切替の実visibility | 別タブを前面化してもheadless Edgeではhidden=False。非表示遷移の実検証は未完了 |
| 合成visibilityイベント | hidden=True/Falseを試験中だけ差し替え、visibilitychange・pagehide/pageshow・blur/focusを送信。ログと仮想ボタン解放を確認。実画面ロックとは区別 |
| 無音のゲーム回帰 | 探索・戦闘中復帰・100勝利反復・MASTERED・閃き・入替・ボス・RETURN・QUESTが進行 |
| 実端末画面ロック | 未実施。SUSPENDEDの代替試験からiOS INTERRUPTEDや実ロックの合格を推定していません |

## 回帰・保存対象の保護

- `python -m unittest discover -s tests`：218件、すべて合格（58.972秒）。
- `tools/verify_save_compatibility.py`：3プロセスで完全終了・再保存・復元が合格。
- `tools/verify_save_ui.py`：GUILD SAVEの完了・取消・失敗、別プロセスCONTINUE、破損保存とアムリタ再入場が合格。
- `tools/verify_audio_recovery.py`：無音進行、100勝利、MASTERED／閃き／入替、ファンファーレ上限が合格。
- `tools/verify_web_build.py --save-ui --pre-save-ui --quest-records --phase6d --final-chapter`：配布埋込みデータと現ソース一致、全9QUEST・27文章・RETURN・お礼・記録・B10 → ENDING・5回連続再挑戦が合格。このツールのゲーム試験はデスクトップPyxelによる埋込み本体の検証です。
- 実Browser試験：`tools/verify_browser_save.py --channel msedge --phase7c`。Playwrightは検証だけの依存で、ゲームのrequirementsには追加していません。
- [保護対象ハッシュ比較](phase7c_preservation.json)：着手前の本体コード・JSON・素材・パレット・ビルド処理等56ファイルが全件一致。B1～B15のTilemapを含む.pyxres、BGM/SEを変更していません。
- `dist/game.html` / `dist/index.html`は変更不要で再生成していません。Webへ配布する新しいゲーム動作の変更はありません。
- プレイヤーの`save/`を編集・削除・配布せず、試験は一時ディレクトリ／隔離ブラウザプロファイルのみで実行しました。

実行結果は[PC別プロセス結果](phase7c_pc_save.json)、[実Browser結果](phase7c_browser_save.json)を参照してください。実機確認時には上記スマートフォン15項目・GKD13項目を記録してから、4環境のリリース合格を判断してください。

## 対象端末の確認とバージョン調査の追記

ユーザー申告の環境は、スマートフォンがiOS Safari、GKD Pixel 2がplumOSです。iOS Safariの実機、WebKitでの実画面ロックを今回のEdge模擬試験で確認済みとは扱いません。

[plumOS Pixel 2の公式README](https://github.com/game-de-it/plumOS-pixel2#pyxelについて)で、Python実行場所が`/storage/pyxel_Python/bin/python3`、Pyxelがオンライン更新可能であることを確認しました。[公開リリース](https://github.com/game-de-it/plumOS-pixel2/releases/tag/plumOS-pixel2_v0.1)とソースREADMEには、正確なPython・Pyxelの同梱バージョンの記載を見つけられませんでした。更新履歴によっても実機の値が変わるため、公開情報からユーザーの実機の版は断定できません。

参考調査として別OSのROGUE OS公開ソースにはPython 3.11ディレクトリとPyxel 2.3.18 / 2.4.10のMETADATAがありましたが、**これはplumOSの同梱版を示す根拠ではありません**。plumOSや手元の実機にこのバージョンを当てはめていません。

実機で確認するため、[check_gkd_versions.sh](../tools/check_gkd_versions.sh)を用意しました。GKDの`roms/ports/`へコピーし、Portsから実行すると同じフォルダへ`gkd_versions.txt`を出力します。Python版・実行パス・そのPython環境のPyxelメタデータを記録し、更新・ネット通信・ゲーム起動・SAVE編集は行いません。別のランチャーやPythonを使っている場合は、ゲーム側の起動設定も照合する必要があります。

確認用スクリプトのPOSIX shell構文を確認し、埋込みPythonの診断部分をPC環境で実行しました。このPC側の確認もGKD実機試験とは区別しています。

### ユーザー提供の実機診断ログと互換性評価

| 項目 | 実機ログの値 |
|---|---|
| OS | plumOS（ユーザー申告） |
| CPU実行環境 | aarch64 |
| Python | 3.11.7、GCC 14.1.0ビルド |
| 実行ファイル | `/storage/pyxel_Python/bin/python3` |
| Pyxel | 2.3.6 |

Python 3.11.7は現行Pyxel 2.9.9のPython条件を満たします。一方、[Pyxel 2.3.6の公式API定義](https://github.com/kitao/pyxel/blob/v2.3.6/python/pyxel/__init__.pyi)と現コードを静的比較すると、次の非互換があります。

- `rpg/app.py`の`pyxel.init()`へ渡す`headless`は2.3.6にはありません。Falseを渡す通常起動も対象です。
- `rpg/art.py`・`rpg/map_resources.py`・`rpg/sound.py`の`load(exclude_...=...)`に対し、2.3.6は`excl_...`の引数名です。
- `rpg/app.py`の`btnp(key, hold, repeat)`に対し、2.3.6の公式定義ではhold/repeatがキーワード専用です。

現コードのままPyxel 2.3.6で正常起動・操作できるとは判定できません。SAVEコードの問題ではなく、その手前のランタイムAPI差です。[静的比較記録](phase7c_gkd_compatibility.json)に対象行・実機ログの版・検証範囲を記載しました。この比較は素材読み込み全体やGKDのSDL動作の実試験ではありません。

対応方針は、まずGKDのPyxelをゲームの固定版2.9.9へ合わせ、起動・入力・SAVE / LOADを実機確認することです。[plumOSの公式更新方法](https://github.com/game-de-it/plumOS-pixel2#pyxelについて)はUSB Wi-Fiで接続後、Toolsの`pyxel_update`を実行します。更新後に診断を再実行して実際の版を確認してください。2.9.9にはARM64 / Python 3.11用の配布がありますが、[Linux glibc 2.28以上が必要](https://pypi.org/project/pyxel/2.9.9/)なので、GKDのライブラリ・表示環境まで更新可能と保証していません。実機の更新と旧版2.3.6へのゲーム移植は今回実施していません。

### 診断スクリプトのログ未生成への対応（2026-10-10）

ユーザーから「更新後に診断を実行したが、PC／ファイルマネージャーのPortsフォルダにgkd_versions.txtがない」と報告されました。ゲーム一覧の拡張子フィルタの問題ではないことを確認しました。実機での直接原因と更新後のPyxelバージョンはまだ未確認です。

旧スクリプトは`dirname "$0"`を基準に出力先を決め、その準備が失敗するとログ作成前に終了していました。revision 2では既知のplumOS Portsフォルダを優先し、書き込み可能な出力先を選んでからPython起動前に実行開始・出力パスを記録します。Python起動失敗時も標準エラーと終了コードが残ります。最終フォールバックは`/tmp/gkd_versions.txt`です。この弱点の修正を、実機で発生した原因の確定や実機合格とは扱っていません。

Git BashのPOSIX shell構文検査、LF/BOM検査、一時フォルダでの通常出力・Python起動失敗（終了コード19）・sourceされたランチャーの不正なパスからのフォールバックを確認しました。[検証結果](gkd_diagnostic_v2.json)に記録しています。ゲーム本体・SaveData・素材・distは変更していません。GKDへrevision 2のファイルを上書きコピーし、実行ログによる追加確認が必要です。

### 更新後のユーザー実機ログ確認（2026-10-10）

ユーザーからrevision 2でログが作成できたと報告を受け、次の実測値を確認しました。

| 項目 | 確認値 |
|---|---|
| Python | 3.11.7 |
| Pyxel | 2.9.9 |
| CPU実行環境 | aarch64 |
| 実行ファイル | `/storage/pyxel_Python/bin/python3` |
| 作業ディレクトリ | `/storage` |
| ログ出力先 | `/storage/roms/ports/gkd_versions.txt` |
| Python終了コード | 0 |
| 診断終了 | CHECK COMPLETE |

PCの検証版とPyxelバージョンが揃い、旧2.3.6とのAPI差を理由とする対応保留は解消しました。診断はPyxelを起動せずメタデータを読むため、ゲームの表示・入力・音声・SAVE / LOADまでは確認していません。次の実機試験はNEW GAME → GUILD SAVE → 完全終了 → CONTINUE → HUB開始 → 保存値一致です。

作業ディレクトリはランチャー依存です。FileSaveBackendの既定パスは相対`save/save.json`なので、ゲーム起動時の作業ディレクトリと実際の保存先も確認する必要があります。上記`/storage`は診断スクリプトの実行環境であり、ゲームの保存先と断定しません。[実機環境の最新記録](phase7c_gkd_compatibility.json)には初回2.3.6の監査も履歴として保持しています。
