"""3-D voxel A* for a 2-block-tall player.

Node = feet block (x, y, z). Moves: walk (4 cardinal + 4 diagonal), 1-block jump up, drops (<=3 on land, <=8 into
water), swim (6-neighbour), and -- when allow_dig -- breaking blocks that are in the way (tunnels, stairs up/down,
digging straight down). Lava and its neighbours are never entered or broken; unknown cells are impassable, so
the planner returns a PARTIAL path to the explored node nearest the goal, and the caller simply re-plans as
the observation window slides.
"""
from __future__ import annotations
import heapq
import math
from dataclasses import dataclass, field

from .world import World, UNKNOWN

CARD = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
SQRT2 = math.sqrt(2.0)
WATER, LAVA = 2, 3


@dataclass(frozen=True)
class Goal:
    x: int
    y: int
    z: int
    radius: float = 0.0
    reach: bool = False          # radius measured from the EYE to the block centre (mining/placing)
    ignore_y: bool = False       # long-range travel where the target height is unknown

    def test(self, n):
        if self.reach:
            dx, dy, dz = n[0] + .5 - (self.x + .5), n[1] + 1.62 - (self.y + .5), n[2] + .5 - (self.z + .5)
            return dx * dx + dy * dy + dz * dz <= self.radius * self.radius and n != (self.x, self.y, self.z) \
                and n != (self.x, self.y - 1, self.z)
        dx, dz = n[0] - self.x, n[2] - self.z
        if self.radius <= 0:
            return dx == 0 and dz == 0 and (self.ignore_y or n[1] == self.y)
        return dx * dx + dz * dz <= self.radius * self.radius and (self.ignore_y or abs(n[1] - self.y) <= 1)

    def h(self, n):
        if self.reach:
            dx, dy, dz = n[0] - self.x, n[1] + 1.62 - (self.y + .5), n[2] - self.z
            return max(0.0, math.sqrt(dx * dx + dy * dy + dz * dz) - self.radius)
        dx, dz = n[0] - self.x, n[2] - self.z
        return max(0.0, math.sqrt(dx * dx + dz * dz) - self.radius) + (0.0 if self.ignore_y else abs(n[1] - self.y) * 0.8)


@dataclass
class Step:
    pos: tuple
    breaks: tuple = ()
    kind: str = "walk"


@dataclass
class PathResult:
    steps: list = field(default_factory=list)
    found: bool = False          # reached the goal
    partial: bool = False        # progressed toward the goal but could not finish with current knowledge
    expanded: int = 0


def find_path(world: World, start: tuple, goal: Goal, *, allow_dig: bool = False, blocked=frozenset(),
              avoid=frozenset(), penalty=None, max_nodes: int = 6000, dig_cost: float = 3.0) -> PathResult:
    cells_get, pal = world.cells.get, world.pal

    def inf(x, y, z):
        return pal[cells_get((x, y, z), UNKNOWN)]

    def lava_near(x, y, z):
        for ox, oy, oz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0), (0, 0, 0)):
            if inf(x + ox, y + oy, z + oz)[0] == LAVA:
                return True
        return False

    def water_near(x, y, z):
        for ox, oy, oz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0)):
            if inf(x + ox, y + oy, z + oz)[0] == WATER:
                return True
        return False

    def free(x, y, z, dig_ok=True):
        """-> (ok, extra_cost, break_cell|None). Cell must be enterable by the body."""
        if (x, y, z) in avoid:
            return False, 0.0, None
        f, name, passable, standable, brk, haz = inf(x, y, z)
        if f == 0 and passable:
            return True, 0.0, None
        if f == WATER:
            return True, 0.4, None
        if f == 1 and brk and allow_dig and dig_ok and (x, y, z) not in blocked and not lava_near(x, y, z):
            return True, dig_cost + (2.0 if water_near(x, y, z) else 0.0), (x, y, z)
        return False, 0.0, None

    def stand_ok(x, y, z):
        """Block below the feet can be stood on (or is water to float in)."""
        f, name, passable, standable, brk, haz = inf(x, y, z)
        return standable or f == WATER

    def moves(n):
        x, y, z = n
        here_water = inf(x, y, z)[0] == WATER
        # ---- walk / diagonal / jump / drop to horizontal neighbours
        for dx, dz in CARD + DIAG:
            diag = dx != 0 and dz != 0
            nx, nz = x + dx, z + dz
            if diag:
                ok = True
                for ax, az in ((x + dx, z), (x, z + dz)):
                    if not (free(ax, y, az, False)[0] and free(ax, y + 1, az, False)[0]):
                        ok = False
                        break
                if not ok:
                    continue
            base = SQRT2 if diag else 1.0
            ok1, c1, b1 = free(nx, y, nz, not diag)
            ok2, c2, b2 = free(nx, y + 1, nz, not diag)
            if ok1 and ok2:
                brk = tuple(b for b in (b1, b2) if b)
                if stand_ok(nx, y - 1, nz) or inf(nx, y, nz)[0] == WATER:
                    yield (nx, y, nz), base + c1 + c2, brk, "walk"
                elif not diag:
                    # drop
                    for k in range(1, 9):
                        fk, ck, bk = free(nx, y - k, nz, True)
                        if not fk:
                            break
                        landed_water = inf(nx, y - k, nz)[0] == WATER
                        if stand_ok(nx, y - k - 1, nz) or landed_water:
                            if k <= 3 or landed_water:
                                yield (nx, y - k, nz), 1.0 + 0.6 * k + c1 + c2 + ck, \
                                    tuple(b for b in (b1, b2, bk) if b), "drop"
                            break
            if not diag:
                # jump up one block: need head room above current cell
                oh, ch, bh = free(x, y + 2, z, True)
                if oh and inf(nx, y, nz)[3]:
                    oj1, cj1, bj1 = free(nx, y + 1, nz, True)
                    oj2, cj2, bj2 = free(nx, y + 2, nz, True)
                    if oj1 and oj2:
                        yield (nx, y + 1, nz), 1.8 + ch + cj1 + cj2, tuple(b for b in (bh, bj1, bj2) if b), "jump"
        # ---- swimming (vertical + straight)
        if here_water:
            for ny in (y + 1, y - 1):
                okv, cv, bv = free(x, ny, z, False)
                if okv and inf(x, ny, z)[0] == WATER or (ny == y + 1 and okv):
                    yield (x, ny, z), 1.4 + cv, (), "swim"
        # ---- dig straight down
        if allow_dig and stand_ok(x, y - 2, z):
            okd, cd, bd = free(x, y - 1, z, True)
            if okd and bd:
                yield (x, y - 1, z), 1.0 + cd, (bd,), "dig"

    open_ = [(goal.h(start), 0.0, start)]
    g = {start: 0.0}
    parent: dict = {}
    how: dict = {}
    closed = set()
    best, best_h = start, goal.h(start)
    start_h = best_h
    expanded = 0
    found = None
    while open_ and expanded < max_nodes:
        f, gc, n = heapq.heappop(open_)
        if n in closed:
            continue
        closed.add(n)
        expanded += 1
        if goal.test(n) and n != start:
            found = n
            break
        if goal.test(n) and n == start:
            return PathResult([], True, False, expanded)
        hn = goal.h(n)
        if hn < best_h - 1e-9 or (abs(hn - best_h) < 1e-9 and gc < g.get(best, 1e18)):
            best, best_h = n, hn
        for m, cost, brk, kind in moves(n):
            if m in blocked or m in closed or (m in avoid) or ((m[0], m[1] + 1, m[2]) in avoid):
                continue
            if penalty is not None:
                cost += penalty(m)
            # hazard adjacency: never next to lava
            if lava_near(*m):
                continue
            ng = gc + cost
            if ng < g.get(m, 1e18):
                g[m] = ng
                parent[m] = n
                how[m] = (brk, kind)
                heapq.heappush(open_, (ng + goal.h(m), ng, m))
    end = found
    partial = False
    if end is None:
        if best != start and best_h < start_h - 0.5:
            end, partial = best, True
        else:
            return PathResult([], False, False, expanded)
    steps = []
    cur = end
    while cur != start:
        brk, kind = how[cur]
        steps.append(Step(cur, brk, kind))
        cur = parent[cur]
    steps.reverse()
    return PathResult(steps, found is not None, partial, expanded)
