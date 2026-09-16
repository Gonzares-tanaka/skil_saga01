"""Display labels; identifiers in JSON remain stable."""
TYPES = {"POWER": "力型", "SPEED": "速型", "MIND": "知型"}
RARITIES = {"BASIC": "基本", "COMMON": "通常", "UNCOMMON": "上位", "RARE": "希少", "LEGEND": "伝説"}
TARGETS = {"enemy": "敵", "ally": "味方", "self": "自分"}
OUTCOMES = {"VICTORY": "勝利", "DEFEAT": "全滅", "DRAW": "引分"}
EFFECTS = {"armor_break": "装甲低下", "weaken": "攻撃低下", "slow": "速度低下",
           "power_up": "力上昇", "focus": "知力上昇", "guard_up": "守り上昇"}
BUFFS = {"power_up", "focus", "guard_up"}
CATEGORIES = {"physical": "ATTACK", "speed": "ATTACK", "magic": "MAGIC",
              "healing": "HEAL", "support": "SUPPORT"}
