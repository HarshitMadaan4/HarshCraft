"""Navigation skills: go to coordinates, nearest block, follow a player, explore."""
from __future__ import annotations
import math
import random

from ..pathfinding import Goal
from .common import Result


def goto_xyz(m, x: float, y: float | None, z: float, radius: float = 1.5) -> Result:
    ix, iz = math.floor(x), math.floor(z)
    goal = Goal(ix, math.floor(y) if y is not None else m.w.by, iz, radius=radius, ignore_y=y is None)
    ok = m.goto(goal, max_steps=1500)
    return Result(ok, "arrived" if ok else "could not find a way there")


def goto_nearest_block(m, fragments, label: str = "block", radius: int = 32) -> Result:
    blocks = m.c.scan(fragments, r=radius, v=16, max_results=16)
    if not blocks:
        return Result(False, f"no {label} within {radius} blocks")
    for b in blocks[:6]:
        if m.goto(Goal(b["x"], b["y"], b["z"], radius=3.0, reach=True), allow_dig=False, max_steps=600):
            return Result(True, f"reached {label}")
    return Result(False, f"could not reach {label}")


def follow_player(m, name: str | None = None, seconds: float = 60.0) -> Result:
    import time
    end = time.time() + seconds
    seen = False
    while time.time() < end:
        players = [e for e in m.w.entities if e.player]
        if not players:
            if not seen:
                return Result(False, "no other player nearby to follow")
            m.stop(10)
            continue
        seen = True
        p = players[0]
        d = m.w.distance_to(p.x, p.y, p.z)
        if d > 4.0:
            m.goto(Goal(math.floor(p.x), math.floor(p.y), math.floor(p.z), radius=2.5), max_steps=40)
        else:
            m.look_at(p.x, p.y + 1.6, p.z, ticks=5)
    return Result(True, "stopped following")


def explore(m, distance: int = 60) -> Result:
    """Walk to a random not-yet-visited sector; returns how far we actually travelled."""
    visited = getattr(m, "_explored", None)
    if visited is None:
        visited = m._explored = set()
    x0, z0 = m.w.x, m.w.z
    visited.add((int(x0) // 16, int(z0) // 16))
    best = None
    angles = list(range(0, 360, 45))
    random.shuffle(angles)
    for a in angles:
        tx = x0 + distance * math.cos(math.radians(a))
        tz = z0 + distance * math.sin(math.radians(a))
        if (int(tx) // 16, int(tz) // 16) not in visited:
            best = (tx, tz)
            break
    if best is None:
        a = random.uniform(0, 360)
        best = (x0 + distance * math.cos(math.radians(a)), z0 + distance * math.sin(math.radians(a)))
    m.goto(Goal(math.floor(best[0]), m.w.by, math.floor(best[1]), radius=3.0, ignore_y=True), max_steps=400)
    visited.add((int(m.w.x) // 16, int(m.w.z) // 16))
    moved = math.hypot(m.w.x - x0, m.w.z - z0)
    return Result(moved > 4, f"explored {moved:.0f} blocks")
