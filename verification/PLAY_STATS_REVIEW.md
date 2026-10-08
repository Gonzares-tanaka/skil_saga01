# 拠点TRZ統一・TOTAL BATTLES実装報告

拠点TOPを含む5画面のTRZを共通ヘッダー右上へ統一し、正式な戦闘開始回数を`Session.total_battles`へ記録しました。GUILD → PARTY STATUSから確認できます。SAVE/LOADは未実装です。

## 指定23項目の報告

| # | 項目 | 実装・確認結果 |
|---|---|---|
| 1 | TRZ統一画面 | BASE / TOWN HUB、GUILD / BASE、TRAINING / BASE、PUB / BASE、SHOP / BASEの各TOP。購入等の詳細画面にある既存の価格説明は維持。 |
| 2 | 共通描画 | 既存`rpg/dungeon_app.py`の`draw_banked_trz()`を拠点TOPでも再利用。定数は`rpg/hub.py`。右端156、Y=2、最大64px。値の文字幅で右揃えするため、同じ残高ならX/Yとも同じ。 |
| 3 | 旧位置 | 拠点TOPの画像下Y=100のTRZを削除。既存の画像下の戦闘終了回数表示も外し、冒険歴はPARTY STATUSへ集約。画像・メニュー位置は変更なし。 |
| 4 | 表示形式 | `TRZ 3`。BANKEDは表示しない。残高は従来の`treasure.banked`を参照。 |
| 5 | total_battles定義 | `rpg/battle.py`の`Session.__init__()`に単純な整数として保持。 |
| 6 | NEW GAME | 新規Session生成時に0。再度NEW GAMEでも0。 |
| 7 | 加算箇所 | `Session.next_battle()`で有効なBattleの生成が成功した後に`self.total_battles += 1`。 |
| 8 | 二重加算防止 | 本体の加算は上記1箇所だけ。ターン・敵行動・settle・結果送り・探索/HUB帰還には加算なし。開始前検査で拒否した戦闘も加算しない。 |
| 9 | 通常戦 | 1回開始で0→1。3ターン経過・settleを繰り返しても不変。2戦目開始で+1。 |
| 10 | QUEST戦 | 既存`begin_encounter(quest_hunt=True)`から共通開始処理を通り+1。QUESTの目的・報酬・記録は変更なし。 |
| 11 | ボス戦 | B5、B10、デーモン、ロードオブエリシオンの各開始で+1。既存ボスデータを使用。 |
| 12 | 守護者3連戦 | guardian_index 0/1/2それぞれで+1、合計+3。 |
| 13 | RUN | 戦闘開始で既に1加算されており、逃走成功で減らさない。逃走時の追加加算もなし。 |
| 14 | 全滅 | settle・通常全滅帰還で累計値を減らさない。 |
| 15 | 最終戦再挑戦 | チェックポイント本体の明示的な復元フィールドにtotal_battlesを追加しないことで累計を保持。本体は変更していない。再戦も`Session.next_battle()`で+1。配布版の実際の5連続全滅/再挑戦で20→21→22→23→24→25を確認。 |
| 16 | PARTY STATUS位置 | 共通の`App.draw_info()`でX=5、Y=15の既存戦績行を`BATTLES n ...`へ変更。キャラクター能力・スキル・履歴の配置は維持。QUEST RECORDや右上ヘッダーには戦闘回数を追加しない。 |
| 17 | 将来SaveData | `"total_battles": session.total_battles`を保存し、LOAD時は保存値を復元する。既存completed/wins/losses/drawsとは別項目。今回SAVE/LOADのコードは追加していない。 |
| 18 | バランスへの影響 | 本体での参照は初期化・開始加算・情報表示の3箇所だけ。敵・乱数・能力・成長・閃き・報酬の計算には使用しない。同一seedで累計0と10000のSessionを比較し、敵・行動後能力・乱数状態が同じことを検証。 |
| 19 | SAVE / LOAD | 未実装のまま。ダミー項目・自動保存・B5/B10到達時の自動記録も追加なし。 |
| 20 | PC | Python 3.13.7 / Pyxel 2.9.9のheadless実Pyxelで描画・仮想D-PAD/A/B操作・スクリーンショット確認。全205ユニットテスト成功。PC通常ウィンドウでの手動操作は未実施。 |
| 21 | Web | `dist/game.html`を再生成。埋め込みコード・資源一致検査後、抽出した配布ペイロードで同じTRZ/戦闘回数/RETURN/QUEST/最終章検証に成功。実ブラウザ上の手動確認とは区別する。 |
| 22 | スマートフォン | D-PAD/A/Bだけで情報表示・B帰還でき、既存タッチ6ボタン・音声復帰コードが配布版にあることを確認。iOS/Android実機の表示・ロック復帰試験は未実施。 |
| 23 | 既知の問題 | 検証範囲で新たな表示重なり・二重加算・チェックポイント巻き戻しは検出なし。実機ブラウザ確認は残る。SAVE未実装のため終了すると累計も消える。勝敗・引分等の既存集計は従来仕様のままで、チェックポイントに復元される値と、復元されない累計開始回数は別物。 |

## 必須CASE 1～32

| CASE | 確認結果 |
|---|---|
| 1 | 成功：BASE / TOWN HUBの右上にTRZ。 |
| 2 | 成功：GUILDの同位置にTRZ。 |
| 3 | 成功：TRAININGの同位置にTRZ。 |
| 4 | 成功：PUBの同位置にTRZ。 |
| 5 | 成功：SHOPの同位置にTRZ。 |
| 6 | 成功：拠点TOPのTRZ文字列は1つだけ。旧位置は削除。 |
| 7 | 成功：実フォント幅でタイトルとの非重複・画面内収まりを検査。DEBUG付きタイトルでも確認。メニュー・操作説明は別のY領域。画像も変更なし。 |
| 8 | 成功：実際のSHOP購入と未確定5 TRZの安全帰還後、現在のbanked値に追従。 |
| 9 | 成功：NEW GAME初期値0、再開始でも0。 |
| 10 | 成功：通常戦開始0→1。 |
| 11 | 成功：1戦で3ターン経過しても1のまま。 |
| 12 | 成功：2戦目の開始で2。 |
| 13 | 成功：実際の逃走成功処理後も戦闘開始分を保持。 |
| 14 | 成功：DEFEATのsettleと通常全滅帰還で保持。 |
| 15 | 成功：QUEST討伐戦で+1。 |
| 16 | 成功：守護者0/1/2で合計+3。最終章通し検証でも既存連戦が正常。 |
| 17 | 成功：デーモン戦で+1。 |
| 18 | 成功：最終戦で+1。 |
| 19 | 成功：最終戦再戦の度に+1。専用UI検証3回、実戦通し検証5回。 |
| 20 | 成功：復元直後は累計不変、続く正式戦闘開始で+1。 |
| 21 | 成功：GUILD→PARTY STATUSにBATTLES 12を表示するfixtureを確認。 |
| 22 | 成功：全種別と再挑戦を経た実際の累計値を参照。 |
| 23 | 成功：既存戦績行の置換だけで、能力・スキル・履歴枠の座標は維持。スクリーンショットを目視確認。 |
| 24 | 成功：BでGUILDへ戻る。 |
| 25 | 成功：TRZ増減コード・価格/報酬データは変更なし。既存テスト成功。 |
| 26 | 成功：9カテゴリの現地達成/RETURNと27件記録・お礼・報酬を回帰検証。 |
| 27 | 成功：探索メニューとSKILLS両方からのRETURNを配布版でも検証。 |
| 28 | 成功：既存通常戦闘テストと開始/ターン/逃走を検証。 |
| 29 | 成功：B5/B10/守護者/デーモン/最終戦開始、配布版B10→ENDINGと5連続全滅再戦を確認。 |
| 30 | PCの自動描画・操作・主要画像の目視確認成功。通常ウィンドウでの手動操作は未実施。 |
| 31 | 配布Webペイロードの自動描画・操作検証成功。実ブラウザ上の手動確認は未実施。 |
| 32 | 仮想D-PAD/A/Bで操作完結。スマートフォン実機表示は未確認。 |

## 変更範囲・証跡

今回開始時の52ファイルをSHA-256比較し、本体の変更は`rpg/battle.py`、`rpg/app.py`、`rpg/dungeon_app.py`だけです。`play_stats_preservation.json`に結果を記録しています。QUEST本体・全JSON・マップ・画像・パレット・音源・FINAL BATTLE CHECKPOINT本体は変更していません。スコープ内でREADME、検証コード・証跡、Web生成物を更新しています。

専用統計検証では対象階・討伐地点・終了状態を設定するfixtureを使用しています。別の最終章通し検証は既存の強化パーティfixtureから実際のB10→ENDING・5連続全滅/再挑戦を進めており、敵データや数値バランスは変更していません。音声APIが利用できない状態でも検証が完了しています。

主な検証：

```bash
python -m unittest discover -s tests
python tools/verify_play_stats_ui.py
python tools/verify_hub_ui.py
python tools/verify_pre_save_ui.py
python tools/verify_phase6d_ui.py
python tools/build_web.py
python tools/verify_web_build.py --play-stats --pre-save-ui --quest-records --final-chapter
```

今回使用した同梱Pythonはカレントディレクトリが自動でモジュール検索対象にならないため、ユニットテストは`sys.path.insert(0, '.')`を指定して実行しています。

結果：全205テスト成功、UI検証・配布版検証もすべて成功、`git diff --check`で空白エラーなし。

証跡JSON：`play_stats_ui.json`、`web_play_stats_ui.json`、`web_final_chapter.json`。画像：Git対象外の`verification/screenshots/play_stats_*.png`。
