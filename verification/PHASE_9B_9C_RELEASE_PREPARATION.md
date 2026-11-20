# PHASE 9B・9C 正式リリース最終調整

対象：Skill Seekers!! ～深淵のアムリタ～ Ver.1.0

完了日：2026-11-20（日本時間）

判定：**READY FOR DEVICE TEST**

PH9-001を修正し、ローカルの正式版配布準備を完了した。公開サイト自体の更新、Git commit・pushは実施していない。iOS Safari・GKD Pixel 2の実機確認はユーザーによる次工程。

## 1. PH9-001の修正内容

`rpg/postgame_ui.py:35`に`restore_final_victory()`を追加し、クリア保存候補の生成時だけ呼び出すようにした。

従来は最終戦精算後に決戦前チェックポイント全体を復元していたため、表示した成長・MASTEREDまで保存候補から消えていた。修正後は、勝利後の永続成果をコピーしてから既存の決戦前復元を行い、保存用の別オブジェクトへ成果を戻す。

**通常戦闘・成長判定・最終戦敗北時の復元処理は変更していない。** `rpg/battle.py`、`rpg/final_battle.py`、通常SAVE/中断の実装と形式、データ・アセットは従来どおり。

## 2. 最終戦の成長・MASTERED保持方法

勝利後の最大HP・STR・AGI・INT、成長/使用/習得履歴、DISCOVERED、MASTERED、習得スキル構成、保持中コピーの習熟補正区分を保存する。勝利の戦闘記録も保持し、既に確定した成果を加算し直す方式にはしていない。

監査時と同じseed909・テスト用HP650/能力80・三段斬りUses1の戦闘を再実行した結果：

| 項目（ロウ） | 決戦前 | 勝利結果 | 修正後のSAVE/CONTINUE |
|---|---:|---:|---:|
| 最大HP | 650 | 652 | 652 |
| STR | 80 | 81 | 81 |
| AGI | 80 | 81 | 81 |
| INT | 80 | 81 | 81 |
| 三段斬りMASTERED | 未達 | 達成 | 達成を保持 |

ほかの3人の当該勝利の成長も、実行時と保存値が一致。MASTERED消失は0件。[再現条件による修正確認](phase9bc_rewards.json)。初期能力の自然成長値を示す表ではなく、監査と同じ固定条件による比較である。

## 3. 最終戦後の消耗資源の復元方式

| 対象 | 処理 |
|---|---|
| 現在HP | 決戦前の現在HPへ復元。最大HP成長分まで全回復する処理ではない |
| 残っている決戦前のスキル | 同じ保持コピーのUsesを決戦前の値へ復元 |
| 使い切って消えたスキル | 消滅結果を維持。MASTERED履歴は残す。自動で旧技を復活させない |
| 入替で外したスキル | 復活させない。勝利後に確定した構成を維持 |
| 新しく閃いたスキル | 通常の閃きで得たUsesを維持。決戦前のUsesと合算しない |
| 同じIDを使い切り後に再取得 | 別の新しいコピーとして扱い、そのコピーの実際のUsesを維持 |
| 通常ITEM・TRZ | 既存チェックポイントの値へ復元。勝利ごとの補充数を足し込まない |
| アムリタ | 再挑戦可能な所持状態へ復元。次の最終戦は障壁あり |
| 本編クリア・ドラゴン記録・QUEST履歴 | 最新記録を保持 |

コピーの区別には、当該戦闘の既存`used_skills`と決戦前のUsesを使う。例えば決戦前Uses1を当該戦闘で1回以上使用済みなら、同IDが再び存在しても古いコピーのUses1へ戻さない。日本語メッセージの文字列解析やSAVE形式への新規フィールド追加は行っていない。

**構成は勝利後を優先し、消滅/入替で空いた枠へ旧技を足し戻さない。** これにより同一IDの重複・6枠超過を防ぐ。未習熟コピーを保持している別キャラクターへ、全体MASTERED登録だけを理由に威力1.2倍を遡及適用することもない。★の履歴判定は従来どおり。

## 4. 保存失敗・再挑戦・二重適用防止の結果

- 保存候補は分離したオブジェクトで生成し、実行中パーティ・チェックポイントを変更しない。
- 保存に失敗すると旧SAVEを維持。再試行は同じ確定済み保存候補を使い、成長・閃きを再抽選しない。
- 同一候補を繰り返し生成しても、能力・Uses・ITEM・TRZを加算しない。初回クリアのrun ID生成を除き同じ内容。
- 最終戦3回連続敗北では既存チェックポイントからHP・技・Uses・ITEM・TRZ・アムリタ・障壁を復元。その後の勝利成果を正しく保存。
- エンディング中のWeb再読込でも、既に保存された成果・クリア/ドラゴン記録から再開できる。

重点ライフサイクルでは、初回クリア→CONTINUE→通常戦闘15勝で育成→使い切りMASTERED→TRZで再取得→全9カテゴリQUESTと追加3回討伐→ドラゴン35ターン記録→最終戦3敗北復元→再勝利→CONTINUE→新規コントローラでLOADを実行。再戦前/再戦中双方の成長、習熟・発見・構成、ドラゴン記録、QUEST履歴を保持し、ITEM/TRZ増殖なし。[結果](phase9bc_lifecycle.json)。

この試験は終盤パーティの能力固定・座標移動・演出待ち省略を含む。戦闘計算は実処理だが、人によるNEW GAMEからの通常プレイ完走やiOS/GKD実機試験ではない。3連続敗北は消耗状態の障害注入を含み、敵に自然に倒されるまでを3回待ったものではない。

## 5. 新たに追加した回帰テスト

`tests/test_final_victory_save.py`に8件を追加。

| テスト | 確認する境界 |
|---|---|
| `test_growth_mastery_exhaustion_resources_continue_and_restart` | 実技消費・成長・MASTERED・Uses/HP/ITEM/TRZ復元・CONTINUE・新規起動LOAD |
| `test_full_six_replacement_survives_without_resurrecting_old_copy` | 6枠で新閃き、入替結果、旧技非復活、Uses非合算 |
| `test_declined_spark_keeps_discovery_but_not_loadout` | 閃き見送り時は発見だけ保持 |
| `test_exhaust_then_same_id_spark_uses_new_copy_even_when_already_mastered` | 新規MASTERED/既MASTERED両方の同ID再取得、コピー区別 |
| `test_party_wide_mastery_does_not_promote_an_existing_unmastered_copy` | 別キャラクターの既存コピーへ威力補正を遡及しない |
| `test_candidate_and_failed_save_retry_never_mutate_or_double_apply` | 候補生成の非破壊性、保存失敗の繰返し、旧SAVE保護、二重適用防止 |
| `test_three_defeats_restore_full_checkpoint_before_rewarded_win` | 3敗北復元・アムリタ・障壁・その後の勝利保存 |
| `test_repeat_clear_preserves_dragon_quests_and_adds_each_new_growth_only_once` | 再クリアの繰返し、成長1回分、ドラゴン/QUEST保持 |

成長・閃きの厳密な回帰ではテスト内だけ乱数/候補を固定し、実`settle()`・消費・`spark()`・入替・SAVEの検証を行う。製品の確率・数値は変更していない。

既存`tests/test_phase7.py`の「勝利後も能力を決戦前へ戻す」旧期待値を、勝利成果を保存する期待値へ更新。既存の保護テストには、新しい保存用関数・1箇所の呼出し差と承認済みライセンスコメントだけを許可し、その他のコード・データ保護を維持した。

## 6. 全自動テストの結果

PHASE 9B完了時、隔離コピーで`python -B -X utf8 -m unittest discover -s tests -v`を実行。

**781件成功 / 失敗0 / エラー0 / スキップ0、303.358秒。**

既存773件＋追加8件。[全ログ](phase9b_all_tests.txt)。末尾の`SUSPEND failed`は破損/書込失敗の障害注入で期待どおり拒否したログであり、テスト失敗ではない。

PHASE 9Cの権利コメント・文書更新後は、関連36件を再実行し全件成功、47.118秒。[最終関連テスト](phase9bc_final_focused.txt)。781件の全件実行は保存修正後に行い、その後の製品Python差分は`main.py`のライセンスコメントのみ。最終版の保存修正コードに追加変更はない。

PC終盤の実Pyxel描画16画面・実戦闘モデルも成功。[PC結果](phase9bc_native.json)。既存の最終章/探索補助ツール2本の旧仕様エラーは、単体テストの失敗件数へ混在させていない（11節参照）。

## 7. GitHub PagesのVer.1.0表記変更

`.github/workflows/deploy-pages.yml`は`dist`をそのまま公開し、`tools/build_web.py`は`dist/game.html`だけを生成する。したがって紹介ページの編集元は**`dist/index.html`**。

同ファイルのdescription、HTMLタイトル、タイトル付近edition、フッターの4箇所をVer.1.0へ更新。ゲームタイトル・ロゴ・画像・CSS・起動スクリプトは変更していない。再ビルドしても紹介文の変更は消えない。

ローカルHTTPでPC幅・Pixel 7タッチ幅を表示し、版表記・画像・横はみ出しなし・起動リンクを確認。[ページ確認結果](phase9bc_page.json)。**GitHub上の公開ページはまだ旧版のまま**であり、今回のローカル修正を公開済みとは扱わない。

## 8. 冒険のヒントへのMASTERED★説明追加

既存の「使い切ったSKILLは、MASTEREDへ」の説明と1.2倍の説明を残し、次の1段落だけを追加した。

> MASTERED済みのスキルは、技名の末尾に「★」が付きます。★は習熟の記録を表し、残り使用回数を示す記号ではありません。

ゲーム内の★はMASTERED履歴を示す現行実装に一致する。未MASTEREDにも付く、Usesを示す、既存コピー全てが即1.2倍になる、といった説明は追加していない。

[PC幅の描画](phase9bc_screenshots/desktop_mastered.png)、[スマホ幅の描画](phase9bc_screenshots/touch_mastered.png)を実際に確認。折り返し・文字重なりに問題なし。ほかのヒント、施設、操作、エレベータの片道説明、中断とQUEST説明は維持。

## 9. READMEの更新箇所

- Ver.1.0のローカル公開準備と、この報告への案内を冒頭へ追加。
- QUEST新規範囲を表で明記：探索B1～3/6～8/11～13、調査B2～4/7～9/12～14、討伐B3～5/8～10/13～14。
- B15は旧セーブの受注済みQUEST用候補を維持する説明へ修正。新規抽選と旧互換を混同しない。
- F9による遭遇45%の旧説明を削除。AREA1が7～16歩、AREA2/3が9～22歩のカウント方式、DEBUGでも同方式、B15通常遭遇なしを明記。
- 通常版のQ/F9/キーボードAオート無効、開発PCの`--debug`のみ有効を操作表でも統一。状態ページは左右切替、技一覧は全62件と記載。
- 権利表記は作者承認済みの内容に確定。過去PHASEの開発記録を無差別置換せず、その他のユーザー文章は維持。

ゲーム内QUEST、遭遇方式、カーソル、スキルを変更したものではない。

## 10. ライセンス・権利表記の確認事項

作者から「この表記で確定する」と明示承認を得て、`README.md`と`main.py`ヘッダを次の内容へ更新した。

`Copyright (c) 2026 GONZARES TANAKA. All rights reserved.`

ゲーム本体をMIT・CC等へ変更していない。Pyxel MITライセンス、美咲ゴシック第2の作者文書・利用条件、第三者通知、既存スタッフロールは変更せず全配布物に同梱。素材由来についてはPHASE 9時に作者が「自作・AI生成のみ（第三者素材なし）」と確認済み。

作品の権利表記に関する承認待ちは解消。第三者ランタイム・フォントの条件は作品の権利表記とは別に維持する。

## 11. 旧検証ツールの扱い

`verify_final_chapter.py`（通常F9開放前提）と`verify_expedition.py`（削除済み`safe_steps`参照）は今回は更新せず、開発用の残課題として維持。製品側のDEBUG制限や遭遇方式を元へ戻していない。

今回必要な検証は新規回帰8件、監査再現スクリプト、重点ライフサイクル、実ブラウザで実施した。`tools/verify_phase7.py`と`tools/verify_browser_phase7.py`だけは、「クリアSAVEが常に決戦前能力と一致する」という旧期待値を、**勝利成果を含む確定SAVEとCONTINUEの一致**へ追従させた。旧ツール2本を成功扱いしたものではない。

## 12. PC・Web・GKDの検証結果

| 環境/項目 | 結果と限界 |
|---|---|
| PC | Pyxel 2.9.9、実描画16画面・実戦闘モデル・通常SAVE/再起動LOAD・781単体テスト成功。headless検証であり、実窓を人が通し操作した試験ではない |
| Web通常音声経路 | Edge ChromiumのPC/タッチ両方で、保存失敗再試行・初回ENDING/EXTRA・CONTINUE・ドラゴン・再クリア・エンディング中再読込に成功 |
| Web音声不可 | AudioContext停止・resume失敗を注入しても、同じ経路を進行。JavaScript例外なし |
| Web中断 | 実IndexedDBで、B7位置/毒/TRZ等を復元、一度だけ消費、同時再開は1件、書込/削除失敗から復旧。通常SAVEは独立 |
| 紹介ページ | PC/タッチ幅のVer.1.0・★説明・画像・リンク・横はみ出しを確認 |
| GKD通常/診断 | 74ゲームファイルの内容がPC/Webと一致、必要フォント/リソース/ライセンス同梱、Python 3.11文法検査成功 |
| iOS Safari/GKD実機 | **今回未確認**。ChromiumタッチエミュレーションをiOS実機試験と扱わない |

Webの戦闘/座標/演出時計はテスト用条件を含む。ストレージとキーボード/タッチ操作は実ブラウザ。音楽を人が聴いた確認ではない。

根拠：[通常音声Web](phase9bc_browser_ending_audio.json)、[音声不可Web](phase9bc_browser_ending_silent.json)、[中断](phase9bc_browser_suspend.json)、[紹介ページ](phase9bc_page.json)、[配布比較](phase9bc_packages.json)。

## 13. 更新した配布物

既存手順`tools/build_web.py`→`tools/build_gkd.py`→`tools/build_gkd_diagnostic.py`で再生成。権利表記承認後にも再生成し、最終の配布物へ反映済み。

| 対象 | 更新先 |
|---|---|
| PC | 現在のソース版`main.py`/`rpg/postgame_ui.py`。既存`run.cmd`で起動。新たなEXE化は行わない |
| Webゲーム | `dist/game.html` |
| Web紹介 | `dist/index.html` |
| GKD通常版 | `verification/packages/skill_seekers_gkd.zip`（76エントリ） |
| GKD診断版 | `verification/packages/skill_seekers_gkd_diagnostic.zip`（79エントリ） |

PC/Web/GKDの比較対象74ファイルは一致。配布用`DEVELOPMENT_BUILD=False`と起動/診断用ファイルの違いだけを許可。SAVE・tests・verificationの監査ファイル・キャッシュをゲームZIPに含めない。通常版と診断版のゲーム内容に差なし。

PHASE 9の85保護対象のうち、許可された7ファイル（製品コード1、権利ヘッダ1、README、Web2、ZIP2）以外の78ファイルはSHA256一致。スキル/成長/QUEST設定・敵・ドラゴン能力、マップ・画像・BGM/SE、SAVE形式/保存先、実ユーザーSAVEは変更なし。[最終ハッシュ結果](phase9bc_packages.json)。既存の変更済み検証JSON5件は今回の作業対象にしていない。

## 14. iOS・GKD実機で確認すべき項目

1. 最終戦で技を使い切ってMASTERED→勝利→CONTINUE→アプリ再起動LOAD。能力・MASTERED・構成が残り、HP/ITEM/TRZと残存技Usesが決戦前へ戻ること。
2. クリア後に育成・再取得・ドラゴン討伐→最終戦再クリア→再開。育成と最短記録を保持すること。
3. 最終戦でアムリタ・技・ITEMを消費して3連続敗北→再挑戦。アムリタ・障壁・消耗資源が復元すること。
4. 探索中に中断→再開→中断データが消費されること。通常SAVEが独立し、QUEST再受注が引き続き正常なこと。
5. iOSは探索中/戦闘中/ファンファーレ中に画面ロック→復帰→タップ→戦闘/勝利/ENDING。音声復旧失敗でも進行すること。
6. GKDは通常ZIPと診断ZIPの起動、SAVE互換、SELECT単独長押し終了、エンディングと再開を確認。既存の`save/`を削除・上書きしないこと。

## 15. 正式公開前の残課題

**READY FOR DEVICE TEST**。PH9-001の修正・回帰テスト・説明更新・配布準備は完了。

- iOS Safari・GKD Pixel 2の実機確認を実施する。
- 合格後に、ユーザーの別途指示でGit commit・push・GitHub Pages公開反映を行う。今回は実施していない。
- 旧補助ツール2本の追従と、PH9-004の内部「仮設定」メモ整理は開発用残課題。ゲーム数値や画像を変更する理由にはしていない。

新しいゲームシステムは追加していない。実ユーザーSAVEは試験に使用せず、隔離コピー・テスト専用ファイル・新規ブラウザプロファイルのみ使用した。
