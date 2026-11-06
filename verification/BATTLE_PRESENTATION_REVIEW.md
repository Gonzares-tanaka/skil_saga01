# Battle Presentation Phase 検証報告

2026-10-10。対象は戦闘演出・表示のみ。実行環境はPC Python 3.14.7 / Pyxel 2.9.9、WebはEdge Chromium + Pyodide。ブラウザは独立したテストプロファイルを使用し、プレイヤーのセーブは操作していません。

## 指定38項目の報告

1. **踏み込みの実装場所**：`rpg/battle_presentation.py`の`BattlePresentation.start / actor_offset`。`rpg/app.py`の`draw_battle / apply_visual_action`が描画と既存計算を接続します。
2. **移動量**：左へ6px。30FPSで踏み込み3フレーム、エフェクト9フレーム、戻り3フレーム。撃破なしで計約0.5秒です。
3. **定位置への復帰**：元の座標を変更せず、毎回表示用オフセットを計算します。`actor_return`後の`reset`で0に戻ります。複数行動でズレが蓄積しないことをテスト済みです。
4. **KO Sprite**：既存`game.pyxres`のImage Bank 2、(240,0)、16×16、透過色0。仮画像は墓標です。
5. **KO定数**：`ASSET_BANK / KO_SPRITE_U / KO_SPRITE_V / KO_SPRITE_W / KO_SPRITE_H`。座標は同モジュールへ集約しています。
6. **蘇生時**：毎回現在HPの`actor.alive`で通常画像かKO画像かを判定します。PHOENIX ASHによる実際の蘇生とSprite復帰を確認しました。
7. **effect_id**：`Skill.effect_id`を末尾に任意項目として追加。`data/skills.json`の全31技に指定しました。既存データは未指定でも読み込めます。技の計算式・Usesは変更していません。
8. **初期effect_id**：slash / blunt / pierce / fire / ice / lightning / magic / dark / heal / buff / debuff / legend の12種類。
9. **エフェクト座標**：すべてImage Bank 2、16×16×3コマ。X=192 / 208 / 224。各IDのYは下表。起動時には生成しません。
10. **fallback**：`effect_id()`が未指定、空文字、不明値、不正型を`blunt`へ置換します。名前には依存しません。
11. **敵撃破の実装場所**：同モジュールの`after_action / enemy_visual`。`Battle.step`の直前と直後の生死を比較し、HPが0になった敵だけを対象にします。
12. **点滅時間**：12フレーム＝0.4秒。3フレームごとに表示/非表示を切り替え、2回点滅した後に沈みます。
13. **沈み量**：最大8px、6フレーム＝0.2秒。元のSprite下端でクリップして埋まるように表示し、合計18フレーム＝0.6秒で消滅します。
14. **death_effect_id**：敵データへの項目追加は今回は行っていません。共通`blink_sink`を一箇所で管理し、将来の分岐を追加できます。判定は敵オブジェクト/インデックスによるため表示名に依存しません。
15. **Bossへの適用**：通常敵と同じ処理をB5/B10、守護者、デーモンへ適用。ロードオブエリシオンは専用アムリタ演出と既存ENDING処理を優先し、共通撃破演出の対象から除外しています。最終章通し検証は正常です。
16. **Status Icon座標**：Image Bank 2、各8×8。poison=(192,0)、paralyze=(200,0)、sleep=(208,0)、curse / weak=(216,0)。curseとweakは仮の共通画像です。
17. **描画関数**：`draw_status_icons(pyxel, actor, x, y, limit=3)`。将来の`actor.statuses`を読み取るだけです。
18. **複数配置**：通常戦は最大3個を8px間隔でキャラクターの左横に配置。特殊最終戦はボスと重ならない位置で最大2個。KO中は描画しません。
19. **状態異常ロジック**：継続ダメージ、行動不能、治療、成功率等は追加していません。CharacterやSaveDataにstatus項目も追加していません。
20. **B1～B5床色**：現在のマップ床タイルの主色、色番号0。
21. **B6～B10床色**：同じ取得方法、色番号2。
22. **B11～B15床色**：同じ取得方法、色番号3。B15の通常遭遇禁止仕様は維持。
23. **特殊床色**：ロードオブエリシオン戦は既存の色番号0。ダンジョンの階数による取得から分離しています。パレット変更なし。
24. **字幕削除**：`rpg/app.py`の`draw_result`で「ファンファーレ再生中…」を空のfooterへ変更。RESULT本体、成長・報酬・閃きは維持しています。
25. **ファンファーレ維持**：Music 1を従来どおり勝利時に1回再生。`assets/battle_music.pyxres`のハッシュは変更前と一致し、WAVと通常/ボス結果遷移の検証も成功しています。
26. **audio非依存**：行動演出はフレームと各段階最大2秒の単調時計で進行。勝利演出は2.4秒または72更新フレームで解除し、`play_pos`やチャンネル終了を進行条件にしません。音声APIが例外を返しても進行します。
27. **キャラ別成長**：`result_pages()`で計算済みログを分類し、1人のHP/STR/AGI/INT上昇を1ページへ集約。`draw_result`が名前、画像、上昇一覧を描画します。既存のAとD-PADでページ送りできます。
28. **成長なしのskip**：能力上昇行がないキャラクターは成長ページを作りません。「変化なし」も省略。全員成長なしでも既存の報酬/閃き結果へ進行します。
29. **成長判定の維持**：`rpg/growth.py / battle.py`と成長設定は変更前ハッシュと一致。表示関数には乱数や能力値更新がありません。演出有無で実際の戦闘結果・HP・Uses・乱数状態が一致しました。`Session.settle()`の二重実行防止も維持。
30. **追加state**：既存`resolve`の中でactor_step → skill_effect → 必要ならenemy_death → actor_returnの短い段階を保持します。成長ページは既存`result`内で管理。巨大なstate machineへ置き換えていません。
31. **入力ロック**：演出がactiveなら`update`の先頭で演出更新後にreturn。A/B/D-PAD、情報画面など通常入力には到達しません。終了時には入力をキューへ保存せず、通常の新規押下を扱います。終了用Q/SELECTは従来どおり使用できます。
32. **PC Python**：追加12件を含む全250件のunittestが成功。描画は実Pyxelのheadless環境で確認し、22枚の画像を出力。323回の文字描画が画面内に収まることを確認しました。実機GKD Pixel 2での操作確認は今回は未実施です。
33. **PC Browser**：ローカル配布HTMLを実Edge/Pyodideで起動し、実キーボード入力で戦闘→RESULT→探索、SAVE→再読み込み→CONTINUEを確認。詳細ログは`battle_presentation_browser.json`。
34. **Smartphone Browser**：EdgeのPixel 7タッチエミュレーションでD-PAD/A/B、戦闘→RESULT→探索、SAVE/CONTINUEを確認。**iOS Safari実機は未確認**で、エミュレーション結果を実機結果とは扱っていません。
35. **audio freeze回帰**：全音声APIの故障注入、各段階の時間切れ、停止した音声チャンネルでも結果に進めることを確認。無音のMASTERED/閃き/入れ替え、100回連続結果遷移、ボス後会話も成功。実Edge/PyodideではランタイムのAudioContextを実際にsuspendし、resumeを意図的に失敗させたまま、PCキー/タッチの両環境で戦闘→RESULT→探索を完了。記録された音声状態はsuspendedで、resume-failedログも確認しました。背景タブとvisibility/pagehide/pageshow/blur/focusイベントのテストも行いました。実際のスマートフォン自動ロックやiOSのinterrupted状態は未確認です。
36. **QUEST回帰**：Web埋め込み内容の九カテゴリ、討伐戦闘/RUN/敗北、帰還、お礼、QUEST COMPLETE、27種類の固有記録と100%表示が成功。QUEST関連定義・計算は今回変更していません。
37. **SAVE/LOAD回帰**：schemaや保存形式を変更せず、演出情報をSaveDataに含めていません。通常・終盤セーブ、最終章のcheckpointと5種類の敗北/再挑戦、実ブラウザlocalStorageの再読み込みを確認。Web/GKD配布にもプレイヤーSAVEを含めていません。
38. **既知の問題/制限**：画像は編集用の仮素材です。状態異常は表示の土台のみ。iOS Safariの実際の画面ロック→復帰、GKDの実機テンポ確認は利用者による確認が必要です。今回の自動検証範囲では進行不能・数値変化・データ破損は見つかりませんでした。

| effect_id | Image Bank | Y | コマのX |
|---|---:|---:|---|
| slash | 2 | 32 | 192,208,224 |
| blunt | 2 | 48 | 192,208,224 |
| pierce | 2 | 64 | 192,208,224 |
| fire | 2 | 80 | 192,208,224 |
| ice | 2 | 96 | 192,208,224 |
| lightning | 2 | 112 | 192,208,224 |
| magic | 2 | 128 | 192,208,224 |
| dark | 2 | 144 | 192,208,224 |
| heal | 2 | 160 | 192,208,224 |
| buff | 2 | 176 | 192,208,224 |
| debuff | 2 | 192 | 192,208,224 |
| legend | 2 | 208 | 192,208,224 |

## 必須44ケースと確認方法

| CASE | 結果・確認方法 |
|---|---|
| 1～4 | PASS：追加テスト。行動者A/Bだけ-6px、4回の行動で元座標に復帰。 |
| 5 | PASS：回復/self BUFF/敵DEBUFFの対象と表示、既存九カテゴリ検証。 |
| 6～9 | PASS：HP0、他メンバー正常、ASH蘇生、KO画面の文字範囲とSprite呼び出し。 |
| 10～15 | PASS：12共通素材、攻撃/魔法/回復/補助、未指定・不正値fallback、次の行動。 |
| 16～18 | PASS：HP0→点滅→沈む→消滅、待機中はRESULT未到達、他の敵は表示維持。 |
| 19～20 | PASS：Web埋め込み内容のB10→B15→守護者→デーモン→最終イベント→ENDINGと敗北再挑戦。 |
| 21～24 | PASS：開発用statuses3件、重複しない配置、KO優先、画像pixel編集が画面に反映。 |
| 25～28 | PASS：全15階の床主色、エリア別画像、最終戦の独立した床色。 |
| 29～32 | PASS：RESULT、既存Music1、字幕なし、無音時の進行と有界タイマー。 |
| 33～37 | PASS：1人/2人/複数能力/全員成長なしのページ、表示前後のparty不変、成長計算ファイル不変。 |
| 38 | PASS：実Edge/Pyodide、実キーボード操作。 |
| 39 | エミュレーションPASS：実Webランタイムへのタッチ入力。スマートフォン実機は未確認。 |
| 40 | 音声故障・復帰イベントの模擬検証PASS。実機ロックは未確認。 |
| 41 | PASS：全音声API故障、実Web AudioContextのsuspendとresume失敗、フレーム進行、各段階最大2秒、無音RESULT。 |
| 42 | PASS：既存SaveData往復、別プロセスCONTINUE、実ブラウザ再読み込み、演出stateなし。 |
| 43～44 | PASS：討伐戦闘と帰還/お礼/完了。既存九カテゴリ・27記録回帰を実行。 |

## 資産とルールの保全

`verification/backups/battle_presentation/baseline.json`との比較で、今回の変更対象以外の既存ゲームファイルのハッシュが一致しました。`skills.json`はeffect_idを除いた全項目が元のデータと一致しています。

`game.pyxres`を更新前後でPyxelへ読み込み、すべてのTilemap、Image Bank 0/1、全Sound/Musicを比較して一致を確認。Image Bank 2の変更は、今回予約したKO/Status/Effect領域の2199pixelsだけです。area2/area3、各パレット、戦闘BGMも不変です。画像は`tools/add_battle_presentation_assets.py`で一度だけ作成し、編集後の起動/ビルドでは再生成しません。

## 検証の再実行

```text
python -m unittest discover -s tests
python tools/verify_battle_presentation_ui.py
python tools/verify_battle_music.py
python tools/verify_audio_recovery.py
python tools/verify_web_build.py --phase6d --save-ui --quest-records --final-chapter
python tools/verify_browser_battle_presentation.py --playwright-path <Playwrightを配置した場所>
```

資産の前後比較にはローカルの`verification/backups/battle_presentation`が必要です。バックアップはGit管理対象外。Webブラウザ検証にはPlaywrightとEdge、ランタイム取得のネットワーク接続が必要です。

## 配布物

`dist/game.html`へ新しいPythonモジュール・技データ・画像を埋め込み済み。`dist/index.html`のキャッシュ回避付き起動は維持しました。`verification/packages/skill_seekers_gkd.zip`も更新し、saveフォルダや開発用テストを同梱していません。

GKD更新はゲームを終了した状態で、既存ゲームフォルダへZIPの`Skill_Seekers/`内のゲームファイルを上書きしてください。**既存saveフォルダはそのまま残し、フォルダごと削除しないでください。**ユーザー環境に合わせて変更済みの起動.shもそのまま使用できます。GitHubへのcommit/pushはこの作業では行っていません。
