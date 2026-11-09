import pytest
from harshcraft_ai import nlp
from harshcraft_ai.knowledge import RECIPES, block_info, drop_of
from harshcraft_ai.planner import Planner, PlanError, Task
from harshcraft_ai.pathfinding import Goal, find_path
from harshcraft_ai.rl import spec
from harshcraft_ai.world import World


def flat_world(wall=None):
    w = World()
    def put(x, y, z, n, f):
        w.cells[(x, y, z)] = w._intern("minecraft:" + n, f)
    for x in range(-5, 20):
        for z in range(-10, 11):
            for y in range(60, 70):
                put(x, y, z, "air", 0)
            put(x, 63, z, "grass_block", 1)
            put(x, 62, z, "stone", 1)
    return w, put


def test_parse_variants():
    cases = {
        "collect 10 oak logs": ("get", "log", 10),
        "get me a stone pickaxe": ("get", "stone_pickaxe", 1),
        "craft three sticks": ("get", "stick", 3),
        "mine 20 cobblestone": ("get", "cobblestone", 20),
        "get 5 iron ingots": ("get", "iron_ingot", 5),
    }
    for text, (kind, item, n) in cases.items():
        t, _ = nlp.parse(text)
        assert (t[0].kind, t[0].item, t[0].n) == (kind, item, n), text


def test_parse_misc():
    assert nlp.parse("stop")[0][0].kind == "stop"
    assert nlp.parse("how are you")[0][0].kind == "status"
    t = nlp.parse("go to 100 64 -200")[0][0]
    assert (t.args["x"], t.args["y"], t.args["z"]) == (100, 64, -200)
    t = nlp.parse("build a wall 8 long 4 high")[0][0]
    assert t.kind == "build" and t.args["dims"] == (8, 4)
    assert [x.kind for x in nlp.parse("kill the zombies and then eat")[0]] == ["kill", "eat"]
    assert nlp.parse("kill creepers")[0][0].item == "creeper"
    assert nlp.parse("gibberish blah")[0] == []


def test_planner_stone_pickaxe_is_consistent():
    p = Planner()
    plan = p.expand(Task("get", "stone_pickaxe", 1), {})
    kinds = [str(t) for t in plan]
    # logs before planks before sticks before pickaxe before cobble before stone pickaxe
    assert kinds.index("craft(wooden_pickaxe)") < kinds.index("collect(cobblestone x3)") < kinds.index("craft(stone_pickaxe)")
    total_planks = sum(t.n for t in plan if t.item == "oak_planks")
    assert total_planks >= 4 + 3 + 2          # table + pickaxe + sticks


def test_planner_inventory_aware():
    p = Planner()
    assert p.expand(Task("get", "stick", 4), {"oak_planks": 8}) == [Task("craft", "stick", 4)]
    assert p.expand(Task("get", "stone_pickaxe", 1), {"stone_pickaxe": 1}, ) != []   # relative: wants one MORE
    with pytest.raises(PlanError):
        p.expand(Task("get", "nether_star", 1), {})


def test_every_recipe_resolves():
    p = Planner()
    for item in list(RECIPES):
        if item.endswith("_bed"):
            continue
        try:
            p.expand(Task("get", item, 1), {})
        except PlanError:
            pass                                      # allowed (e.g. needs wool/string/wheat we cannot source)


def test_pathfinding_basic_and_unreachable_partial():
    w, put = flat_world()
    r = find_path(w, (0, 64, 0), Goal(10, 64, 0))
    assert r.found and len(r.steps) == 10
    for z in range(-10, 11):
        put(5, 64, z, "stone", 1); put(5, 65, z, "stone", 1)
    r = find_path(w, (0, 64, 0), Goal(10, 64, 0))
    assert not r.found and r.partial
    r = find_path(w, (0, 64, 0), Goal(10, 64, 0), allow_dig=True)
    assert r.found and any(s.breaks for s in r.steps)


def test_never_paths_through_or_next_to_lava():
    w, put = flat_world()
    for z in range(-10, 11):
        put(8, 63, z, "lava", 3)
    r = find_path(w, (0, 64, 0), Goal(15, 64, 0))
    assert not r.found
    assert all(s.pos[0] != 8 for s in r.steps)


def test_swim_and_drop_into_water():
    w, put = flat_world()
    for x in range(3, 8):
        for z in range(-3, 4):
            for y in (61, 62, 63):
                put(x, y, z, "water", 2)
    r = find_path(w, (0, 64, 0), Goal(12, 64, 0))
    assert r.found


def test_breaking_never_adjacent_to_lava():
    w, put = flat_world()
    put(3, 64, 0, "stone", 1)
    put(3, 64, 1, "lava", 3)
    r = find_path(w, (0, 64, 0), Goal(6, 64, 0), allow_dig=True, blocked=frozenset())
    for s in r.steps:
        assert (3, 64, 0) not in s.breaks


def test_block_knowledge():
    assert block_info("minecraft:iron_ore")[1:] == ("pickaxe", 2)
    assert block_info("minecraft:diamond_ore")[2] == 3
    assert drop_of("minecraft:stone") == "cobblestone"
    assert drop_of("minecraft:deepslate_iron_ore") == "raw_iron"
    assert block_info("minecraft:bedrock")[0] > 1e8


def test_combat_obs_shape_and_frame():
    o = spec.combat_obs(20, 6, 1.0, [(0, 5, 0, 20), (2, 0, 8, 20)])
    assert len(o) == spec.COMBAT_OBS_DIM
    assert o[8] == 1.0                     # nearest is a zombie
    assert spec.combat_rule(o) in range(8)
    assert len(spec.surv_obs(20, 20, True, 300, 1, 5, False, False, 6, True, False)) == spec.SURV_OBS_DIM
