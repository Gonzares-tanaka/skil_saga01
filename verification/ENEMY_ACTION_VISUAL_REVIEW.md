# Enemy Action Visual Feedback Pass

確認日: 2026-10-11。今回の変更は敵行動の表示メタデータ、Battle Presentation、4種類の小さな編集可能素材のみ。敵AI、行動weight、能力値、ダメージ・BUFF/DEBUFF倍率、GUARD性能、出現テーブル、PLAYER Skill、成長、QUEST、SAVE schemaを維持。

## 完了報告（指定36項目）

1. **heavy_attack**: 通常より大きく踏み込み、対象にheavy_hitの放射状打撃マークを6フレーム表示。その後、既存の短い被弾反応。
2. **通常attackとの差**: attackは既存の被弾反応と3pxの敵の動き。heavyは9pxの踏み込み、専用マーク、命中時の短い強めの揺れ。
3. **踏み込み量**: heavyは最大9px。3フレームで到達し、被弾反応とともに戻る。PLAYERのノックバック量は既存4pxのまま。
4. **Screen Shake**: heavy命中時のみ専用の短い揺れ。通常の既存ダメージ揺れは維持。
5. **Shake量**: X最大3px、Y最大1px。順に(3,0)、(-2,1)、(1,-1)。
6. **Shake時間**: 3フレーム、30FPSで約0.1秒。踏み込み・効果表示中にはheavy専用の揺れを出さず、命中時から開始。
7. **double_attackの間隔**: 1発目の効果3フレーム→反応3フレーム→無表示の間2フレーム（約0.067秒）→2発目。効果開始の間隔は8フレーム、総時間14フレーム（約0.467秒）。従来の18フレームの効果＋3フレーム反応より短い。
8. **各hitのreaction**: 同じ対象へ各3フレームの4pxノックバック。2回の反応開始を8フレーム離す。追加の3回目の反応はなし。
9. **初撃KO**: 戦闘処理が記録した実hit数を使用。1発分の6フレームで終了し、別PLAYERへ移さない。反撃で敵が倒れた場合も、実行されなかった2発目は表示しない。
10. **magic effect_id**: 既存`magic`。
11. **magic位置**: 対象PLAYERの16×16画像位置、X=98、Y=13+16×party_index。敵はその場に留まる。効果9フレーム→既存被弾反応3フレーム。
12. **再利用**: magic、slash、blunt、buff、debuffを既存素材のまま再利用。PLAYER Skillの既存表示も維持。
13. **area_attack**: 生存者全員へ既存bluntを同時表示し、全員ノックバック。KO済みの味方は対象外。
14. **area_magic**: 生存者全員の画像位置へmagicを同時表示し、全員ノックバック。単体魔法とは対象数で区別。画面フラッシュは追加していない。
15. **guard**: 敵画像位置に盾とガードラインの3コマを9フレーム表示。継続マークは追加せず、使用時の表示に留めた。効果量・次の自身の行動までの持続は変更なし。
16. **power_up**: 敵画像位置へ既存buffの上向き矢印。9フレーム。追加の再適用はしない。
17. **weaken**: 対象PLAYERへ既存debuffの下向き矢印。9フレーム。ダメージ・ノックバックは発生しない。
18. **armor_break**: 対象PLAYERへ割れた盾と下向き矢印。9フレーム。weakenと異なる素材。
19. **slow**: 対象PLAYERへ砂時計と減っていく速度線。9フレーム。既存DEBUFF扱いを維持し、状態異常Systemは追加していない。
20. **追加effect_id**: heavy_hit、guard、armor_down、slowの4種類。共通EFFECT_SPRITESへ登録。
21. **追加素材**: game.pyxres Image Bank 2の未使用領域へ、各16×16×3コマ。4色のみ。起動時に生成せず、Python内にPixel Arrayを埋め込んでいない。
22. **素材座標**: X=144/160/176。heavy_hit Y=96、guard Y=112、armor_down Y=128、slow Y=144。magicは既存X=192/208/224、Y=128。buff Y=176、debuff Y=192。Pyxel editorで編集可能。
23. **fallback**: effect_idが未設定、None、空文字、未知の場合は既存bluntへ安全にフォールバック。追加テストで確認。
24. **Message早送り**: 従来のA押下・長押し処理を変更していない。演出がactiveの間は入力処理へ進まず、短いフレーム演出を維持。通常／早送り両方で同じ演出フレーム数。
25. **最低表示**: 通常物理の既存反応3、heavy効果6＋反応3、double各効果3＋反応3、magic/全体/補助効果9。連撃の間は2フレーム。各phaseには最大2秒の壁時計タイムアウトもあるため、長い停止からの復帰では演出を短縮して進行を優先。
26. **入力ロック**: App/DungeonApp.updateの既存`resolve and visual.active`分岐でadvanceだけを実行してreturn。A/B/D-PADを連打しても次のキューをpopしない。SELECT終了の既存処理は維持。
27. **damage一度のみ**: Battle.stepで1キュー分だけ処理する既存構造を維持。アニメーションは確定済み対象・hit数を参照するだけ。heavy/magicは1回、doubleは2回またはKO中止、areaは各生存者1回をspyで検証。全11行動×通常/早送りで次のstepが実行されないことも確認。
28. **weight不変**: data/enemies.jsonとrpg/enemy_actions.pyが変更前のSHA-256と一致。重み付き抽選処理・fallbackのAIには変更なし。
29. **倍率不変**: enemy_actions.jsonはeffect_idのみ変更。全11行動×15seedでダメージ、全状態、メッセージ、音声cue、乱数状態が演出メタデータを除いた従来処理と一致。
30. **敵能力不変**: 全18敵のデータファイルがハッシュ一致。enemy_id、画像、基本能力、HUNT補正、出現テーブルを維持。
31. **自動テスト**: 全322件、77.530秒、成功。今回の演出専用12件を追加し、既存連撃の表示テスト1件を新しい短い演出へ更新。
32. **PC Python**: WindowsのPython 3.14.7 / Pyxel 2.9.9の実エンジンをheadlessで検証。全11行動の56枚の描画を保存・目視確認。文字境界を自動確認。B10→ENDINGの通し試験、5種類の実全滅再挑戦も成功。
33. **PC Browser**: 実Edge Chromium/Pyodideで全11行動×通常/早送り成功。強攻撃の9px/9フレーム、連撃の2回の反応と8フレーム間隔、魔法の静止も検証。JSエラーなし。
34. **Smartphone Browser**: Edge ChromiumのPixel 7タッチ端末エミュレーションで同じ22パターン成功。物理スマートフォンとiOS Safariの実機確認ではない。
35. **audio freeze回帰**: 両ブラウザで実AudioContextをsuspendedにし、resumeを意図的に失敗させた。pyxel.play/playm/play_posも失敗させ、全行動と全滅→RESULT→拠点を確認。visibilitychange/blur/focus/pageshow通知も実施。新しい音声終了待ちはない。
36. **既知の問題／確認限界**: 進行不能・二重ダメージは検出されなかった。iOS Safari実機での画面ロックとGKD Pixel2実機の今回の演出確認は未実施。BUFF/DEBUFFとarea_magicは現行敵に未割り当てのため、専用fixtureで検証。難易度・プレイ体感は今回調整していない。

## 必須41ケース

| CASE | 結果・証拠 |
|---|---|
| 1～4 | 通常物理を保持。heavyの大きい踏み込み・効果・命中時の短い揺れ、早送り中の最低表示、damage1回を確認 |
| 5～8 | 3フレームずつの2回の効果と2回の反応、2フレームの間、初撃KOでの停止、damage2回のみを確認 |
| 9～11 | magicを既存素材で対象位置へ表示し、敵は静止。通常／早送りとも効果9フレーム |
| 12～14 | 生存者全員に各1回のdamageと同時ノックバック。既存bluntを使用 |
| 15～17 | 全生存者へ同時magicと各1回のdamage。単体とは表示位置数が異なる |
| 18～20 | 盾の使用時表示が早送りでも残り、既存GUARD軽減・ラウンド跨ぎ持続テストも成功 |
| 21～25 | 上向き矢印、下向き矢印、割れた盾、砂時計を区別。効果の重複適用なし |
| 26～28 | 全11行動の通常／早送り・A/B/D-PAD連打をPC Pythonと実ブラウザで確認。次のstepはロック |
| 29～32 | 通常戦闘、HUNT生成・SAVE/LOAD、B5/B10の通常遭遇とボス戦の既存テスト成功 |
| 33～35 | 同一SessionでB10→守護者3連戦→泉→デーモン→アムリタ→ロードオブエリシオン→ENDING成功 |
| 36～38 | RUN、RESULT、SAVE/LOADの既存テストとWeb埋込み終盤再挑戦に成功。SAVE_VERSION=1を維持 |
| 39～41 | 無音と実AudioContext suspended/resume失敗でも完走。Screen Shake/Effectはtimerのみ |

## 配布・保全

- data/enemies.json、Skill、成長、TRZ、ITEM、QUEST、SAVE、HUNT、出現設定、マップ等の既存51ファイルが変更前のハッシュと一致。
- game.pyxresはImage 2の上記未使用セルだけ変更。Image 0/1、全Tilemap、Sound/Musicは内容一致。既存素材を上書きしていない。
- HP計算は従来どおり行動時に確定。表示上は効果を先に見せ、被弾・KOへ移行。連撃のHP表示は効果完了まで直前値を保ち、ダメージを表示演出側で分割計算しない。
- 反撃で倒れた敵も攻撃効果・被弾反応中は表示を保ち、その後に既存点滅＋沈み＋撃破SEへ移る。途中で消えて再び点滅開始時に現れる表示を避けた。
- dist/game.htmlを再生成し、埋込みコード・JSON・素材の一致を検証。
- verification/packages/skill_seekers_gkd.zipを再生成。58エントリ、最新ソース・素材のバイト一致を検証。SAVEを含めない。rpg全PythonファイルはPython 3.11構文互換も確認。実機のセーブ形式は変更なし。
- ユーザーの実SAVE・ブラウザ保存は読み書きしていない。ブラウザは隔離プロファイル、既存SAVEテストは一時ファイルを使用。

## 検証コマンド

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_enemy_action_visuals.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_final_chapter.py
.\.venv\Scripts\python.exe -B -X utf8 tools/build_web.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_web_build.py
.\.venv\Scripts\python.exe -B -X utf8 tools/verify_browser_enemy_actions.py --playwright-path verification/backups/quest_spawn/browser_deps
.\.venv\Scripts\python.exe -B -X utf8 tools/build_gkd.py
```

詳細データはenemy_visual_preservation.json、enemy_actions_browser.json、final_chapter.json。描画サンプルはscreenshots/enemy_visual_*.png。
