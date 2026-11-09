"""Combat: the trained PPO policy (or rule fallback) chooses tactics; the motor executes them."""
from __future__ import annotations
import math

from .. import config as C
from ..knowledge import ANIMALS, PASSIVE_AVOID, mob_class, weapon_stats, short
from ..motor import yaw_to
from ..rl import spec
from ..rl.policies import combat_policy
from .common import Result

_policy = None


def policy():
    global _policy
    if _policy is None:
        _policy = combat_policy()
    return _policy


def weapon_damage(m) -> float:
    wp = m.best_weapon()
    ws = weapon_stats(wp) if wp else None
    return ws[0] if ws else 1.0


def weapon_rate(m) -> float:
    wp = m.best_weapon()
    ws = weapon_stats(wp) if wp else None
    return ws[1] if ws else 4.0


def select_targets(w, types):
    out = []
    for e in w.entities:
        if e.type in PASSIVE_AVOID and types is None:
            continue
        if (types is None and e.hostile) or (types is not None and (e.type in types or ("*hostile" in types and e.hostile))):
            out.append(e)
    out.sort(key=lambda e: e.dist(w.x, w.y, w.z))
    return out


def fight(m, types=None, max_steps: int = 400, radius: float = 20.0) -> Result:
    """Fight until no matching target remains within `radius`. types=None -> any hostile mob."""
    with m.quiet():
        return _fight(m, types, max_steps, radius)


def _fight(m, types, max_steps, radius) -> Result:
    pol = policy()
    m.equip_weapon()
    rate = weapon_rate(m)
    dmg = weapon_damage(m)
    since_hit = 99.0
    kills, steps = 0, 0
    last_ids = set()
    start_hp = m.w.health
    while steps < max_steps:
        w = m.w
        ts = [e for e in select_targets(w, types) if e.dist(w.x, w.y, w.z) <= radius]
        ids = {e.id for e in ts}
        kills += len(last_ids - ids) if last_ids else 0
        last_ids = ids
        if not ts:
            m.collect_drops(8.0)
            return Result(True, f"fight over, {kills} defeated, HP {m.w.health:.0f}")
        steps += 1
        ready = min(1.0, since_hit * spec.STEP_SECONDS * rate)
        mobs = [(mob_class(e.type), e.x - w.x, e.z - w.z, e.health) for e in ts]
        obs = spec.combat_obs(w.health, dmg, ready, mobs)
        a = spec.COMBAT_ACTIONS[pol.act(obs)]
        t = ts[0]
        dx, dz = t.x - w.x, t.z - w.z
        toward = yaw_to(dx, dz)
        look = [t.x, t.y + 1.0, t.z]
        tk = C.COMBAT_TICKS
        hit = False
        if a in ("attack", "jump_attack"):
            r = m.act(ticks=tk, **{"do": "attack", "entity": t.id, "fwd": 1 if a == "jump_attack" else 0,
                                   "sprint": a == "jump_attack", "jump": a == "jump_attack"})
            if r.result == "hit":
                hit = True
            elif r.result == "out_of_reach":
                m.act(ticks=tk, look_at=look, fwd=1, sprint=True)
        elif a == "approach":
            m.act(ticks=tk, look_at=look, fwd=1, sprint=True)
        elif a == "retreat":
            m.act(ticks=tk, yaw=toward + 180.0, pitch=0.0, fwd=1, sprint=True)
        elif a == "backpedal":
            m.act(ticks=tk, look_at=look, fwd=-1)
        elif a in ("strafe_left", "strafe_right"):
            m.act(ticks=tk, look_at=look, strafe=1 if a == "strafe_left" else -1)
        else:
            m.act(ticks=tk, look_at=look)
        since_hit = 0.0 if hit else min(since_hit + 1.0, 99.0)
    return Result(False, f"fight timed out; HP {m.w.health:.0f}")


def hunt(m, animal: str, count: int = 1) -> Result:
    """Kill `count` animals of a type (cow/pig/sheep/chicken) and collect the drops."""
    killed, tries = 0, 0
    while killed < count and tries < 6:
        tries += 1
        prey = m.w.entities_of({animal}, 32.0)
        if not prey:
            from .navigate import explore
            explore(m, 30)
            continue
        from ..pathfinding import Goal
        p = prey[0]
        m.goto(Goal(math.floor(p.x), math.floor(p.y), math.floor(p.z), radius=2.0), max_steps=150)
        r = fight(m, {animal}, max_steps=120, radius=6.0)
        if r.ok:
            killed += 1
    return Result(killed >= count, f"hunted {killed}/{count} {animal}")
