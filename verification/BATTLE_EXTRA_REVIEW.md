# Battle Presentation追加改善 検証報告

2026-10-10。PC Python 3.14.7 / Pyxel 2.9.9。対象はRUN成功の演出、敵撃破SE、簡易背景、RESULTの表示フローです。

## 指定30項目

1. **RUN実装場所**：`rpg/app.py`のRUN選択成功分岐、`update_battle_visual`。`rpg/battle_presentation.py`の`start_run / advance / actor_offset`が表示を担当。
2. **反転方法**：Pyxelの`blt`へ幅-16を渡し、既存の16×16画像を左右反転。新たな4人分のSpriteは不要。KO画像も移動します。
3. **移動量**：右へ16px。座標の累積変更ではなく表示時のオフセットです。次戦の通常位置を壊しません。
4. **時間**：15フレーム/30FPS＝0.5秒。単調時計でも0.5秒を上限とし、復帰後は古い演出を持ち越しません。入力をロックし、終了後にESCAPEの既存精算を1回行って探索へ直接戻ります。
5. **RUN SE位置**：`assets/battle_music.pyxres`のSound 30、定数`SOUND_RUN_SUCCESS`。3つの短いノイズ足音。チャンネル0。Editor変更後の起動時にも内容を維持します。
6. **撃破SE実装場所**：`rpg/app.py`の`apply_visual_action`。再生関数は`rpg/sound.py`の`play_cue('enemy_defeat')`。
7. **撃破SE位置**：同じ資材のSound 31、`SOUND_ENEMY_DEFEAT`。下降する短いノイズと減衰音量で崩れる感触を意図しています。
8. **タイミング**：実際のHP0判定後、enemy_death開始と同じ更新で1回。点滅更新では再生しません。同時撃破は1つのSEへまとめます。ロードオブエリシオンの専用終了処理を優先し、このSEは鳴らしません。
9. **AREA1背景**：`game.pyxres` Image Bank 2、壁(0,160)32×32、床(0,192)32×16。
10. **AREA2背景**：同Bank、壁(64,160)32×32、床(64,192)32×16。
11. **AREA3背景**：同Bank、壁(128,160)32×32、床(128,192)32×16。
12. **描画方法**：`draw_battle_background`で壁/床パーツを反復blt。壁Y11～66、床Y67～79、X0～95だけにクリップ。敵・味方・エフェクト・文字はその後に描画し、新しい色は増やしていません。起動時の線/Pixel Arrayによる背景生成はありません。
13. **切替**：`battle_area(floor)`で0始まりfloorを1～3へ分類。`begin_encounter`で取得し、`BATTLE_BACKGROUNDS`の一箇所の定義を参照。B5/B10/B15にも同じ判定を使います。
14. **旧床色**：通常戦の単色rectと点模様を背景パーツの描画に置換。通常画面の床主色取得は不要になりました。ダンジョン外の最終戦では旧色0と点模様を維持。旧床色取得関数は以前の検証用に残していますが通常戦描画では使用しません。
15. **成長再表示の原因**：`update_replacement`が最後の入れ替え後に`set_result_pages(session.results)`を呼び、`result_page=0`、`state='result'`へ戻していました。ここが全成長ページを再表示していました。
16. **修正**：結果のページを成長→残り結果の順に整理し、最後の入れ替え確定後は既存`finish_results()`へ直接進めます。再構築/ページ番号リセットはしません。複数人の入れ替えは全員の決定後に終了。
17. **二重計算の有無**：ありませんでした。入れ替え後は計算済みの`session.results`を表示し直していただけです。`Session.settle`には以前から確定済み結果を返すガードがあります。
18. **加算1回**：追加テストで入れ替え前後のHP/maxHP/STR/AGI/INT一致とsettle呼び出し1回を確認。表示順変更は計算関数・乱数に触れません。
19. **戻り先**：通常/討伐戦は探索（討伐成功時は既存の完了会話）、B5/B10はボス後会話、守護者は連戦会話、最終戦はENDINGまたは再挑戦へ。DEBUG、拠点再習得、探索閃きの既存の戻り先は優先して維持。
20. **RUN率不変**：`battle.py`、RUN設定のハッシュが作業前と一致。AGI補正・min/max・ボス禁止・失敗時敵行動を変更していません。
21. **敵能力不変**：敵/フロアの定義・AIが一致。B15の通常ランダム遭遇なしも維持。
22. **SKILL不変**：技能データ、Uses、MASTERED、DISCOVERED、LEGEND、ITEM、GUARD等のルールが一致。
23. **成長率不変**：growth.py、設定、成長/閃き計算を変更していません。成長と閃きの計算は戦闘確定時にまとめて一度だけ行い、表示を成長→閃きの順へ変えています。
24. **audio非依存**：RUNは0.5秒/15フレーム、撃破は従来の0.6秒/18フレーム。`play_pos`やSE終了を待ちません。音声再生の例外は捕捉してゲームを継続。勝利演出も固定タイマーです。
25. **PC Python**：追加14件を含む全264件PASS。旧テストの「全bltが16×16」を「敵/味方Spriteが16×16」に修正し、32×32背景を誤検出しないようにしました。画面内文字323回、背景3種・成長・KO等22画面を実Pyxelで確認。
26. **PC Browser**：実Edge/Pyodide、独立プロファイルでキー操作による無音戦闘、RUN、入れ替え→直接帰還、SAVE→リロード→CONTINUEを検証。記録は`battle_presentation_browser.json`。
27. **Smartphone Browser**：EdgeのPixel 7タッチエミュレーションで同じ操作を検証。実際のiOS SafariやPixel 2は今回は利用できず未確認です。
28. **audio freeze回帰**：実ブラウザのAudioContextをsuspendし、resumeを意図的に失敗させた状態で新しいRUN/撃破/RESULTを確認。全Pyxel音声API故障時の100回連続結果遷移とMASTERED/閃き/入れ替えもPASS。visibility/pagehide/pageshow/blur/focusイベントを検証。実機の自動ロックとiOS固有のinterrupted状態は未確認。
29. **SAVE回帰**：SaveData/保存実装はハッシュ一致。一時的なrun_success/背景/成長表示stateを追加していません。PCの別プロセス再開、実Web localStorageリロード、最終章の5種類の敗北/再挑戦、既存のクエスト記録が正常。配布物にプレイヤーSAVEは含めません。
30. **既知の問題**：背景とSEは調整可能な仮素材です。実機の音の印象・演出テンポはプレイテストでの確認が必要。iOS実機の画面ロックとGKD実機操作は未確認。自動検証範囲では進行不能・既存数値変化・データ破損はありません。

## 必須41ケース

| CASE | 結果・確認方法 |
|---|---|
| 1～5 | PASS：実UIでRUN成功、4人の幅-16、右移動、SE1回、15更新後の直接帰還。全音声API故障と壁時計上限でも帰還。 |
| 6～7 | PASS：失敗時の反転/移動/成功SEなし、敵行動継続。計算と設定は変更前一致。 |
| 8～13 | PASS：撃破SE開始時1回、同時複数撃破1回、各敵の消滅、無音で次へ。ボス後会話も正常。 |
| 14～19 | PASS：全15階判定、B5/B10/B15の背景、3エリアの実画面。 |
| 20～22 | PASS：既存4色内・前景後描画・範囲クリップ。背景のpixel編集が反復表示へ反映。既存領域は前後比較で一致。 |
| 23～24 | PASS：ひらめきなし/空き枠自動習得も通常結果終了。成長ページが閃き表示より先。 |
| 25～27 | PASS：満杯時の取得/拒否、複数キャラクター決定後とも成長へ戻らず直接終了。 |
| 28～29 | PASS：settle1回、入れ替え前後の能力不変、キャラクター別ページ維持。 |
| 30～36 | PASS：通常/討伐/B5/B10/守護者/デーモン/エリシオン。Web埋め込みデータでB10→ENDING、5種の敗北/再挑戦。 |
| 37～38 | PASS：実Pyxel headlessと実Edge/Pyodide。 |
| 39 | タッチエミュレーションPASS。スマートフォン実機は未確認。 |
| 40 | AudioContext suspendとresume失敗、復帰イベントの模擬検証PASS。実機ロックは未確認。 |
| 41 | PASS：既存SAVE schema、別プロセスと実ブラウザリロード/CONTINUE。 |

## 保全・再実行・配布

`verification/backups/battle_presentation_extra/baseline.json`と更新前資産で比較しました。`verification/battle_extra_preservation.json`に詳細を保存。新背景は既存Image Bank 2の空き領域だけ、新SEは未使用Sound 30/31だけです。全Tilemap、既存画像、音楽シーケンス、既存Sound、パレット、数値/QUEST/SAVEの定義は一致しています。

```text
python -m unittest discover -s tests
python tools/verify_battle_extra_assets.py
python tools/verify_battle_presentation_ui.py
python tools/verify_audio_recovery.py
python tools/verify_battle_music.py
python tools/verify_web_build.py --phase6d --save-ui --quest-records --final-chapter
python tools/verify_browser_battle_presentation.py --playwright-path <Playwrightの場所>
```

初回作成ツールは`tools/add_battle_extra_assets.py`。通常起動時に実行せず、Editorでの編集を上書きしません。背景は`edit.cmd`、SEは`edit_music.cmd`で変更します。Webへは`tools/build_web.cmd`による再ビルドが必要です。

`dist/game.html`と`verification/packages/skill_seekers_gkd.zip`を更新済み。GKDは既存ゲームフォルダへゲームファイルだけを上書きし、saveフォルダと独自ランチャーは保持してください。この作業でcommit/pushは行っていません。
