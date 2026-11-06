# 献上イベント用BGM

実施日：2026-10-17。

## 原因と変更

`start_final_story()`には音楽の切替がなく、毎フレームの`sync_scene_audio()`にも`final_story`用の指定がなかったため、直前の拠点BGMがそのまま流れていました。

`rpg/dungeon_app.py`の上記2メソッドだけを変更。献上決定時に即時同期し、会話状態では`bgm_omen`を指定します。ページ送りや描画の変更はありません。`rpg/sound.py`にはIDと新しいリソースバンクの対応を追加しました。AudioManagerの全メソッドは変更していません。

| 状況 | BGM |
|---|---|
| 献上確認画面 | 既存の拠点曲 |
| 「後で」またはBで戻る | 拠点曲を継続 |
| 「はい」決定、そのフレームから | 献上――玉座の影（bgm_omen） |
| 最終イベントの会話全ページ | 同曲を継続、ページ送りで再スタートしない |
| ロードオブエリシオン戦開始 | 既存のbgm_boss |
| アムリタでバリアを解除 | 既存のbgm_final |
| 最終戦の再挑戦 | 既存のbgm_boss |

## 曲と編集場所

オリジナル曲「献上――玉座の影」。Dを中心とした低音ドローン、半音の緊張、増四度を含む疎らな旋律で、拠点から不穏な会話への変化を付けています。4/4拍子、60 BPM、8小節・32秒ループ。既存の拠点・ボス・最終戦の曲は変更していません。

| 項目 | 場所 |
|---|---|
| Pyxelリソース | assets/omen_music.pyxres |
| 編集用起動 | edit_event_music.cmd |
| Music | 0 |
| 旋律：チャンネル1 | Sound 0 → 1 |
| 低音：チャンネル2 | Sound 2 → 3 |
| 伴奏：チャンネル3 | Sound 4 → 5 |
| チャンネル0 | SE用に未使用 |
| 初期譜面 | tools/art/omen_music.json |
| 試聴WAV | verification/audio/omen/offering_omen.wav（gitignore対象） |

初回生成ツールは`tools/create_omen_music.py`。既存のEditor編集を上書きしないよう、リソースがすでに存在する場合は停止します。今後の曲編集はPyxel Editorで行ってください。

## 保護対象

作業前に`tests/fixtures/omen_music_before.json`へ65ファイルのハッシュとDungeonApp/AudioManagerのメソッド別ハッシュを保存しました。変更した2ファイルを除く**63ファイルが完全一致**しています。

ユーザーが今回の作業前にEditorで更新した`game.pyxres`も、SHA-256 `5ca735f3205452e5912b60b3b69721c8df1eedda7010227fd77d383fd1b79d85`のままです。既存画像・ロゴ・マップ・パレット・全BGM/SE・62技・敵・QUEST・SAVE・アムリタ/RARE/LEGEND演出を変更していません。DungeonAppは上記2メソッド以外、AudioManagerはすべてのメソッドが作業前と一致しました。

過去フェーズの保護テストは、今回の追加BGMとユーザーによるEditor更新を扱えるように調整しています。全体リソースを旧画像へ戻さず、新しい作業前スナップショットで既存資産全体を保護。過去の音源データ比較と、現在のAudioManagerメソッド不変検査も維持しました。

## 検証

- 全体：**589/589成功**（214.745秒）。`verification/omen_music_all_tests.txt`。
- 献上BGM専用：8項目成功。即時切替、会話中の継続、「後で」/B、再帰還時の献上、戦闘/バリア解除/再挑戦の既存曲、ミュート/再生例外時の進行、共通SE、資産・ソースの変更範囲を検証。
- PCブラウザ・タッチエミュレーション × AudioContext running/suspendedの4条件で各8項目、**32/32成功**。さらに実際のキーボード/HTML D-PAD・A・B入力で、「後で」→再確認→献上→会話全ページ→バリア付き最終戦まで通過。pageerrorなし。
- ブラウザの音声停止ケースでは、AudioContextをsuspendし、resumeが失敗する状態にしてvisibilitychange/blur/focus/pageshowを送っています。それでも会話と戦闘が進行しました。
- ネイティブ再生は従来どおりチャンネル別`pyxel.play()`。`playm()`を再導入していません。Webでは従来のMusic APIを使用。
- 音楽の終了を待つ処理、音声待ちフラグ、新たな進行待ちは追加していません。
- WAVは32.0秒、無音でないことを確認。ピーク2710、クリップ率0。3つの音楽チャンネルの長さもすべて32秒で一致。
- Web同梱版の通常遭遇、B15専用区間、無音での守護者・アムリタ・最終戦再挑戦・ENDINGテストも成功。

ブラウザ記録：`omen_music_browser_running.json`、`omen_music_browser_unavailable.json`。音声記録：`omen_music.json`。

**iOS Safari、画面ロック、Pixel2の実機と実機スピーカーでの聴感は今回未確認**です。タッチエミュレーションや波形解析を実機確認とは扱っていません。

## 配布物

- `dist/game.html`更新済み。
- `verification/packages/skill_seekers_gkd.zip`更新済み（64エントリ）。
- `verification/packages/skill_seekers_gkd_diagnostic.zip`更新済み（67エントリ）。
- 共通ゲームファイル63個がWeb/通常ZIP/診断ZIP/作業ツリーで一致。Python 3.11構文検査成功、プレイヤーSAVEは同梱していません。詳細は`omen_music_packages.json`。

更新時は既存の`save/`を削除せず、ゲームファイルを上書き・結合してください。GitHubへのpushは行っていません。
