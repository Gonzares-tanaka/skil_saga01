"""Static, editable RARE visual families; no gameplay effects or RNG."""

RARE_PRESENTATION_IDS = ('rare_impact', 'rare_slash', 'rare_magic',
                         'rare_dark', 'rare_heal', 'rare_support')
RARE_ASSET_BANK = 1
RARE_FRAME_SIZE = 32
RARE_FRAME_COUNT = 3
# Three horizontal frames per family, in previously empty Image Bank 1 cells.
RARE_SPRITES = {
    'rare_impact': (0, 96), 'rare_slash': (96, 96),
    'rare_magic': (0, 128), 'rare_dark': (96, 128),
    'rare_heal': (0, 160), 'rare_support': (96, 160),
}
RARE_CAST_FRAMES = 4
RARE_EFFECT_FRAMES = 9
RARE_FEEDBACK_FRAMES = 3
RARE_SHAKE_OFFSETS = ((1, 0), (-1, 0), (0, 1))


def rare_presentation_id(skill):
    """Missing/unknown IDs and every other rarity retain the legacy visual."""
    ident = getattr(skill, 'presentation_id', None)
    return ident if (getattr(skill, 'rarity', None) == 'RARE'
                     and isinstance(ident, str) and ident in RARE_SPRITES) else None
