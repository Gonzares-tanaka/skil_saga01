# Battle Presentation追加修正 検証報告

2026-10-10～11。対象は撃破SE、味方被弾反応、エリア別下部背景帯の3点です。PC Python 3.14.7 / Pyxel 2.9.9、実Edge/Pyodideで検証しました。戦闘数値・マップ・セーブ仕様は今回変更していません。

## 指定25項目

1. **撃破SE変更内容**：低いノイズ音をG1→E1→C1→G0→E0→C0へ下降させ、後半の音量を減衰させました。通常ヒット音の約0.075秒に対して長く、開始音量も強めています。WAV生成で非無音を確認し、出力ピークは撃破4072、通常2058でした。主観的な聞き分けは実機で確認が必要です。
2. **SE位置**：`assets/battle_music.pyxres`、Sound 31。既存定数`rpg/sound.py`の`SOUND_ENEMY_DEFEAT`を使用。SEチャンネル0です。`edit_music.cmd`で編集できます。
3. **長さ**：約0.292秒（7音×speed 5）。指定0.2～0.4秒の範囲です。
4. **再生タイミング**：実際のHP0判定後、`enemy_death`開始時に1回。点滅や沈みの更新時は鳴らしません。同時撃破は1回にまとめます。反撃で味方も被弾した場合は被弾反応→撃破演出の順で、撃破演出開始時に鳴らします。最終ボスには既存専用処理を優先します。
5. **被弾実装場所**：`rpg/app.py`の`apply_visual_action`が既存`Battle.step()`前後のHPを比較し、`rpg/battle_presentation.py`の`after_action / advance / actor_offset`が`party_hit`を管理。`draw_battle`が表示します。新たなダメージ計算や乱数処理はありません。
6. **方向**：右方向。対象以外の味方には被弾オフセットを付けません。
7. **距離**：最大4px。元位置からの一時的なオフセットで、繰り返しても位置ずれは蓄積しません。
8. **時間**：3更新フレーム/30FPS、約0.1秒。`HIT_FRAMES / HIT_SECONDS`のフレーム上限と単調時計の上限で終了します。オフセット4→3→1→0。「踏み込みより短く」の条件を満たすため、踏み込みだけ3→4フレーム（約0.133秒）へ調整しました。SKILL EFFECTと戻り時間は従来のままです。
9. **HP0時の順番**：ダメージでHP0→通常画像のまま被弾→元位置→KO専用画像。実ダメージによる致死ケースで描画呼び出しと画面を確認しました。HP0自体を遅らせず、画像切替だけを遅らせます。
10. **AREA1**：`game.pyxres` Image Bank 2、左上(0,208)、96×16。B1～B5。石床・小さな柱・瓦礫・苔。
11. **AREA2**：同Bank、左上(0,224)、96×16。B6～B10。規則的な石床・水路・古い柱。
12. **AREA3**：同Bank、左上(0,240)、96×16。B11～B15。亀裂・古代文字・崩れた柱。
13. **横幅**：96px。敵側X0～95のみ。味方画像の基準X98や右側ステータス欄へ伸びません。
14. **高さ**：3エリアとも16px固定。AREAごとに1枚の横長画像であり、パーツを繰り返す方式ではありません。
15. **画面Y**：64。Y64～79へ表示。コマンド/メッセージ枠開始Y80へ重ねません。
16. **上部背景**：既存`App.draw()`の`cls(0)`をそのまま使い、通常戦の背景描画は下部帯の1回の`blt`だけにしました。敵・味方・エフェクトは後から描きます。
17. **全面背景の扱い**：旧壁/床の反復描画を廃止。旧画像と`BATTLE_BACKGROUNDS`は以前の素材生成ツールとの互換性のため残しましたが、通常戦では参照して描きません。ロードオブエリシオン戦は既存特殊背景を維持。
18. **Editor編集**：`edit.cmd`→Image Bank 2の上記座標から96×16全体を編集。`BATTLE_FLOOR_STRIP_AREA1`～`AREA3`へ座標を集約しています。任意位置へ柱や亀裂を描き足せます。Webは編集後に`tools/build_web.cmd`で再生成してください。
19. **既存画像保護**：今回の開始時点と比較し、Image 0/1、既存Image 2の全画像、KO、状態アイコン、SKILL EFFECT、旧壁/床は一致。新しい帯は元が0の空き領域だけに追加。全Tilemap・パレットも一致。音源はSound 31だけ変更し、Sound 30とBGMは一致。
20. **audio非依存**：演出はフレーム/時計で進行。`play_pos`や再生終了を進行条件にしません。音声API例外時も既存の捕捉処理で続行。起動時にSE/画像の編集内容を生成し直しません。
21. **PC Python**：全275テストPASS（最終実行200.723秒、終了コード0）。追加11件で対象限定、複数対象、GUARD、回復/0ダメージ、致死、入力ロック、音声故障、反撃後SEタイミング、画像帯範囲、個別編集、SEを検証。距離・時間とも踏み込みより小さいことも確認。実Pyxel headlessで22画面・323回の文字範囲チェックに加え、致死反応/KOの2画面を生成して目視確認。
22. **PC Browser**：実Edge/Pyodideのキー操作PASS。無音戦闘→勝利→成長→探索、致死被弾→KO、RUN成功→探索、満杯スキル入れ替え→成長へ戻らず探索、SAVE→リロード→CONTINUEを検証。埋め込みデータでも9カテゴリのQUEST、27件の完了記録、B10→ENDING、最終戦敗北/復元A～EがPASS。
23. **Smartphone Browser**：EdgeのPixel 7タッチエミュレーションでD-PAD/A/B操作、同じ戦闘/被弾/KO/逃走/入れ替え/SAVE再開がPASS。スマートフォン実機/iOS Safari/GKD実機は今回確認できていません。
24. **audio freeze回帰**：実ブラウザのAudioContextを`suspended`にし、`resume()`も意図的に失敗、全Pyxel音声APIを使用不可にしたまま上記操作がPASS。タブ切り替えとvisibilitychange/pagehide/pageshow/blur/focusイベントを検証。別の無音テストでは100回連続勝利/結果/帰還、MASTERED/閃き/入れ替え、停止ファンファーレのタイムアウトもPASS。物理的な画面ロックとiOS固有の`interrupted`は未確認です。
25. **既知の問題/限界**：進行不能・数値変更・データ破損は今回の検証で検出されませんでした。音の聞こえ方と実機のテンポは未確認。iOS実機ロック復帰とGKD実機操作は別途実機確認が必要です。

## 必須32ケース

| CASE | 結果・確認方法 |
|---|---|
| 1 | 設計/音声データPASS：下降する低音ノイズ、約3.9倍の長さ、強い開始音量。実機での主観的な聞き分けは未確認。 |
| 2～3 | PASS：enemy_death開始時1回。点滅や同時撃破で重複せず、反撃時にも実際の開始に同期。 |
| 4 | PASS：実AudioContext suspend＋resume失敗＋Pyxel音声API故障でも撃破→勝利→探索。 |
| 5～7 | PASS：実ダメージでA/Bのみ右4px、3フレーム後に元へ戻る。 |
| 8 | PASS：複数人のHPが減少した場合、対象だけ同時に反応。既存戦闘計算に新たな全体攻撃は追加していません。 |
| 9 | PASS：実HP1→0の攻撃で通常画像の被弾→KO。PC Pythonと実Webで確認。 |
| 10 | PASS：HP増加、変化なしでは反応なし。GUARDの実ダメージでは反応。 |
| 11 | PASS：対象を交互に複数回攻撃しても元位置へ復帰。 |
| 12～14 | PASS：全15階のAREA判定、B5/B10/B15を含む3エリアの実画面。 |
| 15～16 | PASS：上部は単色、旧壁/柱の反復描画なし。 |
| 17～19 | PASS：1回の96×16 blt、X0～95/Y64～79にクリップ、上部・右側UI・Y80以降への描画なし。 |
| 20 | PASS：背景帯を先に描き、敵Sprite/エフェクト/UIを後から描画。 |
| 21 | PASS：Editor相当の画像pixel編集がそのまま描画へ反映。Editor GUIによる手操作は未実施。 |
| 22 | PASS：AREA1を編集しても他の2領域のpixelは不変。 |
| 23～28 | PASS：既存踏み込み・撃破点滅/沈み・KO/蘇生・12種エフェクト・RUN・成長/入れ替え回帰テスト。 |
| 29 | PASS：PC Python全275件、実Pyxel画面確認。 |
| 30 | PASS：実Edge/Pyodide、キー操作。 |
| 31 | タッチエミュレーションPASS。スマートフォン実機は未確認。 |
| 32 | 音声停止/復旧失敗と復帰イベントによる代替確認PASS。実機画面ロック→復帰は未確認。 |

## 証跡・再実行

保全結果：`verification/battle_hit_strip_preservation.json`。比較元は`verification/backups/battle_hit_strip/`。最終の全テスト実行ログは同フォルダの`final_tests.txt`です。独立したテストデータを使用し、実プレイヤーのSAVEには触れていません。

実Web結果：`verification/battle_presentation_browser.json`。`silent_hit_ko`もPC/タッチ両方でtrue。画像：`verification/screenshots/battle_presentation_area1.png`～`area3.png`、`battle_hit_before_ko.png`、`battle_hit_after_ko.png`。SE比較WAVは比較用バックアップフォルダ内の`enemy_defeat.wav`と`normal_hit.wav`です。

```text
python -m unittest discover -s tests
python tools/verify_battle_hit_strip_assets.py
python tools/verify_battle_presentation_ui.py
python tools/verify_audio_recovery.py
python tools/verify_battle_music.py
python tools/verify_web_build.py --phase6d --save-ui --quest-records --final-chapter
python tools/verify_browser_battle_presentation.py --playwright-path <Playwrightの場所>
```

画像の一度だけの作成ツールは`tools/add_battle_strip_assets.py`です。編集後には再実行しないでください。`dist/game.html`と`verification/packages/skill_seekers_gkd.zip`を更新済み。GKD ZIPのゲーム55ファイルは最新ソースと一致し、Python 3.11構文検証PASS、SAVEやキャッシュは含みません。更新時はゲームデータだけを上書きし、既存SAVEと独自ランチャーは保持してください。commit/pushは行っていません。
