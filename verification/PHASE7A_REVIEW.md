# Phase 7A：共通SaveData・PC Python SAVE / LOAD

確認日：2026-10-08。PC Python版の1スロット手動保存とCONTINUEを実装しました。ブラウザ保存は今回実装していません。

## 1. SaveData構造

`rpg/save.py`でJSON互換のdict/list/str/int/bool/Noneだけに変換します。pickle、Pythonオブジェクトの直接保存はありません。

| キー | 保存内容 |
|---|---|
| save_version | 1 |
| party | 4人のname、growth_type、hp、max_hp、strength、agility、intellect、sprite、skills、history |
| party[].skills | 所持順のskill_id、uses、max_uses、mastered_copy |
| discovered_skills / mastered_skills | パーティ共通の記録ID配列 |
| items | POTION / PHOENIX ASH / REMEDYの全個数 |
| banked_trz | 確定TRZ |
| completed / wins / losses / draws / total_battles | 既存の終了集計と累計戦闘開始回数 |
| quest_clear_counts | explore / investigate / huntの累計CLEAR |
| completed_quest_ids | 固定27件のうち達成済みの固有ID |
| quest_completed_levels | 既存の達成Lv集合を配列化 |
| active_quest | type、level、target_floor、progress、required_count、completed、reward、flavor_id。討伐はhunt_enemy_id、hunt_source_floorも保存 |
| last_flavor_id | 前回受注ID。連続受注回避に使用 |
| dungeon_progress | defeated_bossesの配列。内部0始まりの4 / 9 / 14 |
| story | guardians_defeated、demon_defeated、has_amrita、final_event_started、lord_of_elysion_defeated、amrita_power_spent、read_lore |
| hub_intro_shown | 初回拠点説明済みフラグ |

## 2. save_version

厳密な整数の1を受け付けます。未設定、bool、999などは拒否します。将来の版移行は`migrate_save_data()`へ追加できます。現在、未知バージョンを現行版へ自動補正する処理はありません。

## 3. make_save_data()

永続項目を明示的に選択してデータ化します。`__dict__`の丸ごと保存はしません。集合は配列にし、所持技の順番を維持します。呼び出してもゲーム状態を変更しません。

## 4. apply_save_data()

`prepare_saved_game()`で新しいSession / Dungeon / Explorationを作り、全項目の検証・復元が成功してからまとめて差し替えます。必須キー欠損や不正データの途中適用はありません。LOAD直後の画面と古い演出待ちの解除は`DungeonApp.continue_game()`が担当します。

## 5. SaveManager

保存可否確認、共通データ変換、保存前検証、バックエンドの読み書きを担当します。バックエンドをコンストラクタ注入できます。複雑な抽象クラス階層はありません。

## 6. FileSaveBackend

`read()` / `write(data)` / `available`を提供します。UTF-8・インデント付き・日本語をそのまま読めるJSONです。読み込み時はUTF-8 BOM付きも受け付けます。Windows専用APIや固定ドライブの指定はありません。

## 7. 保存場所

既定は実行ディレクトリ基準の`save/save.json`です。`run.cmd`は最初にプロジェクトへ移動するため、通常はプロジェクト内へ保存します。`FileSaveBackend(path)`で変更可能です。`save/`を`.gitignore`に追加しました。テストは一時ディレクトリを使用し、プロジェクトの実プレイヤーデータは作成・上書きしていません。

## 8. 安全な書き込み

同じディレクトリの`save.tmp`へ書き、flush / fsync完了後に`save.json`を置換します。置換失敗を注入して、元ファイルが完全に残り、一時ファイルが片付くことを確認しました。1スロットの上書き保存です。

## 9. GUILD

PARTY STATUS / QUEST RECORD / SAVE / HELPの4項目です。既存の4行用スペースを利用しました。SAVEで「保存しますか？」と「はい／いいえ」、成功で「セーブしました。」、失敗でエラーメッセージを表示します。B・いいえは書き込まずGUILDへ戻り、結果画面のA/Bでも戻れます。画面の文字収まりを画像と描画範囲検査で確認しました。

## 10. CONTINUE

タイトルからLOADし、正常時は通常HUBへ直接移動します。INTRO / HUB PREVIEW / HUB INTROは通りません。新規開始処理を呼びません。読み込み失敗はメッセージ画面からA/Bでタイトルへ戻れます。アムリタ所持中でもLOAD直後に献上確認は出ません。外へ出て再帰還したときに既存条件で出ます。

## 11. PARTY復元

4人の名前・成長タイプ・能力・現在HP・最大HP・スプライト参照・成長履歴を復元します。拠点到着時の既存HP全回復は変更していません。変換処理自体は保存HPをそのまま戻し、追加回復はしません。全員生存不能など不正な拠点データは拒否します。

## 12. SKILL復元

順番、空き枠、残りUses、最大Usesを維持します。既存仕様で0 Usesの技は所持から消えるため、所持技の保存Usesは1以上です。技データを変更して最大Usesが一致しなくなった場合は、黙って丸めず読み込み失敗にします。

## 13. DISCOVERED / MASTERED

共通記録と所持コピーごとの`mastered_copy`を別々に保存します。LOAD時に`learn()`を呼ばないため、記録済みというだけで古い未強化コピーへ1.2倍が付くことはありません。復元した各キャラクターは同じ共通MASTERED集合を参照します。MASTEREDの威力・回復技等の扱いは変更していません。

## 14. ITEM

全3種類を復元し、各0～9を検証します。2 / 7 / 9の個数で往復確認しました。アムリタは通常ITEMへ入れません。

## 15. TRZ

17 TRZを保存・復元し、繰り返しLOADしても17のままです。初期3は加算しません。UNBANKEDは通常SAVEから除外し、LOAD後は0です。17から5増やして再保存・再LOADすると22になります。価格・報酬・全滅処理は変更していません。

## 16. TOTAL BATTLES

123を復元し、124へ進めて再保存・再LOADを確認しました。最終戦のセッション用チェックポイントには追加せず、再挑戦時の累計を巻き戻さない既存仕様を維持します。

## 17. QUEST CLEAR

探索5 / 調査3 / 討伐2を復元します。通常完了時の一度だけ加算する処理は変更していません。

## 18. 固有QUEST達成率

固定27件のIDだけを受け付け、重複・不明ID・fallbackの混入は拒否します。分母は探索9 / 調査9 / 討伐9 / TOTAL27のままです。既存UI検証で27件の達成率・100%・再クリア時の重複防止も通過しました。

## 19. active_quest

全3種×3Lvで、契約内容と進捗が往復一致しました。画面座標は保存しません。同じ対象階の`spawn_candidates()`から必要数を取り直し、調査済みprogress分を新しい配置の調査済み地点として対応付けます。調査Lv2の途中進捗1も維持しました。依頼・対象階・進捗・報酬の再抽選はしません。討伐敵IDと元階は戦闘再現に必要なため保存します。

## 20. フレーバー

flavor_idを維持し、依頼人・依頼文・お礼文は現行のデータから解決します。本文のコピーは保存しません。現在の文章を編集すれば、同じIDの受注にも編集後の文章が使われます。古い受注のIDがない・見つからない場合は、既存の種別・Lv別fallbackを使用します。これは受注表示の救済であり、不明IDを固有達成数へ登録する処理ではありません。

## 21. ダンジョン進行

B5 / B10 / デーモン撃破を復元し、既存の解放条件を利用します。マップ本体と敵・報酬データは変更していません。

## 22. ストーリー

守護者3連戦達成、デーモン、最終イベント開始、ロードオブエリシオン撃破、アムリタの力消費、石碑既読を復元します。ボス撃破・KEY ITEM・最終撃破の相互矛盾は拒否します。GUILDから保存できない最終イベント進行中のデータも拒否します。その状態をチェックポイントなしで通常HUBへ復元することによる詰みを防ぎます。最終撃破後フラグの変換自体はテストしています。

## 23. KEY ITEM

has_amritaを独立フラグとして復元します。通常ITEM、9個制限、UNBANKED TRZには入りません。デーモン前・取得後・最終撃破後の各段階を往復確認しました。

## 24. 初回説明

hub_intro_shownを保存します。CONTINUEではフラグに関係なく通常HUB開始とし、保存済みの初回演出を再生しません。NEW GAMEの既存初期化・導入フローも回帰確認しました。

## 25. 保存対象外

現在の階・XY・向き・Tile位置、探索中だけの宝箱・泉・スイッチ・扉などの状態、QUEST地点座標、BUFF / DEBUFF / GUARD、敵HP・ターン・行動順・キュー、バリアやアムリタの演出、音声待ち、一時メッセージ、未確定受注、技入れ替え待ち、FINAL BATTLE CHECKPOINTは含めません。LOAD後は新しい探索用オブジェクトで、次回出発は既存の開始処理を使います。

## 26. FINAL BATTLE CHECKPOINTとの分離

`rpg/final_battle.py`は変更していません。通常SAVEへチェックポイントは入りません。LOADでは古いUI側チェックポイントも破棄します。最終章通し検証で実際に5回全滅し、HP・技・Uses・ITEM・アムリタ・バリアの復元とENDING到達を確認しました。通常全滅への誤適用も既存テストが通っています。

## 27. 破損・欠損

保存なし、壊れたJSON、配列ルート、必須キー欠損、型違い、負値、範囲外、未知技などを検査します。復元前のゲーム状態・元ファイルを保持し、自動上書きしません。書き込み権限エラーもクラッシュせずGUILDへ戻れました。

## 28. 未対応バージョン

save_version=999、bool、未設定を拒否しました。未知バージョンを既存値で埋めて進行させる処理はありません。

## 29. PC SAVE確認

Python 3.13.7 / Pyxel 2.9.9、実際のFileSaveBackendと一時保存先を使いました。headless Pyxelのupdate / drawへD-PAD・A/B入力を渡し、GUILDで保存確認・取消・成功・失敗を確認しました。実ファイルが生成され、日本語をUTF-8で読めます。確認画像は`verification/screenshots/save_*.png`です。通常の可視ウィンドウを人が操作したテストではありません。

## 30. PC LOAD確認

SAVE後に別のPythonプロセスを起動し、タイトルのCONTINUEからHUBへ入りました。TRZ17、戦闘回数123、技残数17 / 2、ITEM2 / 7 / 9、受注中依頼、依頼人、アムリタが一致しました。さらにLOAD後の進行・再保存・再LOADを確認しています。

## 31. 回帰テスト

- 全unittest：212件成功。最後の保存検証強化後に保存専用7件も再実行し、すべて成功。
- HUB、GUILDの4項目、RETURNの2経路、QUESTお礼・記録27件、9種の受注、タイトル・導入：成功。
- `tools/verify_web_build.py --save-ui --pre-save-ui --quest-records --final-chapter`：成功。再生成した`dist/game.html`の埋め込みコードを抽出し、PC Pythonで検証。
- B10からENDING、実全滅再挑戦5ケース：成功。音声APIが失敗する状態でも進行。
- `git diff --check`：差分エラーなし。
- 既存バックアップに対する36ファイルのSHA-256：一致。全data、画像・パレット・マップ、最終戦チェックポイント、戦闘演出・音声・成長・ITEM・QUEST処理などを含む。`phase7a_preservation.json`参照。

## 32. Phase 7Bへの接続

BrowserSaveBackendが同じ`read()` / `write(data)` / `available`を提供し、SaveManagerへ注入する構成です。現状emscripten / wasiではUnavailableSaveBackendを使用し、ブラウザ内の一時ファイルへ保存したふりはしません。ブラウザ環境の保存・CONTINUEは未対応表示になります。localStorage / IndexedDB / 新しいJSは追加していません。Web配布物を更新し、ブラウザバックエンド未対応もテストで確認しました。

## 33. 既知の制限・未確認

- PC / スマートフォンブラウザでの永続保存はPhase 7Bの対象です。実ブラウザ・スマートフォン・GKD Pixel 2での実機確認は未実施です。
- ゲームバランスやB1～B15マップは変更していません。数値バランスの評価は今回のテスト対象外です。
- 保存した後に技ID・最大Uses・QUESTルールを変更すると、厳密検証で旧保存を読み込めない場合があります。今後の構造変更は版移行処理で扱います。
- QUEST位置はLOAD時に再配置されます。契約・進捗は同じですが、元の座標は復元しません。
- 乱数内部状態は保存しません。LOAD後の抽選を保存前と同じ順番で再現する機能はありません。
- 最終戦チェックポイントはセッション中だけです。終了後は最後にGUILDで保存した地点から再開します。

## 指定36ケースの結果

PCの実ファイル・データ変換・headless実UI・別プロセス・既存回帰検証を組み合わせています。「Web payload」はブラウザ実機ではなく配布HTML内のコードをPC Pythonで動かした確認です。

| CASE | 確認内容 | 結果・証跡 |
|---|---|---|
| 1 | GUILD SAVEでファイル生成 | 成功。save_ui.json |
| 2 | 保存成功メッセージ | 成功。save_success.png |
| 3 | 再起動してCONTINUE | 成功。別Pythonプロセス |
| 4 | LOAD時INTROなし | 成功。state=campへ直接 |
| 5 | 通常HUB開始 | 成功。save_loaded_hub.png |
| 6 | 能力値復元 | 成功。全SaveData往復比較 |
| 7 | HPの既存拠点回復仕様 | 成功。拠点回復を変更せず、codecは非満タンHPもそのまま復元 |
| 8 | SKILL / Uses 17・2 | 成功。UI実ファイルと別プロセス。コピーのMASTERED状態も確認 |
| 9 | DISCOVERED / MASTERED | 成功。集合・参照・所持コピー復元 |
| 10 | 空き技枠 | 成功。空の所持技リストも往復 |
| 11 | ITEM復元 | 成功。2 / 7 / 9 |
| 12 | BANKED TRZ 17 | 成功 |
| 13 | LOADで3加算されない | 成功。3回LOADして17維持 |
| 14 | UNBANKED=0 | 成功。保存対象外 |
| 15 | total_battles=123 | 成功。別プロセスも一致 |
| 16 | CLEAR 5 / 3 / 2 | 成功 |
| 17 | 固有達成率 | 成功。ID往復と既存27/27 UI回帰 |
| 18 | active_quest | 成功。全9種、途中進捗も保持 |
| 19 | flavor_id | 成功。再抽選なし |
| 20 | 依頼人・本文・Lv・対象階 | 成功。現在データから同じIDで解決 |
| 21 | B5撃破でLv2解放 | 成功。既存解放条件と復元済み4 |
| 22 | B10撃破でLv3解放 | 成功。復元済み9、Lv3受注往復 |
| 23 | デーモン撃破前 | 成功。falseを維持 |
| 24 | デーモン撃破後 | 成功。trueと撃破階14を維持 |
| 25 | アムリタKEY ITEM | 成功。独立フラグ、通常ITEM外 |
| 26 | LOAD直後に献上確認なし | 成功。通常HUBへ |
| 27 | 外へ出て再帰還で確認 | 成功。D-PAD・A/Bで検証 |
| 28 | 最終フラグ | 成功。取得前・取得後・撃破後往復、矛盾データ拒否 |
| 29 | CHECKPOINTを保存しない | 成功。通常SaveDataに含まれない |
| 30 | 既存CHECKPOINT再挑戦 | 成功。実全滅5回、Web payloadも通過 |
| 31 | 保存ファイルなし | 成功。専用メッセージ、タイトルへ戻れる |
| 32 | 破損JSON | 成功。旧状態・元ファイル保持 |
| 33 | version=999 | 成功。読み込み拒否 |
| 34 | 重要キー欠損 | 成功。全トップレベル必須キーを1つずつ欠損させ検証 |
| 35 | LOAD→進行→再SAVE→再LOAD | 成功。TRZ22・戦闘回数124 |
| 36 | 上書き保存 | 成功。1スロット維持、取消時は書かない |

## 再実行

プロジェクトのPython環境から実行してください。

```powershell
python -m unittest discover -s tests
python tools/verify_save_ui.py
python tools/verify_hub_ui.py
python tools/verify_pre_save_ui.py
python tools/verify_quest_records_ui.py
python tools/verify_opening_ui.py
python tools/build_web.py
python tools/verify_web_build.py --save-ui --pre-save-ui --quest-records --final-chapter
```

失敗注入テストでは、意図した`SAVE failed` / `LOAD failed`の開発ログが出ます。テスト全体がPASSで終了することを確認してください。
