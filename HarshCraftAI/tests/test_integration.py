"""End-to-end tests of the Python stack against the mock Minecraft server."""
import itertools
import pytest

from harshcraft_ai.agent import Bot
from harshcraft_ai.client import MCClient
from harshcraft_ai.motor import Motor
from harshcraft_ai.pathfinding import Goal
from harshcraft_ai.skills import build, combat, craft, mine, survive
from sim.mock_server import Mock, serve

_ports = itertools.count(5100)


def make(**kw):
    mock = Mock(**kw)
    port = next(_ports)
    srv = serve(mock, port)
    bot = Bot(MCClient(f"http://127.0.0.1:{port}"), log=lambda *_: None)
    bot.m.sync()
    return mock, bot, srv


def test_goto_and_jump():
    mock, bot, srv = make(trees=(), stone=False)
    for y in (64,):
        mock.blocks[(4, 64, -1)] = "stone"; mock.blocks[(4, 64, 0)] = "stone"; mock.blocks[(4, 64, 1)] = "stone"
        for z in range(-6, 7):
            mock.blocks[(4, 64, z)] = "stone"           # 1-high wall: must jump
    assert bot.m.goto(Goal(9, 64, 0, radius=0), max_steps=300)
    assert abs(mock.x - 9.5) < 0.6 and abs(mock.z - 0.5) < 0.6
    srv.shutdown()


def test_two_high_wall_needs_dig():
    mock, bot, srv = make(trees=(), stone=False)
    for z in range(-12, 13):
        for y in (64, 65):
            mock.blocks[(4, y, z)] = "stone"
    bot.m.select_item(lambda n: False)
    assert not bot.m.goto(Goal(9, 64, 0, radius=0), max_steps=120, allow_dig=False)
    assert bot.m.goto(Goal(9, 64, 0, radius=0), max_steps=300, allow_dig=True)
    srv.shutdown()


def test_collect_logs():
    mock, bot, srv = make(stone=False)
    r = mine.mine_resource(bot.m, "log", 4)
    assert r.ok, r.msg
    assert mock.count("oak_log") >= 4
    srv.shutdown()


def test_craft_planks_sticks_table():
    mock, bot, srv = make(inventory={"oak_log": 3}, stone=False, trees=())
    assert craft.craft(bot.m, "oak_planks", 8).ok
    assert mock.count("oak_planks") >= 8
    assert craft.craft(bot.m, "stick", 4).ok
    assert mock.count("stick") >= 4
    assert craft.craft(bot.m, "crafting_table", 1).ok
    assert mock.count("crafting_table") == 1
    srv.shutdown()


def test_craft_with_table_pickaxe():
    mock, bot, srv = make(inventory={"oak_planks": 12, "stick": 4}, stone=False, trees=())
    r = craft.craft(bot.m, "wooden_pickaxe", 1)
    assert r.ok, r.msg
    assert mock.count("wooden_pickaxe") == 1
    assert mock.menu_type == "inventory"
    srv.shutdown()


def test_full_tech_tree_stone_pickaxe_via_voice_command():
    mock, bot, srv = make(trees=((4, 0), (5, 2), (-4, 3), (6, -3), (-5, -3), (3, 5)))
    bot.start()
    bot.command("get a stone pickaxe")
    import time
    t0 = time.time()
    while (bot.busy or not bot.q.empty() or time.time() - t0 < 1) and time.time() - t0 < 240:
        time.sleep(0.3)
    bot.shutdown()
    assert mock.count("stone_pickaxe") == 1, mock.inv
    srv.shutdown()


def test_smelt_iron():
    mock, bot, srv = make(inventory={"raw_iron": 2, "cobblestone": 8, "coal": 2, "crafting_table": 1}, stone=False, trees=())
    r = craft.smelt(bot.m, "raw_iron", 2)
    assert r.ok, r.msg
    assert mock.count("iron_ingot") == 2
    srv.shutdown()


def test_build_wall():
    mock, bot, srv = make(inventory={"cobblestone": 40}, stone=False, trees=())
    r = build.build_structure(bot.m, "wall", (5, 2), "cobblestone")
    assert r.ok, r.msg
    placed = [k for k, v in mock.blocks.items() if v == "cobblestone"]
    assert len(placed) == 10
    srv.shutdown()


def test_build_house():
    mock, bot, srv = make(inventory={"cobblestone": 128}, stone=False, trees=())
    r = build.build_structure(bot.m, "house", (), "cobblestone")
    assert r.ok, r.msg
    srv.shutdown()


def test_fight_zombie():
    mock, bot, srv = make(inventory={"stone_sword": 1}, stone=False, trees=(), zombies=((6, 0),))
    r = combat.fight(bot.m, None, max_steps=200)
    assert r.ok, r.msg
    assert not [e for e in mock.entities.values() if e["type"] == "zombie"]
    assert mock.health > 0
    srv.shutdown()


def test_eat():
    mock, bot, srv = make(inventory={"cooked_beef": 2}, stone=False, trees=())
    mock.food = 8
    bot.m.sync()
    r = survive.eat(bot.m)
    assert r.ok and mock.food > 8
    srv.shutdown()


def test_drowning_reflex_surfaces():
    mock, bot, srv = make(stone=False, trees=(), water=True)
    mock.x, mock.y, mock.z = -2.5, 61.0, 8.5          # at the bottom of the pool
    mock.air = 100
    bot.m.sync()
    for _ in range(80):
        bot.m.act(ticks=2, fwd=0)
        if not bot.m.w.underwater:
            break
    assert mock.health > 12 and not bot.m.w.underwater
    srv.shutdown()


def test_nlp_to_tasks_roundtrip():
    from harshcraft_ai import nlp
    t, _ = nlp.parse("go to 100 64 -200 and then kill the zombies")
    assert [x.kind for x in t] == ["goto", "kill"]
