# 竜48×48・スタッフロール曲の調整

実施日：2026-11-07（日本時間）

## 変更内容

- エンシェントドラゴンの戦闘絵の参照範囲を、`assets/postgame.pyxres` Image 0 **(16,0)から48×48**へ変更しました。
- ユーザーが描いた画像は変更していません。元の32×32枠の外側にあった308個の不透明ピクセルも表示対象になりました。探索シンボルはImage 0 (0,0)・8×8のままです。
- 通常の戦闘画面では左上(22,12)へ表示し、右端70・下端60に収まります。48×48全体がタイトル・味方欄・背景帯に重なりません。
- 竜の状態異常アイコンは画像の左へ移しました。撃破時の沈み込みも維持し、背景帯の開始Y=64でクリップします。他の敵の配置・画像は変更していません。
- スタッフロール曲を「Beyond the Deep - A New Horizon」へ変更しました。75 BPM、16小節・約52秒、D minorからD major/add9へ展開します。低音の長い音価、控えめな和声、ゆっくり上昇する旋律で、荘厳さと新しい旅への余韻を付けています。
- チャンネル1＝旋律、2＝和声、3＝低音、0＝従来のSE用です。終止後に休符を置き、約51.6秒のスタッフロール終了時は休符区間になります。音声終了をゲームの進行条件にはしていません。

## 編集場所

`edit_postgame.cmd`で`assets/postgame.pyxres`を開きます。竜の画像は上記領域、曲は**Music 0 / Sound 0～29・32～49**です。

譜面は`tools/art/credits_journey_music.json`。`python tools/rework_credits_music.py --render`でMusic 0と専用Soundだけを再作成できます。画像・Tilemap・他Music・共通SEのブロックをバイト単位で保持するインポーターです。Editorで曲を直接編集した後に再インポートすると、曲はJSONの譜面へ戻ります。

## 変更ファイル

| ファイル | 変更 |
|---|---|
| `data/postgame.json` | `battle_sprite`を`[16,0,48,48]`へ変更 |
| `rpg/postgame.py` | 画像サイズに基づく表示範囲・沈み込み |
| `rpg/app.py` | 竜のクリップ範囲・状態異常アイコン位置 |
| `assets/postgame.pyxres` | 専用Music 0と専用Soundのみ変更 |
| `tools/art/credits_journey_music.json` | 新しい編集用譜面 |
| `tools/rework_credits_music.py` | 画像等を保護した譜面インポート・WAV出力 |
| `README.md` | 48×48と現在の曲・編集方法を記載 |
| `dist/game.html`、GKD通常／診断ZIP | 再ビルド |

ユーザー編集済みの竜HP9999、デーモン後の文章、エレベーター文章、その他のデータは維持しています。セーブ・スキル・敵性能・マップ・既存BGM／SEには変更していません。

## 検証結果

- `tests.test_phase7`の12件と`tests.test_audio_pass.AudioManagerTests`の10件、計**22件成功**。
- 実Pyxelで48×48の全2304ピクセルを表示できること、状態異常アイコンが外側にあること、撃破アニメーション中も背景帯を保護することを確認しました。
- `postgame.pyxres`の画像・Tilemap・専用曲以外のSound／Musicは元のブロックと完全一致。変更対象外の69ファイルも元のハッシュと一致しています。実セーブも保持しています。
- 新曲を52秒のWAVへ書き出し、波形のクリップ率0、音声あり、3声の長さが一致することを確認しました。実機スピーカーでの聴感は未確認です。
- Webに埋め込まれたコード・リソースで、入力・パレット・通常遭遇・守護者・アムリタ障壁・再挑戦・ENDINGの既存スモーク検証が成功しました。
- Web／GKD通常／GKD診断のゲーム用73ファイルが最新ソースと一致し、Python 3.11構文・ZIP整合性・セーブ非同梱を確認しました。
- 今回は全757テストの再実行やiOS／GKD物理端末での確認は行っていません。Git commit／pushもしていません。

## 確認用ファイル

- [48×48の戦闘画面](screenshots/dragon_48x48.png)
- [新曲の試聴WAV](audio/credits_journey.wav)
- [画像・保護検証](dragon_48_journey.json)
- [音楽・波形検証](credits_journey_audio.json)
- [配布物検証](dragon_48_journey_packages.json)
- [関連22テストのログ](credits_journey_tests.txt)
- [ビルド・Web検証ログ](dragon_48_journey_build.txt)

現在の配布物は`dist/game.html`、`verification/packages/skill_seekers_gkd.zip`、`verification/packages/skill_seekers_gkd_diagnostic.zip`です。
