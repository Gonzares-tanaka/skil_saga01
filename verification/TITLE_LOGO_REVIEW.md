# TITLE LOGO IMAGE IMPLEMENTATION 検証報告

実施日：2026-10-16。ユーザーが作成したロゴを参照する描画変更です。ロゴを含むリソースへの書き込みは行っていません。

## 1. 変更ファイル一覧

- 製品コード：`rpg/dungeon_app.py`。`draw_title_logo()`の本体と、不要になったタイトル文字列のimportだけを変更。
- 説明：`README.md`、本報告。
- ロゴ検証：`tests/test_title_logo.py`、`tests/fixtures/title_logo_before.json`、`tools/snapshot_title_logo.py`、`tools/verify_title_logo.py`。
- ブラウザ検証：`tools/browser_title_logo_case.py`、`tools/verify_browser_statuses.py`の任意指定`--title-menu`。
- 過去の資産保護テストへの対応：`tests/balance_preservation.py`、`tests/test_audio_pass02.py`、`tests/test_audio_pass03.py`。
- 配布物：`dist/game.html`、`verification/packages/skill_seekers_gkd.zip`、`verification/packages/skill_seekers_gkd_diagnostic.zip`。
- 検証記録：`title_logo.json`、`title_logo_all_tests.txt`、`title_logo_browser_running.json`、`title_logo_browser_unavailable.json`、`title_logo_packages.json`（本報告と同じフォルダ）。スクリーンショットは`verification/screenshots/title_logo*.png`（gitignore対象）。

ユーザーのEditor保存後のリソースは、過去の音源フェーズ開始時点の画像やTOML書式とは異なります。古いスナップショットへ画像を戻すことはせず、今回の作業前のファイル全体をハッシュで保護しました。過去の音源テストでは許可スロット以外のSound/Musicデータを比較し、今回のテストでリソース全バイトの不変を別途確認しています。既存の音源変更スロットを確認するassertは維持しています。

## 2. 削除した旧TITLE TEXT描画箇所

`DungeonApp.draw_title_logo()`内の`Skill Seekers!!`とサブタイトルのテキスト描画を除去し、`pyxel.blt()`1回へ置換しました。TITLEとセーブなし案内画面の両方で旧テキストが描画されないことを確認。ウィンドウ名などのゲーム名メタデータは維持しています。

## 3. ロゴ参照Image Bank

**Image Bank 1**。

## 4. Source座標

**u=0、v=192**。

## 5. Source Size

**128×32ピクセル**。別領域への移動・複製保存は行っていません。

## 6. 画面上の描画座標

**(16,23)**。X座標は`(pyxel.width - 128) // 2`で計算します。160×120画面で、左右の余白はいずれも16ピクセルです。

## 7. 透明色 / colkey設定

**colkey指定なし（None）**。元画像の外周はすべて色0で、画面背景と同じため、そのまま矩形全体を描画します。色3/20/24のロゴ部分もそのまま使用します。パレットは変更していません。

## 8. ロゴ1:1表示確認

幅128・高さ32を指定し、scale/rotateを指定していません。実際のフレームバッファの**全4,096ピクセル**が元のImage Bank 1の対応ピクセルと一致しました。ブラウザがゲーム画面全体を表示用に拡大する既存動作はそのままです。

## 9. MENUとの重なりなし確認

ロゴ範囲はx=16～143、y=23～54。既存の横線y=21/57の間に収まります。メニュー選択背景はy=68からで、文字位置やカーソル位置は変更していません。ネイティブ・PCブラウザ・タッチエミュレーションの画像を目視確認しました。

## 10. TITLE操作回帰結果

カーソル上下、A決定、はじめから、保存ありのつづきから、保存なし案内とBで戻る動作を確認。合成セーブのBANKED TRZ=17がCONTINUEで復元され、NEW GAMEでは既存初期化が動きます。実プレイヤーの保存データは検証に使用していません。

## 11. TITLE BGM変更なし確認

`bgm_title`の音源、Music/Sound割り当て、Audio Manager、再生APIを変更していません。タイトル状態で`bgm_title`が選択されること、関連する音声テストの再生・継続条件を確認しています。実機スピーカーでの聴感確認は未実施です。

## 12. OPENING BGM遷移変更なし確認

TITLE→NEW GAME→INTRO全ページで`bgm_title`、最初の城下町表示（HUB PREVIEW）から`bgm_hub`という既存動作を維持。PC/タッチの実ブラウザ入力でも確認しました。HUB PREVIEW終了後の入力解放待ちも既存のままです。

## 13. .pyxresを変更していない確認

作業前の`game.pyxres`全体SHA-256：

`bf80c4ccfc5411d81d2fc82b5a0fa0c94da712efb457b385b1429f4da11eec7c`

作業後も一致。ロゴ領域のピクセルSHA-256は`f8ed83065ca50db4acd871dd62afe80ce2c54d8becb232d9e9cf476828640b2f`で一致しています。

全64個の保護対象ファイル（リソース・パレット・データ・他ゲームコード・ランチャー等）が作業前と一致。`DungeonApp`も`draw_title_logo()`以外の**67メソッド**のソースが一致しています。画像・音源・マップ、62技、敵/ボス、QUEST、SAVE、戦闘、RARE/LEGEND、アムリタ演出を変更していません。

## 14. 自動Test結果

- ロゴ専用：**6/6成功**。実描画全ピクセル、旧テキスト非表示、座標、メニュー/CONTINUE、開始BGM、変更範囲を確認。
- 音声3フェーズとロゴの集中テスト：**54/54成功**。
- 全体回帰テスト：**581/581成功**（160.888秒）。最終実行結果は`title_logo_all_tests.txt`に記録。
- Web同梱版の進行テスト：通常遭遇、B15専用区間、守護者、無音、アムリタ、最終戦再挑戦、ENDINGまで成功。
- ブラウザ：PC/タッチ×音声running/suspendedの4条件で各6件、**24/24成功**。さらに実入力でNEW GAME/CONTINUEと開始フローを確認。

最初の全体テスト実行では、作業ディレクトリを変更する既存テストによって相対的なモジュール検索パスが使えなくなり、検証モジュールのimportエラーが発生しました。プロジェクトの絶対パスを検索パスに追加して再実行しています。ゲームコードの不具合として変更を加えてはいません。

## 15. PC Browser確認

再生成した`dist/game.html`をローカルHTTPで配信し、Edge Chromium / Pyodideで確認。キーボード上下・Z・X、タイトル/保存なし案内/CONTINUE/INTRO/HUBを通過。JavaScriptのpageerrorなし。通常音声と、AudioContextをsuspendedにしてresumeを意図的に失敗させた状態の両方で成功しています。

## 16. Touch Browser確認

Edge ChromiumのPixel 7タッチエミュレーションで、HTML D-PAD・A・Bへ実際のタッチイベントを送って同じフローを確認。通常音声・音声使用不可の両方で成功、pageerrorなし。画像も確認済みです。

**iOS Safari実機、スマートフォン画面ロック、GKD Pixel2実機は今回未確認**です。タッチエミュレーション結果を実機確認済みとは扱っていません。今回の変更で判明した製品上の不具合はありませんが、この実機確認は残ります。

## 17. Web版更新結果

`python tools/build_web.py`で`dist/game.html`を更新。埋め込まれたゲームファイル62個が作業ツリーとバイト一致し、ユーザーロゴを含むリソースも一致。スキル数62、SAVE version 1を維持し、プレイヤーセーブは含みません。GitHubへのpush/deployは今回行っていません。

## 18. GKD Pixel2 ZIP更新結果

`verification/packages/skill_seekers_gkd.zip`更新済み（63エントリ）。診断版`skill_seekers_gkd_diagnostic.zip`も更新済み（66エントリ）。両方の共通ゲームファイル62個がWeb版・作業ツリーと一致し、Python 3.11構文互換検査も成功しました。保存フォルダは含めていません。更新時も既存`save/`は削除しないでください。

## 必須15ケースの対応

| CASE | 確認内容 | 結果 |
|---|---|---|
| 1 | ゲーム起動 | ネイティブ検証起動・実Web起動で成功 |
| 2 | TITLE表示 | ネイティブ/PC/タッチで確認 |
| 3 | 旧TEXT非表示 | TITLEと保存なし案内の描画呼び出しを検査 |
| 4 | Bank1 (0,192)ロゴ | 全4,096ピクセル一致 |
| 5 | 1:1サイズ | 幅128・高さ32、scale指定なし |
| 6 | 横中央 | (160−128)//2=16 |
| 7 | メニュー非重複 | 座標検査と実画像確認 |
| 8 | はじめから | 実入力でINTRO→HUBまで通過 |
| 9 | つづきから | 合成セーブを実ブラウザlocalStorageから復元 |
| 10 | カーソル | 実入力で上下選択確認 |
| 11 | A決定 | 実入力でNEW GAME/CONTINUE/INTRO送り確認 |
| 12 | TITLE BGM | 選択状態・既存音源/再生動作を確認 |
| 13 | OPENING中TITLE曲継続 | INTRO全ページで確認 |
| 14 | 城下町からHUB曲 | HUB PREVIEWへ入った時点で確認 |
| 15 | Touch Browserメニュー | D-PAD/A/Bタッチイベントで確認（実機ではない） |
