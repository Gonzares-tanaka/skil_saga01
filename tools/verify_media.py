"""Verify Japanese glyph coverage and non-silent, distinct synthesized audio."""
import ast
from array import array
import json
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyxel
from rpg.content import ROOT
from rpg.text import FONT_PATH, font, text_width, wrap_lines
from rpg.sound import init_sound, ATTACK_SOUND, SKILL_SOUND


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


pyxel.init(160, 120, headless=True)
glyphs = {int(line.split()[1]) for line in FONT_PATH.read_text(encoding="ascii").splitlines()
          if line.startswith("ENCODING ")}
characters = set()
for path in (ROOT / "rpg").glob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            characters.update(c for c in node.value if ord(c) > 127)
for path in (ROOT / "data").glob("*.json"):
    for value in strings(json.loads(path.read_text(encoding="utf-8-sig"))):
        characters.update(c for c in value if ord(c) > 127)
missing = sorted(c for c in characters if ord(c) not in glyphs)
assert not missing, f"Font missing glyphs: {missing}"
assert text_width("攻撃") == 16 and text_width("STR") == 12
long_line = "日本語の長い技名と成長履歴 ABC123" * 10
wrapped = wrap_lines([long_line])
assert "".join(wrapped) == long_line
assert all(text_width(line) <= 144 for line in wrapped)

init_sound()
output = ROOT / "verification" / "audio"
output.mkdir(parents=True, exist_ok=True)
raw_audio = []
details = []
for name, sound_id in (("attack", ATTACK_SOUND), ("skill", SKILL_SOUND)):
    path = output / f"{name}.wav"
    duration = pyxel.sounds[sound_id].total_sec()
    assert 0 < duration < 1
    pyxel.sounds[sound_id].save(str(path), 1.0)
    with wave.open(str(path), "rb") as audio:
        assert audio.getsampwidth() == 2
        data = audio.readframes(audio.getnframes())
        samples = array("h", data)
        peak = max(abs(s) for s in samples)
        assert peak > 100, f"Silent sound: {name}"
        raw_audio.append(data)
        details.append({"sound": name, "duration": duration, "peak": peak})
assert raw_audio[0] != raw_audio[1]
result = {"japanese_characters_checked": len(characters), "missing_glyphs": missing, "sounds": details}
(ROOT / "verification" / "media.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
