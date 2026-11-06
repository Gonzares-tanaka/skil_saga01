# BGM / SE AUDIO PASS 01 確認報告

タイトル・拠点・AREA1/2/3・ボス・最終戦の7曲と、探索SE6種類を追加しました。既存通常戦闘BGMを含めて8場面にBGMがあり、既存勝利ファンファーレも維持しています。新規曲はオリジナルの仮Chiptuneで、後からPyxel Editorで変更できます。

作業開始時の静的ファイル58件、全画像・Tilemap、既存音声、RARE20技・LEGEND8技の描画トレースを `tests/fixtures/audio_pass_before.json` に記録しました。今回以前からの未コミット変更は保持しています。

## 指定55項目

### 1. 今回の変更ファイル

| 区分 | ファイル | 内容 |
|---|---|---|
| ゲーム | `rpg/sound.py` | 小さなAudioManager、ID/Scene/Event割当、2バンクのキャッシュ、native/Web再生、同一曲継続、Boss位置復帰 |
| ゲーム | `rpg/app.py` | 初期化済みAudioManagerをAppへ保持 |
| ゲーム | `rpg/dungeon_app.py` | 各SceneのBGM、探索6SE、既存HUNT達成記録の即時化と音のResult後表示 |
| 資材 | `game.pyxres` | 空いていたSound/Musicへ7曲・6SE・共用Cueを追加。Image/Tilemapは変更なし |
| 原稿・初回取込み | `tools/art/audio_pass_01.json`, `tools/add_audio_pass_assets.py`（新規） | 音列をゲームコードに埋めず、オフライン原稿から一度だけ取込み |
| 変更前記録 | `tools/snapshot_audio_pass.py`, `tests/fixtures/audio_pass_before.json`（新規） | 元データと描画の比較資料。既存baselineの上書きを拒否 |
| 新規試験 | `tests/test_audio_pass.py` | 28テスト：ID・曲長・チャンネル・native/Web・各Scene/Event・SAVE・保護監査 |
| 既存試験 | `tests/test_battle_extra.py`, `test_final_battle.py`, `test_finale.py` | 新AudioManagerをテスト用Appに保持、RUNのSEと復帰BGMをチャンネル別に数える |
| 既存監査 | `tests/test_rare_skill_presentation.py`, `test_legend_skill_presentation.py`, `test_player_skill_roster.py` | 後続Audio追加を新しい専用監査へ移し、画像・性能・描画回帰を継続 |
| 検証 | `tools/verify_audio_pass.py`, `tools/browser_audio_pass_case.py`, `tools/verify_audio_distribution.py`（新規） | WAV・native Boss/Final・実Pyodide・配布物の検証 |
| 既存検証 | `tools/verify_gkd_freeze.py`, `verify_battle_music.py`, `verify_browser_statuses.py`, `verify_legend_distribution.py`, `verify_rare_skill_presentation.py`, `verify_legend_skill_presentation.py` | 実探索→戦闘のBGM切替を大量試験、旧曲検証継続、音声有効Browser条件、出力先指定、後続Audio変更を専用監査へ移す |
| 案内 | `README.md`, 本報告 | Audio ID、編集場所、追加手順、試験範囲 |
| 配布 | `dist/game.html`, `verification/packages/skill_seekers_gkd.zip`, `skill_seekers_gkd_diagnostic.zip` | 全体テスト後の最新ゲーム・資材 |
| 記録 | `verification/audio_pass*.json`, `audio_pass_all_tests.txt`, `audio_pass_web_build.txt` | 最終確認結果。診断ビルドの既存 `gkd_diagnostic_package.json` も更新 |

途中の `audio_pass_focused_tests.txt` は試験初期の記録です。最終結果は `audio_pass_all_tests.txt` を参照してください。ユーザーのSAVEを読み書き・削除・上書きする処理は追加していません。

### 2. AudioManagerの構造

`rpg/sound.py`に集約しました。`play_bgm(id)`、`stop_bgm()`、`current_bgm`、`play_se(id)`、`update()`を持ち、Sceneは番号を直接指定しません。現在BGMは要求したAudio IDを保持し、同じIDでは再生を呼び直しません。音声デバイスが失敗しても毎Frame再試行しません。

Pyxel Editorの標準枠はSound64・Music8です。BGM8曲＋既存勝利曲を編集しやすく保持するため、既存2ファイルを別バンクとして初期化時に読み込みます。`game.pyxres`が追加曲、`assets/battle_music.pyxres`が通常戦闘・勝利曲です。切替時はキャッシュ済みSound/Musicを使い、ディスクの再読込や音列生成はしません。

共用SEは両バンクに同じデータを割り当てます。既存Sound30/31/59の編集元は元の `assets/battle_music.pyxres`、新SE50～55と既存Cue60～63の編集元は `game.pyxres`です。既存Cueを編集して再起動しても、その内容が両バンクで使われるテストを追加しました。

### 3～4. BGM・SE ID

3. BGMは `bgm_title`, `bgm_hub`, `bgm_area1`, `bgm_area2`, `bgm_area3`, `bgm_battle`, `bgm_boss`, `bgm_final` の8個です。

4. SEは `se_stairs`, `se_treasure`, `se_trap_damage`, `se_healing_spring`, `se_pitfall`, `se_quest_complete` の6個です。

### 5～12. BGMのMusic / Sound / Channel

番号はすべて0始まりです。**同じ番号でもファイルが違えば別の音源**です。全BGMのChannel0は空、Channel1～3をBGM専用にします。

| 項目 | Audio ID | 編集ファイル | Music | Channel1：旋律 | Channel2：Bass | Channel3：伴奏/Rhythm |
|---|---|---|---:|---|---|---|
| 5 | bgm_title | game.pyxres | 0 | Sound0～3 | 4,5 | 6 |
| 6 | bgm_hub | game.pyxres | 1 | 7～10 | 11,12 | 13 |
| 7 | bgm_area1 | game.pyxres | 2 | 14～17 | 18,19 | 20 |
| 8 | bgm_area2 | game.pyxres | 3 | 21～24 | 25,26 | 27 |
| 9 | bgm_area3 | game.pyxres | 4 | 28,29,32,33 | 34,35 | 36 |
| 10 | bgm_battle（既存） | assets/battle_music.pyxres | 0 | 0～7 | 8～11 | 12,13 |
| 11 | bgm_boss | game.pyxres | 5 | 37～40 | 41,42 | 43 |
| 12 | bgm_final | game.pyxres | 6 | 44～47 | 48,49 | 56 |

既存Victoryは `assets/battle_music.pyxres` のMusic1、Channel1=Sound20/23、Channel2=21/24、Channel3=22/25です。このファイルは作業開始時とバイト単位で一致し、曲の作り直しはしていません。

### 13～18. SEのSound番号

編集ファイルは全て `game.pyxres`、再生Channelは **0** です。

| 項目 | Audio ID | Sound | 長さ | 音の方向性 |
|---|---|---:|---:|---|
| 13 | se_stairs | 50 | 0.30秒 | 短い段階的な移動音 |
| 14 | se_treasure | 51 | 0.35秒 | 開く音から高い喜びの音 |
| 15 | se_trap_damage | 52 | 0.208秒 | 短い下降Noise |
| 16 | se_healing_spring | 53 | 0.667秒 | 明るい上昇音 |
| 17 | se_pitfall | 54 | 0.60秒 | 下降Pitchと低い着地 |
| 18 | se_quest_complete | 55 | 2.40秒 | 短い目標達成Fanfare |

### 19. Tempo / Length / Loop構造

新曲は32音以下の短いSoundパターンをMusicで並べます。Editorの48音・32パターン枠を超えず、3チャンネルの総時間も一致します。新曲のTempoは8分音符2個/拍としての目安です。

| 曲 | 目安BPM | SPEED | Loop長 | 構造・意図 |
|---|---:|---:|---:|---|
| TITLE | 90 | 40 | 42.67秒 | A→B→C→D。堂々とした長調の旋律、低いBass、控えめな伴奏 |
| HUB | 約106 | 34 | 36.27秒 | A→B→C→D。休符を含む軽い旋律と穏やかな伴奏 |
| AREA1 | 120 | 30 | 32.00秒 | A→B→C→D。上昇する旋律と前向きな探索感 |
| AREA2 | 100 | 36 | 38.40秒 | A→B→C→D。短調の低めの旋律と不穏なBass |
| AREA3 | 150 | 24 | 38.40秒 | A→B→A→C→D→D。進撃する短調のPulseとRhythm |
| 通常戦闘（既存） | 150 | 12 | 25.60秒 | 元の16分刻み・8パターンを保持 |
| BOSS | 180 | 20 | 32.00秒 | A→B→A→C→D→D。広い音域の斬り込む旋律と強めのRhythm |
| FINAL | 225 | 16 | 34.13秒 | A→B→C→B→A→C→D→D。専用旋律と高速の最終決戦感 |

FINALはBOSSの速度変更コピーではなく、音列・音域・曲構造が別です。7曲は既存作品の音源を使用せずに作成しました。新曲のVolumeは伴奏1～2・Bass2～3・旋律2～5、SEはおおむね2～6の仮調整です。Sound EditorのVolumeで変更できます。Fade/Crossfade Engineは追加していません。

全8BGM・6SE・既存勝利曲をWAVへ書き出し、非無音・クリッピング0を確認しました。[WAVと数値記録](audio_pass.json)。PC上のファイル試聴例：[TITLE](audio/pass01/bgm_title.wav)、[BOSS](audio/pass01/bgm_boss.wav)、[FINAL](audio/pass01/bgm_final.wav)。音楽の聴感・音量の最終評価は、テストプレイヤーと実機で調整してください。

### 20～27. Scene割当

| 項目 | Scene / 既存State | Audio ID |
|---|---|---|
| 20 | TITLE・セーブなし表示 | bgm_title |
| 21 | HUB、施設、導入・拠点Preview、帰還、LOAD後 | bgm_hub |
| 22 | B1～B5探索・探索Menu | bgm_area1 |
| 23 | B6～B10探索・探索Menu | bgm_area2 |
| 24 | B11～B15探索・探索Menu | bgm_area3 |
| 25 | normal / quest_hunt | bgm_battle |
| 26 | boss / guardian / demon | bgm_boss |
| 27 | elysion | bgm_final |

Battle判定は既存 `battle_kind` を使い、敵表示名では判定しません。Final Retryの確認画面とENDINGに専用曲は追加せず、既存結果演出の後はBGM停止です。Ending最後・再挑戦辞退でTITLEへ戻るとタイトル曲を再生します。

### 28～32. 移動・復帰・Retry

28. 階段のFloor移動確定イベントでSE1回、現在Floorに対応するBGMを要求します。移動拒否では鳴らしません。B5→B6、B10→B11で切替、同じAREA内では継続します。

29. `current_bgm`と要求IDを比較し、同じならplay/stop/loadを呼びません。B2→B3、B7→B8、B12→B13を確認しています。キャッシュは初回だけ読み込むため、同一曲の継続中にディスク読込もありません。

30. 通常VictoryのResult終了後は現在FloorのAREA曲。Boss撃破後の探索・会話は該当AREA曲。HUB帰還は拠点曲です。既存勝利Fanfareは1回、既存2.4秒/72更新のPresentation Timerを保持し、音声終了では判断しません。

31. RUN成功後も既存の逃走Visualを経て現在AREAの曲へ復帰します。逃走成功率・HP/Uses/道具は変更していません。

32. Final敗北後は既存Checkpoint/Retryを使い、再挑戦で `bgm_final` を開始します。辞退でタイトル曲。守護者連戦は同じBoss曲を保持し、Fanfareで中断した場合は保持したおおよその再生位置から復帰します。毎戦、曲の冒頭へ戻す動作を避けています。

### 33～35. Quest達成とChannel競合

33. EXPLORE/INVESTIGATEは既存の `investigate()` がcompleted=False→Trueになった時だけSEを出します。HUNTは対象撃破でVICTORYが確定した時に、既存 `hunt_victory()` による仮達成記録を即時に行います。既存処理を二重実行せず、元の目標達成メッセージを保持し、SEだけResult終了後の短い表示時へ移します。安全帰還・報酬確定のルールは変更していません。

34. 条件地点の再訪・達成済み調査・PUB報酬時には再生しません。HUNTも達成記録の更新は1回、保持した音声表示を1回消費します。ロードした達成済みQuestを自動的に再発音する処理はありません。

35. BGMは1～3、全SEは0。SEを鳴らしてもBGMチャンネルを停止しません。宝箱Trapは開くSE後、12更新Frame（0.4秒）だけ音のPresentationをずらしてDamage音を出します。HP処理は即時で、音の終了を待ちません。遅延SEは最大1件で蓄積せず、帰還・NEW GAME・LOADでクリアします。毒沼は実際にHPが減った処理で1回、静止中の毎Frame再生はありません。

### 36～40. Native・Freeze・音声失敗

36. NativeはMusic Editorの各チャンネルのSound列をスナップショットし、既存の安全な `pyxel.play(channel, sequence, loop=...)` で再生します。BGM停止は1～3だけで、SE0を止めません。

37. `pyxel.playm` は `sys.platform == 'emscripten'` の分岐内のみ。Linuxを模擬した全8曲/勝利/SE試験と、Windows nativeの実開始試験ではplaymを禁止して確認しました。専用の危険なNative経路はありません。

38. 既存Battle開始Regressionは **26,400 / 26,400成功**。各試行で探索BGMへ戻してから通常戦闘BGMへ切り替えるよう検証を更新し、実際の切替を繰り返しました。COMMAND_READY、描画、D-PAD/A/Bを確認。Audio通常/停止/例外・Transition bypassも含みます。別途B5/B10/守護者3種/Demon各100回＋Final100回＝**700 / 700成功**。[開始記録](audio_pass_freeze.json)、[Boss/Final記録](audio_pass.json)

39. Audio完全停止でもFloor処理・Pit・探索・Quest完了・Battle・Result復帰が進みます。状態更新の条件に `play_pos` や音声完了を使いません。

40. BGM/SE/play/stop/playmの例外を模擬しても進行します。起動時の音源読込が失敗しても音声だけを省略します。診断コード・ランチャー・切替設定は作業開始時ハッシュと一致し、既存診断テストも成功しています。

### 41～44. pyxres・編集・今後の追加

41. `game.pyxres`の元のSound/Musicは全て未使用でした。そこへ7曲、6SE、既存Cueの共用データを追加しました。全Image pixel・全Tilemapは一致しています。`assets/battle_music.pyxres`はそのままです。新しい曲も標準Music0～6・Sound0～63内で編集でき、Music7・Sound57/58は未使用です。

42. `pyxel edit game.pyxres`で新曲/SE、`edit_music.cmd`または `pyxel edit assets/battle_music.pyxres`で既存曲/既存Cue30/31/59を編集します。Ctrl+S後にゲームを再起動してください。旋律・Tone・Volume・Effect・SPEED、MusicのSound配列を自由に変更できます。ループ3列の総時間を揃え、Channel0は空にします。起動時に `.set()` で音列を再生成する処理は撤去しました。

43. 今後1曲増やす場合：空きMusic7とSound57/58で1～2Voiceの曲を作り、`BGM_IDS`へ例 `bgm_ending: ('scene', 7)` を登録します。Endingなど該当SceneからそのIDを要求する小さな接続を足せば使えます。3Voice以上・さらに多くの音源が必要なら、編集用pyxresをもう1バンク用意して `RESOURCE_BANKS` とBGM IDに登録します。バンクを増やしてもSceneはMusic番号を意識しません。Demon専用曲も `BATTLE_BGM['demon']` のID差替えで接続できます。

44. 新SEは空きSound57/58へ作成し、`SE_IDS`へ名前/番号を追加、`COMMON_SOUNDS`へ共用番号を追加します。該当Eventから `play_se(id)` を呼びます。通常SEはChannel0を使い、Music番号は不要です。将来のSE追加時は使用枠が他の新曲と重ならないよう対応表を更新してください。

通常の起動・Editor保存・ビルドでは取込みスクリプトを実行しません。`tools/add_audio_pass_assets.py`は初稿作成の記録で、使用中データがあれば上書きを拒否します。ゲームコードに大量のNote Dataはありません。`tools/art/audio_pass_01.json`はオフライン原稿で、配布物には含めません。

### 45～48. SAVE・性能・回帰・件数

45. SAVE schemaは変更していません。BGM ID・再生位置・SE QueueはSAVEに保存しません。LOAD後は現在Sceneの曲を要求するだけです。実プレイヤーのSAVEは変更せず、テストでは合成Saveと隔離Browser profileのみを使いました。

46. **save_version = 1** を維持しています。旧Saveの直接LOAD/再保存とBrowser backend経由の往復を確認しました。

47. Skill62、RARE20、LEGEND8、技性能、PARALYZE50%、Persistent Poison、CURE/REMEDY、敵・Boss能力、Encounter、Map、Quest内容、TRZ、Final Battle Logic・Checkpointを維持。変更前54静的ファイルのハッシュと全画像・Mapが一致し、RARE20＋LEGEND8の全描画/Frameトレースも一致しています。`battle.py`, `models.py`, `statuses.py`, `exploration.py`, `dungeon.py`, `final_battle.py`, `finale.py`, `save.py`と全dataを変更していません。

48. 全自動テストは **539 / 539成功**（追加28件、最終166.868秒）。旧曲の25.6秒Loop・2.4秒Victory・Palette・各ライフサイクルを検証する `verify_battle_music.py` も成功。[最終全体ログ](audio_pass_all_tests.txt)

### 49～55. Browser・配布・実機・制限

49. PC Browser：最終音源の実Pyodideで、音声有効 **38 / 38成功**、停止・復帰拒否 **38 / 38成功**、pageerror0。[音声有効記録](audio_pass_browser_running.json) / [停止・復帰拒否記録](audio_pass_browser_unavailable.json)。Audio26試験＋Status10ケース＋旧SAVE2往復です。8BGM場面・6SE・28技の描画トレース・実キーボードDown/Z/Xを含みます。

50. Touch Browser：同じ最終音源をEdge Chromium / Pixel7タッチエミュレーションで確認し、音声有効 **38 / 38成功**、停止・復帰拒否 **38 / 38成功**、pageerror0。実D-PAD/A/B pointer入力で、音声追加による入力・Stateの停止がないことを確認しました。音声有効ではAudioContext running、停止条件ではsuspendedとresume拒否を使いました。

51. Web版：全体テスト成功後に **`dist/game.html`を更新**。埋込み63entry中、ゲーム62ファイルが現在のコード・資材と一致します。SAVE/cache/testsを含めません。

52. Pixel2通常版 **`verification/packages/skill_seekers_gkd.zip`** と診断版 **`skill_seekers_gkd_diagnostic.zip`** を更新しました。通常63entry、診断66entry、ゲーム62ファイル一致・Python3.11構文互換・SAVE除外を確認しました。[配布監査](audio_pass_packages.json)。コピー更新時は既存 `save/` を残してください。今回、本体への転送やWeb公開は行っていません。

| ZIP | SHA-256 |
|---|---|
| 通常版 | `0d046d24761ff322304bf4b690eb43f9960b27095393af4ff96f02fe59500f8d` |
| 診断版 | `88225c6854b4958adabf8548a572837b962b6b85462035e2962b7a748cd4daa5` |

53. **iOS Safari実機は未確認**です。Browser試験はEdge/ChromiumのPCとタッチ模擬環境です。

54. **GKD Pixel2実機は未確認**です。Windows native実試験とLinux経路の自動監査までです。

55. 自動試験で残る不具合はありません。曲はαテスト用の仮仕上げです。自動WAV検査は非無音・信号レベル・クリッピングを確認するもので、聴感や実機スピーカーの音量・快適さの評価は含みません。BrowserもAudioContext/API/入力を検証し、出力を人が聴いた確認ではありません。端末のAudio Device・iOSの自動再生/復帰は実機で確認が必要です。プロジェクト `.venv` の参照先Pythonがないため、既存 `C:\temp\mypyxel\adventure_test\.venv-verify\Scripts\python.exe`（Python3.12.14 / Pyxel2.9.9）で検証しました。

## 必須CASE 1～84の対応

| CASE | 確認 | 対応試験・結果 |
|---|---|---|
| 1～4 | 起動/TITLE/離脱/次曲 | `test_title_new_game_load_and_hub_return`、成功 |
| 5～7 | HUB/帰還/曲切替 | 同上、成功 |
| 8～13 | B1/B5/B6/B10/B11/B15 | `test_all_area_endpoints_and_same_area_stairs_no_restart`、成功 |
| 14～16 | 同AREA3区間・Restartなし | 同上＋Manager同一曲100要求、成功 |
| 17～18 | AREA境界2区間 | `test_both_area_boundaries_switch_once_and_invalid_stairs_no_sound`、成功 |
| 19～23 | 各AREA通常戦/Victory/RUN復帰 | `test_each_area_normal_battle_victory_and_run_restore`＋既存RUN回帰、成功 |
| 24～28 | B5/B10/守護者/Demon・Boss曲 | 分類/継続試験＋native開始各100回、成功 |
| 29～32 | Final専用曲・Retry | `test_final_battle_retry_and_decline_title`＋既存Final Retry一式＋native100開始、成功 |
| 33～35 | 階段SE1回・Floor正常 | 同AREA/境界試験、成功 |
| 36～38 | 箱Open/SE/報酬 | `test_chest_open_rewards_and_trap_damage_delayed_sound_without_logic_wait`、成功 |
| 39～43 | 沼/箱Trap/SE/毎Frame再生なし | 同上＋ `test_swamp_actual_damage_once_idle_frames_silent_and_minimum_one`、成功 |
| 44～48 | 泉/SE/生存者全回復/Poison/Uses | `test_spring_heals_living_preserves_poison_uses_and_repeat_silent`＋既存回帰、成功 |
| 49～52 | Pit/SE/Floor/音声待ちなし | `test_pit_repositions_immediately_without_audio_completion`、成功 |
| 53～56 | Explore/Investigate達成SE | `test_explore_investigate_goal_once_never_at_pub_reward`、成功 |
| 57～59 | Hunt達成/SE/多重なし | `test_hunt_goal_immediate_sound_after_result_only_once`、成功 |
| 60～64 | BGM/SE失敗・完全停止で進行 | Manager例外・無効化試験＋Scene進行＋既存Audio Recovery、成功 |
| 65 | native playm禁止 | 全8BGM/Victory/6SEのLinux分岐、native実大量試験、成功 |
| 66～67 | 大量Battle開始/COMMAND_READY | 26,400回・描画・D-PAD/A/B、成功 |
| 68～70 | Boss/Final開始・切替Freezeなし | native700開始、成功 |
| 71～74 | BGM中の階段/箱/Quest/複数SE | `test_all_six_se_and_stopping_only_bgm_do_not_touch_bgm_channels` / 全バンク共用Cue、成功 |
| 75 | Skill62 | 既存Roster試験・静的全dataハッシュ・配布監査、成功 |
| 76～77 | Rare/Legend表示 | 既存表示回帰一式＋28技の開始前描画トレース比較、成功 |
| 78～81 | Paralyze50/Poison/Cure/Remedy | 既存回帰一式＋Browser Status10ケース、成功 |
| 82 | Quest | 既存Quest全パターン・新SE・即時記録/報酬分離、成功 |
| 83 | Save/Load | SAVE全体試験・Audio state非保存・旧Save往復、成功 |
| 84 | Final Retry | 既存Checkpoint・Amrita/Barrier・今回音楽再開試験、成功 |

## 再検証・再生成

```text
python -m unittest discover -s tests
python tools/verify_audio_pass.py
python tools/verify_battle_music.py
python tools/verify_paralyze_freeze.py --output verification/audio_pass_freeze.json
python tools/build_web.py
python tools/build_gkd.py
python tools/build_gkd_diagnostic.py
python tools/verify_audio_distribution.py
python tools/verify_browser_statuses.py --fixture tools/browser_audio_pass_case.py --base-fixture tools/browser_status_case.py --unit-fixture tests/test_audio_pass.py --extra-fixture tests/fixtures/audio_pass_before.json --extra-fixture tests/test_rare_skill_presentation.py --extra-fixture tests/legend_presentation_helpers.py --save-fixture tests/fixtures/skill_foundation_save_v1.json --expected-count 38 --keep-audio --output verification/audio_pass_browser_running.json
```

停止条件のBrowser試験は最後のコマンドから `--keep-audio` を外し、出力先を `verification/audio_pass_browser_unavailable.json` にします。Playwright・Edgeと公式Pyxel/Pyodide配信へのアクセスが必要です。WAV・試験fixture・原稿は配布物に含めません。
