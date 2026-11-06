# 外部αテスト用 Web紹介ページ

実施日：2026-10-17。

## 1. 変更ファイル

- `dist/index.html`：正式タイトル、ストーリー、遊び方と紹介文章、意味のある見出し・ページ内目次を追加。
- `dist/site.css`：白背景、濃い本文、緑のアクセント、中央カラム、画面幅に応じたレイアウト。
- `dist/assets/title_logo.png`、`dist/assets/skill_seekers_party.png`：ユーザー提供画像のコピー。
- 検証用：`tools/verify_alpha_index.py`、`verification/alpha_index_before.json`、本報告。実行結果は`verification/alpha_index.json`、画像は`verification/screenshots/alpha_index*.png`。

ゲーム本体のPython・データ・`.pyxres`・音声・`dist/game.html`は変更していません。ゲームを再ビルドする必要のないページ改修です。

## 2. 追加した画像Assets

指定された`OneDrive/画像/game_asset`から、添付と一致する2枚をコピーしました。切り抜き、色変更、リサイズ、再圧縮、再保存は行っていません。表示サイズのみCSSで調整し、縦横比を保持しています。

| Web用ファイル | 元ファイル | 元のサイズ |
|---|---|---|
| dist/assets/title_logo.png | タイトル.png | 128×32 |
| dist/assets/skill_seekers_party.png | スキルシーカーズ!! 深淵の冒険者たち.png | 2172×724 |

コピー元・先のSHA-256が一致：

- ロゴ：`a98cdcb8757ab8031f649b0ac8f1b022ee0a6ba8378b11cee02a4a79af7d0e0b`
- パーティ：`9fb4457d734f9cab2d12c20dbdaf5b46e12dd17a84b8a76df37c3627da1cef5c`

HTMLから`assets/…`の相対パスで参照します。ページをGitHub Pagesのリポジトリ配下に公開しても、同じ相対構成で参照できます。

## 3. ページ構成

1. タイトルロゴ、αテスト版表記、プレイ位置へのリンク
2. ストーリー
3. パーティイラスト
4. GAME PLAY、既存のPLAYボタンとゲームiframe、簡易操作と保存案内
5. ゲームの説明、通常攻撃なし・使用回数・消失・ひらめき・6枠の特徴
6. 基本操作
7. 拠点の5施設、セーブの注意
8. ダンジョンメニュー
9. 戦闘コマンドとスキル入替
10. 成長、MASTEREDの攻撃威力1.2倍、収集100%、QUESTのヒント
11. ロウ・カイ・ミオ・セン・デーモンの紹介

h1/h2/h3、箇条書き、操作表、説明リスト、人物カード、余白・区切りで整理しました。目次とプレイ位置へのリンクは通常のページ内リンクで、新しいJavaScriptは追加していません。

## 4. PC向けレイアウト

中央カラムの最大幅880px、ストーリー本文最大700px。白地に濃いグレーの本文、緑の見出し・リンク。ロゴの薄い副題を読みやすくするため、ロゴ部分だけ濃い緑のCSS背景を使用しています。人物紹介は2列、デーモンは横幅全体のカードです。

## 5. スマホ向けレイアウト

560px以下では左右18pxの余白、人物紹介は1列。画像は`max-width:100%; height:auto`で縦横比を保持し、表・メニュー説明も画面幅内に収めています。320px・390pxと、768px・1280pxで横スクロールがないことを検査しています。

## 6. ゲーム埋め込みへの変更有無

ゲームiframeとPLAYボタンを紹介ページ内のGAME PLAYへ配置しました。iframeの説明用titleは正式名称へ更新しています。

`#play`、`#game`、fullscreen許可、`game.html?v=Date.now()`、クリック1回での起動、ボタン非表示、`playing`クラス、iframeへのfocusは維持。**起動スクリプトの内容は改行コードを除き変更前と完全一致**しています。既存のPC/タッチ向けiframe高さも維持しています。

`dist/game.html`を含む**66個のゲーム関連ファイルが変更前のSHA-256と一致**しています。SAVEやバーチャルパッドの入力処理も同じファイルのままです。

## 7. Virtual Pad回帰確認

**成功**。実際のタッチイベントでA/BとD-PADを操作し、6ボタンの存在・文字なし・非重複・入力解放を検査しました。タイトル選択、決定、キャンセル、NEW GAMEからHUB、探索中のBメニューと復帰まで通過。パッドを表示するCSSや入力処理は今回編集していません。結果は`alpha_index.json`に記録しています。

## 8. 画像表示確認

4つの画面幅で2枚とも読み込み成功、元の自然サイズを取得でき、表示の縦横比と画面幅内への収まりを検査しました。コピー元の画像とバイト一致しています。ロゴの濃緑の背景はCSSであり、PNG自体の変更ではありません。

## 9. Browser確認結果

Edge Chromiumの隔離プロファイルでPC表示とPixel 7タッチエミュレーションを使用。**両方成功**。画像/CSSの読み込み、ページ内リンク、見出し、横はみ出し、ゲームの起動・タイトル操作・NEW GAME・INTRO・HUB・探索・Bメニューを確認しました。HTTPエラー・JavaScript例外なし。PCのZ/X、タッチのA/B/D-PADとも正常です。

| 画面幅 | 画像2枚の表示・縦横比 | 横はみ出し | ページ内リンク |
|---|---|---|---|
| 1280px | 正常 | なし | 正常 |
| 768px | 正常 | なし | 正常 |
| 390px | 正常 | なし | 正常 |
| 320px | 正常 | なし | 正常 |

PC/スマホの上部・ゲーム表示のスクリーンショットを目視確認済みです。全体プレビューは`verification/screenshots/alpha_index_1280.png`と`alpha_index_390.png`、操作時は`alpha_index_desktop_playing.png`と`alpha_index_touch_emulation_playing.png`。最終結果の詳細は`alpha_index.json`を参照してください。

既存のWeb同梱版検証も成功。通常遭遇、B15専用区間、無音での守護者・アムリタ・最終戦再挑戦・ENDINGの進行が維持されています。実プレイヤーの保存データは使用していません。

## 10. 既知の問題・確認範囲

今回の検証で判明したページ上の不具合はありません。iOS Safari/Androidの物理端末での今回の確認は未実施です。タッチエミュレーションを実機確認済みとは扱いません。

GitHubへのpush/deployは今回行っていません。公開時は`dist/index.html`だけでなく、**`dist/site.css`と`dist/assets/`の2枚のPNGも一緒にpush**してください。既存の`dist/game.html`も公開フォルダ内に必要です。現在のGitHub Actionsは`dist`全体を配信する設定です。
