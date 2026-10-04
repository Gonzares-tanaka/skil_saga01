"""Explicit, backed-up resource edit for three subtle pit chips."""
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.tiles import AREA_RESOURCES, TILE_PIT, TILE_PIT_AREA2, TILE_PIT_AREA3


def main():
    pyxel.init(160, 120, headless=True)
    pyxel.load(str(AREA_RESOURCES[0]))
    bases = ((0, 0), (8, 8), (2, 8))
    pits = (TILE_PIT, TILE_PIT_AREA2, TILE_PIT_AREA3)
    drawings = []
    floor_drawings = []
    for area, (u, v) in enumerate(bases):
        pixels = [[pyxel.images[1].pget(u * 8 + x, v * 8 + y)
                   for x in range(8)] for y in range(8)]
        floor_drawings.append([row[:] for row in pixels])
        # A small displaced floor fleck hints at the trap without a black hole.
        flecks = [(x, y) for y in range(2, 6) for x in range(2, 5)
                  if pixels[y][x] != pixels[y][x + 1]]
        if flecks:
            x, y = flecks[area % len(flecks)]
            pixels[y][x], pixels[y][x + 1] = pixels[y][x + 1], pixels[y][x]
        else:
            colors = [color for row in pixels for color in row if color != pixels[4][3]]
            hint = colors[0] if colors else (1 if pixels[4][3] != 1 else 2)
            pixels[4][3] = pixels[4][4] = hint
        drawings.append(pixels)
    backup = AREA_RESOURCES[0].parent / 'verification/backups' / (
        'area_pits_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True)
    pattern = r'(?ms)^\[\[images\]\]\r?\n.*?(?=^\[\[[a-z]+\]\]|\Z)'
    for area, path in enumerate(AREA_RESOURCES):
        shutil.copy2(path, backup / path.name)
        with zipfile.ZipFile(path) as archive:
            entries = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
        pyxel.load(str(path))
        for (u, v), pixels in zip(bases, floor_drawings):
            for y, row in enumerate(pixels):
                for x, color in enumerate(row):
                    pyxel.images[1].pset(u * 8 + x, v * 8 + y, color)
        for (u, v), pixels in zip(pits, drawings):
            for y, row in enumerate(pixels):
                for x, color in enumerate(row):
                    pyxel.images[1].pset(u * 8 + x, v * 8 + y, color)
        # Existing pits acquire their area's chip; positions stay unchanged.
        for tilemap in pyxel.tilemaps[:5]:
            for y in range(tilemap.height):
                for x in range(tilemap.width):
                    if tuple(tilemap.pget(x, y)) == TILE_PIT:
                        tilemap.pset(x, y, pits[area])
        # Use Pyxel's serializer, retaining all unrelated original sections.
        temporary = backup / ('serialized_' + path.name)
        pyxel.save(str(temporary))
        with zipfile.ZipFile(temporary) as archive:
            serialized = archive.read('pyxel_resource.toml').decode()
        original = next(data.decode() for entry, data in entries
                        if entry.filename == 'pyxel_resource.toml')
        images = list(re.finditer(pattern, original))
        new_images = list(re.finditer(pattern, serialized))
        bank = images[1]
        updated = original[:bank.start()] + new_images[1].group() + original[bank.end():]
        if area:
            tile_pattern = pattern.replace('images', 'tilemaps')
            old_maps = list(re.finditer(tile_pattern, updated))
            new_maps = list(re.finditer(tile_pattern, serialized))
            for index in reversed(range(5)):
                section = old_maps[index]
                updated = updated[:section.start()] + new_maps[index].group() + updated[section.end():]
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for entry, data in entries:
                archive.writestr(entry, updated.encode() if entry.filename == 'pyxel_resource.toml' else data)
        temporary.unlink()
    print(f'Updated three pit chips. Backup: {backup}')


if __name__ == '__main__':
    main()
