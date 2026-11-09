"""World model: parses observations, keeps a persistent voxel memory."""
from __future__ import annotations
import math
from dataclasses import dataclass

from .knowledge import HAZARD_BELOW, HAZARD_IN, breakable, short, matches, FOOD


@dataclass
class Ent:
    id: int
    type: str
    x: float
    y: float
    z: float
    hostile: bool = False
    player: bool = False
    health: float = 0.0
    item: str = ""
    count: int = 1

    def dist(self, x, y, z) -> float:
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2 + (self.z - z) ** 2)


# palette entry layout: (flag, name, passable, standable, breakable, hazard)
UNKNOWN = 0


class World:
    PRUNE_AT = 400_000

    def __init__(self):
        self.cells: dict[tuple[int, int, int], int] = {}
        self.pal: list[tuple] = [(-1, "unknown", False, False, False, True)]
        self._pal_idx: dict[tuple, int] = {}
        self.raw: dict = {}
        self.entities: list[Ent] = []
        self.inventory: dict[str, int] = {}
        self.slots: list[dict] = []
        self.menu: dict = {"type": "inventory", "slots": []}
        self.target: dict = {"hit": False}
        self.result = "ok"
        self.p: dict = {}
        self.x = self.y = self.z = 0.0
        self.version = 0

    # ----------------------------------------------------------- parsing
    def _intern(self, name: str, flag: int) -> int:
        key = (name, flag)
        i = self._pal_idx.get(key)
        if i is None:
            n = short(name)
            passable = flag == 0 and n not in HAZARD_IN
            standable = flag == 1 and n not in HAZARD_BELOW
            hazard = flag == 3 or n in HAZARD_IN
            i = len(self.pal)
            self.pal.append((flag, n, passable, standable, flag == 1 and breakable(n), hazard))
            self._pal_idx[key] = i
        return i

    def update(self, obs: dict) -> "World":
        self.raw = obs
        self.version += 1
        self.result = obs.get("result", "ok")
        p = self.p = obs["player"]
        self.x, self.y, self.z = p["x"], p["y"], p["z"]
        g = obs["grid"]
        local = [self._intern(n, f) for n, f in zip(g["pal"], g["fl"])]
        d, i = g["d"], 0
        r, ymin, ymax = g["r"], g["ymin"], g["ymax"]
        ox, oy, oz = g["ox"], g["oy"], g["oz"]
        cells = self.cells
        for dx in range(-r, r + 1):
            x = ox + dx
            for dy in range(ymin, ymax + 1):
                y = oy + dy
                for dz in range(-r, r + 1):
                    cells[(x, y, oz + dz)] = local[d[i]]
                    i += 1
        if len(cells) > self.PRUNE_AT:
            self._prune()
        self.entities = [Ent(e["id"], short(e["type"]), e["x"], e["y"], e["z"], e.get("hostile", False),
                             e.get("player", False), e.get("health", 0.0), short(e.get("item", "")),
                             e.get("count", 1)) for e in obs.get("entities", [])]
        self.slots = obs.get("inventory", [])
        inv: dict[str, int] = {}
        for s in self.slots:
            n = short(s["id"])
            inv[n] = inv.get(n, 0) + s["count"]
        self.inventory = inv
        self.menu = obs.get("menu", self.menu)
        self.target = obs.get("target", {"hit": False})
        return self

    def _prune(self):
        bx, by, bz = self.bx, self.by, self.bz
        self.cells = {k: v for k, v in self.cells.items()
                      if abs(k[0] - bx) < 48 and abs(k[2] - bz) < 48 and abs(k[1] - by) < 32}

    # ----------------------------------------------------------- player
    @property
    def bx(self): return math.floor(self.x)
    @property
    def by(self): return math.floor(self.y + 1e-3)
    @property
    def bz(self): return math.floor(self.z)
    @property
    def pos(self): return (self.bx, self.by, self.bz)
    @property
    def eye(self): return (self.x, self.y + 1.62, self.z)
    @property
    def health(self): return self.p.get("health", 20.0)
    @property
    def food(self): return self.p.get("food", 20)
    @property
    def air(self): return self.p.get("air", 300)
    @property
    def dead(self): return bool(self.p.get("dead"))
    @property
    def in_water(self): return bool(self.p.get("in_water"))
    @property
    def underwater(self): return bool(self.p.get("underwater"))
    @property
    def in_lava(self): return bool(self.p.get("in_lava"))
    @property
    def on_ground(self): return bool(self.p.get("on_ground"))
    @property
    def is_night(self):
        t = self.raw.get("day_time", 0)
        return 12600 <= t <= 23400

    # ----------------------------------------------------------- blocks
    def info(self, x: int, y: int, z: int) -> tuple:
        return self.pal[self.cells.get((x, y, z), UNKNOWN)]

    def name(self, x: int, y: int, z: int) -> str:
        return self.pal[self.cells.get((x, y, z), UNKNOWN)][1]

    def passable(self, x, y, z) -> bool:
        return self.info(x, y, z)[2]

    def solid(self, x, y, z) -> bool:
        return self.info(x, y, z)[0] == 1

    def is_air(self, x, y, z) -> bool:
        return self.name(x, y, z) in ("air", "cave_air", "void_air")

    def known(self, x, y, z) -> bool:
        return (x, y, z) in self.cells

    # ----------------------------------------------------------- inventory
    def count(self, want: str) -> int:
        if want.startswith("#"):
            return sum(c for n, c in self.inventory.items() if matches(n, want))
        return self.inventory.get(want, 0)

    def has(self, want: str, n: int = 1) -> bool:
        return self.count(want) >= n

    def slot_of(self, pred) -> dict | None:
        """First inventory slot dict whose item name satisfies pred(name). Hotbar slots preferred."""
        best = None
        for s in self.slots:
            if s["slot"] < 36 and pred(short(s["id"])):
                if s["slot"] < 9:
                    return s
                best = best or s
        return best

    def hotbar_free(self) -> int | None:
        used = {s["slot"] for s in self.slots if s["slot"] < 9}
        for i in range(9):
            if i not in used:
                return i
        return None

    def best_food(self):
        cands = [(FOOD[short(s["id"])], s) for s in self.slots
                 if s["slot"] < 36 and short(s["id"]) in FOOD and short(s["id"]) != "rotten_flesh"]
        if not cands:
            return None
        return max(cands, key=lambda t: t[0])[1]

    # ----------------------------------------------------------- entities
    def hostiles(self, radius: float = 24.0) -> list[Ent]:
        out = [e for e in self.entities if e.hostile and e.dist(self.x, self.y, self.z) <= radius]
        out.sort(key=lambda e: e.dist(self.x, self.y, self.z))
        return out

    def entities_of(self, types, radius: float = 32.0) -> list[Ent]:
        out = [e for e in self.entities if e.type in types and e.dist(self.x, self.y, self.z) <= radius]
        out.sort(key=lambda e: e.dist(self.x, self.y, self.z))
        return out

    def dropped_items(self, radius: float = 12.0) -> list[Ent]:
        out = [e for e in self.entities if e.type == "item" and e.dist(self.x, self.y, self.z) <= radius]
        out.sort(key=lambda e: e.dist(self.x, self.y, self.z))
        return out

    def distance_to(self, x, y, z) -> float:
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2 + (self.z - z) ** 2)

    def summary(self) -> str:
        inv = ", ".join(f"{k} x{v}" for k, v in sorted(self.inventory.items())) or "empty"
        return (f"HP {self.health:.0f}/20, food {self.food}/20, pos ({self.x:.0f}, {self.y:.0f}, {self.z:.0f}); "
                f"inventory: {inv}")
