"""Building: blueprints, block placement, pillar-up and bridges."""
from __future__ import annotations
import math

from .. import config as C
from ..knowledge import BUILD_MATERIALS, GRAVITY, LOGS, short
from ..pathfinding import Goal
from .common import Result

FACES = {(0, 1, 0): "up", (0, -1, 0): "down", (1, 0, 0): "east", (-1, 0, 0): "west", (0, 0, 1): "south",
         (0, 0, -1): "north"}


# --------------------------------------------------------------------------- blueprints (relative cells)
def wall(length: int, height: int):
    return [(i, j, 0) for j in range(height) for i in range(length)]


def platform(w: int, d: int):
    return [(i, 0, k) for k in range(d) for i in range(w)]


def house(w: int = 5, d: int = 5, h: int = 3):
    cells = []
    for y in range(h):
        for x in range(w):
            for z in range(d):
                edge = x in (0, w - 1) or z in (0, d - 1)
                door = z == 0 and x == w // 2 and y < 2
                if edge and not door:
                    cells.append((x, y, z))
    cells += [(x, h, z) for x in range(w) for z in range(d)]            # roof
    return cells


def tower(h: int = 6, size: int = 3):
    return [(x, y, z) for y in range(h) for x in range(size) for z in range(size)
            if x in (0, size - 1) or z in (0, size - 1)]


def shelter_cells(cx: int, cy: int, cz: int):
    """Hollow 3x3x3 box around the player's feet/head cells (player stands in the centre)."""
    cells = []
    for y in (0, 1):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if (dx, dz) != (0, 0):
                    cells.append((cx + dx, cy + y, cz + dz))
    cells += [(cx + dx, cy + 2, cz + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
    return cells


BLUEPRINTS = {"wall": wall, "platform": platform, "floor": platform, "house": house, "hut": house, "tower": tower}


# --------------------------------------------------------------------------- material handling
def material_pred(material: str | None):
    if material and material not in ("any", "block", "blocks"):
        if material == "wood":
            return lambda n: n.endswith("_planks")
        if material == "planks":
            return lambda n: n.endswith("_planks")
        return lambda n: n == material or n == material + "_planks" or n == material + "_block"
    order = {n: i for i, n in enumerate(BUILD_MATERIALS)}
    return lambda n: n in order


def pick_material(m, pred):
    """Most plentiful matching placeable item (keeps a single material per structure)."""
    best, bc = None, 0
    for n, c in m.w.inventory.items():
        if pred(n) and c > bc and n in BUILD_MATERIALS:
            best, bc = n, c
    return best, bc


def count_material(m, pred) -> int:
    return pick_material(m, pred)[1]


# --------------------------------------------------------------------------- single placement
def find_support(m, cell):
    """-> (support_cell, face) so that placing against support_cell's `face` creates a block at `cell`."""
    x, y, z = cell
    for d in ((0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0)):
        sx, sy, sz = x + d[0], y + d[1], z + d[2]
        f, name, passable, standable, brk, haz = m.w.info(sx, sy, sz)
        if f == 1 and name not in ("unknown",) and name not in GRAVITY or (f == 1 and d == (0, -1, 0)):
            return (sx, sy, sz), FACES[(-d[0], -d[1], -d[2])]
    return None


def place_cell(m, cell, name: str, avoid=frozenset(), stand_fixed: bool = False) -> bool:
    """Place block `name` at `cell`. Moves into reach (outside `avoid`) unless stand_fixed."""
    w = m.w
    if w.name(*cell) == name:
        return True
    if w.info(*cell)[0] == 1:                       # something else is there -> clear it
        goal = Goal(*cell, radius=C.REACH - 0.5, reach=True)
        if not stand_fixed and not goal.test(w.pos) and not m.goto(goal, avoid=avoid, max_steps=200):
            return False
        if not m.dig(cell):
            return False
    sup = find_support(m, cell)
    if sup is None:
        return False
    goal = Goal(*cell, radius=C.REACH - 0.5, reach=True)
    if not stand_fixed and not goal.test(m.w.pos):
        if not m.goto(goal, avoid=avoid, max_steps=300):
            return False
    if m.select_item(lambda n: n == name) is None:
        return False
    for _ in range(2):
        sup = find_support(m, cell)
        if sup is None:
            return False
        w = m.act(ticks=2, **{"do": "place", "pos": list(sup[0]), "face": sup[1], "_raw": True})
        if w.name(*cell) not in ("air", "cave_air", "unknown", "water", "lava") or w.result == "placed":
            return True
    return m.w.name(*cell) == name


def build_cells(m, cells, material: str | None = None, stand_fixed: bool = False, fill_gaps: bool = True) -> Result:
    """Place all absolute `cells` bottom-up."""
    pred = material_pred(material)
    name, have_n = pick_material(m, pred)
    todo = sorted(set(cells), key=lambda c: (c[1], (c[0] - m.w.bx) ** 2 + (c[2] - m.w.bz) ** 2))
    todo = [c for c in todo if m.w.name(*c) != name]
    if name is None:
        return Result(False, "I have no building blocks")
    if have_n < len(todo):
        return Result(False, f"need {len(todo) - have_n} more {name} (have {have_n}, need {len(todo)})")
    avoid = frozenset(cells) if not stand_fixed else frozenset()
    placed, failed = 0, []
    for rnd in range(3):
        failed = []
        for c in todo:
            if m.w.name(*c) == name:
                continue
            if place_cell(m, c, name, avoid, stand_fixed):
                placed += 1
            else:
                failed.append(c)
        todo = failed
        if not failed:
            break
    ok = not failed
    return Result(ok, f"placed {placed} blocks" + ("" if ok else f", {len(failed)} could not be placed"))


# --------------------------------------------------------------------------- structures
def build_structure(m, kind: str, dims: tuple = (), material: str | None = None) -> Result:
    kind = kind.lower()
    gen = BLUEPRINTS.get(kind)
    if gen is None:
        return Result(False, f"I don't know how to build a {kind}")
    rel = gen(*dims) if dims else gen() if kind not in ("wall",) else gen(6, 3)
    # anchor 3 blocks in front of the player, on the ground
    yaw = m.w.p.get("yaw", 0.0)
    fx, fz = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    ax, az = round(m.w.x + fx * 3), round(m.w.z + fz * 3)
    # snap anchor to a cardinal-aligned corner so structures are axis aligned
    ay = m.w.by
    # find ground level at the anchor
    for dy in range(3, -6, -1):
        if m.w.info(ax, ay + dy - 1, az)[0] == 1 and m.w.info(ax, ay + dy, az)[0] != 1:
            ay = ay + dy
            break
    cells = [(ax + dx, ay + dy, az + dz) for dx, dy, dz in rel]
    return build_cells(m, cells, material)


def build_shelter(m, material: str | None = None) -> Result:
    m.stop(1)
    bx, by, bz = m.w.pos
    cells = shelter_cells(bx, by, bz)
    # recentre on the block so we are exactly in the middle
    m.act(ticks=2, look_at=[bx + .5, m.w.y, bz + .5], fwd=1, _raw=True)
    return build_cells(m, cells, material, stand_fixed=True)


# --------------------------------------------------------------------------- vertical / bridges
def pillar_up(m, n: int = 3, material: str | None = None) -> Result:
    pred = material_pred(material)
    name, c = pick_material(m, pred)
    if name is None:
        return Result(False, "no blocks to pillar with")
    done = 0
    for _ in range(min(n, c)):
        if m.select_item(lambda x: x == name) is None:
            break
        by0 = m.w.by
        bx, bz = m.w.bx, m.w.bz
        for yy in (by0 + 1, by0 + 2):          # head cell and the cell the jump needs
            if m.w.info(bx, yy, bz)[0] == 1:
                if not m.dig((bx, yy, bz)):
                    return Result(done > 0, f"blocked overhead after {done} blocks")
        m.act(ticks=1, pitch=-90.0, _raw=True)  # look up while digging, then back down

        for _ in range(6):
            w = m.act(ticks=1, pitch=90.0, jump=True, _raw=True)
            if w.y > by0 + 1.05:
                break
        w = m.act(ticks=1, **{"do": "place", "pos": [bx, by0 - 1, bz], "face": "up", "jump": False, "_raw": True})
        for _ in range(8):
            w = m.act(ticks=1, _raw=True)
            if w.on_ground:
                break
        if m.w.by > by0:
            done += 1
        else:
            break
    return Result(done > 0, f"pillared up {done} blocks")


def bridge(m, length: int = 8, material: str | None = None) -> Result:
    pred = material_pred(material)
    name, c = pick_material(m, pred)
    if name is None:
        return Result(False, "no blocks to bridge with")
    yaw = m.w.p.get("yaw", 0.0)
    dx, dz = round(-math.sin(math.radians(yaw))), round(math.cos(math.radians(yaw)))
    placed = 0
    for _ in range(min(length, c)):
        bx, by, bz = m.w.pos
        cell = (bx + dx, by - 1, bz + dz)
        if m.w.info(*cell)[0] != 1:
            m.select_item(lambda x: x == name)
            face = FACES[(dx, 0, dz)]
            m.act(ticks=2, **{"do": "place", "pos": [bx, by - 1, bz], "face": face, "sneak": True, "_raw": True})
            if m.w.info(*cell)[0] == 1:
                placed += 1
        m.goto(Goal(cell[0], by, cell[2], radius=0), max_steps=30)
    return Result(placed > 0, f"bridged {placed} blocks")
