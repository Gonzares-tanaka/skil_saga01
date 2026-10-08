# SAVE / LOAD前のUI整理報告

GUILDのHELPとTRZの重なりを解消し、4項目まで使える施設TOP配置へ整理しました。探索メニューの項目名はRETURNに統一し、SKILLS一覧からも同じ既存RETURN使用処理へ接続しました。SAVE/LOADは追加していません。

## 指定19項目の報告

| # | 項目 | 実装・確認結果 |
|---|---|---|
| 1 | GUILDのTRZ表示 | 下部Y=100の`BANKED TRZ ...`を削除。ヘッダー右側に`TRZ 3`の形式で確定残高だけを表示。 |
| 2 | 座標・共通処理 | `DungeonApp.draw_banked_trz()`をGUILD/TRAINING/PUB/SHOPの施設TOPで共用。`rpg/hub.py`の右端156、Y=2、最大幅64pxを参照し、実フォント幅で右揃え。極端な桁数では表示のみ省略し、残高値は変更しない。購入等の詳細画面の既存価格表示は維持。 |
| 3 | GUILD配置 | メニューX=8、開始Y=43、間隔17。現在はPARTY STATUS、QUEST RECORD、HELPがY=43/60/77。画像64×64は既存位置のまま。 |
| 4 | 将来SAVE用余白 | 4項目でもY=43/60/77/94、選択背景の下端は106でフッター開始111より上。テスト中だけSAVE行を挿入して描画・目視確認。本体にはダミーSAVEを追加していない。 |
| 5 | RETURN表記 | 探索メニューの`RETURNで帰還`を`RETURN`へ変更。他のメニュー名・順序は維持。 |
| 6 | ショートカット呼び出し先 | `open_return_skill()` → 既存の`field_return`使用者選択 → `Session.field_return(actor_index)`。 |
| 7 | SKILLS側との共通化 | 探索中のSKILLSでRETURN選択時も`open_return_skill()`へ接続。同じ使用者選択・使用分岐・安全帰還経路を通る。SKILLSで見ていたキャラクターを初期選択し、Bで元の一覧・選択位置へ戻る。別のUses消費処理は作っていない。 |
| 8 | Usesの扱い | 既存`Session.field_return()`が1回だけ消費。通常取得3回・再習得1回等のデータは変更なし。最後の1回で既存どおり消滅・DISCOVERED/MASTERED記録。選択画面に`USES n`と「所持する技のUsesを1回消費」を表示。 |
| 9 | 未所持 | 一覧に使用不可。Aでも「生存者の使用可能なRETURNが必要です。」という既存エラーで留まり、無料帰還・TRZ確保は発生しない。 |
| 10 | 使用不能時 | Uses 0・戦闘不能・未所持は既存スキル検査で拒否。守護者連戦は既存UI制限、戦闘中・ボス戦中は既存戦闘/スキル処理で拒否。失敗時はUses・TRZを消費しない。 |
| 11 | HELP | 「RETURN:有限Usesの帰還スキル」「探索メニュー/技一覧から使用」を表示。既存文字数に収まるようHELP行間を9pxに調整。SKILLSフッターのAは「使用/頁」に整理。 |
| 12 | 安全帰還 | 成功後も既存`enter_camp(returned=True)`を呼ぶ。未確定TRZの確定・HP回復のルールは変更なし。 |
| 13 | QUEST完了 | 既存の安全帰還判定 → お礼 → 正式完了/報酬 → HUBをそのまま使用。未確定TRZ5・初期確定3のfixtureで、帰還直後8、報酬後8+既存報酬、CLEAR1・固有ID1件を両経路で確認。二重更新なし。 |
| 14 | TRZロジック | `rpg/treasure.py`、初期値、価格、報酬JSONは変更なし。今回の変更は表示・呼び出し経路だけ。 |
| 15 | SAVE / LOAD | 未実装のまま。SAVE項目も追加なし。 |
| 16 | PC確認 | Python 3.13.7 / Pyxel 2.9.9のheadless実Pyxelで描画・仮想D-PAD/A/B入力を検証。GUILDの文字矩形の相互非重複、全画面の160×120内収まり、主要スクリーンショットを確認。全202ユニットテスト成功。通常ウィンドウでの手動操作は未実施。 |
| 17 | Web確認 | `dist/game.html`再生成。埋め込み資源・コード・JSON一致を確認し、配布ペイロードを抽出して同じGUILD/RETURN UI検証と27件QUEST記録検証を実行、成功。既存の無音最終戦・再挑戦・ENDING確認も成功。実ブラウザ上の手動操作は未実施。 |
| 18 | スマートフォン確認 | D-PAD/A/Bだけで操作が完結することを自動検証。既存HTMLのタッチ6ボタンと音声復帰処理の存在を検査。iOS/Android実機の表示・画面ロック復帰試験は未実施。 |
| 19 | 既知の問題 | 検証範囲で新たな重なり・二重消費・二重報酬・帰還不整合はなし。ブラウザ/スマートフォン実機確認は残る。SAVE未実装のため終了時に進行・記録は保存されない。 |

## 必須CASE 1～21

| CASE | 結果・確認方法 |
|---|---|
| 1 | 成功：GUILDの3項目を描画。 |
| 2 | 成功：HELPとTRZは別領域。GUILDの文字矩形全組合せで重なりなし。 |
| 3 | 成功：TRZはY=2、操作説明はY=112。 |
| 4 | 成功：初期確定3を`TRZ 3`と表示。未確定残高を使用しない。 |
| 5 | 成功：STATUS・QUEST RECORD・HELPをD-PAD/Aで選択。 |
| 6 | 成功：全3サブ画面からBでGUILDへ戻る。 |
| 7 | 成功：テスト専用4行fixtureでSAVEを含む配置が収まる。本体は3行。 |
| 8 | 成功：探索メニューは従来順でSTATUS・SKILLS・ITEM・RETURN・HELP。前後の日本語補足は従来どおり。 |
| 9 | 成功：所持RETURNがSKILLS一覧に残り、Usesを表示。 |
| 10 | 成功：ショートカットから3→2、1→消滅を確認。 |
| 11 | 成功：SKILLSからも同じ結果。両経路の技能一覧・残数・MASTERED・残高・QUEST記録を比較。 |
| 12 | 成功：最後のUsesで消滅・MASTERED。既存ユニットテストでも確認。 |
| 13 | 成功：未所持で帰還せず、残高不変。 |
| 14 | 成功：Uses 0・戦闘不能・守護者連戦・ボス戦の拒否。通常戦闘の拒否は既存ユニットテストで確認。 |
| 15 | 成功：両経路のRETURNからTRZ確保・QUESTお礼・報酬・記録・HUBへ正常遷移。 |
| 16 | 成功：共有スキル処理の呼び出しは1回、Uses消費1回、QUESTとTRZ更新も1回。 |
| 17 | 成功：既存5施設の操作・SHOP購入・PUB情報・TRAINING・DUNGEON接続を回帰検証。 |
| 18 | 成功：QUEST RECORDのB帰還と全27件100%表示を配布ペイロードでも確認。内容・分母は変更なし。 |
| 19 | 自動描画・目視検証成功。PC通常ウィンドウの手動操作は未実施。 |
| 20 | 配布ペイロードの自動描画・操作検証成功。実ブラウザ確認は未実施。 |
| 21 | 仮想ゲームパッドだけでの操作検証成功。スマートフォン実機表示は未確認。 |

## 保護対象・検証証跡

今回開始時の本体・データ・資源52ファイルをSHA-256で比較し、変更は`rpg/dungeon_app.py`と`rpg/hub.py`のみです。比較結果は`pre_save_ui_preservation.json`を参照してください。QUEST処理・フレーバー・固定ID、TRZ・価格・報酬、スキルデータ、成長、戦闘、マップ、画像、パレット、最終章・チェックポイント、BGM/SEは変更していません。

実行した検証：

```bash
python -m unittest discover -s tests
python tools/verify_pre_save_ui.py
python tools/verify_hub_ui.py
python tools/verify_feedback_ui.py
python tools/verify_phase6d_ui.py
python tools/build_web.py
python tools/verify_web_build.py --pre-save-ui --quest-records
```

全ユニットテスト202件成功。既存UI検証も成功。新しいRETURN検証では、所持者・Uses・QUEST目的達成を設定するfixtureを使用しています。実際のマップ上での目的達成・討伐・RETURNは既存Phase 6Dの9カテゴリ通し検証で確認しています。

証跡は`pre_save_ui.json`、`web_pre_save_ui.json`、`web_quest_records_ui.json`。主要画像はGit対象外の`verification/screenshots/pre_save_*.png`です。4項目画像のSAVEはテスト時だけの仮挿入であり、本体には表示されません。
