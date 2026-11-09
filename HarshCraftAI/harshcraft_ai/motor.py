"""Motor: the body of the bot. One place that sends actions, applies reflexes and follows paths."""
from __future__ import annotations
import math
import random
import threading
import time
from collections import Counter
from contextlib import contextmanager

from . import config as C
from .client import MCClient, MCError
from .knowledge import block_info, short, tool_info, weapon_stats, breakable
from .pathfinding import Goal, find_path
from .world import World


class Cancelled(Exception):
    """User said stop."""


class PlayerDied(Exception):
    pass


class Interrupt(Exception):
    def __init__(self, reason: str, data=None):
        super().__init__(reason)
        self.reason, self.data = reason, data


def yaw_to(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(dz, dx)) - 90.0


def wrap(d: float) -> float:
    return (d + 180.0) % 360.0 - 180.0


class Motor:
    def __init__(self, client: MCClient, world: World | None = None, log=print):
        self.c = client
        self.w = world or World()
        self.log = log
        self.cancel = threading.Event()
        self.steps = 0
        self.visits: Counter = Counter()
        self.blocked: dict = {}
        self.watch = None                 # callable(World) -> Interrupt | None
        self.watch_on = True
        self.reflex_on = True
        self.recent: list = []
        self.home = None

    # ------------------------------------------------------------ state
    def sync(self) -> World:
        self._ingest(self.c.observation())
        return self.w

    def _ingest(self, obs: dict):
        self.w.update(obs)
        self.visits[self.w.pos] += 1

    @contextmanager
    def quiet(self):
        """Disable interrupt watcher (used by reflex skills so they cannot recurse)."""
        old = self.watch_on
        self.watch_on = False
        try:
            yield
        finally:
            self.watch_on = old

    # ------------------------------------------------------------ the one place actions are sent
    def act(self, ticks: int = C.WALK_TICKS, **action) -> World:
        if self.cancel.is_set():
            raise Cancelled()
        raw = action.pop("_raw", False)
        if self.reflex_on and not raw:
            override = self._reflex()
            if override is not None:
                action = override
                ticks = override.pop("ticks", 1)
        action["ticks"] = ticks
        for attempt in range(40):
            obs = self.c.step(**action)
            if obs.get("result") == "paused" or obs.get("paused"):
                if self.cancel.is_set():
                    raise Cancelled()
                time.sleep(0.25)
                continue
            break
        self._ingest(obs)
        self.steps += 1
        if self.w.dead:
            self.c.step(**{"do": "respawn", "ticks": 5})
            self.sync()
            raise PlayerDied()
        if self.watch_on and self.watch is not None and self.steps % 3 == 0:
            irq = self.watch(self.w)
            if irq is not None:
                raise irq
        return self.w

    def stop(self, ticks: int = 1) -> World:
        return self.act(ticks=ticks, _raw=True)

    # ------------------------------------------------------------ reflexes
    def _reflex(self):
        w = self.w
        if w.in_lava:
            lx = ly = lz = 0.0
            n = 0
            bx, by, bz = w.pos
            for dx in range(-3, 4):
                for dz in range(-3, 4):
                    for dy in range(-1, 2):
                        if w.info(bx + dx, by + dy, bz + dz)[0] == 3:
                            lx += dx; lz += dz; n += 1
            yaw = yaw_to(-lx / n, -lz / n) if n else w.p.get("yaw", 0.0)
            return {"fwd": 1, "jump": True, "sprint": True, "yaw": yaw, "ticks": 2}
        if w.underwater and w.air < C.AIR_PANIC:
            shore = self._nearest_air()
            act = {"jump": True, "ticks": 2}
            if shore is not None:
                act.update({"fwd": 1, "yaw": yaw_to(shore[0] + .5 - w.x, shore[2] + .5 - w.z)})
            return act
        return None

    def _nearest_air(self):
        w = self.w
        bx, by, bz = w.pos
        best, bd = None, 1e9
        for dx in range(-8, 9):
            for dz in range(-8, 9):
                for dy in range(-1, 4):
                    x, y, z = bx + dx, by + dy, bz + dz
                    if w.info(x, y, z)[0] == 0 and w.info(x, y + 1, z)[0] == 0 and \
                            (w.info(x, y - 1, z)[0] in (1, 2)):
                        d = dx * dx + dz * dz + dy * dy
                        if d < bd:
                            best, bd = (x, y, z), d
        return best

    # ------------------------------------------------------------ inventory / hotbar
    def select_item(self, pred) -> int | None:
        """Make an item matching pred(name) the held item. Returns hotbar index or None."""
        w = self.w
        s = w.slot_of(pred)
        if s is None:
            return None
        if s["slot"] < 9:
            if w.p.get("selected") != s["slot"]:
                self.act(ticks=1, hotbar=s["slot"], _raw=True)
            return s["slot"]
        free = w.hotbar_free()
        target = free if free is not None else (8 if w.p.get("selected") != 8 else 7)
        self.act(ticks=1, **{"do": "click", "slot": s["slot"], "button": target, "mode": "swap", "hotbar": target,
                             "_raw": True})
        return target

    def best_tool(self, kind: str, min_tier: int = 0):
        best, bt = None, -1
        for s in self.w.slots:
            if s["slot"] >= 36:
                continue
            ti = tool_info(short(s["id"]))
            if ti and ti[0] == kind and ti[1] > bt and ti[1] >= min_tier:
                best, bt = short(s["id"]), ti[1]
        return best

    def equip_for_block(self, block_name: str) -> int | None:
        hard, kind, tier = block_info(block_name)
        if kind is None:
            return None
        tool = self.best_tool(kind)
        if tool is None:
            return None
        return self.select_item(lambda n: n == tool)

    def best_weapon(self):
        best, bs = None, 1.0
        for s in self.w.slots:
            if s["slot"] >= 36:
                continue
            ws = weapon_stats(short(s["id"]))
            if ws and ws[0] * ws[1] > bs:
                best, bs = short(s["id"]), ws[0] * ws[1]
        return best

    def equip_weapon(self):
        wp = self.best_weapon()
        if wp:
            self.select_item(lambda n: n == wp)
        return wp

    # ------------------------------------------------------------ looking
    def look_at(self, x: float, y: float, z: float, ticks: int = 1) -> World:
        return self.act(ticks=ticks, look_at=[x, y, z], _raw=True)

    # ------------------------------------------------------------ digging
    def safe_to_break(self, pos) -> bool:
        x, y, z = pos
        w = self.w
        for ox, oy, oz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
            if w.info(x + ox, y + oy, z + oz)[0] == 3:
                return False
        return breakable(w.name(*pos))

    def dig(self, pos, max_calls: int = 40) -> bool:
        """Break the block at pos (must be within reach). True when it is gone."""
        w = self.w
        name = w.name(*pos)
        if w.is_air(*pos) or w.info(*pos)[0] != 1:
            return True
        if not self.safe_to_break(pos):
            return False
        hotbar = self.equip_for_block(name)
        for _ in range(max_calls):
            kw = {"do": "dig", "pos": list(pos), "ticks": 12}
            if hotbar is not None:
                kw["hotbar"] = hotbar
            w = self.act(**kw)
            r = w.result
            if r in ("broken", "already_air"):
                return True
            if r in ("too_far", "cannot_start", "bad_args"):
                return False
        return False

    # ------------------------------------------------------------ movement
    def _drive(self, tx: float, tz: float, ty: float, kind: str, final: bool):
        """One movement action toward the centre of a path node."""
        w = self.w
        dx, dz = tx - w.x, tz - w.z
        dist = math.hypot(dx, dz)
        a: dict = {}
        if dist > 0.05:
            a["yaw"] = yaw_to(dx, dz)
        a["pitch"] = 0.0
        a["fwd"] = 1
        sprint_ok = kind == "walk" and dist > 1.8 and not w.in_water and w.food > 6
        a["sprint"] = sprint_ok
        jump = False
        if kind == "jump" and dist < 1.3 and w.on_ground:
            jump = True
        if w.p.get("h_collision") and w.on_ground and ty > w.y + 0.4:
            jump = True
        if w.in_water and ty >= w.by - 0.1:
            jump = True
        if kind == "swim" and ty < w.y - 0.3:
            jump = False
        a["jump"] = jump
        speed = 0.28 if sprint_ok else 0.2155
        ticks = max(1, min(6, math.ceil(dist / speed)))
        if kind == "drop" or final:
            ticks = max(1, min(ticks, 2))
        self.act(ticks=ticks, **a)

    def goto(self, goal, *, allow_dig: bool = False, avoid=frozenset(), max_steps: int = 600,
             stop=None) -> bool:
        """Walk until goal.test(position). Returns True on success."""
        if isinstance(goal, tuple):
            goal = Goal(*[int(math.floor(v)) for v in goal])
        start_steps = self.steps
        fails = 0
        last_progress_h = None
        while self.steps - start_steps < max_steps:
            w = self.w
            if goal.test(w.pos) or (stop is not None and stop(w)):
                return True
            now = self.steps
            for k in [k for k, v in self.blocked.items() if v < now]:
                del self.blocked[k]
            visits = self.visits
            res = find_path(w, w.pos, goal, allow_dig=allow_dig, blocked=frozenset(self.blocked), avoid=avoid,
                            penalty=lambda n: min(6.0, 0.35 * visits.get(n, 0)))
            if not res.steps:
                fails += 1
                if fails >= 3:
                    return False
                self._wiggle()
                continue
            h0 = goal.h(w.pos)
            ok = self._follow(res.steps[:24], goal, allow_dig, avoid, stop)
            h1 = goal.h(self.w.pos)
            if goal.test(self.w.pos) or (stop is not None and stop(self.w)):
                return True
            if (res.partial or not ok) and h1 >= h0 - 0.3:
                fails += 1
                if fails >= 4:
                    return False
            else:
                fails = 0
        return False

    def _wiggle(self):
        self.act(ticks=3, fwd=random.choice((-1, 0, 1)), strafe=random.choice((-1, 1)), jump=random.random() < 0.5,
                 yaw=random.uniform(-180, 180))

    def _follow(self, steps, goal, allow_dig, avoid, stop) -> bool:
        for i, st in enumerate(steps):
            if goal.test(self.w.pos) or (stop is not None and stop(self.w)):
                return True
            for b in st.breaks:
                if not self.w.is_air(*b) and self.w.info(*b)[0] == 1:
                    ex, ey, ez = b
                    if self.w.distance_to(ex + .5, ey + .5, ez + .5) > 4.4:
                        return False
                    if not self.dig(b):
                        self.blocked[st.pos] = self.steps + 40
                        return False
            nx, ny, nz = st.pos
            cx, cz = nx + 0.5, nz + 0.5
            final = i == len(steps) - 1
            nxt_walk = i + 1 < len(steps) and steps[i + 1].kind == "walk" and st.kind == "walk"
            tol = 0.28 if final else (0.75 if nxt_walk else 0.45)
            stuck = 0
            hist = []
            for _ in range(30):
                w = self.w
                dx, dz = cx - w.x, cz - w.z
                if math.hypot(dx, dz) < tol and abs(w.y - ny) < 1.1 and (w.on_ground or w.in_water or st.kind == "drop"):
                    break
                if st.kind == "swim" and abs(w.y - ny) < 0.5 and math.hypot(dx, dz) < tol:
                    break
                self._drive(cx, cz, ny, st.kind, final)
                hist.append((self.w.x, self.w.y, self.w.z))
                if len(hist) >= 5:
                    mv = sum(abs(hist[-1][k] - hist[-5][k]) for k in range(3))
                    if mv < 0.12:
                        stuck += 1
                        if stuck == 1:
                            self.act(ticks=3, fwd=1, jump=True, yaw=yaw_to(dx, dz))
                        elif stuck == 2:
                            self.act(ticks=3, fwd=-1, strafe=random.choice((-1, 1)), yaw=yaw_to(dx, dz))
                        elif stuck == 3 and allow_dig:
                            self._clear_ahead(cx, ny, cz)
                        else:
                            self.blocked[st.pos] = self.steps + 60
                            return False
                        hist.clear()
            else:
                self.blocked[st.pos] = self.steps + 60
                return False
        return True

    def _clear_ahead(self, cx, ny, cz):
        w = self.w
        for yy in (ny, ny + 1):
            c = (math.floor(cx), yy, math.floor(cz))
            if w.info(*c)[0] == 1 and self.safe_to_break(c) and w.distance_to(c[0] + .5, c[1] + .5, c[2] + .5) <= 4.4:
                self.dig(c)

    # ------------------------------------------------------------ pickups
    def collect_drops(self, radius: float = 8.0, max_items: int = 8) -> int:
        got = 0
        tried = Counter()
        with_items = self.w.dropped_items(radius)
        while with_items and got < max_items:
            it = with_items[0]
            tried[it.id] += 1
            if tried[it.id] > 2:
                with_items = [e for e in with_items if tried[e.id] <= 2]
                if not with_items:
                    break
                continue
            before = sum(self.w.inventory.values())
            self.goto(Goal(math.floor(it.x), math.floor(it.y), math.floor(it.z), radius=0.7), max_steps=60)
            self.stop(2)
            if sum(self.w.inventory.values()) > before:
                got += 1
            with_items = self.w.dropped_items(radius)
        return got

    # ------------------------------------------------------------ containers
    @staticmethod
    def menu_slot(kind: str, inv_slot: int) -> int:
        """Inventory slot (0-8 hotbar, 9-35 main) -> slot index in the open container menu."""
        if kind == "crafting":
            return inv_slot + 37 if inv_slot < 9 else inv_slot + 1
        if kind == "furnace":
            return inv_slot + 30 if inv_slot < 9 else inv_slot - 6
        return inv_slot + 36 if inv_slot < 9 else inv_slot          # player inventory menu

    def click(self, slot: int, mode: str = "pickup", button: int = 0) -> World:
        return self.act(ticks=1, **{"do": "click", "slot": slot, "mode": mode, "button": button, "_raw": True})

    def close_menu(self):
        if self.w.menu.get("type") != "inventory":
            self.act(ticks=2, **{"do": "close", "_raw": True})
