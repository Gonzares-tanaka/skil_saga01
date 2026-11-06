"""Editable Image Bank 2 facility layout (pixel coordinates)."""

HUB_IMAGE_BANK = 2
HUB_PICTURE_SIZE = 64
HUB_MENU_Y = 43
HUB_MENU_STEP = 17  # Four rows end at y=94, above the footer at y=111.
HUB_CURRENCY_RIGHT = 156
HUB_CURRENCY_Y = 2
HUB_CURRENCY_WIDTH = 16  # 4px units; reserve at most 64px of the header.
HUB_FACILITIES = ("GUILD", "TRAINING", "PUB", "SHOP", "DUNGEON", "ELEVATOR")
# Display labels are separate from stable facility/menu identifiers.
HUB_FACILITY_LABELS = ("ギルド", "訓練場", "パブ", "ショップ", "ダンジョン", "エレベーター")
# Original five positions stay intact; the sixth fits below the 64px picture.
HUB_POSITIONS = ((5, 16), (5, 35), (5, 54), (5, 73), (5, 92), (92, 92))
HUB_SELECTION_WIDTHS = (82, 82, 82, 82, 82, 66)

HUB_ICON_GUILD = (0, 0)
HUB_ICON_TRAINING = (16, 0)
HUB_ICON_PUB = (32, 0)
HUB_ICON_SHOP = (48, 0)
HUB_ICON_DUNGEON = (64, 0)
HUB_ICON_ELEVATOR = (80, 0)

HUB_PIC_GUILD = (0, 32)
HUB_PIC_TRAINING = (64, 32)
HUB_PIC_PUB = (128, 32)
HUB_PIC_SHOP = (0, 96)
HUB_PIC_DUNGEON = (64, 96)

HUB_ICONS = (HUB_ICON_GUILD, HUB_ICON_TRAINING, HUB_ICON_PUB,
             HUB_ICON_SHOP, HUB_ICON_DUNGEON, HUB_ICON_ELEVATOR)
HUB_PICTURES = (HUB_PIC_GUILD, HUB_PIC_TRAINING, HUB_PIC_PUB,
                HUB_PIC_SHOP, HUB_PIC_DUNGEON, HUB_PIC_DUNGEON)
HUB_DESCRIPTIONS = ("仲間と案内", "技の記録と再習得", "依頼と噂", "道具を買う", "迷宮へ出発", "攻略済みエリアへ")
HUB_MENUS = (
    ("PARTY STATUS", "QUEST RECORD", "SAVE", "HELP"),
    ("SKILL ARCHIVE", "RESTORE SKILL"),
    ("QUEST", "HEAR A RUMOR"),
    ("BUY ITEM", "EXIT"),
)
HUB_MENU_LABELS = {
    "PARTY STATUS": "パーティ", "QUEST RECORD": "クエスト記録", "SAVE": "セーブ",
    "HELP": "ヘルプ", "SKILL ARCHIVE": "スキル図鑑", "RESTORE SKILL": "スキル再取得",
    "QUEST": "クエスト", "HEAR A RUMOR": "噂を聞く", "BUY ITEM": "道具を買う", "EXIT": "戻る",
}
