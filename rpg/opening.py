"""Editable opening text and small layout constants, separate from game states."""
import json

from .content import ROOT


GAME_TITLE = "Skill Seekers!!~深淵のアムリタ~"
TITLE_MAIN = "Skill Seekers!!"
TITLE_SUBTITLE = "~深淵のアムリタ~"
TITLE_OPTIONS = ("はじめから", "つづきから")
TITLE_FADE_FRAMES = 4
# The game window runs at 30 FPS, so this shows the town for about three seconds.
HUB_PREVIEW_FRAMES = 90
INTRO_MARGIN = 12
INTRO_LINE_HEIGHT = 14


def load_intro_pages(path=None):
    """Read the only story data file; adding a page needs no UI code changes."""
    source = path or ROOT / "data" / "intro.json"
    pages = json.loads(source.read_text(encoding="utf-8-sig"))["pages"]
    if not isinstance(pages, list) or not pages or any(
        not isinstance(page, list) or not page or
        any(not isinstance(line, str) for line in page)
        for page in pages
    ):
        raise ValueError("intro.json: pagesは空でない文字列配列にしてください。")
    return pages


def load_hub_intro_lines(path=None):
    """Read the first-arrival town explanation from the same editable file."""
    source = path or ROOT / "data" / "intro.json"
    lines = json.loads(source.read_text(encoding="utf-8-sig"))["hub_intro"]
    if not isinstance(lines, list) or not lines or any(not isinstance(line, str) for line in lines):
        raise ValueError("intro.json: hub_introは空でない文字列配列にしてください。")
    return lines
