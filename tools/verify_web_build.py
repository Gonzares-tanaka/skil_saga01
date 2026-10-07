"""Run the embedded Web payload with real Pyxel and simulated pad input."""
import base64
import io
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "dist/game.html").read_text(encoding="utf-8")
index = (ROOT / "dist/index.html").read_text(encoding="utf-8")
assert "game.html?v=" in index  # The PLAY button bypasses stale mobile iframe caches.
assert 'gamepad: "disabled"' in html
assert html.index("window.sparkAudioState") < html.index("cdn.jsdelivr.net/gh/kitao/pyxel")
assert "window.sparkResumeAudio" in html
assert all(event in html for event in ("visibilitychange", "pagehide", "pageshow", "blur", "focus"))
assert html.count('data-gb="') == 6
assert all(f'data-gb="{name}"' in html for name in ('up', 'down', 'left', 'right', 'a', 'b'))
assert len(re.findall(r'<button\b[^>]*data-gb="[^"]+"[^>]*></button>', html)) == 6
assert '<span aria-hidden="true">B</span><button' in html
assert '<span aria-hidden="true">A</span><button' in html
assert 'grid-template-columns: repeat(3, var(--pad-size))' in html
assert 'gap: var(--pad-gap)' in html
assert '-webkit-user-select: none' in html
assert 'Yで情報' not in index and 'STARTでヘルプ' not in index
assert 'スキル収集率100%' in index and 'MASTERED' in index and '最奥のボス' in index
assert '_virtualGamepadStates[index] = true' in html
payload = base64.b64decode(re.search(r'base64: "([^"]+)"', html)[1])
with tempfile.TemporaryDirectory(prefix="verify_pyxel_web_") as temp:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in ("game", "area2", "area3"):
            for suffix in (".pyxpal", ".pyxres"):
                filename = name + suffix
                assert archive.read("spark_web/" + filename) == (ROOT / filename).read_bytes(), filename
        for source in (ROOT / "rpg").glob("*.py"):
            assert archive.read("spark_web/rpg/" + source.name) == source.read_bytes(), source.name
        for source in (ROOT / "data").glob("*.json"):
            assert archive.read("spark_web/data/" + source.name) == source.read_bytes(), source.name
        music = ROOT / 'assets/battle_music.pyxres'
        assert archive.read('spark_web/assets/battle_music.pyxres') == music.read_bytes()
        archive.extractall(temp)
    check = '''
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path.cwd()))
import pyxel
from rpg.battle import Session
from rpg.battle_transition import BATTLE_TRANSITION_HOLD_FRAMES, BATTLE_TRANSITION_FRAMES
from rpg.content import ROOT, load_content
from rpg.dungeon_app import DungeonApp
from rpg.opening import TITLE_FADE_FRAMES, HUB_PREVIEW_FRAMES
from rpg.tiles import TILE_FLOOR, TILE_WALL, TILE_SWITCH, TILE_DOOR, TILE_QUEST, TILE_WARNING, TILE_BOSS
app = DungeonApp(Session(*load_content(), seed=42), run=False, headless=True)
expected = [int(line, 16) for line in (ROOT / "game.pyxpal").read_text().splitlines()]
assert len(expected) == 32 and list(pyxel.colors) == expected
assert pyxel.images[2].pget(7, 5) != 0  # Editable GUILD icon is embedded.
def press(button, held=False):
    with patch.object(pyxel, "btnp", side_effect=lambda code, *args: code == button), patch.object(pyxel, "btn", return_value=held):
        app.update()
    app.draw()
assert app.state == "title"
press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "title_no_save"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "title"
press(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "title_fade"
assert (app.session.treasure.banked, app.session.treasure.unbanked) == (3, 0)
for _ in range(TITLE_FADE_FRAMES):
    press(pyxel.GAMEPAD1_BUTTON_A, held=True)
assert app.state == "intro" and app.intro_page == 0
press(None)
for page in range(4):
    press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "hub_preview"
for _ in range(HUB_PREVIEW_FRAMES - 1):
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN, held=True)
    assert app.state == "hub_preview" and app.camp_cursor == 0
press(pyxel.GAMEPAD1_BUTTON_A, held=True)
assert app.state == "hub_intro"
press(pyxel.GAMEPAD1_BUTTON_A, held=True)
assert app.state == "hub_intro"
press(None)
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "hub_intro"
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "camp"
press(None)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "facility" and app.facility_index == 0
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.overlay == "info"
press(pyxel.GAMEPAD1_BUTTON_B)
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "camp"
press(pyxel.GAMEPAD1_BUTTON_DPAD_UP)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "explore"
app.dungeon.settings["encounter_chance"] = 0
for button, dx, dy, facing in ((pyxel.GAMEPAD1_BUTTON_DPAD_UP,0,-1,"up"),(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN,0,1,"down"),(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT,-1,0,"left"),(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT,1,0,"right")):
    app.dungeon.x, app.dungeon.y = 6, 6
    app.dungeon.maps[0].pset(6+dx, 6+dy, TILE_FLOOR)
    press(button)
    assert (app.dungeon.x, app.dungeon.y) == (6+dx, 6+dy)
    assert app.player_facing == facing
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "menu"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "explore"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "menu"
press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.overlay == "info"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.overlay is None
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "explore"
press(pyxel.GAMEPAD1_BUTTON_B)
for _ in range(4):
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.overlay == "help"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.overlay is None
assert pyxel.sounds[59].notes  # Editable transition sound is in the Web payload.
with patch.object(pyxel, "play", side_effect=RuntimeError("audio suspended")), patch.object(pyxel, "playm", side_effect=RuntimeError("audio suspended")):
    app.handle_event("battle", "")
    assert app.state == "battle_transition"
    for _ in range(BATTLE_TRANSITION_HOLD_FRAMES + BATTLE_TRANSITION_FRAMES):
        press(pyxel.GAMEPAD1_BUTTON_A, held=True)
assert app.state == "command" and not app.actions
press(pyxel.GAMEPAD1_BUTTON_A, held=True)  # Held touch cannot choose a command.
assert app.state == "command" and not app.actions
press(None)  # Release before a fresh touch.
assert app.state == "command"
press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "command" and app.actions[-1].kind == "GUARD"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "command" and not app.actions
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "skill"
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == "command"
for _ in range(4):
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == "resolve"
assert list(pyxel.colors) == expected
# Settle this fixture before starting the later final-area battles. Repeated A
# cannot choose a different skill when the selected skill has run out of Uses.
for _ in range(app.battle.max_rounds + 1):
    while app.battle.queue:
        app.battle.step()
    if app.battle.outcome:
        break
    app.battle.begin_round(app.battle.auto_actions())
else:
    raise AssertionError('Initial command-check battle did not terminate')
app.session.settle()
for actor_index in list(app.session.pending_replacements):
    app.session.resolve_replacement(actor_index)
assert app.session.settled and not app.session.pending_replacements
app.enter_camp()
app.enter_dungeon()
d = app.dungeon
d.settings['encounter_chance'] = 0
assert [len(d.positions(f, TILE_QUEST)) for f in range(5, 10)] == [3, 3, 4, 3, 3]
d.debug_floor(6)
door = d.positions(6, TILE_DOOR)[0]
d.x, d.y = door[0]-1, door[1]
press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
assert (d.x, d.y) != door
sx, sy = d.positions(6, TILE_SWITCH)[0]
d.x, d.y = sx, sy-1
press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
assert not d.activated_switches
with patch.object(pyxel, 'play', side_effect=RuntimeError('audio suspended')):
    press(pyxel.GAMEPAD1_BUTTON_A)
assert d.activated_switches == {6} and app.state == 'field_event'
for _ in range(10):
    if app.state == 'explore':
        break
    press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == 'explore'
d.x, d.y = door[0]-1, door[1]
press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
assert (d.x, d.y) == door
app.enter_camp()
app.enter_dungeon()
assert not d.activated_switches and not d.can_enter(6, *door)
d.debug_floor(14)
d.x, d.y = d.find(14, TILE_WARNING)
for actor in app.session.party:
    actor.hp = actor.max_hp = 500
    actor.strength = actor.intellect = 80
app.session.settings['spark_chance'] = 0
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.state == 'guardian_warning'
press(pyxel.GAMEPAD1_BUTTON_B)
assert app.state == 'explore' and d.finale.guardian_index is None
press(pyxel.GAMEPAD1_BUTTON_A)
press(pyxel.GAMEPAD1_BUTTON_A)
assert app.battle_kind == 'guardian' and app.battle.boss
with patch.object(pyxel, 'play', side_effect=RuntimeError('audio suspended')), patch.object(pyxel, 'playm', side_effect=RuntimeError('audio suspended')):
    for _ in range(2500):
        press(pyxel.GAMEPAD1_BUTTON_A)
        if app.state == 'explore' and d.finale.guardians_defeated:
            break
    else:
        raise AssertionError('Silent pad-only gauntlet did not terminate')
assert not d.finale.has_amrita
with patch.object(pyxel, 'play', side_effect=RuntimeError('audio suspended')), patch.object(pyxel, 'playm', side_effect=RuntimeError('audio suspended')):
    d.x, d.y = d.find(14, TILE_BOSS)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'boss_message'
    for _ in range(1500):
        press(pyxel.GAMEPAD1_BUTTON_A)
        if app.state == 'explore' and d.finale.has_amrita:
            break
    else:
        raise AssertionError('Pad-only demon and story did not terminate')
assert d.finale.demon_defeated and 'AMRITA' not in app.session.inventory.counts
# The shipped payload must also contain the post-Amrita event and retry logic.
with patch.object(pyxel, 'play', side_effect=RuntimeError('audio suspended')), patch.object(pyxel, 'playm', side_effect=RuntimeError('audio interrupted')):
    app.enter_camp(returned=True)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'amrita_offer'
    press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'camp' and d.finale.has_amrita
    app.enter_dungeon()
    app.handle_event('base', '')
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'final_story'
    for _ in app.final_story_pages():
        press(pyxel.GAMEPAD1_BUTTON_A)
    press(None)
    assert app.battle.is_elysion_battle and app.battle.elysion_barrier_active
    saved_hp = [c.hp for c in app.session.party]
    saved_uses = [dict(c.skill_uses) for c in app.session.party]
    saved_items = dict(app.session.inventory.counts)
    press(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)
    press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'battle_item'
    options = app.battle_items()
    for _ in range(options.index('AMRITA')):
        press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
    press(pyxel.GAMEPAD1_BUTTON_A)
    for _ in range(3):
        press(pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)
        press(pyxel.GAMEPAD1_BUTTON_A)
    for _ in range(300):
        if app.state not in ('resolve', 'amrita_effect'):
            break
        press(pyxel.GAMEPAD1_BUTTON_A)
    assert app.state == 'command' and not app.battle.elysion_barrier_active and d.finale.has_amrita
    assert app.final_visual().sprite['width'] == app.final_visual().sprite['height'] == 48
    assert not app.final_visual().active
    for c in app.session.party:
        c.hp = 0
        c.skill_uses = {sid: 1 for sid in c.skills}
    app.session.inventory.counts['POTION'] = 0
    app.battle.outcome = 'DEFEAT'
    app.session.settle()
    app.state = 'result'
    app.finish_results()
    assert app.state == 'final_retry'
    press(pyxel.GAMEPAD1_BUTTON_A)
    press(None)
    assert [c.hp for c in app.session.party] == saved_hp
    assert [c.skill_uses for c in app.session.party] == saved_uses
    assert app.session.inventory.counts == saved_items
    assert d.finale.has_amrita and app.battle.elysion_barrier_active
    # Use the embedded legal-action policy to finish the restored battle.
    while not app.battle.outcome:
        app.battle.begin_round(app.battle.auto_actions())
        while app.battle.queue:
            app.battle.step()
    assert app.battle.outcome == 'VICTORY'
    app.session.settle()
    for index in list(app.session.pending_replacements):
        app.session.resolve_replacement(index)
    app.finish_results()
    assert app.state == 'ending' and d.finale.amrita_power_spent
    assert d.finale.lord_of_elysion_defeated and not d.finale.has_amrita
print("PASS: embedded resources/palette, pad input, silent guardians, Amrita, final barrier/retry and ENDING")
'''
    subprocess.run([sys.executable, "-c", check], cwd=Path(temp) / "spark_web", check=True)
    if '--phase6d' in sys.argv:
        embedded_root = Path(temp) / 'spark_web'
        helpers = embedded_root / 'tools'
        helpers.mkdir(exist_ok=True)
        shutil.copy2(ROOT / 'tools/verify_phase6d_ui.py', helpers / 'verify_phase6d_ui.py')
        subprocess.run([sys.executable, 'tools/verify_phase6d_ui.py'], cwd=embedded_root, check=True)
        shutil.copy2(embedded_root / 'verification/phase6d_ui.json', ROOT / 'verification/web_phase6d_ui.json')
        print('PASS: shipped Web payload Phase 6D nine quests/TRZ/pad/silent play')
    if '--final-chapter' in sys.argv:
        # Execute the same-session integration test against the shipped payload,
        # with verification helpers outside the production package.
        embedded_root = Path(temp) / 'spark_web'
        helpers = embedded_root / 'tools'
        helpers.mkdir(exist_ok=True)
        for name in ('verify_final_chapter.py', 'verify_phase6a_ui.py', 'verify_expedition.py'):
            shutil.copy2(ROOT / 'tools' / name, helpers / name)
        subprocess.run([sys.executable, 'tools/verify_final_chapter.py'], cwd=embedded_root, check=True)
        shutil.copy2(embedded_root / 'verification/final_chapter.json',
                     ROOT / 'verification/web_final_chapter.json')
        print('PASS: shipped Web payload B10 -> ENDING, real defeat/retry cases A-E')
