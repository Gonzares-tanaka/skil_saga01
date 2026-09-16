"""Load 3 editable resource files into 15 independent Pyxel Tilemaps."""
from .tiles import AREA_RESOURCES, FLOOR_TILEMAPS


def load_maps():
    import pyxel
    for path in AREA_RESOURCES:
        if not path.is_file():
            raise ValueError(f"{path.name}がありません。同梱のエリアリソースを戻してください。")
    maps = []
    try:
        for path in AREA_RESOURCES:
            pyxel.load(str(path), exclude_images=True, exclude_sounds=True, exclude_musics=True)
            for index in FLOOR_TILEMAPS:
                source = pyxel.tilemaps[index]
                copy = pyxel.Tilemap(source.width, source.height, source.imgsrc)
                copy.blt(0, 0, source, 0, 0, source.width, source.height)
                maps.append(copy)
    finally:
        # Images/sounds remain those already loaded from the main resource.
        pyxel.load(str(AREA_RESOURCES[0]), exclude_images=True, exclude_sounds=True, exclude_musics=True)
    return maps
