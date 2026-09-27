"""Build the GitHub Pages game from the official Pyxel Web exporter."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
INCLUDE_FILES = ("main.py", "game.pyxres", "area2.pyxres", "area3.pyxres",
                 "game.pyxpal", "area2.pyxpal", "area3.pyxpal")
INCLUDE_DIRS = ("rpg", "data", "assets")

# Pyxel 2.9.9 exposes its virtual pad state to scripts in the same document.
# Keep the official runtime and app2html payload; replace its 4-face-button
# touch presentation with the game's six active inputs (D-pad and A/B).
TOUCH_CONTROLS = r"""
<style>
  html, body { margin: 0; background: #0f380f; -webkit-user-select: none; user-select: none; }
  #gb-controls { display: none; }
  @media (pointer: coarse) {
    :root {
      --pad-size: clamp(36px, 11vw, 42px);
      --pad-gap: 4px;
      --controls-height: calc(var(--pad-size) + var(--pad-size) + var(--pad-size) + 16px);
    }
    #pyxel-screen { height: calc(100% - var(--controls-height)) !important; background: #0f380f !important; }
    #gb-controls {
      position: fixed; inset: auto 0 0; height: var(--controls-height); z-index: 10;
      display: flex; align-items: center; justify-content: space-between;
      box-sizing: border-box; padding: 4px clamp(8px, 4vw, 20px);
      background: #244723; touch-action: none; -webkit-touch-callout: none;
    }
    #gb-controls button {
      width: var(--pad-size); height: var(--pad-size); padding: 0;
      border: 2px solid #c8da91; border-radius: 10px;
      background: #476d49; touch-action: none;
      -webkit-user-select: none; user-select: none; -webkit-touch-callout: none;
      -webkit-tap-highlight-color: transparent;
    }
    #gb-controls button:active { background: #9bbc0f; }
    #gb-dpad {
      display: grid; grid-template-columns: repeat(3, var(--pad-size));
      grid-template-rows: repeat(3, var(--pad-size)); gap: var(--pad-gap);
      flex: none;
    }
    #gb-dpad .up { grid-column: 2; grid-row: 1; }
    #gb-dpad .left { grid-column: 1; grid-row: 2; }
    #gb-dpad .right { grid-column: 3; grid-row: 2; }
    #gb-dpad .down { grid-column: 2; grid-row: 3; }
    #gb-actions { display: flex; gap: clamp(8px, 3vw, 16px); align-items: center; }
    .gb-action { display: flex; flex-direction: column; align-items: center; gap: 4px; }
    .gb-action span { color: #e5edc4; font: bold 15px system-ui; pointer-events: none; }
    #gb-actions button { width: clamp(48px, 16vw, 62px); height: clamp(48px, 16vw, 62px); border-radius: 50%; }
  }
</style>
<div id="gb-controls" aria-label="ゲーム操作">
  <div id="gb-dpad" aria-label="D-PAD">
    <button type="button" class="up" data-gb="up" aria-label="上"></button>
    <button type="button" class="left" data-gb="left" aria-label="左"></button>
    <button type="button" class="right" data-gb="right" aria-label="右"></button>
    <button type="button" class="down" data-gb="down" aria-label="下"></button>
  </div>
  <div id="gb-actions">
    <div class="gb-action"><span aria-hidden="true">B</span><button type="button" data-gb="b" aria-label="B キャンセル・メニュー"></button></div>
    <div class="gb-action"><span aria-hidden="true">A</span><button type="button" data-gb="a" aria-label="A 決定・調べる"></button></div>
  </div>
</div>
<script>
  // Indices are Pyxel 2.9.9's official virtual GAMEPAD1 D-PAD / A / B bits.
  const gbButtons = { up: 0, down: 1, left: 2, right: 3, a: 4, b: 5 };
  for (const button of document.querySelectorAll('#gb-controls button')) {
    const index = gbButtons[button.dataset.gb];
    button.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      button.setPointerCapture(event.pointerId);
      _virtualGamepadStates[index] = true;
    });
    const release = (event) => {
      event.preventDefault();
      _virtualGamepadStates[index] = false;
    };
    button.addEventListener('pointerup', release);
    button.addEventListener('pointercancel', release);
    button.addEventListener('lostpointercapture', release);
  }
  window.addEventListener('blur', () => _virtualGamepadStates.fill(false));
</script>
"""


def main():
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix="pyxel_web_") as temp:
        temp_root = Path(temp)
        app_dir = temp_root / "spark_web"
        app_dir.mkdir()
        for filename in INCLUDE_FILES:
            shutil.copy2(ROOT / filename, app_dir / filename)
        for dirname in INCLUDE_DIRS:
            shutil.copytree(ROOT / dirname, app_dir / dirname,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        subprocess.run([python, "-m", "pyxel", "package", str(app_dir),
                        str(app_dir / "main.py")], cwd=temp_root, check=True)
        app_file = temp_root / "spark_web.pyxapp"
        subprocess.run([python, "-m", "pyxel", "app2html", str(app_file)],
                       cwd=temp_root, check=True)
        DIST.mkdir(exist_ok=True)
        html = (temp_root / "spark_web.html").read_text(encoding="utf-8")
        html = html.replace('gamepad: "enabled"', 'gamepad: "disabled"', 1)
        (DIST / "game.html").write_text(html + TOUCH_CONTROLS, encoding="utf-8")
    print("Built dist/game.html with the official Pyxel Web runtime.")


if __name__ == "__main__":
    main()
