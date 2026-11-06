# ENEMY & BOSS BALANCE PASS 01 検証報告

実施日：2026-10-15。PC：Python 3.14.7 / Pyxel 2.9.9。ブラウザ：実際のPyxel Web/PyodideをEdge Chromiumの隔離プロファイルで実行。

通常敵18種とボス7体を調整し、デーモンの二回行動、守護者BGMの再試行、アムリタの単発フラッシュ・画面揺れ・最終曲への切替を実装した。PLAYER Skill62種、共通状態異常、マップ、成長、報酬、SAVE形式は変更していない。検証には合成パーティーと一時セーブだけを使い、実セーブは読み書きしていない。

実機のiOS Safari／GKD Pixel2は未確認。以下の成功は、自動テスト、ネイティブPC実描画、実Webランタイム、タッチエミュレーションによるもの。自然な成長を伴うNEW GAMEからの全編難易度評価とは区別する。

## 比較条件

調整前データ：`tests/fixtures/enemy_balance_before.json`。敵18種の表は基本値。ゲームでは既存の階層別HP/攻撃倍率を引き続き適用する。

ATK（必要攻撃回数）は、B1～B14の実出現候補と倍率に対し、`ceil(HP / max(1, round(skill.power - DEF/MDEF)))`で算出。乱数±10%とGUARDはこの表のみ除外。AREA1はHP70/STR10/AGI12/INT12、AREA2は120/22/24/24、AREA3は180/34/36/36という開示した比較用能力であり、自然成長の予測値ではない。初期パーティーはHP36～48/STR3～8/AGI5～9/INT2～9で、初期能力データはそのまま。

標準ATKはPUNCH/QUICK HIT/SPARKの平均。鉄のゴーレム・石獣は元来の高DEF役割を尊重しSPARKで比較。全6技（基本3技＋POWER STRIKE/QUICK STAB/FIRE）の各フロア結果は`enemy_balance.json`に残した。ATK増加を全敵一律にしない。標準平均の増加は16/18種で0.5～1.0回、毒蛇0.33回、鉄のゴーレム0回。

## 通常敵18種の変更前後

| ID / 名前 | HP | STR | INT | HP増加率 | 標準ATK | 1行動1対象の期待威力増加 |
|---|---:|---:|---:|---:|---:|---:|
| slime / スライム | 24 → 31 | 5 → 5 | 2 → 2 | 29.17% | 2.33 → 3.00 | +0.00% |
| bat / コウモリ | 20 → 27 | 6 → 7 | 2 → 2 | 35.00% | 2.00 → 2.50 | +16.67% |
| goblin / ゴブリン | 32 → 40 | 7 → 8 | 3 → 3 | 25.00% | 3.22 → 3.78 | +14.29% |
| wisp / 鬼火 | 25 → 31 | 3 → 3 | 8 → 9 | 24.00% | 2.67 → 3.20 | +10.77% |
| golem / ゴーレム | 44 → 52 | 9 → 10 | 2 → 2 | 18.18% | 5.33 → 6.00 | +11.11% |
| skeleton / 骸骨兵 | 38 → 45 | 9 → 10 | 3 → 3 | 18.42% | 3.75 → 4.42 | +11.11% |
| mage / 魔術師 | 30 → 37 | 4 → 4 | 11 → 12 | 23.33% | 2.38 → 3.00 | +8.33% |
| iron_golem / 鉄のゴーレム | 72 → 80 | 10 → 11 | 2 → 2 | 11.11% | 3.00 → 3.00 | +10.00% |
| berserker / 狂戦士 | 70 → 90 | 29 → 31 | 3 → 3 | 28.57% | 3.22 → 4.00 | +6.90% |
| assassin / 暗殺者 | 65 → 85 | 18 → 19 | 8 → 8 | 30.77% | 3.20 → 3.80 | +5.56% |
| stone_beast / 石の獣 | 88 → 98 | 16 → 17 | 4 → 4 | 11.36% | 3.50 → 4.00 | +6.25% |
| horn_rabbit / ツノウサギ | 24 → 29 | 6 → 6 | 2 → 2 | 20.83% | 2.50 → 3.17 | +0.00% |
| poison_snake / 毒蛇 | 58 → 70 | 13 → 14 | 4 → 4 | 20.69% | 3.00 → 3.33 | +7.69% |
| blood_bat / ブラッドバット | 52 → 63 | 15 → 16 | 5 → 5 | 21.15% | 2.33 → 3.00 | +6.67% |
| ghost / ゴースト | 56 → 73 | 8 → 8 | 20 → 22 | 30.36% | 3.13 → 4.07 | +9.06% |
| mummy / ミイラ | 86 → 105 | 18 → 19 | 10 → 10 | 22.09% | 4.33 → 5.33 | +5.56% |
| dark_wisp / ダークウィスプ | 60 → 74 | 6 → 6 | 24 → 26 | 23.33% | 2.89 → 3.67 | +8.33% |
| warlock / ウォーロック | 68 → 84 | 8 → 8 | 27 → 29 | 23.53% | 3.33 → 4.33 | +7.41% |

AGI・DEF・MDEF・Action weight・状態異常成功率・ID・名前・spriteは通常敵全種で不変。低いSTRの整数+1はコウモリで16.67%、ゴブリンで14.29%になるため、スライムとツノウサギの攻撃値は据え置いた。全体としてはAREA平均5～10%内。

HPはATK閾値を優先し、AREA1の開始目安10～15%より大きい敵もある（例：コウモリ20→27、絶対値+7）。高DEFの鉄ゴーレム72→80、石獣88→98は約11%に抑えた。物理相性が悪いケースでは、鉄ゴーレムにPUNCHが12→14回、石獣にPUNCHが22→25回となる。元から1発6/4ダメージの不利な相性によるもので、DEFを更に上げてはいない。SPARKでは鉄ゴーレム3→3回、石獣3.5→4回である。3回が6回になる標準攻撃のケースはない。

## AREA平均と実戦テンポ

各AREAの平均は、そのAREAに登場する各IDを一度ずつ数える単純平均（出現weightによる加重平均ではない）。同じ敵が複数AREAに出る場合はそれぞれで集計。

| AREA | 平均HP増加率 | 平均1行動1対象の威力増加率 |
|---|---:|---:|
| 1 | +24.24% | +9.04% |
| 2 | +21.98% | +8.23% |
| 3 | +22.72% | +7.49% |

同じseed・同じ敵構成で、B1～B14各60組×2装備技条件×調整前後＝3,360戦。B5/B10は既存の前階通常テーブル、B15は通常遭遇なし。4人が同じ比較能力で、基本技条件はPUNCH/QUICK HIT/SPARK/PUNCH、COMMON条件はPOWER STRIKE/QUICK STAB/FIRE/POWER STRIKE＋3人目にFIRST AID。既存auto_actionsを使用し、状態異常・Uses消費・KO・GUARDも実処理。

| AREA / 技条件 | 平均味方行動数 前→後 | 平均ラウンド 前→後 | 総被ダメージ 前→後 | 敵1行動あたり被ダメージ 前→後 | 勝数 前/後 |
|---|---:|---:|---:|---:|---:|
| 1 / basic | 9.69 → 11.74 | 2.80 → 3.32 | 36.09 → 50.97 | 10.42 → 11.35 | 300/300（各300） |
| 1 / common | 9.43 → 12.24 | 2.74 → 3.41 | 23.85 → 36.48 | 8.01 → 8.82 | 300/300（各300） |
| 2 / basic | 9.06 → 10.49 | 2.66 → 3.00 | 48.78 → 61.60 | 15.79 → 16.81 | 300/300（各300） |
| 2 / common | 6.83 → 8.51 | 2.07 → 2.53 | 27.82 → 38.85 | 13.48 → 14.44 | 300/300（各300） |
| 3 / basic | 11.08 → 13.21 | 3.17 → 3.66 | 95.15 → 125.28 | 24.27 → 25.77 | 240/240（各240） |
| 3 / common | 10.66 → 11.59 | 3.03 → 3.25 | 58.71 → 75.17 | 18.42 → 20.05 | 240/240（各240） |

味方行動数は4人合計。1戦全体では約+0.93～2.81行動、+0.22～0.68ラウンド。総被ダメージは攻撃値上昇だけでなく、敵が生き残って行動する回数の増加も含む。5～10%なのは1行動の威力であり、1戦全体の損耗増加が5～10%という意味ではない。準備パーティーの全勝は自然進行の難易度保証ではない。

## ボス基本値と行動

全ボスのAGI/MDEF、耐性、画像、名前、ID、イベント文章は不変。旧ボス全7体は個別actionsなしで、magic_chanceによる単体attack/magicのfallbackだった。今回共通Action定義を変えずに個別weightを設定した。

| ID / 名前 | HP | STR | INT | DEF | 主な役割 / 1ラウンド行動数 |
|---|---:|---:|---:|---:|---|
| guardian / 迷宮の守護者 | 360 → 420 | 22 → 25 | 24 → 24 | 4 → 10 | 1行動 |
| skill_keeper / 技の番人 | 600 → 690 | 32 → 37 | 30 → 30 | 14 → 12 | 1行動 |
| depth_lord / デーモン | 900 → 1080 | 42 → 46 | 44 → 49 | 20 → 20 | 2行動 |
| sentinel_armor / 重装の守護者 | 500 → 560 | 30 → 35 | 8 → 8 | 24 → 22 | 1行動 |
| sentinel_speed / 高速の守護者 | 420 → 490 | 32 → 36 | 12 → 12 | 8 → 8 | 1行動 |
| sentinel_mind / 魔導の守護者 | 460 → 530 | 20 → 23 | 38 → 43 | 6 → 6 | 1行動 |
| lord_of_elysion / ロードオブエリシオン | 990 → 1180 | 50 → 57 | 52 → 60 | 24 → 24 | 1行動 |

以下は防御/乱数/バフ/デバフなしの基準ダメージ。旧攻撃/旧魔法は変更前に選ばれた単体Action。新値は該当Actionを持つ場合だけ表示する。全体技の数字は1人分。実処理では既存の丸めと±10%乱数、GUARD等を適用する。二回行動はこの表の値を単純2倍せず、組合せ制限を適用する。

| ボス | 旧単体攻撃 / 魔法 | 新単体攻撃 / 魔法 | 新強打 | 新連撃合計 | 新全体物理 / 魔法（各人） |
|---|---:|---:|---:|---:|---:|
| 迷宮の守護者 | 22 / 24 | 25.00 / ― | 33.75 | ― | ― / ― |
| 技の番人 | 32 / 30 | 37.00 / ― | 49.95 | 44.40 | ― / ― |
| デーモン | 42 / 44 | ― / 49.00 | 62.10 | ― | ― / 24.50 |
| 重装の守護者 | 30 / 8 | 35.00 / ― | 47.25 | ― | 19.25 / ― |
| 高速の守護者 | 32 / 12 | 36.00 / ― | 48.60 | 43.20 | ― / ― |
| 魔導の守護者 | 20 / 38 | ― / 43.00 | ― | ― | 12.65 / 21.50 |
| ロードオブエリシオン | 50 / 52 | ― / ― | 76.95 | ― | 31.35 / 30.00 |

| ボス | 設定weight | 10,000ラウンドの実測選択率（%） |
|---|---|---|
| guardian | attack 30 / heavy_attack 45 / guard 25 | heavy_attack 44.59 / attack 29.95 / guard 25.46 |
| skill_keeper | attack 25 / heavy_attack 35 / double_attack 40 | heavy_attack 35.04 / double_attack 39.96 / attack 25.00 |
| depth_lord | magic 22 / area_magic 24 / heavy_attack 12 / power_up 6 / weaken 8 / armor_break 6 / slow 6 / poison_bite 6 / sleep_spell 6 / confusion_touch 4 | heavy_attack 12.52 / armor_break 6.30 / area_magic 22.85 / magic 21.33 / poison_bite 6.55 / sleep_spell 6.15 / slow 6.67 / power_up 5.00 / confusion_touch 4.01 / weaken 8.61 |
| sentinel_armor | attack 15 / heavy_attack 25 / area_attack 30 / guard 15 / power_up 15 | area_attack 31.27 / guard 15.82 / heavy_attack 26.11 / power_up 11.55 / attack 15.25 |
| sentinel_speed | attack 10 / double_attack 40 / heavy_attack 20 / slow 10 / armor_break 10 / paralyze_grab 10 | double_attack 40.03 / slow 10.33 / heavy_attack 20.36 / armor_break 10.11 / paralyze_grab 9.09 / attack 10.08 |
| sentinel_mind | magic 25 / area_magic 40 / area_attack 15 / confusion_touch 8 / sleep_spell 12 | area_magic 41.75 / area_attack 15.52 / magic 26.03 / confusion_touch 6.74 / sleep_spell 9.96 |
| lord_of_elysion | heavy_attack 20 / area_attack 30 / area_magic 25 / weaken 10 / armor_break 8 / slow 7 | area_attack 24.75 / area_magic 20.94 / heavy_attack 23.90 / armor_break 10.24 / slow 8.13 / weaken 12.04 |

seed317。バフが有効な間は再使用せず、control（睡眠/マヒ/混乱）の連続選択を除くため、設定weightの比率と実際の選択率は一致しない。デーモンは10,000ラウンド＝20,000行動。ナイトのバフ残りターンも反映した。weightと共通powerは別である。

B5：物理DEF4→10＋GUARD25。B10：DEF14→12で防御一辺倒を避け、STR32→37、連撃40。ナイト：DEF24→22で元からの重装を少し緩め、バフとGUARDで硬さを作る。物理強打1.35倍、連撃0.6倍×2、全体物理0.55倍、全体魔法0.5倍などの共通倍率は一切変更していない。

B5に対しSTR16のCOMMON物理はGUARD中も正のダメージを与え、Armor Breakで増加、INT18のFIREも有効（自動テスト）。HP100/STR16/AGI18/INT18の準備パーティー各100戦では、基本技のみ98勝・平均11.61ラウンド、COMMON技＋FIRST AIDで100勝・9.87ラウンド。RARE/LEGEND不要。初期能力のままでの勝利保証ではない。

## デーモン二回行動と最終ボスHP段階

デーモンはAGI順の一枠に同じ敵のキューを2つ連続で置く。1回目と2回目で行動抽選・対象・ダメージ・演出を実行し、2回目後に次のアクターへ進む。マヒの50%判定・睡眠判定を共有し、状態異常durationと毒tickは本人ターン終了時の1回だけ。バフ/デバフdurationは従来どおりラウンド終了時1回。KO・勝利・敗北なら残りキューを破棄。

同一ラウンドで同一Action2回、major AOE2回、control2回は候補段階で除外。有限候補の重み抽選だけで、再抽選whileはない。10,000ラウンドで違反0、全10Actionが出現。組合せごとの回数も`enemy_balance.json`に収録。GUARDは既存50%軽減、HEAL/CURE/バフ/デバフの効果は不変。

無軽減・敵バフなしの最大乱数でも、デーモンの全体魔法は1人あたり約27、単体強打は約68で、同ターンに全体魔法を2回撃てない。ロードの全体物理は約34、魔法約33（後半も共通倍率は同じ）。比較用終盤HP180の全員を満タンから一撃で倒す全体攻撃はない。ただし、低HPのパーティーや累積デバフ下の生存は保証しない。

ロードは1行動のまま。HP段階でのweightと実測は以下。全体攻撃は最大2連続までで、次は強打またはデバフにする。

| 残HP | heavy_attack | area_attack | area_magic | weaken | armor_break | slow | 全体技実測率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 100%～50%超 | 20 | 30 | 25 | 10 | 8 | 7 | 45.69% |
| 50%以下～25%超 | 20 | 32 | 33 | 5 | 7 | 3 | 51.48% |
| 25%以下 | 20 | 35 | 37 | 3 | 4 | 1 | 55.42% |

変更前の全体技率は0%。今回100%状態45.69%→50%状態51.48%→25%状態55.42%。各10,000選択。全体物理・魔法の個別率もJSONに記録した。HP50%/25%境界の等号を含む。

## 指定63項目の完了報告

1. **変更File**：本体は`data/enemies.json`と`rpg/{models,content,enemy_actions,battle,dungeon_app,app,final_presentation,sound}.py`。README、敵比較/ブラウザ/実描画検証ツール、テストと検証記録も追加・更新。Web本体と通常/診断ZIPを再生成。`enemy_actions.json`や各pyxresは変更していない。
2. **Normal Enemy総数**：18、ボス7、計25を維持。
3. **個別HP**：上の18種の表を参照。全て個別値で調整。
4. **個別Attack**：同表のSTR/INTと期待威力増加を参照。DEF/AGI/MDEFは不変。
5. **AREA1平均HP**：+24.24%。ATK閾値を優先し開始目安を超えた理由は比較条件に記載。
6. **AREA2平均HP**：+21.98%。高DEF2種は約11%増に抑制。
7. **AREA3平均HP**：+22.72%。
8. **代表ATK**：スライム2.33→3.00、ゴブリン3.22→3.78、バーサーカー3.22→4.00、ゴースト3.13→4.07、ミイラ4.33→5.33。全18種・全出現階の表を収録。
9. **平均Action**：実戦テンポ表を参照。4人合計+0.93～2.81行動、+0.22～0.68ラウンド。
10. **POISON Root Cause**：maxHP5%を整数切り捨て＋最低1で、maxHP40未満なら1が正しい。表示は実際に失ったHPなので残りHP1でも1。敵だけ常時1になるバグは確認されなかった。
11. **POISON修正**：数式・状態データとも修正なし。低HP/大HP/KO/睡眠解除と二回行動時のtickをテスト。
12. **Enemy POISON式**：`max(1, int(target.max_hp * 0.05))`、実損失は残HPまで。DEF/GUARDによる軽減はなし。既存の最終バリアは維持。
13. **Player POISON**：共通処理と`statuses.json`を維持。味方と敵で20/39/40/100/1080HPの同じ期待値を確認。
14. **B5前後**：HP360→420、STR22→25、DEF4→10。防御型。
15. **B5 weight**：attack30/heavy45/guard25。実測29.95/44.59/25.46%。
16. **B5 DEF/HP/Attack**：14の値。RARE不要の勝利・物理貫通・魔法/防御低下の有効性を確認。
17. **B10前後**：HP600→690、STR32→37、DEF14→12。猛攻型。
18. **B10 weight**：attack25/heavy35/double40。
19. **B10連撃率**：実測39.96%。1Action内の2hitであり、1Roundは1Action。
20. **KNIGHT**：自己強化・防御・単体強打・全体物理。IDは`sentinel_armor`を保持。
21. **KNIGHT weight**：attack15/heavy25/area30/guard15/power_up15。バフ有効中の再強化を除外。実測表を参照。
22. **CYCLOPS**：妨害・連撃。`sentinel_speed`を保持。
23. **CYCLOPS weight**：attack10/double40/heavy20/slow10/armor_break10/paralyze10。マヒActionの連続選択は禁止。付与成功率35%は不変。
24. **DRAGON**：全体魔法・睡眠・混乱。`sentinel_mind`と既存Dragon画像を保持。
25. **DRAGON weight**：magic25/area_magic40/area_attack15/confusion8/sleep12。control連打は禁止。
26. **守護者の差別化**：ナイトは自強化＋物理、サイクロプスは敵弱体＋連撃、ドラゴンは全体魔法＋状態異常。
27. **3連戦BGM Root Cause**：`play_bgm()`が再生開始に失敗しても`current_bgm`だけを先に設定し、次回は同じIDという理由で成功扱いする不具合をコードで確認。失敗注入で無音が固定される経路を再現した。実機で最初の再生失敗が発生した原因までは未特定であり、この経路が唯一の実機原因と断定はしない。
28. **BGM修正**：`bgm_started`で実行成功を別管理し、失敗なら0.5秒間隔で再試行。同一曲の正常再生は再起動しない。既存のファンファーレ後の曲位置復帰を維持。
29. **守護者2/3のBGM**：実勝利→結果→次戦の3連戦で確認。ネイティブ3チャンネルのplay_posが有効、各ボス100回のCOMMAND READYでもBoss曲。Webでも3連戦を検証。実機聴感は未確認。
30. **DEMON変更**：多彩な魔法・状態異常・弱体＋正式二回行動。
31. **DEMON Stats**：HP900→1080、STR42→46、INT44→49、DEF20据置。
32. **2Action実装**：行動順の一枠に連続2キュー、判定/毒tick/durationは1本人ターン。Battle内の履歴だけで管理しSAVEへ追加しない。
33. **DEMON Action**：magic、area_magic、heavy_attack、power_up、weaken、armor_break、slow、poison_bite、sleep_spell、confusion_touch。
34. **DEMON weight**：順に22/24/12/6/8/6/6/6/6/4。共通威力・付与率は不変。
35. **Combination制限**：同じラウンド内の同一Action、major AOE2回、control2回を禁止。連続controlも抑制。
36. **DEMON Simulation**：10,000Round/20,000Actionで違反0、全Action出現。実描画でも音声正常/失敗/無効の3条件で2行動後にコマンドへ戻る。毒/睡眠/マヒtick、反撃KOによる2回目中止も確認。
37. **LORD変更**：1Actionのまま全体物理/魔法中心、HP低下で攻撃性上昇。正式名称を維持。
38. **LORD Stats**：HP990→1180、STR50→57、INT52→60、DEF24据置。
39. **LORD Action**：heavy_attack、area_attack、area_magic、weaken、armor_break、slow。
40. **HP100% weight**：20/30/25/10/8/7。
41. **HP50%以下 weight**：20/32/33/5/7/3。
42. **HP25%以下 weight**：20/35/37/3/4/1。
43. **全体攻撃頻度**：旧0%、今回45.69/51.48/55.42%（各段階）。最大2連続、3連続なし。
44. **Amrita前BGM**：bgm_boss、game.pyxres Music5。
45. **Amrita後BGM**：破壊演出32frameでbgm_final、Music6。
46. **Flash**：frame24/25の2frame、約0.067秒の1Pulse。反復点滅なし、既存4色の明色を使用。
47. **Screen Shake**：frame26～31、最大X±2/Y±1pixel、6frame。端末振動APIは追加せず、cameraをfinallyで戻す。
48. **Barrier Break順**：使用メッセージ→既存上からの光→単発フラッシュ→画面揺れ→破壊→最終曲→戦闘継続。実画面6枚も確認。
49. **Amrita Gameplay**：Key Item・1行動消費・使用時即バリア解除は不変。見た目の殻だけ破壊まで保持。
50. **Retry BGM**：チェックポイント復元→バリア有効＋Boss曲。再度AmritaでFinal曲。リソース復元方式は変更なし。
51. **native playm**：未使用。Musicのコピーした各チャンネル配列をplayへ渡す既存回避を保持。Webのみ従来playm。
52. **Audio Failure**：play/playm/stop/play_posの例外、Audio無効、Web AudioContext suspended＋resume失敗で進行。演出45frame/最大2秒、音声終了待ちなし。
53. **GKD Freeze回帰**：PCネイティブで通常1000＋ボス7種各100＝1700開始、全て入力可能。守護者/デーモンの実行動も描画経由で進行。GKD実機そのものの検証ではない。
54. **Skill不変**：62技、RARE20/LEGEND8。データ・Growth・Spark等のSHA一致と全62技×2seed×4条件×MASTERED有無＝992比較で、ダメージ/状態/Uses/乱数/メッセージ等が一致。
55. **SAVE schema**：save.pyと既存合成v1セーブが不変。AI weight/履歴やAudio状態を保存しない。実セーブ未使用。
56. **save_version**：1のまま。
57. **自動Test総数**：555/555成功（スキップなし）。別に992挙動比較、3,360通常比較戦、200B5戦、各ボス多数抽選、1,700実描画開始、ブラウザ64実行を実施。
58. **PC Browser**：Edge Chromium実Web版。音声runningと強制suspendedの両方で16/16、キーボードDown/Z/X、ページ復帰イベント、JavaScript例外なし。
59. **Touch Browser**：同じ2条件で16/16、HTML D-PAD/A/Bの実pointer入力。物理iOS Safariの代替確認ではない。
60. **Web更新**：dist/game.html再生成。埋込み版の通常遭遇・守護者・Amrita・バリア・再挑戦・ENDINGも検証。配布source/resource一致。
61. **GKD ZIP更新**：通常ZIP63entry、診断ZIP66entry。ゲーム内容62fileがWeb/通常/診断で一致。Python3.11構文34sourceを確認。ランチャー/診断機能を維持、SAVEを含まない。
62. **実機未確認**：iOS Safariの物理画面ロック・interrupted・実音、GKD plumOS/ARM/SDLでの連戦/音、自然なNEW GAME全編の難易度。診断版も更新しており、実機確認に利用可能。
63. **既知の問題**：現検証範囲で進行不能/復元異常は未検出。B5基本技のみ自動戦闘は2/100敗北。物理不利な重装敵ではPUNCH必要数が+2/+3となるため相性に注意。守護者BGMの実機での初回失敗原因は未確定。画像Editor変更後で過去Phaseのpixel基準が古かった3検査は、画像を巻き戻さず「今回開始時のpyxres/pyxpal完全一致」を検証する方式に更新した。ゲームバランスの最終判断には実機プレイが必要。

## 指定112ケースと証拠の対応

| CASE | 結果 / 検証 |
|---|---|
| 1～7 | 成功。18体の行・HP/ATK/期待ダメージ比較、通常戦3,360比較、率・報酬・Action等の不変ハッシュ。 |
| 8～16 | 成功。PLAYER毒技→敵への付与、共通maxHP/最低値、KO、睡眠解除、duration/成功率不変。 |
| 17～22 | 成功。B5多数選択・実描画、DEF/guard/strong、物理正ダメージと魔法/装甲低下有効、RARE不要勝利。 |
| 23～28 | 成功。B10連撃約40%、高STR/強打、1Round1Action。 |
| 29～33 | 成功。KNIGHT buff/guard/heavy/area。バフ有効中再選択なし。 |
| 34～38 | 成功。CYCLOPS double/debuff/paralyze、control連打なし、KNIGHTとの差。 |
| 39～42 | 成功。DRAGON area_magicとcontrolの実出現、全体圧力。 |
| 43～49 | 成功（PC/Web）。3連戦実勝利後の曲復帰、2/3戦COMMAND READY、不要AREA曲/正常同曲restartなし、native playmなし。実機聴感未確認。 |
| 50～61 | 成功。DEMONの2回実行/次Round、10,000組の全体技/control/同一Action禁止、毒とdurationの1回処理。 |
| 62 | 成功。終盤通しテストのデーモン撃破→アムリタ取得。 |
| 63～74 | 成功。最終開始Boss曲/バリア、0ダメージ/Amrita1行動/光/flash/shake/破壊/Final曲/無音でも進行/解除後ダメージ。 |
| 75～78 | 成功。各HP100/50/25%で10,000選択、全体技増加、3連続禁止、HP境界と進行。 |
| 79 | 成功。実際の最終ボス撃破→ENDING、撃破後フラグ/再戦防止。 |
| 80～86 | 成功。5パターンの実全滅、HP/技/Uses/ITEM/KeyItem/バリア復元、Boss→Amrita→Final曲の再現。 |
| 87～89 | 成功。Boss/Final曲再生例外と音声無効でも、描画・行動・次コマンド/結果へ進む。 |
| 90～95 | 成功（PCネイティブ）。通常1000＋ボス7種各100のCOMMAND READY、入力/表示、native playm呼出禁止。GKD実機は未確認。 |
| 96～102 | 成功。62技/RARE20/LEGEND8、性能・Spark・MASTERED・RESTORE不変、992挙動一致。 |
| 103～107 | 成功。Persistent Poison、マヒ50%、CURE/REMEDY、泉HPのみの既存回帰。 |
| 108～111 | 成功。Quest/TRZ/SAVE/旧v1 LOAD。別プロセスwrite/advance/readも一時フォルダで成功。 |
| 112 | 成功。B1～B15を含むpyxres/pyxpal全バイト一致。マップ構造・石碑文章は無変更。 |

全112ケースを上の範囲でカバーした。「成功」は検証範囲内の結果であり、未実施の物理端末テストを成功としていない。

## 再実行と証拠ファイル

```text
python -B -X utf8 -m unittest discover -s tests
python -B -X utf8 tools/verify_enemy_balance.py
python -B -X utf8 tools/verify_enemy_balance_runtime.py
python -B -X utf8 tools/verify_final_chapter.py
python -B -X utf8 tools/verify_save_compatibility.py
python -B -X utf8 tools/build_web.py
python -B -X utf8 tools/build_gkd.py
python -B -X utf8 tools/build_gkd_diagnostic.py
python -B -X utf8 tools/verify_web_build.py
python -B -X utf8 tools/verify_audio_distribution.py
```

`enemy_balance.json`：全18体・各フロア・各攻撃・実戦・各ボス実測/組合せ。`enemy_balance_runtime.json`：1700開始・全体文字範囲487,150描画・無音進行。`enemy_balance_all_tests.txt`：555件の実行結果。`enemy_balance_browser_{running,unavailable}.json`：PC/Touch×音声2条件。`final_chapter.json`：B10→ENDINGと5回の全滅/復元。`phase7c_pc_save.json`：別プロセスSAVE/LOAD。`audio_pass_packages.json`：配布3種の全ファイル一致。`screenshots/balance_*.png`：開始・光・flash・shake・破壊の実描画6枚（スクリーンショットはgitignore対象）。

今回開始時に対する保護対象 **54ファイル全てSHA-256一致**。診断ツールとWeb Audio復帰JSも無変更。既存セーブの削除・編集は行っていない。
