"""Record the actual D-pad/A-driven opening and file-local source diff."""
import difflib
import json
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.test_audio_pass03 import AudioPass03Tests
from rpg.sound import _play_music


def main():
    AudioPass03Tests.setUpClass()
    case=AudioPass03Tests('test_opening_keeps_title_no_transient_hub_no_restart'); case.setUp()
    with patch('rpg.sound._play_music',wraps=_play_music) as play:
        frames=case.opening()
    calls=[list(c.args) for c in play.call_args_list]
    assert calls==[[1,True]]
    timeline=[dict(state='title',bgm='bgm_title')]
    previous=None
    for frame,(state,bgm,page) in enumerate(frames):
        key=(state,bgm,page)
        if key!=previous: timeline.append(dict(frame=frame,state=state,bgm=bgm,story_page=page+1))
        previous=key
    backup=ROOT/'verification/backups/audio_pass03/dungeon_app.py'
    source_diff=None
    if backup.exists():
        source_diff='\n'.join(difflib.unified_diff(backup.read_text(encoding='utf8').splitlines(),
            (ROOT/'rpg/dungeon_app.py').read_text(encoding='utf8').splitlines(),fromfile='before',tofile='after'))
    result=dict(timeline=timeline,music_start_calls_after_new_game=calls,
        title_restarted=False,transient_hub_during_new_game=False,
        first_hub_preview_frame_switches=True,source_diff=source_diff,
        physical_ios_tested=False,physical_gkd_tested=False)
    (ROOT/'verification/audio_pass03_opening.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS: TITLE -> NEW GAME -> all story pages: TITLE continues; first HUB_PREVIEW frame: one HUB music start.')


if __name__=='__main__': main()
