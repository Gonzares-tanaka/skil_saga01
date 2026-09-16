"""8px Japanese font with pixel-measured truncation and wrapping."""
import pyxel
from .content import ROOT

FONT_PATH = ROOT / "assets" / "fonts" / "misaki_gothic_2nd.bdf"
FONT_HEIGHT = 8
_font = None


def font():
    global _font
    if _font is None:
        _font = pyxel.Font(str(FONT_PATH))
    return _font


def text_width(value):
    return font().text_width(str(value))


def fit(value, pixels):
    value = str(value)
    if pixels <= 0:
        return ""
    if text_width(value) <= pixels:
        return value
    while value and text_width(value + "~") > pixels:
        value = value[:-1]
    return value + "~" if text_width("~") <= pixels else ""


def text(x, y, value, color=3, width=None):
    # width retains the UI's 4px column units; glyph width is measured in pixels.
    pixels = min(160 - x, width * 4 if width is not None else 160)
    pyxel.text(x, y, fit(value, pixels), color, font())


def wrap_lines(lines, width=36):
    result = []
    for value in lines:
        for paragraph in str(value).split("\n"):
            line = ""
            for char in paragraph:
                if line and text_width(line + char) > width * 4:
                    result.append(line)
                    line = ""
                line += char
            result.append(line)
    return result
