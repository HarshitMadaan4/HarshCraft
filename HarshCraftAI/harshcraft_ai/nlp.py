"""Rule-based natural-language command parser (offline, works on speech-to-text output).
Optional LLM refinement lives in llm.py."""
from __future__ import annotations
import difflib
import re

from .knowledge import FOOD, ITEM_ALIASES, MOB_ALIASES, RECIPES, SMELTS
from .planner import Task

NUMS = {"zero": 0, "one": 1, "a": 1, "an": 1, "two": 2, "couple": 2, "three": 3, "few": 4, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "dozen": 12,
        "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "hundred": 100,
        "stack": 64, "some": 6, "several": 6, "lot": 20, "lots": 20, "bunch": 10}
FILLER = re.compile(r"\b(please|hey|ok|okay|hi|hello|could you|can you|would you|will you|i want you to|i need you to|"
                    r"go ahead and|bot|harsh|harshcraft|now|just|kindly|for me|the|some of|of the)\b")

VOCAB: dict[str, str] = {}
VOCAB.update(ITEM_ALIASES)
for r in RECIPES:
    VOCAB.setdefault(r.replace("_", " "), r)
for f in FOOD:
    VOCAB.setdefault(f.replace("_", " "), f)
for r in SMELTS.values():
    VOCAB.setdefault(r.replace("_", " "), r)
VOCAB_KEYS = sorted(VOCAB, key=len, reverse=True)
NEAREST = {"tree": ["_log"], "trees": ["_log"], "water": ["=minecraft:water"], "lava": ["=minecraft:lava"],
           "table": ["=minecraft:crafting_table"], "crafting table": ["=minecraft:crafting_table"],
           "furnace": ["=minecraft:furnace"], "chest": ["=minecraft:chest"], "stone": ["=minecraft:stone"],
           "iron": ["iron_ore"], "coal": ["coal_ore"], "diamond": ["diamond_ore"], "sand": ["=minecraft:sand"],
           "cave": ["=minecraft:stone"], "bed": ["_bed"], "village": ["=minecraft:bell"]}


def num_in(text: str, default: int = 1) -> int:
    m = re.search(r"\b(\d+)\b", text)
    if m:
        return max(1, int(m.group(1)))
    for w in re.findall(r"[a-z]+", text):
        if w in NUMS:
            return NUMS[w]
    return default


def find_item(text: str):
    t = " " + text + " "
    for k in VOCAB_KEYS:
        if f" {k} " in t or f" {k}s " in t or f" {k}es " in t:
            return VOCAB[k]
    toks = re.findall(r"[a-z]+", text)
    for n in (3, 2, 1):
        for i in range(len(toks) - n + 1):
            cand = " ".join(toks[i:i + n])
            hit = difflib.get_close_matches(cand, VOCAB_KEYS, n=1, cutoff=0.82)
            if hit:
                return VOCAB[hit[0]]
    return None


def find_mob(text: str):
    for w in re.findall(r"[a-z]+", text):
        if w in MOB_ALIASES:
            return MOB_ALIASES[w]
    toks = re.findall(r"[a-z]+", text)
    for w in toks:
        hit = difflib.get_close_matches(w, list(MOB_ALIASES), n=1, cutoff=0.84)
        if hit:
            return MOB_ALIASES[hit[0]]
    return None


def find_dims(text: str):
    m = re.search(r"(\d+)\s*(?:x|by|\*)\s*(\d+)(?:\s*(?:x|by|\*)\s*(\d+))?", text)
    if m:
        return tuple(int(g) for g in m.groups() if g)
    d = {}
    for key, pat in (("long", r"(\d+)\s*(?:blocks?\s*)?(?:long|wide|length|width)"),
                     ("high", r"(\d+)\s*(?:blocks?\s*)?(?:high|tall|height)")):
        mm = re.search(pat, text)
        if mm:
            d[key] = int(mm.group(1))
    return d or None


def find_material(text: str):
    mm = re.search(r"(?:of|from|using|with|out of)\s+([a-z ]+)$", text.strip())
    if mm:
        it = find_item(mm.group(1))
        if it:
            return "oak_planks" if it in ("log",) else it
    return None


def split_clauses(text: str):
    parts = re.split(r"\b(?:and then|after that|afterwards|then|and also)\b|[;,]", text)
    out = []
    for p in parts:
        sub = re.split(r"\band\b(?=\s+(?:go|get|collect|gather|mine|craft|make|build|kill|attack|eat|smelt|cook|"
                       r"follow|explore|come|stop|chop|cut|find|fight|hunt|place|pillar|bridge|shelter|survive))", p)
        out += [s.strip() for s in sub if s.strip()]
    return out


def parse_clause(c: str):
    raw = c
    c = FILLER.sub(" ", c)
    c = re.sub(r"\s+", " ", c).strip()
    if not c:
        return [], ""
    if re.search(r"\b(stop|cancel|halt|abort|never mind|nevermind|forget it|freeze|enough)\b", c):
        return [Task("stop")], "Stopping."
    if re.search(r"\b(status|inventory|what do i have|what do you have|what have you got|how are you|health|"
                 r"where are you|what are you doing|report)\b", c):
        return [Task("status")], ""
    if re.search(r"\b(set home|this is home|remember this|mark home|save this place)\b", c):
        return [Task("set_home")], "Home saved."
    if re.search(r"\b(go home|return home|come home|go back home|back home|head home)\b", c):
        return [Task("go_home")], "Heading home."
    if re.search(r"\b(follow|come with)\b", c):
        return [Task("follow")], "Following."
    if re.search(r"\b(survive|stay alive|stay safe|keep yourself alive|survival mode)\b", c):
        n = num_in(c, 5)
        mins = n if re.search(r"minute", c) else max(1, n // 60) if re.search(r"second", c) else 5
        return [Task("survive", args={"seconds": mins * 60})], f"Surviving for {mins} minutes."
    if re.search(r"\b(shelter|take cover|hide|safe house|bunker)\b", c):
        return [Task("shelter")], "Building a shelter."
    if re.search(r"\b(pillar|tower up|build up|climb up|go up)\b", c):
        return [Task("pillar", n=num_in(c, 3))], "Pillaring up."
    if re.search(r"\bbridge\b", c):
        return [Task("bridge", n=num_in(c, 8))], "Building a bridge."
    if re.search(r"\b(eat|hungry|starving|meal|food please)\b", c) and not re.search(r"\b(get|collect|gather|find)\b", c):
        return [Task("eat")], "Eating."
    if re.search(r"\b(explore|wander|scout|look around|roam)\b", c):
        return [Task("explore", n=num_in(c, 3))], "Exploring."
    # coordinates
    mc = re.search(r"(-?\d+)[\s,]+(-?\d+)(?:[\s,]+(-?\d+))?", c)
    if re.search(r"\b(go|goto|walk|travel|move|head|navigate|run|teleport|come)\b", c) and mc:
        a = [int(g) for g in mc.groups() if g is not None]
        if len(a) == 2:
            return [Task("goto", args={"x": a[0], "y": None, "z": a[1]})], f"Going to {a[0]}, {a[1]}."
        return [Task("goto", args={"x": a[0], "y": a[1], "z": a[2]})], f"Going to {a[0]}, {a[1]}, {a[2]}."
    if re.search(r"\b(go|goto|walk|travel|move|head|navigate|run|find)\b", c):
        for k in sorted(NEAREST, key=len, reverse=True):
            if re.search(rf"\b{k}\b", c) and not re.search(r"\b(collect|gather|mine|get|chop|cut)\b", c):
                return [Task("goto_block", k, args={"frag": NEAREST[k]})], f"Going to the nearest {k}."
    # build structures
    mb = re.search(r"\b(house|hut|home|wall|tower|platform|floor|cabin)\b", c)
    if re.search(r"\b(build|construct|erect|put up)\b", c) and mb:
        kind = {"home": "house", "cabin": "house"}.get(mb.group(1), mb.group(1))
        dims = find_dims(c)
        if isinstance(dims, dict):
            if kind == "wall":
                dims = (dims.get("long", 6), dims.get("high", 3))
            elif kind == "tower":
                dims = (dims.get("high", 6),)
            else:
                dims = None
        return [Task("build", kind, args={"dims": dims, "material": find_material(c)})], f"Building a {kind}."
    if re.search(r"\b(smelt|cook|bake|roast|fry)\b", c):
        it = find_item(re.sub(r"\b(smelt|cook|bake|roast|fry)\b", "", c))
        if it is None or it == "food":
            return [Task("cook_all")], "Cooking everything I can."
        return [Task("get", SMELTS.get(it, it), num_in(c, 1), {"relative": True})], f"Smelting {it.replace('_', ' ')}."
    if re.search(r"\b(kill|attack|fight|slay|destroy|defeat|fend|defend|clear|eliminate|battle|hit)\b", c):
        mob = find_mob(c)
        return [Task("kill", mob or "*hostile", num_in(c, 99))], f"Fighting {mob or 'hostile mobs'}."
    if re.search(r"\b(hunt|slaughter)\b", c):
        mob = find_mob(c) or "cow"
        return [Task("hunt", mob, num_in(c, 1))], f"Hunting {mob}."
    if re.search(r"\b(craft|make|create|forge|assemble|produce)\b", c):
        it = find_item(c)
        if it:
            return [Task("get", it, num_in(c, 1), {"relative": True})], f"Crafting {it.replace('_', ' ').lstrip('@')}."
    if re.search(r"\b(collect|gather|get|mine|chop|cut|harvest|dig|fetch|bring|find|grab|obtain|farm|need|want|"
                 r"acquire|loot|fell)\b", c):
        it = find_item(c)
        if it == "food":
            return [Task("food", n=num_in(c, 3))], "Getting food."
        if it:
            return [Task("get", it, num_in(c, 1 if "tool" in c else 4 if not re.search(r"\d", c) and not any(w in NUMS for w in c.split()) else 1), {"relative": True})], \
                f"Getting {it.replace('_', ' ')}."
    if re.search(r"\b(place|put)\b", c):
        it = find_item(c)
        if it:
            return [Task("place", it, num_in(c, 1))], f"Placing {it.replace('_', ' ')}."
    if re.fullmatch(r"(hi|hello|hey|yo|sup)?", c) or re.search(r"\b(thanks|thank)\b", c):
        return [], "Ready for orders."
    return [], f"Sorry, I did not understand '{raw.strip()}'."


def parse(text: str):
    """-> (list[Task], reply_text)"""
    text = text.lower().strip().replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9\s,;\-]", " ", text)
    tasks, replies = [], []
    for c in split_clauses(text):
        t, r = parse_clause(c)
        tasks += t
        if r:
            replies.append(r)
    return tasks, " ".join(replies)
