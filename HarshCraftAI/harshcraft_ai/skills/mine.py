"""Mining + gathering: find resource blocks, tunnel to them if needed, break them with the right tool, pick up drops."""
from __future__ import annotations
import math

from .. import config as C
from ..knowledge import SOURCES, ORE_DEPTH, block_info, short, tool_info
from ..pathfinding import Goal
from .common import Result, have

XRAY = True       # the mod's /scan sees through rock; set False to only mine blocks exposed to air


def fragments_for(item: str):
    if item in SOURCES:
        return SOURCES[item]
    return [f"=minecraft:{item}"]


def can_harvest(m, block_name: str) -> bool:
    hard, kind, tier = block_info(block_name)
    if kind is None or tier <= 0:
        return True
    return m.best_tool(kind, tier) is not None


def exposed(m, b) -> bool:
    x, y, z = b["x"], b["y"], b["z"]
    return any(m.w.info(x + dx, y + dy, z + dz)[0] != 1
               for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))


def mine_block(m, pos, allow_dig: bool = True) -> bool:
    goal = Goal(pos[0], pos[1], pos[2], radius=C.REACH - 0.5, reach=True)
    ok = True
    if not goal.test(m.w.pos):
        ok = m.goto(goal, allow_dig=False, max_steps=200) or \
             (allow_dig and m.goto(goal, allow_dig=True, max_steps=400))
    if not ok:
        return False
    if m.w.name(*pos) == "unknown":
        return False
    return m.dig(tuple(pos))


def descend_toward(m, y_target: int) -> bool:
    """Tunnel (staircase) down/up toward a depth where the ore is common."""
    x, z = m.w.bx, m.w.bz
    return m.goto(Goal(x, y_target, z, radius=0), allow_dig=True, max_steps=500)


def mine_resource(m, item: str, count: int, *, allow_dig: bool = True, max_search: int = 6) -> Result:
    frags = fragments_for(item)
    bad: set = set()
    searches = 0
    mined = 0
    while have(m, item) < count:
        blocks = [b for b in m.c.scan(frags, C.SCAN_RADIUS, C.SCAN_VERTICAL, 48)
                  if (b["x"], b["y"], b["z"]) not in bad and can_harvest(m, b["block"])]
        if not XRAY:
            blocks = [b for b in blocks if exposed(m, b)]
        if not blocks:
            searches += 1
            if searches > max_search:
                return Result(False, f"could not find {item} (mined {mined}, have {have(m, item)}/{count})")
            from .navigate import explore
            if item in ORE_DEPTH and searches % 2 == 1 and allow_dig:
                descend_toward(m, ORE_DEPTH[item])
            else:
                explore(m, 40)
            continue
        target = None
        for b in blocks[:8]:
            pos = (b["x"], b["y"], b["z"])
            before = have(m, item)
            if mine_block(m, pos, allow_dig):
                m.collect_drops(6.0)
                mined += 1
                target = pos
                break
            bad.add(pos)
        if target is None:
            searches += 1
            if searches > max_search:
                return Result(False, f"could not reach any {item} (have {have(m, item)}/{count})")
    return Result(True, f"have {have(m, item)} {item}")


def mine_blocks_named(m, block: str, count: int) -> Result:
    """Generic 'mine N <block>' that counts blocks broken rather than inventory."""
    frags = [f"=minecraft:{block}"]
    done = 0
    bad = set()
    tries = 0
    while done < count and tries < count * 6 + 10:
        tries += 1
        blocks = [b for b in m.c.scan(frags, C.SCAN_RADIUS, C.SCAN_VERTICAL, 24) if (b["x"], b["y"], b["z"]) not in bad]
        if not blocks:
            from .navigate import explore
            explore(m, 40)
            continue
        b = blocks[0]
        pos = (b["x"], b["y"], b["z"])
        if mine_block(m, pos):
            m.collect_drops(6.0)
            done += 1
        else:
            bad.add(pos)
    return Result(done >= count, f"mined {done}/{count} {block}")
