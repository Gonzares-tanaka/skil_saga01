"""Build the GitHub Pages game from the official Pyxel Web exporter."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
INCLUDE_FILES = ("main.py", "game.pyxres", "area2.pyxres", "area3.pyxres")
INCLUDE_DIRS = ("rpg", "data", "assets")


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
        shutil.copy2(temp_root / "spark_web.html", DIST / "game.html")
    print("Built dist/game.html with the official Pyxel Web runtime.")


if __name__ == "__main__":
    main()
