# AUDIO PASS 03 — OPENING BGM / AREA1 REWORK

実施日：2026-10-16。検証環境：PC Python 3.14.7 / Pyxel 2.9.9、実Pyxel Web/Pyodideを使ったEdge Chromium（PC表示・タッチエミュレーション）。実セーブは読み書きしていない。

本体の変更は`rpg/dungeon_app.py`の開始時BGMタイミングと、`game.pyxres`のAREA1専用8 Soundのみ。承認済みTITLE、HUB、AREA2/3、通常戦闘、ボス、最終戦、ファンファーレ、全SEを保護した。Audio Managerの`rpg/sound.py`はファイル全体のSHA-256が変更前と一致。

## 指定27項目の完了報告

1. **変更File一覧**：本体は`rpg/dungeon_app.py`、`game.pyxres`。作曲原稿`tools/art/audio_pass_03.json`、限定インポーター`tools/rework_area1_music03.py`、監査/スコアの共通ツール`tools/audio_pass02_resource.py`・`tools/rework_title_area1_music.py`、今回のsnapshot/音源/OPENING/ブラウザ検証ツールを追加・更新。`tests/test_audio_pass03.py`・変更前fixtureを追加し、前工程のテストは今回の開始曲・AREA1テンポへ期待値を更新した。README、検証記録、`dist/game.html`、Pixel2通常/診断ZIPも更新。

2. **旧Trigger**：`start_new_game()`が初期化のため`enter_camp()`を呼ぶと、その末尾でHUB曲を開始していた。加えて`title_fade`と`intro`がHUB曲対象に含まれ、通常の音声同期でもHUB曲へ切り替わっていた。両方を直さないと一瞬のHUB再生またはTITLEの再スタートが残る。

3. **新Trigger**：`title_fade`・`intro`はTITLE曲の対象とし、初めて`hub_preview`へ遷移した直後に音声を同期する。これが城下町を描画する最初のフレーム。拠点初期化には省略可能な`play_music`引数だけを追加し、開始演出の準備時は音楽を再生しない。通常帰還時の既定値は従来どおりTrue。TITLE起動前の未表示HUBも再生しない。

4. **NEW GAME後のTITLE継続**：成功。初期化途中もHUB曲へ切り替わらない。正常再生中のTITLEは停止・再スタートしない。NEW GAMEから通常HUBまでの曲開始APIは、実際のHUB表示時の1回だけ。

5. **Story中のTITLE継続**：成功。INTRO全4ページの先頭・ページ送り・最終ページで`bgm_title`。ページ番号や文章・入力処理は変更なし。

6. **城下町表示時のHUB切替**：成功。`hub_preview`に入ったフレームでMusic 1を開始。既存90フレームのWAIT、`hub_intro`、通常`camp`でもHUB曲を継続し、重複再生しない。待機時間・入力ロック・初回フラグは変更なし。

7. **LOAD時のHUB BGM**：成功。合成SAVEをTITLEのCONTINUE経由で適用すると`camp`＋`bgm_hub`。全SaveData一致、所持TRZも保存値を保持し、開始演出を再生しない。通常帰還・全滅帰還もHUB曲。

8. **TITLE曲データ不変**：Music 0、Sound 0～6/57の全データとTOML内の各ブロックの生バイトが、今回開始時の`audio_pass03_before.json`と一致。承認済みの曲を再生成していない。

9. **AREA1変更内容**：G majorの明るいスコアから、D minor＋属和音A majorのオリジナル曲「深淵へ踏み出す者たち」へ変更。下降する低音、短いモチーフ、八分音符の刻みとノイズ打楽器を使い、暗さと前進する力を持たせた。1周16小節。コードは主部Dm–C–B♭–A、展開部Gm–B♭–C–A。

10. **Music番号**：`game.pyxres` **Music 2**、Audio ID `bgm_area1`。ID/番号対応は不変。Music 2のパターン並びも既存のまま、参照先Soundだけを作り直した。

11. **使用Sound番号**：**14/15/16/17**＝主旋律の4節、**18/19**＝ベース2節、**20/58**＝伴奏＋リズム2節。全てAREA1専用。チャンネル0は空け、BGMは1/2/3を使用。ほかのMusicからは今回の8 Soundを参照していない。

12. **Tempo**：Speed **29**。1ステップを八分音符とするため、四分音符BPMは`3600 / 29`＝約**124.14**。変更前AREA1はSpeed 30・120 BPM。HUBのSpeed 34より速い刻みで、戦闘のような激しい連続フレーズにはしていない。

13. **Loop長**：約**30.933秒**。32ステップ×4パターン×29/120秒、3チャンネルで等長。ネイティブで末尾直前からループ再生し、全3チャンネルが停止せず先頭へ回ることも検証した。2周WAVも生成。

14. **曲調の変更点**：長調の軽いアルペジオ中心から、短調の明確な旋律と拍のある伴奏へ。低域を下げつつ、ベースが旋律を埋もれさせないよう音量を調整。主旋律RMS 666.49、ベース537.90、伴奏/リズム477.49（Pyxel書き出し）。合奏のクリッピング0%。これは音楽的印象を自動判定した結果ではなく、作曲設計と信号の検査結果。

15. **HUBとの差別化**：HUB曲自体は不変。AREA1は短調、低いベース、はっきりしたリズム、少し速い124 BPMで、町の安心感からダンジョンへ挑む方向へ変更した。

16. **AREA2との差別化**：AREA2曲自体は不変。AREA1は歌える主旋律と規則的な拍・和声で進み、恐怖だけの環境音や不協和音中心にはしていない。危険は感じさせつつ序盤の冒険曲を意図した。

17. **AREA3との差別化**：AREA3曲自体は不変。AREA1は3声・短い主題・抑えた展開で、終盤の攻め込む勢いや決戦的な密度を先取りしない設計。曲調の最終評価は実機の聴感確認が必要。

18. **その他BGM不変**：TITLE/HUB/AREA2/AREA3/BOSS/FINALのMusic/Soundブロックが完全一致。`assets/battle_music.pyxres`はファイル全体が一致し、通常戦闘・勝利ファンファーレ・戦闘用SEも保持。Music配列は0～7の全てが今回開始時と同一。

19. **全SE不変**：階段50、宝51、罠52、泉53、落とし穴54、QUEST55、攻撃60、技61、宝箱62、MASTERED63、RUN30、敵撃破31、突入59を含め、AREA1専用8 Sound以外は全て不変。別バンクのSEもファイル単位で保護。

20. **se_stairs保護**：Sound **50**の生バイトまで一致。ユーザー版はNotes `[33,-1,-1,33,-1,-1,33]`、Tones `[3,3,3,3]`、Volumes `[7,7,7,7]`、Effects `[]`、Speed **7**。各曲へバンク切替後も同じ音データで再生する。再保存による書式の変更も行っていない。

21. **native playm未使用**：Audio ManagerはSHA一致。既存のMusic配列をコピーしてチャンネル別`pyxel.play()`へ渡す方式を維持。ネイティブテストでは`playm()`呼出を禁止し、正常再生・階段SE・戦闘開始を確認。Web版の既存playm経路はそのまま。

22. **自動Test結果**：全体 **575/575成功**。音量調整後の専用20件も成功。通常1000＋ボス7種各100＝**1700回**の実描画戦闘開始とD-PAD/A/B操作も成功。守護者連戦・デーモン2行動・アムリタ後のFinal曲・音声障害時の進行も回帰確認。Skill62、敵/ボス数値、SAVE、QUEST、毒、マヒ、画像マップなど63保護ファイルはSHA-256一致。アプリのソース差分は開始曲タイミングに関する5メソッドだけ。

23. **PC Browser**：実Pyxel Web/PyodideをEdge Chromiumの隔離プロファイルで起動。AudioContext runningと強制suspended＋resume失敗の両条件で**10/10成功**、JavaScript例外0、実キーボード入力も成功。visibilitychange/blur/focus/pageshowの後も進行。

24. **Touch Browser**：同じ2条件で**10/10成功**。HTML D-PAD/A/Bへ実際のタッチpointer入力を送って選択・決定・戻るを確認。物理iOS Safariや画面ロックそのものの検証ではない。

25. **Web版更新**：`dist/game.html`を再生成。埋込み版の通常遭遇、階段、守護者、アムリタ、バリア、最終戦再挑戦、ENDINGを確認。全ゲーム本体62ファイルがローカルソースと一致。既存のWeb Audio復帰JSとタッチUIは変更なし。

26. **GKD Pixel2 ZIP更新**：`verification/packages/skill_seekers_gkd.zip`（63 entry）と別の診断ZIP（66 entry）を更新。Web/通常/診断でゲーム本体62ファイルが一致し、Python3.11構文を検証。診断ツール・設定・ランチャーは保持し、SAVEはZIPに含めない。今回の更新でも本体の既存`save/`を削除しないこと。

27. **既知の問題・未確認**：検証範囲内で進行不能は未検出。物理iOS Safariのinterrupted状態/画面ロック、GKD plumOS/ARM/SDLと小型スピーカーでの音・聴感は未確認。曲の「勇ましさ」「暗さ」の最終評価は試聴と実機プレイで確認してほしい。音声が使用不能でも進行を止めない既存仕様は維持している。

## 指定18ケース

| CASE | 確認内容 | 結果 |
|---|---|---|
| 1 | TITLE表示でTITLE曲 | 成功 |
| 2 | NEW GAME後もTITLE継続・HUBの一瞬の割込みなし | 成功 |
| 3 | Story最初のページ | TITLE継続 |
| 4 | 全4ページの送り | TITLE継続・曲の再スタートなし |
| 5 | 最終ページ・終了直前 | TITLE継続 |
| 6 | 城下町の最初の描画フレーム | HUB_PREVIEWでHUB曲に1回だけ切替 |
| 7 | HUB導入WAIT | HUB曲継続・操作不可も維持 |
| 8 | 通常HUB操作開始 | HUB曲継続 |
| 9 | HUBのSAVEをLOAD | HUB曲・開始演出再表示なし・SaveData一致 |
| 10 | B1進入 | 新AREA1曲 |
| 11 | HUBの安心感との差 | 短調・低音・拍・速度に反映。実機聴感は未確認 |
| 12 | AREA2ほど不気味にしない | 旋律/規則的な拍/和声を残す設計。聴感評価は別途 |
| 13 | AREA3ほど終盤的にしない | 控えた密度と展開で設計。聴感評価は別途 |
| 14 | B1→B2 | 同一曲の開始API呼出なし、階段SEは従来のまま |
| 15 | 通常Battle開始 | 変更していないbgm_battle |
| 16 | Victory後 | 新AREA1へ復帰 |
| 17 | RUN後 | 実RUN成功処理を経て新AREA1へ復帰 |
| 18 | B5→B6 | 変更していないAREA2へ切替 |

## 編集場所・証拠

`edit.cmd`から**game.pyxres → Music 2**。主旋律はSound 14～17、ベース18/19、伴奏20/58。TITLEはMusic 0 / Sound 0～6・57、階段はSound 50であり、今回の編集対象外。

- [新AREA1試聴用WAV](audio/pass03/bgm_area1.wav)（gitignore対象。ゲームはこのWAVを使用せず、pyxresのSound/Musicで再生する）
- `audio_pass03.json`：WAV/ステム実測、63保護ファイル、階段データ。
- `audio_pass03_opening.json`：実入力の状態・ページ・BGM時系列とアプリソース差分。
- `audio_pass03_all_tests.txt`：575件のテスト結果。
- `audio_pass03_browser_running.json` / `audio_pass03_browser_unavailable.json`：PC/Touch×音声2条件、計40実行。
- `audio_pass03_packages.json`：Web/通常/診断の全内容一致とPython3.11構文。
- `enemy_balance_runtime.json`：1700回の開始、487,150回の文字範囲検査、無音時のボス行動。
- `tests/fixtures/audio_pass03_before.json`：今回の実際の開始時データ。TITLE・全SEを含む範囲を固定。

```text
python -B -X utf8 -m unittest discover -s tests
python -B -X utf8 tools/verify_opening_audio03.py
python -B -X utf8 tools/verify_audio_pass03.py
python -B -X utf8 tools/verify_enemy_balance_runtime.py
```

AREA1をPyxel Editorで手修正した後は、旧スコアの再インポートをせず、そのままWeb/ZIPを再ビルドする。インポーターは未知の手修正を検出すると上書きを拒否する。全ての確認に合成状態のみを使い、実セーブを編集・削除していない。
