"""Crafting (2x2 inventory grid and 3x3 table) and smelting, driven by raw container clicks."""
from __future__ import annotations
import math

from .. import config as C
from ..knowledge import FUELS, RECIPES, SMELTS, matches, short
from ..pathfinding import Goal
from .build import place_cell
from .common import Result, have


def _slot_item(s: str):
    if not s:
        return None, 0
    n, c = s.rsplit("*", 1)
    return short(n), int(c)


def find_station(m, block: str, r: int = 12):
    blocks = m.c.scan([f"=minecraft:{block}"], r, 6, 4)
    return (blocks[0]["x"], blocks[0]["y"], blocks[0]["z"]) if blocks else None


def place_station(m, item: str) -> tuple | None:
    """Place a crafting table / furnace on a free ground cell next to us."""
    bx, by, bz = m.w.pos
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (2, 0), (0, 2)):
        c = (bx + dx, by, bz + dz)
        if m.w.is_air(*c) and m.w.info(c[0], c[1] - 1, c[2])[0] == 1 and m.w.is_air(c[0], c[1] + 1, c[2]):
            if place_cell(m, c, item, stand_fixed=True):
                return c
    return None


def open_station(m, pos, kind: str) -> bool:
    if m.w.menu.get("type") == kind:
        return True
    if m.w.distance_to(pos[0] + .5, pos[1] + .5, pos[2] + .5) > 4.0:
        if not m.goto(Goal(*pos, radius=3.0, reach=True), max_steps=200):
            return False
    m.act(ticks=3, **{"do": "use", "pos": list(pos), "face": "up", "_raw": True})
    for _ in range(12):
        if m.w.menu.get("type") == kind:
            return True
        m.act(ticks=1, _raw=True)
    return False


def ensure_station(m, block: str, kind: str) -> tuple | None:
    pos = find_station(m, block)
    if pos is None:
        if m.w.count(block) == 0:
            r = craft(m, block, 1)
            if not r.ok:
                return None
        pos = place_station(m, block)
    if pos is None or not open_station(m, pos, kind):
        return None
    return pos


def _clear_cursor(m):
    cur = m.w.menu.get("cursor", "")
    if cur:
        kind = m.w.menu.get("type", "inventory")
        for i in range(36):
            if not any(s["slot"] == i for s in m.w.slots):
                m.click(m.menu_slot(kind, i), "pickup", 0)
                return


def craft(m, item: str, count: int = 1) -> Result:
    rec = RECIPES.get(item)
    if rec is None:
        return Result(False, f"I don't know a recipe for {item}")
    times = math.ceil(count / rec.count)
    need = {k: v * times for k, v in rec.ingredients().items()}
    for ing, n in need.items():
        if have(m, ing) < n:
            return Result(False, f"missing {n - have(m, ing)} {ing}")
    kind = "inventory"
    if rec.needs_table:
        if ensure_station(m, "crafting_table", "crafting") is None:
            return Result(False, "no crafting table available")
        kind = "crafting"
    width = 3 if kind == "crafting" else 2
    start = have(m, item)
    for _ in range(times):
        _clear_cursor(m)
        for r, c, ing in rec.cells():
            src = None
            for s in m.w.slots:                      # world state is refreshed after every click
                if s["slot"] < 36 and matches(short(s["id"]), ing) and s["count"] >= 1:
                    src = s
                    break
            if src is None:
                return Result(False, f"ran out of {ing}")
            ms = m.menu_slot(kind, src["slot"])
            grid = 1 + r * width + c
            m.click(ms, "pickup", 0)
            m.click(grid, "pickup", 1)
            m.click(ms, "pickup", 0)
        before = have(m, item)
        m.click(0, "quick_move", 0)
        m.act(ticks=1, _raw=True)
        if have(m, item) <= before:
            for g in range(1, width * width + 1):
                if m.w.menu.get("slots") and m.w.menu["slots"][g]:
                    m.click(g, "quick_move", 0)
            m.close_menu()
            return Result(False, f"crafting {item} did not produce anything")
        for g in range(1, width * width + 1):
            if m.w.menu.get("slots") and len(m.w.menu["slots"]) > g and m.w.menu["slots"][g]:
                m.click(g, "quick_move", 0)
    if kind == "crafting":
        m.close_menu()
    return Result(have(m, item) > start, f"crafted {item} (have {have(m, item)})")


def _put(m, kind: str, inv_slot: int, dest: int, n: int, stack: int):
    src = m.menu_slot(kind, inv_slot)
    m.click(src, "pickup", 0)
    if n >= stack:
        m.click(dest, "pickup", 0)
    else:
        for _ in range(n):
            m.click(dest, "pickup", 1)
    m.click(src, "pickup", 0)


def smelt(m, raw: str, count: int) -> Result:
    out = SMELTS.get(raw)
    if out is None:
        return Result(False, f"{raw} cannot be smelted")
    count = min(count, m.w.count(raw))
    if count <= 0:
        return Result(False, f"no {raw} to smelt")
    # fuel
    fuel, per = None, 0.0
    for n, v in sorted(FUELS.items(), key=lambda t: -t[1]):
        if m.w.count(n) > 0 and n != raw:
            need = math.ceil(count / v)
            if m.w.count(n) >= need:
                fuel, per = n, need
                break
    if fuel is None:
        return Result(False, "no fuel (coal, charcoal or planks)")
    if ensure_station(m, "furnace", "furnace") is None:
        return Result(False, "no furnace available (need 8 cobblestone)")
    _clear_cursor(m)
    s_in = next(s for s in m.w.slots if s["slot"] < 36 and short(s["id"]) == raw)
    _put(m, "furnace", s_in["slot"], 0, count, s_in["count"])
    s_f = next(s for s in m.w.slots if s["slot"] < 36 and short(s["id"]) == fuel)
    _put(m, "furnace", s_f["slot"], 1, int(per), s_f["count"])
    start = have(m, out)
    waited = 0
    limit = count * 220 + 400
    while waited < limit:
        m.act(ticks=40, _raw=False)
        waited += 40
        slots = m.w.menu.get("slots", [])
        if len(slots) > 2:
            n, c = _slot_item(slots[2])
            if n == out and c >= count:
                break
    slots = m.w.menu.get("slots", [])
    if len(slots) > 2 and slots[2]:
        m.click(2, "quick_move", 0)
    for g in (0, 1):
        if len(slots) > g and slots[g]:
            m.click(g, "quick_move", 0)
    m.close_menu()
    got = have(m, out) - start
    return Result(got > 0, f"smelted {got} {out}")
