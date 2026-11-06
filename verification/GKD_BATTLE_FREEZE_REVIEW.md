# GKD Pixel 2 戦闘開始フリーズ調査

調査日: 2026-10-13

## 1. 結果 A

**A：自動環境で戦闘開始停止を再現し、停止箇所を特定した。**

PC Python 3.14.7 / Pyxel 2.9.9のheadless実行で、戦闘Transition末尾の`start_battle_music()` → `pyxel.playm(0, loop=True)`が戻らず、その後の更新・入力受付に進めない状態を捕捉した。60秒間隔の複数スタックが同じ位置に止まった。

さらに敵・マップ・Battleを含まない音声APIだけの隔離子プロセスでも、183回目（0起点182）の`playm`要求が戻らず、3秒時点のスタックを取得、10秒で当該子プロセスだけを終了した。同じ音源をチャンネル別に`pyxel.play()`する比較は1,000回成功。修正後の実ゲーム開始経路も26,400回成功した。

**GKD実機の2回の停止が同一原因であることは未確認。** 実機はPython 3.11.7 / Pyxel 2.9.9 / plumOS、起動はユーザー確認済み`Skill_Seekers.sh`。停止時の音声状態は不明。ネイティブAPI内部で停止する再現可能な原因を最小回避し、GKDでなお停止する場合に別原因を捕捉できる診断版も提供する。

## 2. AREA2のSKELETON画像を使う正式ID

Image Bank 0の`(80,16)`、16×16を共有するのは以下の2種類。

| enemy_id | 正式表示名 | AREA2の通常抽選で含む階 |
|---|---|---|
| skeleton | 骸骨兵 | B6 |
| assassin | 暗殺者 | B8、B9、B10 |

B10は既存仕様どおりB9の通常敵テーブルを使用する。B7の通常敵テーブルにはこの2IDは含まない。現在のAREA2抽選ではskeletonとassassinが同じ階の同じグループに混ざる構成はないが、汎用処理の切り分けとして両方を強制生成して検証した。Sprite割当・テーブル・画像は変更していない。

## 3. 実際の開始処理の順番

添付の想定順とは一部異なり、Command初期化はTransitionより先に行われる。また専用のEnemy Intro/Party Introステートは存在しない。

| 順序 | ファイル・関数 | 処理 / State |
|---|---|---|
| 1 | dungeon.py / Dungeon.step | 歩行イベントを判定、通常遭遇で`battle`を返す |
| 2 | dungeon_app.py / handle_event | `battle`で`begin_encounter(animate=True)` |
| 3 | dungeon_app.py / begin_encounter | 現在の探索画面を描画し、Imageへ画面をコピー |
| 4 | dungeon.py / make_enemies | count/weightでID抽選、各行から別Enemyを生成 |
| 5 | models.py / Enemy.from_definition | 固定種別ID・Spriteを持つ独立instance。表示名にはA/B等を付ける |
| 6 | battle.py / Session.next_battle | 枠・生存者・資源を確認、Battle生成、Uses等は持越し |
| 7 | app.py / begin_input | `command`、order=生存者index一覧、actor_position=0、cursor=0、actions=[]、混乱者を有限ループで飛ばす |
| 8 | dungeon_app.py / begin_encounter | input lock=True、`battle_transition`、hold=3、transition frame=0、SE59要求 |
| 9 | dungeon_app.py / draw → App.draw_battle | BattlePresentationを遅延生成。敵・味方・Commandメニューを描画し、その上へ4分割探索画像を描画 |
| 10 | dungeon_app.py / update | holdを3回減算、その後18フレーム進める |
| 11 | dungeon_app.py / update | `command`へ変更、BGM0開始要求。修正前の再現停止位置はこの`playm`内部 |
| 12 | dungeon_app.py / update | 次の更新でTRANSITION_INPUTSの全ボタンが離れているか確認しinput lock解除、その更新はreturn |
| 13 | App.update | 以後の新しい押下で通常Command入力を処理 |

30FPSで既存演出はhold 0.1秒＋Transition 0.6秒。タイマーは変更なし。試験では更新22回でinput lock解除まで到達、続いてD-pad/A/Bの実コード経路を確認した。

## 4–6. ID / Spriteの個体管理

4. `enemy.id`を戦闘内の個体一意キーとして使う辞書・setは、監査対象のBattle/Presentation/Target/Intro/描画に見つからない。DungeonのID辞書は敵種別の定義テーブルであり、個体管理ではない。最終ボス判定も種別ID判定として適切。
5. 同一ID複数はlistの個別indexで管理。片方のHP/Statusを変えてももう片方は変わらず、対象index 1への攻撃・敵行動・演出を識別できることを確認。EnemyAction payloadの`enemy_id`は情報、描画側の個体参照は`enemy_index`。
6. Sprite座標はbltの素材参照だけ。位置・演出・死亡・Targetは戦闘indexで管理し、同Sprite・別IDでも独立する。

## 7–14. 大量試験結果

全て実`begin_encounter()`、フレーム単位`update()/draw()`、入力ロック解除、D-pad下/上、AでSKILL、BでCommandへ戻るまで確認。生存4人・初期技を持つ合成Sessionを再使用。試験間の戦闘終了フラグは試験側でリセットし、自然勝利/成長はこの大量開始試験には含めない。

| 項目 | 編成 / 経路 | 回数 | 結果 |
|---|---|---:|---|
| 7 | skeleton×2 | 1,000 | 全てCOMMAND_READY＋入力可 |
| 8 | skeleton×3 | 1,000 | 同上 |
| 9 | assassin×2 | 1,000 | 同上 |
| 10 | assassin×3 | 1,000 | 同上 |
| 11 | skeleton＋assassin、逆順 | 各1,000 | 同上 |
| 11補足 | skeleton＋assassin＋skeleton、逆の3体構成 | 各1,000 | 同上 |
| 12 | iron_golem×2、berserker×2、mage×2、stone_beast×2 | 各1,000 | 同上 |
| 混成 | skeleton＋mage、assassin＋mage、skeleton×2＋mage、assassin×2＋mage | 各1,000 | 同上 |
| 13 | B6/B7/B8/B9/B10の実make_enemies抽選 | 各2,000 | 同上 |
| Audio比較 | 通常 / 音声API無効 / 音声API例外 | 各100 | 同上 |
| Transition比較 | 既存animate=False経路 | 100 | 同上 |
| 14 TOTAL | 強制16,000＋実テーブル10,000＋比較400 | **26,400** | **26,400成功** |

通常遭遇率そのものは変更せず、10,000件は実テーブルのグループ抽選から先の経路。歩行して9%の抽選を待つ試験ではない。通常Audioの大量試験は修正後のネイティブAPIを実際に呼んでいるが、GKD音声デバイスの試験ではない。

## 15–19. State・Loop・Queueの監査

15. Battle Intro専用State・敵の登場完了待ちは存在しない。最初はidleのBattlePresentationで、行動QueueもメッセージQueueも空。
16. COMMAND到達条件は既存hold/transitionフレームのみ。最後に同期的なBGM要求があり、それが戻って初めて次の更新へ進める。
17. Input lock解除はTRANSITION_INPUTS全てのbtn=Falseの更新。今回強制解除・判定削除はしていない。診断では押され続けているキー番号を記録するため、ランチャー/入力マッピングの問題も区別できる。
18. Python開始経路に終了しないLoopは見つからない。混乱者スキップはactor_positionが増加し最大4人、敵・描画は最大4体、Target検索も有限list。捕捉した停止はPythonのwhileではなくネイティブ関数呼び出し内。
19. Presentationは開始時phase=NoneでQueue待ちはない。frame/wall-clockで終わる既存行動演出は維持。Enemy index別状態も独立。

## 20–24. Audio・Transitionと直接原因

20. 通常遭遇時はTransition開始SE59 → 3＋18フレーム → BGM0要求。開始SEとBGMは同じゲームフレームではない。無音や例外では既存try/exceptにより進行できるが、**native APIが戻らない場合は例外が発生せず、try/exceptでは回避できない**。
21. 音声APIだけの旧playm試験は183回目で停止。音声を無効化・例外化した開始経路は各100回成功。同じ曲のチャンネル別再生は1,000回成功し、実ゲーム修正後も26,400回成功。
22. Transition hold/18-frame処理は有限。通常演出ありの26,300開始が完了。
23. 比較用に既存animate=False経路を100回実行し全て完了。診断版だけで設定可能、通常の演出設定は維持。
24. **直接原因：同期`pyxel.playm`呼び出しがネイティブ内部で戻らず、主更新処理が止まる。** 敵・個体ID・Spriteがなくても再現する。内部のどのMutexをどのネイティブthreadが所有したかはPythonスタックだけでは断定できない。

内部機構については、公式v2.9.9の`play_music`がchannels参照取得後にAudioLockを取得し、音声レンダラーもchannels参照を取得するため、ロック順序の衝突が疑われる。これは**ソースからの推論**でありネイティブthreadの実測ではない。`play()`はAudioLock後にchannelsを取得する実装であり、今回の回避方式の根拠とした。[Pyxel公式v2.9.9 audio.rs](https://raw.githubusercontent.com/kitao/pyxel/v2.9.9/crates/pyxel-core/src/audio.rs)

## 25–29. 最小修正と回帰テスト

25. 製品コードの変更は`rpg/sound.py`のみ。検証・診断・梱包用tools、tests、README、報告・配布物を追加/更新。
26. `_play_music()`を設け、ネイティブではMusic EditorのseqsをPython listへコピーしてから非空チャンネルを`pyxel.play(channel, seq, loop=...)`で起動する。BGM0と同じAPIを使うファンファーレ1に適用。SEは従来どおり、Web/emscriptenは従来のplaymを維持。
27. 停止が再現したネイティブplaym経路を使用しない。音を無効にする処理や別threadへ投げる処理ではなく、同じ曲データを既存の別再生APIへ渡す。開始経路の比較とnative API試験で回避を確認した。
28. enemy.id、SAVE、HUNT、QUEST、Skill62、Enemy/Action/Status/Map/画像/音源に変更なし。開始State、hold、入力ロックも未変更。保護ファイルの全hash一致を専用大量試験で検証。
29. `tests/test_gkd_diagnostic.py`にnative playmを禁止してEditor seqs/loop flagを検証する回帰、Web playm維持、実Transition→Command→入力解除の診断回帰を恒久追加。`tools/probe_gkd_audio.py`に子プロセスによる旧API停止再現比較、`tools/verify_gkd_freeze.py`に26,400開始試験を残す。

## 30–36. 回帰と環境確認

30. 全自動テスト **449/449成功**（既存443＋追加6）。
31. 通常戦闘、HUNT、B5/B10 Boss、B15守護者/デーモン、LORD、RUN、勝利、Status、持越し毒の既存テスト成功。最終章通しもB10→ENDING、5回実全滅の再挑戦を確認。
32. 正式Skill62の全テスト成功。データファイルhash一致により数値・名前・Uses・成長・RESTORE・閃きWeightの変更なし。
33. SAVE/LOADテスト成功、旧31技セーブ・新62技セーブの合成データ往復成功。schema/version1とsave.pyのhash一致。プレイヤーのセーブにはアクセスしていない。
34. 更新Web埋込みソース/JSON/全素材一致、実Edge Chromium Pyodideで27テスト、実Down/Z/X入力、localStorage、suspended/resume失敗時進行を確認。
35. 同じ27テストをPixel 7タッチエミュレーションで成功。HTML D-PAD/A/BへのtouchStart/endで操作確認。実iOS Safariの試験ではない。
36. GKD実機・plumOSの実オーディオ・ボタン・画面はCodex環境では直接確認できない。修正ZIP/診断ZIPでユーザーの実機確認が必要。

## 37–41. 診断版

37. Python標準faulthandlerの実スタック出力を一時フォルダで確認済み。GKD Python3.11で利用可能なら更新が20秒途絶えた場合に1回dumpする。ゲームを終了させたりStateを強制変更したりしない。未対応時はWATCHDOG_UNAVAILABLEを記録。GKDでの利用可否は起動ログで判定する。
38. 診断ZIPだけの`diagnostic_main.py`がoriginalメソッドを観測する。通常main.pyは診断コードをimportしない。例外はCheckpointを出した後に再raiseし、ゲーム例外を診断側で握りつぶさない。
39. **保存場所**：ゲームディレクトリ`Skill_Seekers/diagnostics/`。SAVEとは別領域。

| ファイル | 内容 / 上限 |
|---|---|
| battle_start.jsonl、battle_start.jsonl.1 | seq・frame・floor・enemy count/id/name/sprite/index・state・presentation・active player・input lock・queue length・Audio要求。各256KiB、ローテーション |
| python_stacks.log、python_stacks.log.1 | 更新停止時/例外のスタック。1回の更新停止につき1dump、64KiB以上なら再予約を停止。1dump分の超過はあり得る。前起動分は.1へ |
| launcher階層 / skill_seekers_diagnostic_launch.log | 起動環境、標準出力、終了例外 |

Checkpointごとにflush。戦闘突入SE/BGMの主要要求直前・COMMAND_READY・例外ではfsyncも行い、電源断前の最後の位置を残す。毎フレームのファイル書込はしない。input lock中の追加チェックは0.5秒間隔、キーが変化した場合に詳細を記録。音声APIのENTER/RETURN/EXCEPTION、最初の敵・味方描画、実Command表示、入力解除を区別する。

40. **診断ZIP**：`verification/packages/skill_seekers_gkd_diagnostic.zip`、64エントリ。通常修正版のゲームソースと完全一致し、追加ランチャー/診断entry/config/手順書だけを加える。Python3.11構文確認済み。SAVEなし。
41. **通常Pixel2 ZIPは更新した。** 再現したnative playm停止を最小回避する`skill_seekers_gkd.zip`、61エントリ。診断ZIP作成処理が通常ZIPを再上書きしないこともhash確認済み。dist/game.htmlも共有ソースを再梱包したがWebの再生経路は従来どおり。

### 実機での起動・ログ回収

1. 診断ZIPを展開し、`Skill_Seekers`を既存フォルダへ**上書き/結合**する。既存フォルダや`save/`を削除しない。
2. `Skill_Seekers_Diagnostic.sh`を通常`Skill_Seekers.sh`と同じ場所へコピーする。通常ランチャーはこの診断ZIPでは上書きしない。
3. **Skill_Seekers_Diagnostic.sh**から起動し、まずデフォルト設定でAREA2をプレイする。
4. 再発した場合はPC/ファイルマネージャーで上記jsonl・stack・launcher logを回収する。セーブの提出は不要。

設定は`Skill_Seekers/diagnostic_config.json`。次回起動から有効。

```json
{
  "battle_start_audio": true,
  "skip_transition": false,
  "watchdog_seconds": 20
}
```

比較Bはbattle_start_audioだけfalse。戦闘開始音声要求だけ抑制し、通常の戦闘中SEは維持する。比較Cはskip_transitionだけtrue。既存のanimate=False開始経路を使い、入力Stateへ強制ジャンプしない。比較は1項目ずつ変え、通常修正版/通常Webでは有効化しない。

## 42. 既知の問題・限界

- PCでの停止位置と回避は再現・検証できたが、GKDの2回の停止が同じ原因かは実機のログ待ち。
- 内部ロック衝突は公式ソースからの推論。PythonのfaulthandlerはRust/SDLのネイティブ所有Mutexまで表示しない。
- チャンネル別起動は複数チャンネルを単一APIで原子的に開始する方式ではない。音源・速度・loop・使用チャンネルは同じだが、実機での聴感も合わせて確認したい。
- GKDの音声デバイスや別のnative API停止まで、今回のPC試験で完全保証するものではない。再発時にCheckpointとスタックを取れる手段を残した。
- 試験中の60秒周期スタック出力には、正常に進行中のMock/描画位置も含む。それは大量試験全体の時間経過による定期dumpで、停止判定ではない。修正前に繰り返し同じplaym位置で止まった記録と、子プロセス10秒timeoutの証拠を区別している。

## 証拠・再実行

- `verification/gkd_audio_probe.json`、`gkd_audio_playm.txt`、`gkd_audio_playm_stacks.txt`：敵なしの旧API停止
- `verification/gkd_audio_channels.txt`：同音源チャンネル別再生1,000回成功
- `verification/gkd_freeze_stress.json`：26,400開始・各編成・input・hash
- `verification/gkd_freeze_browser.json`：Desktop/Touch各27テスト
- `verification/gkd_diagnostic_package.json`：診断梱包の一致・SAVE除外
- `verification/final_chapter.json`、`web_final_chapter.json`：終盤回帰

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools/probe_gkd_audio.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_gkd_freeze.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd_diagnostic.py
```

probeは停止した自身の専用子プロセスだけを10秒で終了する。ユーザーのゲームプロセス・セーブ・インストール済みPyxelは変更しない。
