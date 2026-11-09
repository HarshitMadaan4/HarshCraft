"""The Bot: command queue -> parser -> planner -> skills, with a survival arbiter that can interrupt any task."""
from __future__ import annotations
import queue
import threading
import time

from . import config as C
from . import nlp
from .client import MCClient, MCError
from .knowledge import ANIMALS, LOGS, PLANKS, RAW_MEAT, SMELTS, mob_class
from .motor import Cancelled, Interrupt, Motor, PlayerDied
from .pathfinding import Goal
from .planner import PlanError, Planner, Task
from .rl import spec
from .rl.policies import survival_policy
from .skills import build, combat, craft, mine, navigate, survive
from .skills.common import Result, have


class Arbiter:
    """Decides when to interrupt the current task. Uses the trained survival PPO policy (rule fallback)."""

    def __init__(self, motor: Motor):
        self.m = motor
        self.policy = survival_policy()
        self.cool = 0
        self.last = None
        self.repeat = 0

    def features(self, w):
        th = w.hostiles(16.0)
        nd = th[0].dist(w.x, w.y, w.z) if th else 16.0
        t0 = th[0].type if th else ""
        wp = self.m.best_weapon()
        from .knowledge import weapon_stats
        ws = weapon_stats(wp) if wp else None
        blocks = build.count_material(self.m, build.material_pred(None))
        return spec.surv_obs(w.health, w.food, w.best_food() is not None, w.air, len(th), nd,
                             t0 == "creeper", t0 in ("skeleton", "stray", "blaze", "ghast"),
                             ws[0] if ws else 1.0, blocks >= 12, w.is_night)

    def __call__(self, w):
        if self.cool > 0:
            self.cool -= 1
            return None
        threats = w.hostiles(16.0)
        if not (threats or w.health < 12 or w.food <= C.HUNGRY or w.air < 250):
            return None
        a = spec.SURV_ACTIONS[self.policy.act(self.features(w))]
        if a == "continue" or (a == "eat" and (w.best_food() is None or w.food >= 20)) or \
                (a == "shelter" and build.count_material(self.m, build.material_pred(None)) < 12) or \
                (a in ("fight", "flee") and not threats):
            self.cool = 3
            return None
        return Interrupt(a)

    def handled(self, reason):
        self.repeat = self.repeat + 1 if reason == self.last else 0
        self.last = reason
        self.cool = 8 if self.repeat < 2 else 60


class Bot:
    def __init__(self, client: MCClient | None = None, speak=None, log=print):
        self.c = client or MCClient()
        self.m = Motor(self.c, log=log)
        self.arb = Arbiter(self.m)
        self.m.watch = self.arb
        self.planner = Planner()
        self.q: queue.Queue = queue.Queue()
        self.speak = speak
        self.log = log
        self.busy = False
        self.thread = None
        self.running = False

    # ------------------------------------------------------------------ I/O
    def say(self, msg: str):
        self.log(f"[bot] {msg}")
        if self.speak:
            try:
                self.speak(msg)
            except Exception:
                pass
        try:
            self.c.step(**{"do": "say", "msg": f"[Bot] {msg}", "ticks": 1})
        except Exception:
            pass

    def command(self, text: str, llm=None):
        """Entry point for typed or spoken commands."""
        tasks, reply = nlp.parse(text)
        if (not tasks) and llm is not None:
            try:
                tasks, reply = llm(text, self.m.w.summary())
            except Exception as e:
                self.log(f"[llm] failed: {e}")
        if reply:
            self.say(reply)
        if any(t.kind == "stop" for t in tasks):
            self.stop()
            return
        if tasks:
            self.q.put(tasks)

    def stop(self):
        self.m.cancel.set()
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def shutdown(self):
        self.running = False
        self.stop()

    def _worker(self):
        try:
            self.m.sync()
        except MCError as e:
            self.say(f"Cannot reach Minecraft: {e}")
        while self.running:
            try:
                tasks = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            self.busy = True
            self.m.cancel.clear()
            for t in tasks:
                try:
                    r = self.run_task(t)
                    if r is not None:
                        self.say(("Done: " if r.ok else "Failed: ") + r.msg)
                        if not r.ok:
                            break
                except Cancelled:
                    self.say("Stopped.")
                    break
                except PlayerDied:
                    self.say("I died. Respawned; dropping the current plan.")
                    break
                except (MCError, PlanError) as e:
                    self.say(str(e))
                    break
                except Exception as e:                       # never let the worker die
                    import traceback
                    self.log(traceback.format_exc())
                    self.say(f"Unexpected error: {type(e).__name__}: {e}")
                    break
            self.busy = False
            self.m.cancel.clear()

    # ------------------------------------------------------------------ interrupts
    def handle_interrupt(self, irq: Interrupt):
        m = self.m
        self.log(f"[arbiter] interrupt: {irq.reason}")
        m.close_menu() if m.w.menu.get("type") != "inventory" else None
        with m.quiet():
            if irq.reason == "fight":
                r = combat.fight(m, None, max_steps=250, radius=16.0)
            elif irq.reason == "flee":
                r = survive.flee(m)
            elif irq.reason == "eat":
                r = survive.eat(m)
            elif irq.reason == "shelter":
                r = survive.shelter(m)
                if r.ok:
                    survive.rest_until_healed(m)
            else:
                r = Result(True)
        self.arb.handled(irq.reason)
        return r

    def guarded(self, fn):
        for _ in range(10):
            try:
                return fn()
            except Interrupt as irq:
                self.handle_interrupt(irq)
        return Result(False, "too many interruptions")

    # ------------------------------------------------------------------ tasks
    def run_task(self, t: Task) -> Result | None:
        self.log(f"[task] {t}")
        m = self.m
        m.sync()
        k = t.kind
        if k in ("get", "craft_item"):
            plan = self.planner.expand(t, m.w.inventory)
            if not plan:
                return Result(True, f"already have {t.item.replace('_', ' ')}")
            self.log("[plan] " + " -> ".join(str(p) for p in plan))
            for p in plan:
                r = self.run_task(p)
                if r is not None and not r.ok:
                    return r
            return Result(True, f"got {t.item.replace('_', ' ')}")
        if k == "status":
            self.say(m.w.summary())
            return None
        if k == "set_home":
            m.home = m.w.pos
            return Result(True, f"home set at {m.home}")
        if k == "go_home":
            if m.home is None:
                return Result(False, "I have no home yet; say 'set home' first")
            return self.guarded(lambda: navigate.goto_xyz(m, m.home[0] + .5, m.home[1], m.home[2] + .5, 1.5))
        if k == "goto":
            a = t.args
            return self.guarded(lambda: navigate.goto_xyz(m, a["x"] + .5, a["y"], a["z"] + .5, 1.5))
        if k == "goto_block":
            return self.guarded(lambda: navigate.goto_nearest_block(m, t.args["frag"], t.item))
        if k == "follow":
            return self.guarded(lambda: navigate.follow_player(m, None, 120))
        if k == "explore":
            def go():
                for _ in range(max(1, t.n)):
                    navigate.explore(m, 60)
                return Result(True, "explored")
            return self.guarded(go)
        if k == "eat":
            return self.guarded(lambda: survive.eat(m))
        if k == "shelter":
            return self.guarded(lambda: survive.shelter(m))
        if k == "pillar":
            return self.guarded(lambda: build.pillar_up(m, t.n))
        if k == "bridge":
            return self.guarded(lambda: build.bridge(m, t.n))
        if k == "build":
            return self.guarded(lambda: build.build_structure(m, t.item, tuple(t.args.get("dims") or ()),
                                                              t.args.get("material")))
        if k == "place":
            def go():
                bx, by, bz = m.w.pos
                for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                    c = (bx + dx, by, bz + dz)
                    if m.w.is_air(*c) and build.find_support(m, c):
                        return Result(build.place_cell(m, c, t.item, stand_fixed=True), f"placed {t.item}")
                return Result(False, "no free spot to place it")
            return self.guarded(go)
        if k == "collect":
            target = have(m, t.item) + t.n
            return self.guarded(lambda: mine.mine_resource(m, t.item, target))
        if k == "craft":
            if t.args.get("skip_if_station") and craft.find_station(m, t.args["skip_if_station"], 16):
                return None
            item = self._planks_variant(t.item)
            target = have(m, item) + t.n
            return self.guarded(lambda: craft.craft(m, item, max(1, target - have(m, item))))
        if k == "smelt":
            raw = t.item
            if raw == "log":
                 raw = next((l for l in LOGS if have(m, l) > 0), "oak_log")
            return self.guarded(lambda: craft.smelt(m, raw, t.n))
        if k == "cook_all":
            def go():
                done = []
                for raw in RAW_MEAT:
                    if m.w.count(raw) > 0:
                        r = craft.smelt(m, raw, m.w.count(raw))
                        done.append(r.msg)
                return Result(bool(done), "; ".join(done) or "nothing to cook")
            return self.guarded(go)
        if k == "hunt":
            return self.guarded(lambda: combat.hunt(m, t.item, t.n))
        if k == "kill":
            types = None if t.item == "*hostile" else {t.item}
            def go():
                if not combat.select_targets(m.w, types):
                    from .skills.navigate import explore
                    for _ in range(3):
                        explore(m, 40)
                        if combat.select_targets(m.w, types):
                            break
                    else:
                        return Result(True, "nothing to fight nearby")
                with m.quiet():
                    return combat.fight(m, types, max_steps=600, radius=32.0)
            return self.guarded(go)
        if k == "food":
            def go():
                got = 0
                for animal in ("cow", "pig", "sheep", "chicken"):
                    if got >= t.n:
                        break
                    r = combat.hunt(m, animal, 1)
                    got += int(r.ok)
                return Result(got > 0, f"hunted {got} animals")
            r = self.guarded(go)
            if r.ok:
                self.run_task(Task("cook_all"))
            return r
        if k == "survive":
            return self.guarded(lambda: self._survive(t.args.get("seconds", 300)))
        raise PlanError(f"unknown task {k}")

    def _planks_variant(self, item: str) -> str:
        if item in PLANKS:
            wood = item[:-7]
            if have(self.m, f"{wood}_log") == 0:
                for l in LOGS:
                    if have(self.m, l) > 0:
                        return l[:-4] + "_planks"
        return item

    def _survive(self, seconds: float) -> Result:
        m = self.m
        end = time.time() + seconds
        while time.time() < end:
            m.sync()
            if m.w.hostiles(12.0):
                with m.quiet():
                    combat.fight(m, None, max_steps=120, radius=14.0)
            elif m.w.food <= C.HUNGRY:
                if not survive.eat(m).ok:
                    combat.hunt(m, "cow", 1)
            elif m.w.health < 14:
                survive.rest_until_healed(m)
            else:
                m.act(ticks=20)
        return Result(True, "survived")
