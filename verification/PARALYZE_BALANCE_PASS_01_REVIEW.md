# PARALYZE BALANCE PASS 01

実施日: 2026-10-14

ゲームの変更は `data/statuses.json` の `paralyze.skip_chance: 0.35 → 0.50` のみ。
PLAYER / Enemy は既存の `Battle.prepare_turn()` → 共通 `control_decision()` → `Battle.step()` を使用する。
`rpg/` のコードは変更していない。失敗率の正式値は引き続きJSONに置き、別の麻痺処理は追加していない。
開始時点の未コミット変更を保持した。

## 変更ファイル

- ゲーム定義: `data/statuses.json`
- 説明: `README.md` の麻痺失敗率を50%に更新
- 新規試験: `tests/test_paralyze_balance.py`（10テスト）
- 既存保全試験: `tests/test_enemy_roster.py`, `tests/test_player_skill_roster.py`
  - 古い35%定義のハッシュを保持し、今回の `0.35 → 0.50` 一箇所だけを許可する比較を追加。
  - その他のバイト変更は引き続き失敗する。
- 検証ツール: `tools/browser_paralyze_balance_case.py`, `tools/verify_paralyze_balance.py`, `tools/verify_paralyze_freeze.py`
- 再生成配布物: `dist/game.html`, `verification/packages/skill_seekers_gkd.zip`
- 本報告および `verification/paralyze_balance_before.json`, `paralyze_balance.json`, `paralyze_balance_browser.json`, `paralyze_balance_freeze.json`, `paralyze_balance_tests.txt`

## 指定28項目の報告

| # | 項目 | 結果 |
|---|---|---|
| 1 | 変更ファイル | 上記の一覧。ゲームコードは無変更、バランス変更はJSONの一値のみ。 |
| 2 | PARALYZE旧失敗率 | 35%（0.35）。開始時点の定義を保存。 |
| 3 | PARALYZE新失敗率 | 50%（0.50）。乱数が0.5未満なら失敗、0.5以上なら通常行動。 |
| 4 | Duration | 3本人ターンを維持。成功・失敗とも本人ターンで減少、0で解除。 |
| 5 | PLAYER / Enemy共通 | 同じJSON定義・共通判定を参照。各10,000回の実Battle判定で確認。 |
| 6 | shock_stab付与率 | 30%のまま。スキル定義のハッシュも一致。 |
| 7 | thunder_bind付与率 | 45%のまま。スキル定義のハッシュも一致。 |
| 8 | Enemy PARALYZE Action付与率 | paralyze_grabは35%のまま。Action定義・weight・敵能力は無変更。 |
| 9 | 行動失敗時Uses | ターンを消費、Uses・使用記録・成長記録は非消費。SkillのDamage/Status/Visualなし。 |
| 10 | ITEM非消費 | 失敗時POTION在庫・対象HPは変わらず、ターンのみ消費。 |
| 11 | Cooldown非追加 | 失敗時Cooldownを設定しない。成功時は既存Cooldownを通常付与。 |
| 12 | SLEEP | 完全行動不能・実HPダメージで解除を維持。麻痺はDamageで解除されない。 |
| 13 | CONFUSION | 行動置換・抽選weight・資源非消費を維持。 |
| 14 | POISON | 本人ターンのDamage、探索持ち越し、歩行Damageなしを維持。Control Statusとの共存も維持。 |
| 15 | REMEDY回帰 | 麻痺を含む4状態の解除・BUFF/DEBUFF維持・KO/健常者への非消費を確認。 |
| 16 | CURE回帰 | 既存スキルの4状態解除・対象・HP/effects不変・無効時の資源非消費を確認。 |
| 17 | PURIFY WIND回帰 | 既存全体治療の4状態解除・生存対象・資源処理を確認。 |
| 18 | 62Skill回帰 | 62技を維持。BASIC 3 / COMMON 18 / UNCOMMON 13 / RARE 20 / LEGEND 8。元技、Uses、Cooldown、Power等の保全試験成功。 |
| 19 | Enemy回帰 | 通常18体＋Boss扱い7体を維持。Encounter Table・能力・Action Weight・Boss Resistance/Immunity無変更。 |
| 20 | SAVE回帰 | SAVE/LOAD・旧SAVE互換の既存テスト成功。save_version=1、schema無変更。Web localStorage roundtripも成功。 |
| 21 | Final Battle回帰 | 最終戦・Amrita barrier・チェックポイント・繰り返しRetry・Finaleの既存テスト成功。 |
| 22 | GKD native audio修正 | `rpg/sound.py` の開始前後ハッシュ一致。nativeでは編集済みチャンネル列を `pyxel.play()` で再生し、`playm()`を使わない既存試験成功。 |
| 23 | Battle開始Freeze Regression | 既存 `verify_gkd_freeze` のFORCED/identity_checks/run_trialsを再使用し、同じ26,400開始すべて成功。通常・無効・例外Audio、Transition bypass、COMMAND_READY、D-pad/A/B操作を確認。 |
| 24 | 自動テスト総数 / 成功数 | 全459/459テスト成功（既存449＋追加10）、失敗・エラー・skipなし。ブラウザは別途PC20/20、Touch20/20。開始ストレス試行は26,400/26,400。 |
| 25 | PC Browser | Edge Chromiumの実Pyodideで20/20ケース成功。50%境界・実Battle統計・状態異常演出・音声不可・SAVE/LOAD、ページエラー0。 |
| 26 | Touch Browser | Pixel 7設定のTouchエミュレーション、実Pyodideで20/20成功。実スマートフォン・iOS Safari・画面ロックは未検証。 |
| 27 | Pixel2用ZIP | 更新成功。61エントリ、ゲームファイル60件が現ソースと一致。50%設定を内包、SAVE/cache/test依存を除外、既存launcherを維持。 |
| 28 | 既知の問題 / 未確認 | この変更に起因する既知のゲーム不具合なし。GKD Pixel 2の実機体感は未検証。プロジェクト `.venv` の参照先Pythonが欠落しているため既存の別Python環境で試験。ブラウザの初回起動待ちタイムアウトは通信制限を解除した再試験で解消。 |

## 確率試験と必須ケース

固定Seed=501、許容範囲48～52%。PLAYER / Enemyそれぞれ10,000回、各試行で標準Durationを再付与し、実際のキューを `prepare_turn()` / `step()` で進めた。成功時のGUARD効果、失敗時の効果不発、キュー消費、Duration減少も毎試行検査した。実際の麻痺判定を置き換えていない。

| 実行環境 | PLAYER失敗 | Enemy失敗 |
|---|---:|---:|
| PC Python | 4,980 / 10,000 (49.80%) | 5,026 / 10,000 (50.26%) |
| PC Browser Pyodide | 4,980 / 10,000 (49.80%) | 5,026 / 10,000 (50.26%) |
| Touch Browser Pyodide | 4,980 / 10,000 (49.80%) | 5,026 / 10,000 (50.26%) |

統計に加え、0.35・0.499999で失敗、0.5・0.999999で成功する境界を両陣営で確認。previewを5回行っても同じ麻痺判定が再利用され、行動実行で追加の麻痺抽選をしない。

必須CASE 1–18は新規試験と既存Status試験、CASE 19–26はStatus/Persistent Poison/Skill Roster/Foundation試験、CASE 27–37はRoster/Enemy/Save/Final/Audioの既存試験と26,400開始試験で確認した。
Control Status排他・再付与・Icon/Visual・治療・KO・Battle終了処理はコードを変更せず回帰試験を実行した。

## 証跡と再実行

- `paralyze_balance_before.json`: 開始時点の定義と保全ハッシュ
- `paralyze_balance.json`: 許可された一値だけの変更、その他60ファイル一致、両配布物の全ソース一致、確率試験
- `paralyze_balance_tests.txt`: 全自動テストのログ
- `paralyze_balance_browser.json`: desktop / touch各20ケース、音声状態・エラー・確率試験
- `paralyze_balance_freeze.json`: 26,400回の既存開始回帰試験

試験環境: Windows / Python 3.12.14 / Pyxel 2.9.9。ブラウザはEdge Chromium / Pyodide。
今回使用したPythonは `C:\temp\mypyxel\adventure_test\.venv-verify\Scripts\python.exe`。

正常なPython / Pyxel 2.9.9環境から実行:

```powershell
python -m unittest discover -s tests -v
python tools/build_web.py
python tools/build_gkd.py
python tools/verify_paralyze_balance.py
python tools/verify_paralyze_freeze.py
python tools/verify_browser_statuses.py --fixture tools/browser_paralyze_balance_case.py --base-fixture tools/browser_status_case.py --extra-fixture tests/test_paralyze_balance.py --expected-count 20 --output verification/paralyze_balance_browser.json
```

ZIP SHA-256: `d4a4ec470d61f0dec99e0192b5f0edc11a677eb338a22f0ef022724531b760d2`

Web/ZIPをローカルで再生成・検証した。コミット・Push・公開デプロイは実施していない。
Pixel2へコピーする際は本体の既存 `save/` を保持し、PLAYER→Enemy、Enemy→PLAYERの両方向で実機の体感を確認する。
