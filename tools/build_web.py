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
  html, body { margin: 0; background: #0f380f; }
  #gb-controls { display: none; }
  @media (pointer: coarse) {
    #pyxel-screen { height: calc(100% - 126px) !important; background: #0f380f !important; }
    #gb-controls {
      position: fixed; inset: auto 0 0; height: 126px; z-index: 10;
      display: flex; align-items: center; justify-content: space-between;
      box-sizing: border-box; padding: 4px clamp(8px, 5vw, 24px);
      background: #244723; touch-action: none; user-select: none;
    }
    #gb-controls button {
      position: absolute; width: 48px; height: 48px; padding: 0;
      border: 2px solid #c8da91; border-radius: 10px;
      background: #476d49; color: #e5edc4; font: bold 22px system-ui;
      touch-action: none; user-select: none;
    }
    #gb-controls button:active { background: #9bbc0f; color: #0f380f; }
    #gb-dpad { position: relative; width: 112px; height: 112px; flex: none; }
    #gb-dpad .up { left: 32px; top: 0; }
    #gb-dpad .left { left: 0; top: 32px; }
    #gb-dpad .right { right: 0; top: 32px; }
    #gb-dpad .down { left: 32px; bottom: 0; }
    #gb-actions { display: flex; gap: clamp(8px, 3vw, 20px); align-items: center; }
    #gb-actions button { position: static; width: 62px; height: 62px; border-radius: 50%; }
  }
</style>
<div id="gb-controls" aria-label="ゲーム操作">
  <div id="gb-dpad" aria-label="D-PAD">
    <button class="up" data-gb="up" aria-label="上">▲</button>
    <button class="left" data-gb="left" aria-label="左">◀</button>
    <button class="right" data-gb="right" aria-label="右">▶</button>
    <button class="down" data-gb="down" aria-label="下">▼</button>
  </div>
  <div id="gb-actions">
    <button data-gb="b" aria-label="B キャンセル・メニュー">B</button>
    <button data-gb="a" aria-label="A 決定・調べる">A</button>
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
