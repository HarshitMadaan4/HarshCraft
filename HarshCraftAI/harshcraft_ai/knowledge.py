"""Static Minecraft 1.21 knowledge used by every skill (all names are WITHOUT the 'minecraft:' prefix)."""
from __future__ import annotations
import math

def short(name: str) -> str:
    return name.split(":", 1)[1] if ":" in name else name

# ----------------------------------------------------------------- materials
WOODS = ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"]
LOGS = [f"{w}_log" for w in WOODS]
PLANKS = [f"{w}_planks" for w in WOODS]
COBBLE = ["cobblestone", "cobbled_deepslate", "blackstone"]
TAGS = {
    "#planks": PLANKS, "#logs": LOGS, "#cobble": COBBLE,
    "#coal": ["coal", "charcoal"],
}
TIER = {"wooden": 1, "golden": 1, "stone": 2, "iron": 3, "diamond": 4, "netherite": 5}
TOOLS = ["pickaxe", "axe", "shovel", "hoe", "sword"]

def tool_info(item: str):
    """-> (kind, tier) for a tool item, else None."""
    for m, t in TIER.items():
        for k in TOOLS:
            if item == f"{m}_{k}":
                return k, t
    if item == "shears":
        return "shears", 1
    return None

def matches(item: str, want: str) -> bool:
    """True if `item` satisfies `want` (a concrete name or a '#tag')."""
    return item in TAGS[want] if want.startswith("#") else item == want

# ----------------------------------------------------------------- blocks
UNBREAKABLE = {"bedrock", "barrier", "command_block", "chain_command_block", "repeating_command_block",
               "end_portal", "end_portal_frame", "end_gateway", "nether_portal", "reinforced_deepslate",
               "structure_block", "jigsaw", "light", "water", "lava"}
HAZARD_IN = {"fire", "soul_fire", "lava", "cactus", "sweet_berry_bush", "cobweb", "campfire", "soul_campfire",
             "wither_rose", "powder_snow", "magma_block", "tnt", "bubble_column"}
HAZARD_BELOW = {"magma_block", "cactus", "campfire", "soul_campfire", "fire", "lava"}
GRAVITY = {"sand", "red_sand", "gravel", "anvil"}
STONE_WORDS = ("stone", "deepslate", "andesite", "granite", "diorite", "tuff", "calcite", "basalt", "blackstone",
               "netherrack", "end_stone", "sandstone", "brick", "terracotta", "concrete", "obsidian", "furnace",
               "_ore", "prismarine", "quartz", "purpur", "dripstone", "iron_block", "gold_block", "diamond_block")
SHOVEL_WORDS = ("dirt", "grass_block", "sand", "gravel", "clay", "snow", "soul_sand", "soul_soil", "mud", "podzol",
                "mycelium", "farmland", "path", "rooted")
AXE_WORDS = ("_log", "_wood", "_stem", "planks", "crafting_table", "chest", "bookshelf", "barrel", "_door",
             "fence", "_sign", "ladder", "pumpkin", "melon", "bamboo", "scaffolding", "note_block", "jukebox", "lectern")
ORE_TIER = {"coal_ore": 1, "copper_ore": 2, "iron_ore": 2, "lapis_ore": 2, "gold_ore": 3, "redstone_ore": 3,
            "diamond_ore": 3, "emerald_ore": 3, "obsidian": 4, "ancient_debris": 4, "nether_gold_ore": 1,
            "nether_quartz_ore": 1}

def block_info(name: str):
    """-> (hardness, tool_kind|None, min_tier). Approximate vanilla values."""
    n = short(name)
    base = n.replace("deepslate_", "")
    if n in UNBREAKABLE:
        return 1e9, None, 99
    if base in ORE_TIER or n in ORE_TIER:
        return 3.0 if "deepslate" not in n else 4.5, "pickaxe", ORE_TIER.get(base, ORE_TIER.get(n, 1))
    if n == "obsidian":
        return 50.0, "pickaxe", 4
    if "leaves" in n:
        return 0.2, None, 0
    if any(w in n for w in AXE_WORDS):
        return 2.0, "axe", 0
    if any(w in n for w in SHOVEL_WORDS):
        return 0.6, "shovel", 0
    if any(w in n for w in STONE_WORDS):
        return (3.0 if "deepslate" in n else 1.5), "pickaxe", 1
    if n.endswith("glass") or n.endswith("glass_pane") or n in ("ice", "packed_ice"):
        return 0.4, None, 0
    if n in ("grass", "short_grass", "tall_grass", "fern", "dead_bush", "vine", "seagrass", "kelp") or "flower" in n:
        return 0.0, None, 0
    return 1.0, None, 0

def breakable(name: str) -> bool:
    return short(name) not in UNBREAKABLE and block_info(name)[0] < 1e8

def drop_of(name: str) -> str | None:
    n = short(name)
    simple = {"stone": "cobblestone", "deepslate": "cobbled_deepslate", "grass_block": "dirt", "podzol": "dirt",
              "mycelium": "dirt", "farmland": "dirt", "coal_ore": "coal", "iron_ore": "raw_iron",
              "copper_ore": "raw_copper", "gold_ore": "raw_gold", "diamond_ore": "diamond",
              "emerald_ore": "emerald", "lapis_ore": "lapis_lazuli", "redstone_ore": "redstone",
              "nether_quartz_ore": "quartz", "clay": "clay_ball", "glowstone": "glowstone_dust"}
    base = n.replace("deepslate_", "") if n.endswith("_ore") else n
    if base in simple:
        return simple[base]
    if n in ("short_grass", "tall_grass", "fern", "dead_bush", "vine", "water", "lava") or "leaves" in n:
        return None
    return n

# item -> block-name fragments to scan for ("=" prefix = exact match).
def _ex(*names):
    return [f"=minecraft:{n}" for n in names]
SOURCES = {
    "log": ["_log"], "coal": _ex("coal_ore", "deepslate_coal_ore"),
    "raw_iron": _ex("iron_ore", "deepslate_iron_ore"), "raw_copper": _ex("copper_ore", "deepslate_copper_ore"),
    "raw_gold": _ex("gold_ore", "deepslate_gold_ore"), "diamond": _ex("diamond_ore", "deepslate_diamond_ore"),
    "emerald": _ex("emerald_ore", "deepslate_emerald_ore"), "redstone": _ex("redstone_ore", "deepslate_redstone_ore"),
    "lapis_lazuli": _ex("lapis_ore", "deepslate_lapis_ore"), "cobblestone": _ex("stone", "cobblestone", "andesite", "diorite", "granite"),
    "cobbled_deepslate": _ex("deepslate"), "dirt": _ex("dirt", "grass_block", "podzol", "coarse_dirt"),
    "sand": _ex("sand"), "gravel": _ex("gravel"), "clay_ball": _ex("clay"), "sandstone": _ex("sandstone"),
    "obsidian": _ex("obsidian"), "netherrack": _ex("netherrack"), "snowball": _ex("snow"),
}
for _l in LOGS:
    SOURCES[_l] = [f"=minecraft:{_l}"]
# best y-levels to search underground for an ore
ORE_DEPTH = {"coal": 45, "raw_iron": 16, "raw_copper": 40, "raw_gold": -16, "diamond": -58, "redstone": -58,
             "lapis_lazuli": 0, "emerald": 100, "obsidian": 11}

# ----------------------------------------------------------------- food / mobs
FOOD = {"cooked_beef": 8, "cooked_porkchop": 8, "pumpkin_pie": 8, "cooked_mutton": 6, "cooked_chicken": 6,
        "cooked_salmon": 6, "golden_carrot": 6, "mushroom_stew": 6, "cooked_cod": 5, "bread": 5, "baked_potato": 5,
        "apple": 4, "carrot": 3, "beef": 3, "porkchop": 3, "mutton": 2, "chicken": 2, "cod": 2, "salmon": 2,
        "melon_slice": 2, "cookie": 2, "sweet_berries": 2, "potato": 1, "beetroot": 1, "dried_kelp": 1,
        "rotten_flesh": 4}
AVOID_FOOD = {"spider_eye", "pufferfish", "poisonous_potato", "suspicious_stew", "rotten_flesh"}
RAW_MEAT = {"beef": "cooked_beef", "porkchop": "cooked_porkchop", "mutton": "cooked_mutton",
            "chicken": "cooked_chicken", "cod": "cooked_cod", "salmon": "cooked_salmon", "potato": "baked_potato"}
ANIMALS = {"cow": "beef", "pig": "porkchop", "sheep": "mutton", "chicken": "chicken", "rabbit": "rabbit"}
ZOMBIES = {"zombie", "husk", "drowned", "zombie_villager", "zombified_piglin"}
SKELETONS = {"skeleton", "stray", "bogged", "wither_skeleton"}
SPIDERS = {"spider", "cave_spider"}
PASSIVE_AVOID = {"enderman", "zombified_piglin", "iron_golem", "wolf", "piglin"}  # never start fights with these

def mob_class(t: str) -> int:
    """0 zombie-like, 1 skeleton-like, 2 creeper, 3 spider, 4 other"""
    if t in ZOMBIES: return 0
    if t in SKELETONS: return 1
    if t == "creeper": return 2
    if t in SPIDERS: return 3
    return 4

WEAPON_DPS = {"sword": (None, 1.6), "axe": (None, 1.0)}
SWORD_DMG = {"wooden": 4, "golden": 4, "stone": 5, "iron": 6, "diamond": 7, "netherite": 8}
AXE_DMG = {"wooden": 7, "golden": 7, "stone": 9, "iron": 9, "diamond": 9, "netherite": 10}

def weapon_stats(item: str):
    """-> (damage, attacks_per_second) or None"""
    for m in TIER:
        if item == f"{m}_sword": return SWORD_DMG[m] + 0.0, 1.6
        if item == f"{m}_axe": return AXE_DMG[m] + 0.0, {"wooden": .8, "golden": 1.0, "stone": .8, "iron": .9, "diamond": 1.0, "netherite": 1.0}[m]
    return None

BUILD_MATERIALS = ["cobblestone", "cobbled_deepslate", "stone", "dirt", "oak_planks", "spruce_planks", "birch_planks",
                   "jungle_planks", "acacia_planks", "dark_oak_planks", "mangrove_planks", "cherry_planks",
                   "netherrack", "andesite", "granite", "diorite", "blackstone", "sandstone"] + LOGS
FUELS = {"coal": 8.0, "charcoal": 8.0, "blaze_rod": 12.0, "oak_planks": 1.5, "spruce_planks": 1.5, "birch_planks": 1.5,
         "jungle_planks": 1.5, "acacia_planks": 1.5, "dark_oak_planks": 1.5, "mangrove_planks": 1.5,
         "cherry_planks": 1.5, "stick": 0.5}
SMELTS = {"raw_iron": "iron_ingot", "raw_gold": "gold_ingot", "raw_copper": "copper_ingot", "sand": "glass",
          "cobblestone": "stone", "clay_ball": "brick", "kelp": "dried_kelp", "cobbled_deepslate": "deepslate",
          **{k: v for k, v in RAW_MEAT.items()}, **{l: "charcoal" for l in LOGS}}

# ----------------------------------------------------------------- recipes
class Recipe:
    __slots__ = ("result", "count", "pattern", "key", "shapeless", "w", "h")
    def __init__(self, result, count, pattern=None, key=None, shapeless=None):
        self.result, self.count = result, count
        self.shapeless = shapeless            # list of ingredient names/tags (no layout) or None
        if shapeless is None:
            self.pattern, self.key = pattern, key
            self.h, self.w = len(pattern), max(len(r) for r in pattern)
        else:
            n = len(shapeless)
            self.pattern, self.key = None, None
            self.w = self.h = 1 if n == 1 else (2 if n <= 4 else 3)
    @property
    def needs_table(self): return self.w > 2 or self.h > 2
    def cells(self):
        """-> list of (row, col, ingredient) for shaped; (i//w, i%w, ing) for shapeless."""
        if self.shapeless is not None:
            return [(i // self.w, i % self.w, ing) for i, ing in enumerate(self.shapeless)]
        return [(r, c, self.key[ch]) for r, row in enumerate(self.pattern) for c, ch in enumerate(row) if ch != " "]
    def ingredients(self):
        out = {}
        for _, _, ing in self.cells():
            out[ing] = out.get(ing, 0) + 1
        return out

RECIPES: dict[str, Recipe] = {}
def _r(result, count, pattern=None, key=None, shapeless=None):
    RECIPES[result] = Recipe(result, count, pattern, key, shapeless)

for w in WOODS:
    _r(f"{w}_planks", 4, shapeless=[f"{w}_log"])
    _r(f"{w}_slab", 6, ["PPP"], {"P": f"{w}_planks"})
    _r(f"{w}_stairs", 4, ["P  ", "PP ", "PPP"], {"P": f"{w}_planks"})
    _r(f"{w}_door", 3, ["PP", "PP", "PP"], {"P": f"{w}_planks"})
    _r(f"{w}_fence", 3, ["PSP", "PSP"], {"P": f"{w}_planks", "S": "stick"})
    _r(f"{w}_trapdoor", 2, ["PPP", "PPP"], {"P": f"{w}_planks"})
_r("stick", 4, ["P", "P"], {"P": "#planks"})
_r("crafting_table", 1, ["PP", "PP"], {"P": "#planks"})
_r("chest", 1, ["PPP", "P P", "PPP"], {"P": "#planks"})
_r("furnace", 1, ["CCC", "C C", "CCC"], {"C": "#cobble"})
_r("torch", 4, ["C", "S"], {"C": "#coal", "S": "stick"})
_r("ladder", 3, ["S S", "SSS", "S S"], {"S": "stick"})
_r("bucket", 1, ["I I", " I "], {"I": "iron_ingot"})
_r("shears", 1, [" I", "I "], {"I": "iron_ingot"})
_r("bow", 1, [" ST", "S T", " ST"], {"S": "stick", "T": "string"})
_r("arrow", 4, ["F", "S", "E"], {"F": "flint", "S": "stick", "E": "feather"})
_r("bread", 1, ["WWW"], {"W": "wheat"})
_r("stone_bricks", 4, ["SS", "SS"], {"S": "stone"})
_r("glass_pane", 16, ["GGG", "GGG"], {"G": "glass"})
_r("sandstone", 1, ["SS", "SS"], {"S": "sand"})
_r("iron_block", 1, ["III", "III", "III"], {"I": "iron_ingot"})
_r("white_bed", 1, ["WWW", "PPP"], {"W": "white_wool", "P": "#planks"})
_r("shield", 1, ["PIP", "PPP", " P "], {"P": "#planks", "I": "iron_ingot"})
for mat, ing in [("wooden", "#planks"), ("stone", "#cobble"), ("iron", "iron_ingot"),
                 ("golden", "gold_ingot"), ("diamond", "diamond")]:
    k = {"M": ing, "S": "stick"}
    _r(f"{mat}_pickaxe", 1, ["MMM", " S ", " S "], k)
    _r(f"{mat}_axe", 1, ["MM", "MS", " S"], k)
    _r(f"{mat}_shovel", 1, ["M", "S", "S"], k)
    _r(f"{mat}_hoe", 1, ["MM", " S", " S"], k)
    _r(f"{mat}_sword", 1, ["M", "M", "S"], k)
for mat, ing in [("iron", "iron_ingot"), ("diamond", "diamond"), ("golden", "gold_ingot"), ("leather", "leather")]:
    k = {"M": ing}
    _r(f"{mat}_helmet", 1, ["MMM", "M M"], k)
    _r(f"{mat}_chestplate", 1, ["M M", "MMM", "MMM"], k)
    _r(f"{mat}_leggings", 1, ["MMM", "M M", "M M"], k)
    _r(f"{mat}_boots", 1, ["M M", "M M"], k)

# ----------------------------------------------------------------- aliases for NLP
ITEM_ALIASES = {
    "wood": "log", "woods": "log", "log": "log", "logs": "log", "tree": "log", "trees": "log", "timber": "log",
    "stone": "cobblestone", "stones": "cobblestone", "cobble": "cobblestone", "cobblestone": "cobblestone",
    "iron": "iron_ingot", "irons": "iron_ingot", "iron ore": "raw_iron", "raw iron": "raw_iron",
    "gold": "gold_ingot", "gold ore": "raw_gold", "copper": "copper_ingot", "diamond": "diamond", "diamonds": "diamond",
    "coal": "coal", "charcoal": "charcoal", "redstone": "redstone", "lapis": "lapis_lazuli", "emerald": "emerald",
    "emeralds": "emerald", "dirt": "dirt", "soil": "dirt", "sand": "sand", "gravel": "gravel", "clay": "clay_ball",
    "obsidian": "obsidian", "planks": "oak_planks", "plank": "oak_planks", "sticks": "stick", "stick": "stick",
    "table": "crafting_table", "crafting table": "crafting_table", "workbench": "crafting_table",
    "furnace": "furnace", "chest": "chest", "torch": "torch", "torches": "torch", "bucket": "bucket", "bow": "bow",
    "arrows": "arrow", "arrow": "arrow", "bread": "bread", "food": "food", "meat": "food", "bed": "white_bed",
    "ladder": "ladder", "ladders": "ladder", "door": "oak_door", "doors": "oak_door", "shield": "shield",
    "shears": "shears", "glass": "glass", "bricks": "stone_bricks", "stone bricks": "stone_bricks",
    "sandstone": "sandstone", "beef": "beef", "steak": "cooked_beef", "pork": "porkchop", "porkchop": "porkchop",
    "chicken": "chicken", "mutton": "mutton", "apple": "apple", "apples": "apple", "slab": "oak_slab", "stairs": "oak_stairs",
}
for _m in list(TIER) + ["wood"]:
    for _k in TOOLS:
        ITEM_ALIASES[f"{_m} {_k}"] = f"{'wooden' if _m == 'wood' else _m}_{_k}"
for _k in TOOLS:
    ITEM_ALIASES[_k] = f"@best_{_k}"            # resolved by planner to best tier obtainable
for _p in ("helmet", "chestplate", "leggings", "boots"):
    for _m in ("iron", "diamond", "golden", "leather"):
        ITEM_ALIASES[f"{_m} {_p}"] = f"{_m}_{_p}"
for _m in ("iron", "diamond"):
    ITEM_ALIASES[f"{_m} armor"] = f"@armor_{_m}"
MOB_ALIASES = {"zombie": "zombie", "zombies": "zombie", "skeleton": "skeleton", "skeletons": "skeleton",
               "creeper": "creeper", "creepers": "creeper", "spider": "spider", "spiders": "spider",
               "monster": "*hostile", "monsters": "*hostile", "mob": "*hostile", "mobs": "*hostile",
               "enemy": "*hostile", "enemies": "*hostile", "hostile": "*hostile", "hostiles": "*hostile",
               "cow": "cow", "cows": "cow", "pig": "pig", "pigs": "pig", "sheep": "sheep", "chicken": "chicken",
               "chickens": "chicken", "rabbit": "rabbit", "rabbits": "rabbit", "witch": "witch", "drowned": "drowned",
               "husk": "husk", "slime": "slime", "phantom": "phantom", "pillager": "pillager"}
