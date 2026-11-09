"""Task + tech-tree planner: turns 'get a stone pickaxe' into an ordered list of atomic tasks."""
from __future__ import annotations
import math
from dataclasses import dataclass, field

from .knowledge import (LOGS, PLANKS, RECIPES, SMELTS, SOURCES, TAGS, TIER, block_info, drop_of, matches, short,
                        tool_info)


class PlanError(Exception):
    pass


@dataclass
class Task:
    kind: str
    item: str = ""
    n: int = 1
    args: dict = field(default_factory=dict)

    def __str__(self):
        extra = f" {self.args}" if self.args else ""
        return f"{self.kind}({self.item or ''}{' x' + str(self.n) if self.n != 1 else ''}){extra}"


DROP_MOBS = {"beef": "cow", "leather": "cow", "porkchop": "pig", "mutton": "sheep", "white_wool": "sheep",
             "chicken": "chicken", "feather": "chicken", "string": "spider", "rabbit": "rabbit",
             "bone": "skeleton", "gunpowder": "creeper", "rotten_flesh": "zombie", "arrow": None}
SMELT_FROM = {v: k for k, v in SMELTS.items() if not k.endswith("_log")}
SMELT_FROM["charcoal"] = "log"
TIER_NAMES = {1: "wooden", 2: "stone", 3: "iron", 4: "diamond"}


class Planner:
    def expand(self, task: Task, inventory: dict) -> list[Task]:
        """Expand a high-level task using the current inventory. Atomic tasks are returned unchanged."""
        k = task.kind
        if k in ("get", "craft_item"):
            item = self.resolve_alias(task.item, inventory)
            if item.startswith("@armor_"):
                mat = item[7:]
                out, sim = [], dict(inventory)
                for piece in ("helmet", "chestplate", "leggings", "boots"):
                    self._acquire(f"{mat}_{piece}", sim.get(f"{mat}_{piece}", 0) + 1, sim, out, 0)
                return out
            sim = dict(inventory)
            have = self._count(sim, item)
            target = have + task.n if task.args.get("relative", True) else task.n
            out: list[Task] = []
            self._acquire(item, target, sim, out, 0)
            return out
        return [task]

    # ------------------------------------------------------------------ helpers
    def resolve_alias(self, item: str, inv: dict) -> str:
        if item.startswith("@best_"):
            kind = item[6:]
            best = "stone"
            if self._count(inv, "iron_ingot") >= 3:
                best = "iron"
            return f"{best}_{kind}"
        return item

    @staticmethod
    def _count(sim: dict, item: str) -> int:
        if item == "log":
            return sum(sim.get(l, 0) for l in LOGS)
        if item.startswith("#"):
            return sum(c for n, c in sim.items() if matches(n, item))
        return sim.get(item, 0)

    @staticmethod
    def _add(sim: dict, item: str, n: int):
        sim[item] = sim.get(item, 0) + n

    @staticmethod
    def _consume(sim: dict, want: str, n: int):
        names = TAGS[want] if want.startswith("#") else (LOGS if want == "log" else [want])
        for nm in sorted(names, key=lambda x: -sim.get(x, 0)):
            take = min(sim.get(nm, 0), n)
            if take:
                sim[nm] -= take
                n -= take
            if n <= 0:
                return

    def _concrete(self, want: str, sim: dict) -> str:
        """Pick a concrete item for a tag ingredient we have to obtain."""
        if not want.startswith("#"):
            return want
        opts = TAGS[want]
        have = [o for o in opts if sim.get(o, 0) > 0]
        return have[0] if have else opts[0]

    def _acquire(self, item: str, n: int, sim: dict, out: list, depth: int):
        if depth > 14:
            raise PlanError(f"recipe chain for {item} is too deep")
        have = self._count(sim, item)
        if have >= n:
            return
        need = n - have
        if item.startswith("#"):
            conc = self._concrete(item, sim)
            return self._acquire(conc, self._count(sim, conc) + need, sim, out, depth + 1)
        if item == "log":
            out.append(Task("collect", "log", need))
            self._add(sim, "oak_log", need)
            return
        if item in RECIPES:
            rec = RECIPES[item]
            times = math.ceil(need / rec.count)
            if rec.needs_table and sim.get("crafting_table", 0) == 0:
                self._acquire("crafting_table", 1, sim, out, depth + 1)
                out[-1].args["skip_if_station"] = "crafting_table"
            for ing, c in rec.ingredients().items():
                self._acquire(ing, c * times, sim, out, depth + 1)
                self._consume(sim, ing, c * times)       # reserve now so later ingredients cannot reuse it
            t = Task("craft", item, times * rec.count)
            out.append(t)
            self._add(sim, item, times * rec.count)
            return
        if item in SMELT_FROM and item not in SOURCES:
            raw = SMELT_FROM[item]
            self._acquire(raw, self._count(sim, raw) + need, sim, out, depth + 1)
            if sim.get("furnace", 0) == 0:
                self._acquire("furnace", 1, sim, out, depth + 1)
                out[-1].args["skip_if_station"] = "furnace"
                self._add(sim, "furnace", 1)
                from .knowledge import FUELS
                fuel_have = sum(sim.get(f, 0) * v for f, v in FUELS.items() if f != item)
                if fuel_have < need:                       # any fuel in inventory counts: coal, charcoal, any planks, sticks
                    self._acquire("#planks", self._count(sim, "#planks") + math.ceil((need - fuel_have) / 1.5),
                          sim, out, depth + 1)
            out.append(Task("smelt", raw, need))
            self._add(sim, item, need)
            return
        if item in DROP_MOBS and DROP_MOBS[item]:
            out.append(Task("hunt", DROP_MOBS[item], need, {"want": item}))
            self._add(sim, item, need)
            return
        if item in SOURCES or any(drop_of(b.replace("=minecraft:", "")) == item for v in SOURCES.values() for b in v[:1]):
            src = SOURCES.get(item, [f"=minecraft:{item}"])[0].replace("=minecraft:", "")
            hard, kind, tier = block_info(src if src != "_log" else "oak_log")
            if kind == "pickaxe":
                t = max(1, tier)
                if not any((ti := tool_info(n)) and ti[0] == "pickaxe" and ti[1] >= t for n in sim if sim[n] > 0):
                    self._acquire(f"{TIER_NAMES.get(t, 'diamond')}_pickaxe", 1, sim, out, depth + 1)
            out.append(Task("collect", item, need))
            self._add(sim, item, need)
            return
        if item in ("stone",):
            return self._acquire("cobblestone", need, sim, out, depth + 1)
        raise PlanError(f"I don't know how to obtain {item.replace('_', ' ')}")
