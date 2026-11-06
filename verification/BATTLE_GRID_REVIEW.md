# 敵2×2配置・最大4体対応

2026-10-11。16×16の通常敵を左上(22,18)、右上(50,18)、左下(22,42)、右下(50,42)へ配置しました。下段の下端はY58、背景帯はY64からで6px空きます。敵選択カーソル、スキル効果、撃破の点滅・沈みも同じ`enemy_position()`を使います。倒した敵の枠は詰めません。味方の状態アイコンX66以降へも重なりません。単体敵・ボスは既存位置、ロードオブエリシオンは専用描画を維持します。

位置の編集場所：`rpg/battle_presentation.py`の`ENEMY_GRID_POSITIONS`。出現人数：`data/dungeon.json`の`count`。従来[2,3]だったB2～B4/B9/B11～B14を[2,4]にし、B5/B10の通常遭遇も直前階の設定を引き継ぎます。[1,2]の階と単体ボスは維持し、B15の通常ランダム遭遇なしも維持しました。出現率、候補の重み、HP/攻撃等の倍率、技、成長、SAVEは変更していません。ダンジョン外の自動育成テスト用編成は従来の2～3体のままです。

全280テストPASS（122.597秒）。追加5件で4体の描画範囲、4体すべてのカーソル/効果位置、4体目の選択、撃破時の枠維持、4体生成と5体設定の拒否、単体位置維持を確認。古い背景テストは「仮画像のpixelが0」という前提を外し、編集済みの画像pixelと描画結果を比較するようにしました。実Pyxelで3体/4体/4体目選択の画像を生成し、54回の文字範囲チェックと目視確認を実施しました。

画面：`verification/screenshots/battle_grid_three.png`、`battle_grid_four.png`、`battle_grid_fourth_target.png`。実Edge/PyodideのPCキー・Pixel 7タッチエミュレーションは両方PASS。結果は`verification/battle_presentation_browser.json`の`four_enemy_grid`と`fourth_target_selected`を参照。音声をsuspendしresumeを失敗させた状態でも4体表示/選択、戦闘継続、KO、RUN、SAVE/CONTINUEが正常でした。スマートフォン/iOS/GKD実機は今回利用できていません。

保全：`verification/battle_grid_preservation.json`。作業開始時点と終了時点で`game.pyxres`、`area2.pyxres`、`area3.pyxres`、各パレット、音源、既存画像、敵/技/成長設定のハッシュが一致。ユーザーが描いた背景を作り直したり上書きしたりしていません。

`dist/game.html`とGKD用ZIPを更新し、埋め込みPython/データ/マップが最新ソースと一致することを確認しました。GKD ZIPはゲーム55ファイルとランチャーのみ、SAVEを含まず、Python 3.11構文確認PASSです。commit/pushは実施していません。

再実行：`python -m unittest discover -s tests`、`python tools/verify_battle_grid.py`。Web生成は`tools/build_web.cmd`。
