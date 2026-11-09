"""Survival skills: eat, flee, shelter, wait-to-heal."""
from __future__ import annotations
import math

from .. import config as C
from ..knowledge import FOOD
from ..motor import yaw_to
from ..pathfinding import Goal
from .build import build_shelter, count_material, material_pred
from .common import Result


def eat(m) -> Result:
    if m.w.food >= 20:
        return Result(True, "not hungry")
    s = m.w.best_food()
    if s is None:
        # desperate: rotten flesh
        s = m.w.slot_of(lambda n: n == "rotten_flesh") if m.w.food <= 3 else None
        if s is None:
            return Result(False, "no food")
    from ..knowledge import short
    name = short(s["id"])
    before = m.w.food
    for _ in range(3):
        if m.select_item(lambda n: n == name) is None:
            break
        m.act(ticks=40, **{"do": "eat"})
        if m.w.food > before:
            return Result(True, f"ate {name}, food {m.w.food}")
    return Result(m.w.food > before, f"food {m.w.food}")


def flee(m, distance: int = 24) -> Result:
    w = m.w
    th = w.hostiles(24.0)
    if not th:
        return Result(True, "nothing to flee from")
    cx = sum(e.x for e in th) / len(th)
    cz = sum(e.z for e in th) / len(th)
    dx, dz = w.x - cx, w.z - cz
    n = math.hypot(dx, dz) or 1.0
    tx, tz = w.x + dx / n * distance, w.z + dz / n * distance
    ok = m.goto(Goal(math.floor(tx), w.by, math.floor(tz), radius=3.0, ignore_y=True), max_steps=120)
    return Result(ok or bool(m.w.hostiles(10.0)) is False, "fled")


def shelter(m) -> Result:
    if count_material(m, material_pred(None)) < 12:
        return Result(False, "not enough blocks for a shelter (need 12)")
    return build_shelter(m)


def rest_until_healed(m, target: float = 18.0, max_ticks: int = 1200) -> Result:
    waited = 0
    while m.w.health < target and waited < max_ticks:
        if m.w.hostiles(12.0):
            return Result(False, "enemy nearby")
        if m.w.food <= 14 and eat(m).ok:
            continue
        m.act(ticks=40, _raw=True)
        waited += 40
    return Result(m.w.health >= target, f"HP {m.w.health:.0f}")
