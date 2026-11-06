"""8px Japanese font with pixel-measured truncation and wrapping."""
import pyxel
from .content import ROOT

FONT_PATH = ROOT / "assets" / "fonts" / "misaki_gothic_2nd.bdf"
FONT_HEIGHT = 8
_font = None
DESCRIPTION_HOLD_FRAMES = 30  # 1 second at the game's 30 FPS, at both ends.
DESCRIPTION_STEP_FRAMES = 2  # 15 pixels/second.


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


class DescriptionScroll:
    """One-line marquee, clipped in a transient image, never in asset banks."""

    def __init__(self):
        self.identity = None
        self.last_frame = None
        self.start_frame = 0
        self.offset = 0
        self.image = None
        self.render_frame = None
        self.used = False

    def begin_frame(self):
        """Forget an actually hidden viewport, not skipped rendering frames."""
        if self.render_frame != pyxel.frame_count:
            if not self.used:
                self.identity = None
            self.used = False
            self.render_frame = pyxel.frame_count

    def draw(self, x, y, value, color=2, width=37, context=None):
        # Keep paragraphs readable in a one-line viewport without editing data.
        value = str(value).replace('\r\n', '　').replace('\n', '　').replace('\r', '　')
        pixels = max(0, min(160 - x, width * 4))
        frame = pyxel.frame_count
        identity = (context, value, x, y, pixels)
        if (identity != self.identity or self.last_frame is None or frame < self.last_frame):
            self.identity, self.start_frame = identity, frame
        self.last_frame = frame
        self.used = True
        overflow = max(0, text_width(value) - pixels)
        self.offset = 0
        if not pixels:
            return
        if not overflow:
            text(x, y, value, color, width)
            return
        travel = overflow * DESCRIPTION_STEP_FRAMES
        phase = (frame - self.start_frame) % (travel + 2 * DESCRIPTION_HOLD_FRAMES)
        self.offset = min(overflow, max(0, phase - DESCRIPTION_HOLD_FRAMES)
                          // DESCRIPTION_STEP_FRAMES)
        if self.image is None or self.image.width != pixels:
            self.image = pyxel.Image(pixels, FONT_HEIGHT)
        transparent = 0 if color else 1
        self.image.cls(transparent)
        self.image.text(-self.offset, 0, value, color, font())
        pyxel.blt(x, y, self.image, 0, 0, pixels, FONT_HEIGHT, transparent)
