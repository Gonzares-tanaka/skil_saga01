# QUESTシンボル配置の調査・修正（2026-10-10）

**B14の調査シンボルが明るい床と同色になり、ほぼ見えなくなる表示不具合を確認・修正した。ユーザーの再確認でも「地面と同色で見つけられなかっただけ」と確認された。別に、B15の安全な配置候補不足も修正した。B14・調査Lv3・1/3のCONTINUE後に残り2地点が論理的に消える不具合は再現していない。**

ユーザー提示の公開版 https://gonzares-tanaka.github.io/skil_saga01/ の`game.html`を取得し、今回の変更前のQUEST処理・SAVE処理・3エリアのリソースと一致することを確認した。公開サイトやプレイヤーのlocalStorage、PC/GKDの既存セーブは変更していない。ブラウザテストはローカル配信と隔離プロファイルを使った。

## 修正前後の候補

座標は0始まりのタイル単位。既存候補はImage Bank 1の`TILE_QUEST=(13,0)`。B15の補助候補だけ`data/dungeon.json → floors[14].quest_spawn_points`で普通の床に明示登録した。

| フロア | リソース / Tilemap | 登録数：修正前→後 | フィルタ前：修正前→後 | 有効数：修正前→後 | 調査必要数 | 修正後 |
|---|---|---:|---:|---:|---:|---|
| B1 | game / 0 | 3→3 | 3→3 | 3→3 | 2 | 全種OK |
| B2 | game / 1 | 3→3 | 3→3 | 3→3 | 2 | 全種OK |
| B3 | game / 2 | 3→3 | 3→3 | 3→3 | 2 | 全種OK |
| B4 | game / 3 | 3→3 | 3→3 | 3→3 | 2 | 全種OK |
| B5 | game / 4 | 3→3 | 3→3 | 3→3 | 2 | 全種OK |
| B6 | area2 / 0 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B7 | area2 / 1 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B8 | area2 / 2 | 4→4 | 4→4 | 4→4 | 3 | 全種OK |
| B9 | area2 / 3 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B10 | area2 / 4 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B11 | area3 / 0 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B12 | area3 / 1 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B13 | area3 / 2 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B14 | area3 / 3 | 3→3 | 3→3 | 3→3 | 3 | 全種OK |
| B15 | area3 / 4 | 3→7 | 3→7 | 1→5 | 3 | 全種OK |

B15の既存3候補は`(4,10) / (20,12) / (6,29)`。最初の2地点は警告・守護者の先にあり、安全な候補から除外されていた。`(2,27) / (7,27) / (2,30) / (7,30)`を入口側の普通の床に追加登録し、既存の`(6,29)`と合わせ5地点を使う。守護者撃破後もQUEST候補は変えず、泉・デーモン・石碑・警告地点とは重ならない。リソースへ書き込んでいない。

B14の候補は`(6,19) / (11,3) / (19,14)`。現在のSAVE方式で調査1/3をCONTINUEすると、再構築した候補の先頭`(6,19)`を調査済みに割り当て、残りは`(11,3) / (19,14)`となる。座標の保持をしない既存仕様なので、受注時の調査済み座標と必ずしも一致しない。この復元方針は変更していない。

## B14で確認した表示不具合

調査用の虫眼鏡はImage Bank 1の`(240,0)`の8×8画像。輪の部分はすべて色3、持ち手の3ピクセルだけ色2だった。B14の候補地点の床も主に色3で、透明色0による元の重ね描画では輪が床に溶け込み、持ち手の小さな点だけが見えていた。SAVEなし・LOAD後の両方で起こり、SAVEによって画像が欠落したわけではない。

`rpg/art.py → draw_quest_symbol()`で画像の非透明ピクセルの上下左右へ色0の縁取りを描き、元の画像を重ねる。探索・調査・討伐の3種に共通適用し、明るい床でも位置と形が分かるようにした。地図のクリップ内だけに描画する。元の画像・パレット・マップは変更せず、Pyxel editorでの画像差し替えも維持した。実ピクセルのテストで元の色が保たれ、全15階の全有効候補で輪郭が付くことを確認した。

## 完了報告30項目

| No. | 項目 | 結果 |
|---:|---|---|
| 1 | 根本原因 | B14では調査シンボルの輪と床が色3で一致し、ほぼ見えなかった。別にB15は安全候補1地点で調査3地点を満たせず、生成時にB15が除外されていた。論理的なB14シンボル消失は再現なし。 |
| 2 | Lv1が正常だった理由 | B1～B5の候補各3地点がすべて安全に到達可能で、必要数1/2/1を満たしていた。暗い床では明るい虫眼鏡が見えるため、床色による表示問題も目立ちにくい。 |
| 3 | Lv2に同じ問題があったか | B6～B10は必要候補数を満たす。B7の扉も到達可能なスイッチによって開けられる。候補不足はなし。明るい床ではLvにかかわらず同色のシンボルが見えにくくなるため、Lv2を含む全階・3種へ縁取りを適用。 |
| 4 | Lv3で発生した理由 | B14の明るい床と調査画像の色が重なった。B15では進行イベントの前後で候補が分断されていた。B11～B14の候補不足・番号ずれ・B10までの条件漏れは検出なし。 |
| 5 | 問題のあったfloor | 表示不具合を確認：B14（内部13）。候補不足：B15（内部14）。表示対策は全15階に共通適用。 |
| 6 | TYPE別影響 | B14の調査画像は輪がほぼ消え、持ち手のみ見えた。床色と画像色が同じ場合は探索・討伐にも影響し得るため3種を修正。B15の探索・討伐は修正前も生成可能、調査のみ3地点不足。修正後は全種可能。 |
| 7 | 修正ファイル | 本体：`rpg/art.py`, `rpg/dungeon_app.py`, `rpg/quests.py`, `rpg/exploration.py`, `rpg/dungeon.py`, `rpg/save.py`, `data/dungeon.json`。検証：`tests/test_quest_visibility.py`, `tests/test_quest_spawn.py`, `tests/test_quests.py`, `tests/test_feedback.py`, `tests/test_finale.py`, `tools/verify_quest_spawn.py`, `tools/verify_browser_quest_spawn.py`。説明：READMEと本報告。配布：`dist/game.html`, GKDコピー用ZIP。 |
| 8 | 候補の定義場所 | 通常は各リソースのTilemap0～4の`TILE_QUEST`。補助は`data/dungeon.json`の各floorの`quest_spawn_points`。 |
| 9 | floor番号 | Dungeon/Tilemap配列は0～14。QUESTの`target_floor`とSAVE・画面は1～15。境界で±1し、Lv3は11～15を維持。 |
| 10 | B6～B10有効候補数 | 3 / 3 / 4 / 3 / 3。 |
| 11 | B11～B15有効候補数 | 3 / 3 / 3 / 3 / 5。 |
| 12 | B15配置 | 守護者より手前の入口区画の5地点から抽選。調査3地点を相異なる座標に配置。B15を対象から除外していない。 |
| 13 | 探索Lv2 | B6～B10各階に強制指定して1地点を生成。SAVEなし・SAVE後・新規オブジェクトへのLOADでPASS。 |
| 14 | 調査Lv2 | B6～B10各階に3地点を生成。部分進捗LOAD・重複調査防止・安全帰還と正式完了もPASS。 |
| 15 | 討伐Lv2 | B6～B10各階に1地点を生成し保存復元もPASS。配布ペイロードの実UI検証で接触戦闘・勝利・RUN時の継続を確認。 |
| 16 | 探索Lv3 | B11～B15各階に1地点を生成。保存復元ともPASS。 |
| 17 | 調査Lv3 | B11～B15各階に3地点を生成。保存復元・部分進捗・重複防止・正式完了ともPASS。 |
| 18 | 討伐Lv3 | B11～B15各階に1地点を生成。保存復元ともPASS。配布ペイロードの実UI討伐・勝利・報酬もPASS。 |
| 19 | SAVEなし | 全15階×3種＝45通りを強制指定しPASS。別階ではシンボルを表示しないことも確認。 |
| 20 | SAVE/LOADあり | 全45通りで実ファイルSAVE→別の新規ゲームオブジェクト→LOADを確認。実Edge/Pyodide/localStorageでも代表6階×3種×PC/タッチ＝36ケースを確認。B6/B14/B15調査はページ再読み込みも実施。 |
| 21 | active_quest再構築 | `prepare_saved_game()`が保存されたtype/level/target_floor/progress/required_count/flavor_idを検証し、同じ対象階の共通候補関数で座標を再構築。生成とLOADに異なるフィルタは使わない。 |
| 22 | 座標SAVE有無 | 従来どおりSAVEにpoints・investigated_pointsは含めない。LOAD時に候補を割り当て、progress数だけ調査済みにし、残りを表示。 |
| 23 | validator | `tools/verify_quest_spawn.py`を追加。全階の登録数・重複除去後数・有効数・除外理由・種別ごとの必要数を確認し、不足時は非0終了。 |
| 24 | Lv1回帰 | 全5階×全3種の生成・LOAD・部分調査を含めPASS。 |
| 25 | B1～B15マップ保持 | 全3 `.pyxres`と関連素材・パレットを含む25ファイルのSHA-256一致。`dungeon.json`の変更もB15の補助候補項目だけと比較確認。Tilemapの変更なし。 |
| 26 | 完了・お礼・TRZ | 埋め込みWebペイロードの実Pyxel UIで9パターンの接触・徒歩帰還/RETURN・お礼→報酬・全滅時の未完了を確認。通常27件＋fallback9件のお礼もPASS。 |
| 27 | completed_quest_ids | 固定27IDのまま。重複達成・CLEAR回数・固有ID・100%・fallback除外の回帰PASS。 |
| 28 | save_version | 1のまま。Browserキー`skill_seekers_save_v1`も維持。 |
| 29 | 既存SAVE互換 | 共通SAVE項目・JSON形式・IDを変更していない。旧形式の論理QUEST状態をそのまま復元する。公開版と同じ処理で作ったB14・1/3のSAVEを継続可能。ユーザー本人のSAVEは取得していない。 |
| 30 | 既知の問題・制限 | B14の表示不具合は修正・描画検証済みで、ユーザーも同色が原因と確認。修正後のiOS SafariとPixel2実機確認は未実施。Windows上のPlaywright WebKitはゲーム初期起動待ちでタイムアウトし、QUESTテストまで到達できなかった。候補が将来編集で壊れた場合は受注を拒否し、LOADも失敗を明示して元SAVEを保持する。 |

## 失敗防止とレビュー

候補は必ず普通の床または候補印に限定し、壁・マップ外・イベント上・到達不能・進行ゲートの先を除く。重複座標を除去する。B1～B15共通で適用し、受注の確定時にも再検証する。プレビューが無効になった場合は対象階を変えず拒否し、RNG・active_quest・報酬を変更しない。生成時/LOAD時の不足は`QUEST SPAWN FAILED type=... level=... target_floor=B...F required_count=... valid_candidate_count=...`をログへ出す。

過去のテストは「生成できるeligible階だけ」を期待値としており、B15調査が除外されても成功していた。新テストは全15階を明示的に指定し、各階の3種すべてが生成できることを要求する。旧テストの「必ず候補印のタイルである」という前提は、床へのデータ登録にも対応する安全候補確認へ変更した。

## 検証結果と再実行

- `python -m unittest discover -s tests`：233件PASS（103.952秒）。候補・全45通りのSAVE/LOAD・部分進捗に加え、全階の実描画ピクセルと素材非変更の3テストを含む。
- `python tools/verify_quest_spawn.py`：全15階PASS。候補データは[quest_spawn.json](quest_spawn.json)、修正前は[quest_spawn_before.json](quest_spawn_before.json)。
- `python tools/verify_web_build.py --phase6d --save-ui --quest-records --final-chapter`：埋め込み内容と画像一致、9種のQUEST・27固有依頼＋9fallback・RETURN・SAVE失敗・新規プロセスCONTINUE・全滅・B10→ENDINGと最終戦5回再挑戦がPASS。無音状態もPASS。
- `python tools/verify_browser_quest_spawn.py --channel msedge --playwright-path verification/backups/quest_spawn/browser_deps`：配置修正後の実Edge/Pyodide/localStorageの36ケースPASS。[quest_spawn_web.json](quest_spawn_web.json)。縁取り追加後は`--b14-only`のPC/タッチ2ケースと`verify_web_build.py --phase6d`を再実行しPASS。
- `--before-fix`：修正前WebでB14調査・SAVE・再読み込み・CONTINUE・1/3復元をPC/タッチ双方で確認。論理的な消失はなし。[quest_spawn_web_before.json](quest_spawn_web_before.json)。表示の実画像では床と虫眼鏡の輪が同色だった。
- `--b14-only`：修正後B14の残りシンボルをカメラ内へ配置して描画を追加確認。調査済み座標へ移動する重複チェック用のテスト位置と、残りシンボルを撮る位置を区別する。結果は[quest_spawn_web_b14.json](quest_spawn_web_b14.json)。
- ハッシュ保持・GKD ZIP照合：[quest_spawn_preservation.json](quest_spawn_preservation.json)。

修正前後の同じカメラ位置のスクリーンショットを確認し、修正前は輪が床に溶け込んで持ち手の点しか見えず、修正後は虫眼鏡の輪郭がはっきり表示されることを目視確認した。実機Safariの検証結果としては扱っていない。

ブラウザの到達階・ボス撃破・カメラ位置・部分進捗は検証用fixture。実際のA/B操作でGUILD SAVEとCONTINUEを行い、ブラウザ内の実PythonとlocalStorageを検証した。自然な長時間プレイやユーザーのiOS実セーブの再現を代替するものではない。今回のWeb再生成はローカルの`dist/game.html`までで、公開URLへPushしていない。既存SAVEを消してやり直す必要はない。

追加のB5/B10通常遭遇修正については[ボス階の通常遭遇修正報告](BOSS_ENCOUNTER_REVIEW.md)を参照。B15はユーザーの最終指定に従い通常ランダム遭遇なしのまま、QUESTは有効。
