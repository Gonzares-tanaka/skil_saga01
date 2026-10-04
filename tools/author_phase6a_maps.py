"""One-off B11-B15 draft authoring; NEVER run after human Editor changes.

Running without arguments only prints geometry. ``--write`` deliberately replaces
the 24x24 draft area of area3.pyxres Tilemap 0-4. It is not used by the game or
the Web build. All resource data outside those five rectangles is preserved.
"""
from collections import Counter, deque
from pathlib import Path
import argparse
import io
import re
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "area3.pyxres"
SIZE = 24
SYMBOLS = {".": (2, 8), "#": (1, 0), "^": (2, 0), "v": (3, 0),
           "C": (4, 0), "B": (7, 0), "R": (9, 0), "P": (10, 0),
           "O": (20, 0), "H": (12, 0), "Q": (13, 0), "S": (15, 0),
           "D": (16, 0), "a": (21, 0), "b": (22, 0), "c": (23, 0),
           "d": (24, 0), "e": (25, 0), "f": (26, 0),
           "G": (27, 0), "W": (28, 0)}


class Draft:
    def __init__(self):
        self.grid = [["#"] * SIZE for _ in range(SIZE)]

    def room(self, x1, y1, x2, y2):
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self.grid[y][x] = "."
        return self

    def path(self, x1, y1, x2, y2):
        assert x1 == x2 or y1 == y2
        return self.room(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def put(self, mark, x, y):
        assert self.grid[y][x] == ".", (mark, x, y)
        self.grid[y][x] = mark
        return self

    def lines(self):
        return ["".join(row) for row in self.grid]


def floors():
    # B11: legible chambers around two circulation loops; records in a side room.
    b11 = (Draft()
           .room(2, 2, 7, 6).room(11, 2, 15, 6).room(18, 2, 22, 7)
           .room(3, 10, 8, 14).room(11, 10, 16, 14).room(18, 11, 22, 15)
           .room(2, 18, 7, 22).room(11, 18, 16, 22).room(19, 19, 22, 22)
           .path(7, 4, 11, 4).path(15, 4, 18, 4)
           .path(5, 6, 5, 10).path(13, 6, 13, 10)
           .path(8, 12, 11, 12).path(16, 12, 18, 12).path(20, 7, 20, 11)
           .path(5, 14, 5, 18).path(7, 20, 11, 20)
           .path(13, 14, 13, 18).path(16, 20, 19, 20)
           .put("^", 3, 3).put("v", 20, 20)
           .put("C", 21, 3).put("C", 3, 21).put("R", 21, 14)
           .put("a", 6, 13).put("Q", 6, 3).put("Q", 14, 11).put("Q", 15, 21))
    # B12: a closed-door archive visible early, its switch on the south detour.
    # Poison crosses the loop faster; a pit sits in a separate optional spur.
    b12 = (Draft()
           .room(2, 17, 7, 22).room(10, 18, 15, 22).room(18, 17, 22, 22)
           .room(2, 10, 7, 13).room(10, 9, 15, 13).room(18, 10, 22, 14)
           .room(2, 2, 6, 6).room(10, 2, 15, 6).room(18, 2, 22, 6)
           .path(7, 20, 10, 20).path(15, 20, 18, 20)
           .path(4, 14, 4, 17).path(12, 13, 12, 17).path(20, 14, 20, 17)
           .path(7, 12, 10, 12).path(15, 12, 18, 12)
           .path(4, 6, 4, 10).path(12, 6, 12, 9)
           .path(7, 4, 10, 4).path(15, 4, 18, 4)
           .path(20, 6, 20, 10)
           .put("^", 3, 20).put("v", 12, 3)
           .put("S", 21, 21).put("D", 16, 4)
           .put("C", 21, 3).put("R", 21, 5).put("C", 3, 3).put("C", 14, 21)
           .put("P", 8, 12).put("P", 9, 12).put("O", 18, 19)
           .put("b", 5, 11).put("c", 20, 4)
           .put("Q", 6, 19).put("Q", 13, 10).put("Q", 19, 12))
    # The north-east archive must have only one access, through its door.
    for y in range(7, 10):
        b12.grid[y][20] = "#"
    # B13: a short northern crossing vs two extended southern treasure loops.
    b13 = (Draft()
           .room(2, 2, 7, 6).room(10, 2, 14, 6).room(18, 2, 22, 6)
           .room(2, 10, 7, 15).room(10, 10, 15, 14).room(18, 10, 22, 15)
           .room(2, 19, 7, 22).room(10, 18, 15, 22).room(18, 19, 22, 22)
           .path(7, 4, 10, 4).path(14, 4, 18, 4)
           .path(4, 6, 4, 10).path(20, 6, 20, 10)
           .path(7, 12, 10, 12).path(15, 12, 18, 12)
           .path(4, 15, 4, 18).path(12, 14, 12, 18).path(20, 15, 20, 18)
           .path(7, 20, 10, 20).path(15, 20, 18, 20).path(11, 9, 11, 10)
           .put("^", 3, 3).put("v", 21, 3)
           .put("C", 6, 14).put("R", 2, 21).put("C", 11, 21).put("R", 22, 21).put("C", 21, 14)
           .put("P", 8, 12).put("P", 9, 12).put("P", 16, 20).put("P", 17, 20)
           .put("O", 11, 9).put("d", 13, 13)
           .put("Q", 6, 5).put("Q", 3, 19).put("Q", 20, 11))
    # B14: outer ring and archive alcoves, longer approach to the final stairs.
    b14 = (Draft()
           .room(18, 2, 22, 7).room(10, 2, 14, 6).room(2, 2, 7, 7)
           .room(2, 10, 7, 15).room(10, 10, 15, 14).room(18, 11, 22, 15)
           .room(2, 18, 7, 22).room(10, 19, 15, 22).room(18, 19, 22, 22)
           .path(7, 4, 10, 4).path(15, 4, 18, 4)
           .path(4, 7, 4, 10).path(20, 7, 20, 11)
           .path(7, 12, 10, 12).path(15, 12, 18, 12)
           .path(4, 15, 4, 18).path(12, 14, 12, 18).path(20, 15, 20, 18)
           .path(7, 20, 10, 20).path(15, 20, 18, 20)
           .put("^", 21, 3).put("v", 3, 21)
           .put("C", 3, 3).put("C", 21, 21).put("R", 11, 19)
           .put("e", 5, 13).put("f", 13, 11)
           .put("Q", 11, 3).put("Q", 19, 14).put("Q", 6, 19))
    # B15: the two one-tile chokepoints impose warning -> guardians -> spring.
    # No branches bypass the guardians, and no hazards intervene after them.
    b15 = (Draft()
           .room(2, 17, 7, 22).room(2, 9, 7, 14).room(10, 9, 15, 13)
           .path(4, 14, 4, 17).path(7, 11, 10, 11)
           .path(15, 11, 19, 11).path(19, 8, 19, 11)
           .room(17, 4, 21, 7).path(17, 5, 13, 5)
           .room(9, 3, 12, 7).path(9, 5, 6, 5).room(2, 2, 5, 7)
           .put("^", 3, 20).put("W", 16, 11).put("G", 19, 8)
           .put("H", 15, 5).put("B", 6, 5)
           .put("C", 6, 10)
           .put("Q", 6, 21).put("Q", 12, 12).put("Q", 10, 6))
    return [b11, b12, b13, b14, b15]


def route(draft, start, goal, blocked=(), door_open=True):
    queue, prev = deque([start]), {start: None}
    while queue:
        p = queue.popleft()
        if p == goal:
            result = []
            while prev[p] is not None:
                result.append(p)
                p = prev[p]
            return list(reversed(result))
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nxt = p[0] + dx, p[1] + dy
            if not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE) or nxt in prev:
                continue
            mark = draft.grid[nxt[1]][nxt[0]]
            if mark in {"#", "O"} | set(blocked) or mark == "D" and not door_open:
                continue
            prev[nxt] = p
            queue.append(nxt)
    return None


def positions(draft, symbol):
    return [(x, y) for y, row in enumerate(draft.grid) for x, mark in enumerate(row) if mark == symbol]


def validate(drafts):
    for index, draft in enumerate(drafts):
        count = Counter("".join(draft.lines()))
        assert count["^"] == 1 and count["Q"] == 3
        assert count["v"] == (index < 4)
        start = positions(draft, "^")[0]
        for y, row in enumerate(draft.grid):
            for x, mark in enumerate(row):
                if mark not in ("#", "O"):
                    assert route(draft, start, (x, y)) is not None, (index + 11, x, y)
        if index < 4:
            assert 246 <= SIZE * SIZE - count["#"] <= 287, (index + 11, count)
        assert count["C"] + count["R"] == [3, 4, 5, 3, 1][index]
        print(f"B{index+11}: walkable={SIZE*SIZE-count['#']}, counts={dict(count)}")
    b12 = drafts[1]
    start, switch = positions(b12, "^")[0], positions(b12, "S")[0]
    assert route(b12, start, switch, door_open=False)
    assert route(b12, start, positions(b12, "v")[0], door_open=False)
    assert route(b12, start, positions(b12, "c")[0], door_open=False) is None
    b13 = drafts[2]
    assert route(b13, positions(b13, "^")[0], positions(b13, "v")[0], {"P", "O"})
    b15 = drafts[4]
    start = positions(b15, "^")[0]
    boss = positions(b15, "B")[0]
    for mark in ("W", "G", "H"):
        assert route(b15, start, boss, {mark}) is None, mark + " can be bypassed"


def write_resource(drafts):
    with zipfile.ZipFile(RESOURCE) as old:
        info = old.getinfo("pyxel_resource.toml")
        original = old.read(info).decode("utf8")
    data = tomllib.loads(original)
    for tilemap in data["tilemaps"]:
        assert all(tuple(row[x:x+2]) not in {(u, 0) for u in range(21, 29)}
                   for row in tilemap["data"] for x in range(0, len(row), 2)), "New event coordinate already used"
    sections = original.split("[[tilemaps]]")
    assert len(sections) == 9
    for index, draft in enumerate(drafts):
        old_rows = data["tilemaps"][index]["data"]
        rows = [list(row) for row in old_rows]
        while len(rows) < SIZE:
            rows.append([])
        for y, grid_row in enumerate(draft.grid):
            while len(rows[y]) < SIZE * 2:
                rows[y].extend((0, 0))
            for x, symbol in enumerate(grid_row):
                rows[y][x*2:x*2+2] = SYMBOLS[symbol]
        encoded = "data = " + str(rows)
        sections[index+1], count = re.subn(r"(?m)^data = .*", encoded, sections[index+1], count=1)
        assert count == 1
    updated = "[[tilemaps]]".join(sections)
    after = tomllib.loads(updated)
    assert all(data[key] == after[key] for key in ("images", "sounds", "musics"))
    assert data["tilemaps"][5:] == after["tilemaps"][5:]
    for index in range(5):
        assert data["tilemaps"][index]["data"][24:] == after["tilemaps"][index]["data"][24:]
        for y in range(24):
            previous = data["tilemaps"][index]["data"][y] if y < len(data["tilemaps"][index]["data"]) else []
            assert previous[48:] == after["tilemaps"][index]["data"][y][48:]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as new:
        new.writestr(info, updated.encode("utf8"))
    temp = RESOURCE.with_suffix(".phase6a.tmp")
    temp.write_bytes(output.getvalue())
    temp.replace(RESOURCE)
    print("WROTE ONLY area3.pyxres Tilemap0-4 24x24 rectangles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="replace draft maps (never after human Editor changes)")
    parser.add_argument("--print", action="store_true", dest="print_maps")
    args = parser.parse_args()
    drafts = floors()
    validate(drafts)
    if args.print_maps:
        for draft in drafts:
            print("\n".join(draft.lines()), "\n")
    if args.write:
        write_resource(drafts)
