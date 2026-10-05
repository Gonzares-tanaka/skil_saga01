"""Copy the shared map image/palette into area2/3 for Pyxel Editor.

game.pyxres Image Bank 1 is the same authoritative image used during gameplay.
Only that image and the Editor palette are synchronized; maps, other images,
sounds and music remain untouched. Changed targets are backed up first.
"""
import argparse
from datetime import datetime
import io
from pathlib import Path
import shutil
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("area2.pyxres", "area3.pyxres")


def sync_map_chips(filenames=TARGETS):
    with zipfile.ZipFile(ROOT / "game.pyxres") as archive:
        source_text = archive.read("pyxel_resource.toml").decode("utf-8")
    source_image = tomllib.loads(source_text)["images"][1]
    source_section = source_text.split("[[images]]")[2]
    source_palette = (ROOT / "game.pyxpal").read_bytes()
    backup = ROOT / "verification" / "backups" / "map_chips" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def write_with_backup(path, content):
        backup.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, backup / path.name)
        temporary = path.with_name(path.name + ".chips.tmp")
        temporary.write_bytes(content)
        temporary.replace(path)

    for filename in filenames:
        if filename not in TARGETS:
            raise ValueError("Only area2.pyxres and area3.pyxres can be synchronized.")
        path = ROOT / filename
        with zipfile.ZipFile(path) as archive:
            original = archive.read("pyxel_resource.toml").decode("utf-8")
            before = tomllib.loads(original)
            if before["images"][1] != source_image:
                parts = original.split("[[images]]")
                parts[2] = source_section
                updated = "[[images]]".join(parts)
                expected = dict(before)
                expected["images"] = list(before["images"])
                expected["images"][1] = source_image
                if tomllib.loads(updated) != expected:
                    raise ValueError(f"Unexpected change outside Image Bank 1: {filename}")
                output = io.BytesIO()
                with zipfile.ZipFile(output, "w") as destination:
                    destination.comment = archive.comment
                    for entry in archive.infolist():
                        content = updated.encode("utf-8") if entry.filename == "pyxel_resource.toml" else archive.read(entry)
                        destination.writestr(entry, content)
                resource_bytes = output.getvalue()
            else:
                resource_bytes = None
        changed = resource_bytes is not None
        if changed:
            write_with_backup(path, resource_bytes)
        palette = path.with_suffix(".pyxpal")
        if not palette.exists() or palette.read_bytes() != source_palette:
            write_with_backup(palette, source_palette)
            changed = True
        print(f"{filename}: {'synced' if changed else 'already current'} (shared Image Bank 1 / palette)")
    if backup.exists():
        print(f"Backup: {backup.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resources", nargs="*", choices=TARGETS)
    args = parser.parse_args()
    sync_map_chips(args.resources or TARGETS)
