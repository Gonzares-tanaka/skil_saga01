# Enemy Identity / Sprite Consistency Fix

確認日: 2026-10-11

今回のゲーム変更は、定義から生成したEnemyの固定ID設定とB15守護者3体のSprite参照変更のみ。敵追加、能力、AI、抽選、報酬、イベント判定、SAVE形式の変更は行っていない。既存の未コミット変更はそのまま保持した。

## 完了報告（指定27項目）

1. **空IDの原因**: `Enemy.id`の既定値は空文字。`Dungeon.make_enemies`と`Session.next_battle`の単独戦闘経路が定義の`id`をコンストラクタへ渡していなかった。
2. **修正した生成経路**: 通常ダンジョン、B5/B10、守護者1～3、デーモン、単独戦闘。既にIDが正しかったHUNTと最終ボスも共通生成処理へ接続した。
3. **共通処理**: `rpg/models.py`の`Enemy.from_definition(row, **overrides)`へ集約。名前・能力の既存補正を受け取り、IDは必ず`row['id']`から設定する。抽選や補正式は呼び出し元に維持。手動のテスト用Enemyコンストラクタは従来どおり使用可能。
4. **通常敵ID**: 全11種類を確認。slime、bat、goblin、wisp、golem、skeleton、mage、iron_golem、berserker、assassin、stone_beast。A～Dの表示名接尾辞と同種複数編成でも固定IDを保持する。
5. **B5 ID**: `guardian`を確認。
6. **B10 ID**: `skill_keeper`を確認。
7. **守護者ID**: `sentinel_armor` → `sentinel_speed` → `sentinel_mind`の生成順と各IDを確認。
8. **デーモンID**: `depth_lord`を確認。
9. **HUNT ID**: 保存された`hunt_enemy_id`と生成されたEnemy.idが一致。通常敵定義と既存のHUNT補正を継続使用。
10. **最終ボスID**: `lord_of_elysion`を確認。IDに基づく最終戦・バリア判定を維持。
11. **sentinel_armor**: SpriteをGOLEM `(64,16)`からKNIGHT `(112,16)`へ変更。
12. **sentinel_speed**: SpriteをSKELETON `(80,16)`からCYCLOPS `(144,16)`へ変更。
13. **sentinel_mind**: SpriteをMAGE `(96,16)`からDRAGON `(160,16)`へ変更。
14. **守護者1の画像**: Image Bank 0の既存KNIGHT画像、16×16を参照。画像領域に実際の画素があることも確認。
15. **守護者2の画像**: Image Bank 0の既存CYCLOPS画像、16×16を参照。同上。
16. **守護者3の画像**: Image Bank 0の既存DRAGON画像、16×16を参照。同上。新画像は作成していない。
17. **B5画像維持**: `guardian`のKNIGHT `(112,16)`は変更なし。
18. **B10画像維持**: `skill_keeper`のCYCLOPS `(144,16)`は変更なし。
19. **デーモン画像維持**: `depth_lord`のDEMON `(192,16)`は変更なし。
20. **最終ボス画像維持**: `rpg/final_presentation.py`と`data/final_battle.json`は変更なし。実際の描画呼び出しでImage Bank 0 `(144,64)`、48×48を確認。game.pyxresのハッシュも一致。
21. **能力維持**: 全18件の定義を修正前と比較。差は守護者3件のspriteのみ。HP/STR/DEF/AGI/INT/MDEF/magic_chance、表示名、ID文字列、その他の定義値は完全一致。生成結果315体でも許可されたIDと守護者sprite以外に差はない。
22. **AI維持**: 敵行動処理を変更していない。物理/魔法の選択、対象選択、行動回数、行動順は従来どおり。表示には引き続きnameを使う。名前を最終ボス名へ変えた通常敵でも最終戦判定にならない専用テストが通過。
23. **出現率維持**: dungeon.jsonは修正前と同一。敵候補、weight、敵数、倍率、遭遇率に変更なし。B5/B10通常遭遇あり、B15通常遭遇なしの回帰確認も通過。
24. **HUNT維持**: 対象選択、強化式、報酬、SAVE項目に変更なし。Lv1～3で受注→SAVEデータ生成→LOAD→HUNT敵生成を確認。表示名変更後も保存IDで継続可能。
25. **SAVE維持**: `rpg/save.py`は修正前と同一、SAVE_VERSION=1のまま。修正前の実装でメモリへ記録したLv1～3のHUNTセーブを修正後にLOADし、再生成したSaveDataの完全一致と討伐敵生成を確認。プレイヤーのセーブは読み書きしていない。
26. **回帰テスト**: 下記をすべて通過。
27. **既知の問題**: 今回の変更に由来する不具合は自動検証では検出されなかった。スマートフォン、GKD Pixel2の実機確認と実ブラウザ上での再プレイは未実施。Web確認は埋め込みパッケージの内容照合と、そのパッケージを実際のデスクトップPyxelで実行する検証。

## 実行した検証

- `python -B -X utf8 -m unittest discover -s tests`: **286件成功**。今回追加した専用6件を含む。ボス進行、HUNT、SAVE/CONTINUE、最終戦チェックポイントと再挑戦の既存テストも通過。
- 修正前後比較: **138組 / 315体**。通常生成15階×8seed、B5/B10/デーモン、守護者3体、HUNT Lv1～3、単独戦闘8seed、最終ボス。B15の通常生成関数の直接呼び出しは比較用であり、B15の通常遭遇を有効にしたものではない。
- 全18敵定義: 変更は守護者3体のspriteだけ。
- 変更対象外40ファイル: ハッシュ一致。マップ・画像・音声リソース、出現設定、SAVE、イベント判定、最終ボス専用描画などを含む。
- 修正前形式のHUNTセーブ: Lv1 goblin / Lv2 assassin / Lv3 assassin、すべてLOAD後の保存値一致と敵ID一致。
- `tools/verify_final_chapter.py`: B10→B11～B15→守護者3連戦→泉→デーモン→アムリタ→拠点→最終イベント→最終戦→ENDING成功。同じSessionで進行。5種類の実際の全滅と再挑戦が成功。最終部分はD-PAD/A/Bのみ、無音状態で検証。
- `tools/build_web.py`: `dist/game.html`を更新。
- `tools/verify_web_build.py`: 埋め込みコード/JSON/画像/音声が最新版と一致。パッケージ内の実際のPyxelを使った入力、無音での守護者、アムリタ、バリア、再挑戦、ENDINGの確認が成功。

## 今回のソース変更

- `rpg/models.py`: 共通生成メソッド。
- `rpg/dungeon.py`: ダンジョン敵を共通メソッドで生成。
- `rpg/battle.py`: 単独戦闘敵を共通メソッドで生成。
- `rpg/exploration.py`: 既存HUNT生成を共通メソッドへ接続。
- `rpg/final_battle.py`: 既存最終ボス生成を共通メソッドへ接続。チェックポイントは変更していない。
- `data/enemies.json`: 守護者3体のSprite座標だけを変更。
- `dist/game.html`: 上記を含むWeb配布データを再生成。
- `tests/test_enemy_identity.py`: 生成経路、名前分離、画像、HUNT SAVE/LOAD、最終ボス専用描画の専用回帰テスト。

既存の画像そのもの、敵名、ID文字列、敵総数18件は維持。
