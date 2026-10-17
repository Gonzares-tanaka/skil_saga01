"""Editable resource-bank audio. BGM 1-3 / SE 0; native never calls playm."""
import sys
import time
import pyxel
from .content import ROOT
from .battle_transition import SOUND_BATTLE_TRANSITION

BGM_IDS = {
    'bgm_title': ('scene', 0), 'bgm_hub': ('scene', 1),
    'bgm_area1': ('scene', 2), 'bgm_area2': ('scene', 3),
    'bgm_area3': ('scene', 4), 'bgm_battle': ('battle', 0),
    'bgm_boss': ('scene', 5), 'bgm_final': ('scene', 6),
    'bgm_omen': ('omen', 0),
}
BATTLE_BGM = {'normal': 'bgm_battle', 'quest_hunt': 'bgm_battle',
              'boss': 'bgm_boss', 'guardian': 'bgm_boss',
              'demon': 'bgm_boss', 'elysion': 'bgm_boss'}
SE_IDS = {'se_stairs': 50, 'se_treasure': 51, 'se_trap_damage': 52,
          'se_healing_spring': 53, 'se_pitfall': 54, 'se_quest_complete': 55}
FIELD_SE = {'stairs': 'se_stairs', 'chest': 'se_treasure',
            'poison': 'se_trap_damage', 'pit': 'se_pitfall', 'spring': 'se_healing_spring'}
ATTACK_SOUND, SKILL_SOUND, CHEST_SOUND, MASTERED_SOUND = 60, 61, 62, 63
SOUND_RUN_SUCCESS, SOUND_ENEMY_DEFEAT = 30, 31
CUE_SOUNDS = {'battle_transition': SOUND_BATTLE_TRANSITION, 'attack': ATTACK_SOUND,
              'skill': SKILL_SOUND, 'chest': CHEST_SOUND, 'mastered': MASTERED_SOUND,
              'run_success': SOUND_RUN_SUCCESS, 'enemy_defeat': SOUND_ENEMY_DEFEAT}
BGM_CHANNELS = (1, 2, 3)
COMMON_SOUNDS = (30, 31, 50, 51, 52, 53, 54, 55, 59, 60, 61, 62, 63)
RESOURCE_BANKS = {'scene': ROOT / 'game.pyxres', 'battle': ROOT / 'assets/battle_music.pyxres',
                  'omen': ROOT / 'assets/omen_music.pyxres'}
TITLE_STATES = ('title', 'title_no_save')
HUB_STATES = ('title_fade', 'intro', 'hub_preview', 'hub_intro', 'camp', 'facility',
              'archive', 'shop', 'pub', 'quest_board', 'quest_type', 'quest_preview',
              'quest_record', 'quest_thanks', 'quest_reward', 'return_result',
              'relearn_character', 'relearn_list', 'relearn_confirm', 'save_confirm',
              'save_result', 'amrita_offer')
FIELD_STATES = ('explore', 'menu', 'items', 'item_target', 'clear', 'boss_message',
                'boss_after', 'guardian_warning', 'guardian_after')
BATTLE_STATES = ('command', 'skill', 'target', 'battle_item', 'resolve', 'amrita_effect')


def area_bgm(floor):
    """Dungeon floor is zero-based; no dependency on display names."""
    return 'bgm_area1' if floor < 5 else 'bgm_area2' if floor < 10 else 'bgm_area3'


def _play_music(index, loop, sec=0):
    options = dict(loop=loop)
    if sec: options['sec'] = sec
    if sys.platform == 'emscripten':
        pyxel.playm(index, **options)
        return True
    # Preserve the SDL lock ordering of the verified native workaround.
    sequences = [list(sequence) for sequence in pyxel.musics[index].seqs]
    played = False
    for channel, sequence in enumerate(sequences):
        if sequence:
            pyxel.play(channel, sequence, **options)
            played = True
    return played


class AudioManager:
    """Two small Editor banks cached once, one current BGM, one delayed SE."""
    def __init__(self):
        self.banks = {}
        self.bank = None
        self.current_bgm = None
        self.started_at = 0
        self.start_offset = 0
        self.boss_offset = 0
        self.pending_se = None
        self.enabled = True
        self.bgm_started = False
        self.retry_after = 0

    def load(self):
        for name, path in RESOURCE_BANKS.items():
            try:
                pyxel.load(str(path), exclude_images=True, exclude_tilemaps=True)
                self.banks[name] = (list(pyxel.sounds), list(pyxel.musics))
            except Exception:
                continue
        scene = self.banks.get('scene')
        if scene:
            for sounds, _ in self.banks.values():
                for slot in COMMON_SOUNDS:
                    # Existing editable cues keep their original canonical file.
                    source = self.banks.get('battle', scene) if slot in (30, 31, 59) else scene
                    sounds[slot] = source[0][slot]
        self.bank = None
        if 'battle' in self.banks: self._install_bank('battle')

    def _install_bank(self, name):
        if self.bank != name:
            sounds, musics = self.banks[name]
            pyxel.sounds[:] = sounds
            pyxel.musics[:] = musics
            self.bank = name

    def play_bgm(self, audio_id):
        if audio_id not in BGM_IDS: return False
        if self.current_bgm == audio_id:
            if self.bgm_started: return True
            if not self.enabled or time.monotonic() < self.retry_after: return False
        self.stop_bgm()
        self.current_bgm = audio_id
        self.started_at = time.monotonic()
        self.start_offset = self.boss_offset if audio_id == 'bgm_boss' else 0
        if audio_id != 'bgm_boss': self.boss_offset = 0
        if not self.enabled: return False
        try:
            bank, index = BGM_IDS[audio_id]
            self._install_bank(bank)
            self.bgm_started = bool(_play_music(index, True, self.start_offset)
                                    if self.start_offset else _play_music(index, True))
        except Exception:
            self.bgm_started = False
        if not self.bgm_started: self.retry_after = time.monotonic() + .5
        return self.bgm_started

    def stop_bgm(self):
        if self.current_bgm == 'bgm_boss' and self.bgm_started:
            try:
                music = self.banks['scene'][1][BGM_IDS['bgm_boss'][1]]
                length = sum(self.banks['scene'][0][n].total_sec() for n in music.seqs[1])
                self.boss_offset = (self.start_offset + time.monotonic() - self.started_at) % length
            except Exception:
                self.boss_offset = 0
        self.current_bgm = None
        self.bgm_started = False
        for channel in BGM_CHANNELS:
            try: pyxel.stop(channel)
            except Exception: pass

    def play_victory(self):
        self.stop_bgm()
        if not self.enabled: return False
        try:
            self._install_bank('battle')
            return _play_music(1, False)
        except Exception:
            return False

    def play_se(self, audio_id, delay_frames=0):
        if audio_id not in SE_IDS: return False
        if delay_frames:
            self.pending_se = (audio_id, delay_frames)
            return True
        if not self.enabled: return False
        try:
            pyxel.play(0, SE_IDS[audio_id])
            return True
        except Exception:
            return False

    def update(self):
        if self.pending_se:
            audio_id, remaining = self.pending_se
            self.pending_se = (audio_id, remaining - 1) if remaining > 1 else None
            if remaining <= 1: self.play_se(audio_id)


_audio = AudioManager()


def init_sound():
    global _audio
    _audio = AudioManager()
    _audio.load()
    return _audio


def play_cue(cue):
    if cue in CUE_SOUNDS and _audio.enabled:
        try: pyxel.play(0, CUE_SOUNDS[cue])
        except Exception: pass


def start_battle_music(kind='normal'):
    return _audio.play_bgm(BATTLE_BGM.get(kind, 'bgm_battle'))


def play_victory_music():
    return _audio.play_victory()


def music_is_playing():
    try: return any(pyxel.play_pos(channel) is not None for channel in BGM_CHANNELS)
    except Exception: return False


def stop_battle_music():
    _audio.stop_bgm()
