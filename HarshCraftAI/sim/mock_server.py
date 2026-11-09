"""A small fake Minecraft implementing the same HTTP protocol as the Fabric mod, for testing the Python stack
without the game. Physics/menus are simplified models of vanilla behaviour; it is a protocol/logic test, NOT proof
that behaviour in real Minecraft is identical."""
from __future__ import annotations
import json
import math
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harshcraft_ai.knowledge import (RECIPES, SMELTS, FUELS, block_info, drop_of, matches, short, tool_info,
                                     weapon_stats, FOOD)

R, YMIN, YMAX = 10, -4, 5
PASSABLE = {"air", "short_grass", "tall_grass", "torch"}


class Mock:
    def __init__(self, inventory=None, trees=((6, 0), (8, 3), (-7, 4)), stone=True, zombies=(), water=False):
        self.blocks: dict = {}
        self.t = 0
        self.eid = 100
        self.entities: dict = {}
        self.x, self.y, self.z = 0.5, 64.0, 0.5
        self.vy = 0.0
        self.yaw, self.pitch = 0.0, 0.0
        self.health, self.food, self.air = 20.0, 20, 300
        self.on_ground = True
        self.hcol = False
        self.inv = [None] * 36                      # 0-8 hotbar, 9-35 main
        self.selected = 0
        self.dead = False
        self.menu_type = "inventory"
        self.grid: list = [None] * 9
        self.cursor = None
        self.furn = [None, None, None]
        self.furn_prog = 0
        self.dig_pos, self.dig_prog = None, 0
        self.atk_cd = 0
        self.eating = 0
        for name, n in (inventory or {}).items():
            self.give(name, n)
        for (tx, tz) in trees:
            for h in range(5):
                self.blocks[(tx, 64 + h, tz)] = "oak_log"
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    self.blocks.setdefault((tx + dx, 69, tz + dz), "oak_leaves")
        if stone:
            for x in range(14, 20):
                for z in range(-3, 4):
                    for y in range(64, 67):
                        self.blocks[(x, y, z)] = "stone"
            self.blocks[(16, 65, 0)] = "iron_ore"
            self.blocks[(17, 65, 1)] = "coal_ore"
        if water:
            for x in range(-4, 0):
                for z in range(6, 12):
                    for y in (61, 62, 63):
                        self.blocks[(x, y, z)] = "water"
        for (zx, zz) in zombies:
            self.spawn("zombie", zx, 64, zz, hp=20.0, hostile=True)
        self.spawn("cow", -5, 64, -5, hp=10.0)

    # ------------------------------------------------------------------ world
    def block(self, x, y, z):
        b = self.blocks.get((x, y, z))
        if b is not None:
            return b
        if y > 63:
            return "air"
        if y == 63:
            return "grass_block"
        if y >= 60:
            return "dirt"
        return "stone"

    @staticmethod
    def flag(name):
        if name in PASSABLE:
            return 0
        if name == "water":
            return 2
        if name == "lava":
            return 3
        return 1

    def spawn(self, typ, x, y, z, hp=20.0, hostile=False, item=None, count=1):
        self.eid += 1
        self.entities[self.eid] = dict(id=self.eid, type=typ, x=x + 0.5, y=float(y), z=z + 0.5, hostile=hostile,
                                       health=hp, item=item, count=count, cd=0)
        return self.eid

    def give(self, name, n):
        for i in range(36):
            s = self.inv[i]
            if s and s[0] == name and s[1] < 64:
                add = min(n, 64 - s[1])
                s[1] += add
                n -= add
                if n == 0:
                    return True
        for i in range(36):
            if self.inv[i] is None:
                add = min(n, 64)
                self.inv[i] = [name, add]
                n -= add
                if n == 0:
                    return True
        return n == 0

    def count(self, name):
        return sum(s[1] for s in self.inv if s and s[0] == name)

    def solid_at(self, x, y, z):
        return self.flag(self.block(math.floor(x), math.floor(y), math.floor(z))) == 1

    # ------------------------------------------------------------------ physics
    def collides(self, x, y, z):
        for ox in (-0.3, 0.3):
            for oz in (-0.3, 0.3):
                for oy in (0.001, 0.9, 1.7):
                    if self.solid_at(x + ox, y + oy, z + oz):
                        return True
        return False

    def in_water(self):
        return self.block(math.floor(self.x), math.floor(self.y), math.floor(self.z)) == "water"

    def head_water(self):
        return self.block(math.floor(self.x), math.floor(self.y + 1.62), math.floor(self.z)) == "water"

    def tick(self, a):
        self.t += 1
        yaw = math.radians(self.yaw)
        fwd, strafe = a.get("fwd", 0), a.get("strafe", 0)
        sprint = a.get("sprint", False) and fwd > 0
        sp = 0.28 if sprint else 0.2155
        if self.in_water():
            sp *= 0.5
        dx = -math.sin(yaw) * fwd - math.cos(yaw) * strafe
        dz = math.cos(yaw) * fwd - math.sin(yaw) * strafe
        n = math.hypot(dx, dz)
        mx = mz = 0.0
        if n > 0:
            mx, mz = dx / n * sp, dz / n * sp
        self.hcol = False
        nx = self.x + mx
        if not self.collides(nx, self.y, self.z):
            self.x = nx
        elif mx:
            self.hcol = True
        nz = self.z + mz
        if not self.collides(self.x, self.y, nz):
            self.z = nz
        elif mz:
            self.hcol = True
        if self.in_water():
            self.vy = 0.1 if a.get("jump") else max(self.vy - 0.02, -0.1)
        elif a.get("jump") and self.on_ground:
            self.vy = 0.42
        ny = self.y + self.vy
        if self.vy <= 0 and self.collides(self.x, ny, self.z):
            landing = math.floor(ny) + 1.0
            if not self.collides(self.x, landing, self.z):
                self.y = landing
            if self.vy < -0.6 and not self.in_water():
                self.health -= max(0.0, (-self.vy - 0.6) * 12)
            self.vy = 0.0
            self.on_ground = True
        elif self.vy > 0 and self.collides(self.x, ny, self.z):
            self.vy = 0.0
            self.on_ground = False
        else:
            self.y = ny
            self.on_ground = False
        if not self.in_water() and not self.on_ground:
            self.vy = (self.vy - 0.08) * 0.98
        elif self.on_ground:
            self.vy = -0.0784 if False else 0.0
        if self.head_water():
            self.air -= 1
            if self.air <= -20:
                self.health -= 2
                self.air = 0
        else:
            self.air = min(300, self.air + 5)
        if a.get("do") == "eat":
            s = self.inv[self.selected]
            if s and s[0] in FOOD:
                self.eating += 1
                if self.eating >= 32:
                    self.food = min(20, self.food + FOOD[s[0]])
                    s[1] -= 1
                    if s[1] <= 0:
                        self.inv[self.selected] = None
                    self.eating = 0
        else:
            self.eating = 0
        for e in list(self.entities.values()):
            if e["type"] == "zombie":
                d = math.hypot(self.x - e["x"], self.z - e["z"])
                if d > 1.0:
                    e["x"] += (self.x - e["x"]) / d * 0.04
                    e["z"] += (self.z - e["z"]) / d * 0.04
                e["cd"] = max(0, e["cd"] - 1)
                if d < 1.6 and e["cd"] == 0:
                    self.health -= 3
                    e["cd"] = 20
            if e["type"] == "item":
                if math.dist((self.x, self.y, self.z), (e["x"], e["y"], e["z"])) < 1.3:
                    if self.give(e["item"], e["count"]):
                        del self.entities[e["id"]]
        if self.menu_type == "furnace" and self.furn[0] and self.furn[1] and self.furn[0][0] in SMELTS:
            self.furn_prog += 1
            if self.furn_prog >= 200:
                self.furn_prog = 0
                out = SMELTS[self.furn[0][0]]
                if self.furn[2] is None:
                    self.furn[2] = [out, 1]
                elif self.furn[2][0] == out:
                    self.furn[2][1] += 1
                self.furn[0][1] -= 1
                if self.furn[0][1] <= 0:
                    self.furn[0] = None
                if self.t % 8 == 0 or FUELS.get(self.furn[1][0], 1) < 8:
                    self.furn[1][1] -= 1
                    if self.furn[1][1] <= 0:
                        self.furn[1] = None
        if self.atk_cd:
            self.atk_cd -= 1
        if self.health <= 0:
            self.dead = True

    # ------------------------------------------------------------------ ops
    def look(self, a):
        if "look_at" in a:
            tx, ty, tz = a["look_at"]
        elif a.get("do") in ("dig", "use", "place") and a.get("pos"):
            tx, ty, tz = (a["pos"][0] + .5, a["pos"][1] + .5, a["pos"][2] + .5)
        elif a.get("do") == "attack" and a.get("entity") in self.entities:
            e = self.entities[a["entity"]]
            tx, ty, tz = e["x"], e["y"] + 1, e["z"]
        else:
            if "yaw" in a:
                self.yaw = a["yaw"]
            if "pitch" in a:
                self.pitch = a["pitch"]
            return
        dx, dz = tx - self.x, tz - self.z
        if math.hypot(dx, dz) > 1e-4:
            self.yaw = math.degrees(math.atan2(dz, dx)) - 90

    def op_dig(self, a):
        pos = tuple(a["pos"])
        name = self.block(*pos)
        if name == "air":
            self.dig_pos = None
            return "broken" if self.dig_prog else "already_air"
        if math.dist((self.x, self.y + 1.62, self.z), (pos[0] + .5, pos[1] + .5, pos[2] + .5)) > 5.0:
            return "too_far"
        if self.dig_pos != pos:
            self.dig_pos, self.dig_prog = pos, 0
        self.dig_prog += 1
        hard, kind, tier = block_info(name)
        held = self.inv[self.selected][0] if self.inv[self.selected] else ""
        ti = tool_info(held)
        right = bool(ti and ti[0] == kind)
        need = max(2, int(hard * (4 if right else 12)))
        if self.dig_prog >= need:
            self.blocks[pos] = "air"
            self.dig_pos, self.dig_prog = None, 0
            ok = kind is None or tier <= 0 or (right and ti[1] >= tier)
            d = drop_of(name)
            if d and ok:
                self.spawn("item", pos[0], pos[1], pos[2], item=d)
            return "broken"
        return "digging"

    def op_place(self, a):
        sx, sy, sz = a["pos"]
        face = {"up": (0, 1, 0), "down": (0, -1, 0), "north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0),
                "west": (-1, 0, 0)}[a["face"]]
        c = (sx + face[0], sy + face[1], sz + face[2])
        s = self.inv[self.selected]
        if not s or self.block(*c) not in ("air", "water"):
            return "not_placed"
        if self.flag(self.block(sx, sy, sz)) != 1:
            return "not_placed"
        if math.floor(self.x) == c[0] and math.floor(self.z) == c[2] and c[1] in (math.floor(self.y), math.floor(self.y) + 1):
            return "not_placed"
        self.blocks[c] = s[0]
        s[1] -= 1
        if s[1] <= 0:
            self.inv[self.selected] = None
        return "placed"

    def op_use(self, a):
        n = self.block(*tuple(a["pos"]))
        if n == "crafting_table":
            self.menu_type = "crafting"
            return "used"
        if n == "furnace":
            self.menu_type = "furnace"
            return "used"
        return "not_used"

    def op_attack(self, a):
        e = self.entities.get(a["entity"])
        if not e:
            return "gone"
        if math.dist((self.x, self.y + 1.6, self.z), (e["x"], e["y"] + 1, e["z"])) > 3.4:
            return "out_of_reach"
        if self.atk_cd:
            return "cooldown"
        held = self.inv[self.selected][0] if self.inv[self.selected] else ""
        ws = weapon_stats(held)
        e["health"] -= ws[0] if ws else 1.0
        self.atk_cd = 12
        if e["health"] <= 0:
            del self.entities[e["id"]]
            if e["type"] == "zombie":
                self.spawn("item", int(e["x"]), int(e["y"]), int(e["z"]), item="rotten_flesh")
            if e["type"] == "cow":
                self.spawn("item", int(e["x"]), int(e["y"]), int(e["z"]), item="beef", count=2)
        return "hit"

    # ------------------------------------------------------------------ menus
    def menu_map(self):
        m = {}
        if self.menu_type == "inventory":
            m[0] = ("res", 0)
            for i in range(4):
                m[1 + i] = ("grid", [0, 1, 3, 4][i])
            for i in range(9, 36):
                m[i] = ("inv", i)
            for i in range(9):
                m[36 + i] = ("inv", i)
            for i in (5, 6, 7, 8, 45):
                m[i] = ("dummy", i)
        elif self.menu_type == "crafting":
            m[0] = ("res", 0)
            for i in range(9):
                m[1 + i] = ("grid", i)
            for i in range(9, 36):
                m[i + 1] = ("inv", i)
            for i in range(9):
                m[37 + i] = ("inv", i)
        else:
            m[0], m[1], m[2] = ("furn", 0), ("furn", 1), ("furn", 2)
            for i in range(9, 36):
                m[i - 6] = ("inv", i)
            for i in range(9):
                m[30 + i] = ("inv", i)
        return m

    def get(self, c):
        k, i = c
        if k == "inv":
            return self.inv[i]
        if k == "grid":
            return self.grid[i]
        if k == "furn":
            return self.furn[i]
        if k == "res":
            return self.recipe_result()
        return None

    def put(self, c, v):
        k, i = c
        if k == "inv":
            self.inv[i] = v
        elif k == "grid":
            self.grid[i] = v
        elif k == "furn":
            self.furn[i] = v

    def recipe_result(self):
        w = 2 if self.menu_type == "inventory" else 3
        cells = {}
        for r in range(w):
            for c in range(w):
                g = self.grid[r * 3 + c]
                if g:
                    cells[(r, c)] = g[0]
        if not cells:
            return None
        for rec in RECIPES.values():
            if rec.shapeless is not None:
                items = sorted(cells.values())
                if len(items) == len(rec.shapeless) and all(matches(a, b) for a, b in zip(items, sorted(rec.shapeless))):
                    return [rec.result, rec.count]
                continue
            rs = [r for r, _ in cells]
            cs = [c for _, c in cells]
            r0, c0 = min(rs), min(cs)
            if max(rs) - r0 + 1 != rec.h or max(cs) - c0 + 1 != rec.w:
                continue
            ok = True
            for (r, c), name in cells.items():
                row = rec.pattern[r - r0]
                ch = row[c - c0] if c - c0 < len(row) else " "
                if ch == " " or not matches(name, rec.key[ch]):
                    ok = False
                    break
            if ok and sum(1 for row in rec.pattern for ch in row if ch != " ") == len(cells):
                return [rec.result, rec.count]
        return None

    def _consume_grid(self):
        for i, g in enumerate(self.grid):
            if g:
                g[1] -= 1
                if g[1] <= 0:
                    self.grid[i] = None

    def click(self, slot, mode, button):
        mp = self.menu_map()
        if slot not in mp or mp[slot][0] == "dummy":
            return
        c = mp[slot]
        if mode == "swap":
            if c[0] == "res":
                return
            a, b = self.get(c), self.inv[button]
            self.put(c, b)
            self.inv[button] = a
            return
        if mode == "quick_move":
            if c[0] == "res":
                while True:
                    r = self.recipe_result()
                    if not r or not self.give(r[0], r[1]):
                        break
                    self._consume_grid()
                return
            s = self.get(c)
            if not s:
                return
            if c[0] == "inv" and self.menu_type == "furnace":
                if s[0] in SMELTS and self.furn[0] is None:
                    self.furn[0] = s[:]
                    self.put(c, None)
                elif s[0] in FUELS and (self.furn[1] is None or self.furn[1][0] == s[0]):
                    if self.furn[1] is None:
                        self.furn[1] = s[:]
                    else:
                        self.furn[1][1] += s[1]
                    self.put(c, None)
                return
            self.put(c, None)
            if not self.give(s[0], s[1]):
                self.put(c, s)
            return
        cur = self.cursor
        s = self.get(c)
        if c[0] == "res":
            if cur is None and s:
                self.cursor = self.recipe_result()[:]
                self._consume_grid()
            return
        if button == 0:
            if cur is None:
                self.cursor = s
                self.put(c, None)
            elif s is None:
                self.put(c, cur)
                self.cursor = None
            elif s[0] == cur[0]:
                tot = s[1] + cur[1]
                s[1] = min(64, tot)
                self.cursor = [cur[0], tot - s[1]] if tot > 64 else None
            else:
                self.put(c, cur)
                self.cursor = s
        else:
            if cur is not None and (s is None or s[0] == cur[0]):
                if s is None:
                    self.put(c, [cur[0], 1])
                else:
                    s[1] += 1
                cur[1] -= 1
                if cur[1] <= 0:
                    self.cursor = None
            elif cur is None and s:
                half = (s[1] + 1) // 2
                self.cursor = [s[0], half]
                s[1] -= half
                if s[1] <= 0:
                    self.put(c, None)

    def close(self):
        for i, g in enumerate(self.grid):
            if g:
                self.give(g[0], g[1])
                self.grid[i] = None
        if self.cursor:
            self.give(self.cursor[0], self.cursor[1])
            self.cursor = None
        if self.menu_type == "furnace":
            for i, f in enumerate(self.furn):
                if f:
                    self.give(f[0], f[1])
                    self.furn[i] = None
        self.menu_type = "inventory"

    # ------------------------------------------------------------------ API
    def step(self, a):
        ticks = max(1, int(a.get("ticks", 1)))
        op = a.get("do", "none")
        if "hotbar" in a:
            self.selected = a["hotbar"]
        result = "ok"
        if op == "click":
            self.click(a["slot"], a.get("mode", "pickup"), a.get("button", 0))
        elif op == "close":
            self.close()
        elif op == "respawn" and self.dead:
            self.dead, self.health, self.x, self.y, self.z = False, 20.0, 0.5, 64.0, 0.5
        elif op == "command":
            cmd = a.get("cmd", "")
            if cmd.startswith("tp @s"):
                p = cmd.split()[2:5]
                self.x, self.y, self.z = float(p[0]), float(p[1]), float(p[2])
        for _ in range(ticks):
            self.look(a)
            if op == "dig":
                result = self.op_dig(a)
            elif op == "place":
                result = self.op_place(a)
            elif op == "use":
                result = self.op_use(a)
            elif op == "attack":
                result = self.op_attack(a)
            self.tick(a)
            if op == "dig" and result in ("broken", "already_air", "too_far"):
                break
            if op in ("place", "use", "attack") and result in ("placed", "used", "hit", "not_placed", "not_used",
                                                              "gone", "out_of_reach"):
                break
        return self.observe(result, ticks)

    def observe(self, result="ok", ticks=0):
        bx, by, bz = math.floor(self.x), math.floor(self.y + 1e-3), math.floor(self.z)
        pal, idx, fl, data = [], {}, [], []
        for dx in range(-R, R + 1):
            for dy in range(YMIN, YMAX + 1):
                for dz in range(-R, R + 1):
                    n = "minecraft:" + self.block(bx + dx, by + dy, bz + dz)
                    if n not in idx:
                        idx[n] = len(pal)
                        pal.append(n)
                        fl.append(self.flag(short(n)))
                    data.append(idx[n])
        inv = [dict(slot=i, id="minecraft:" + s[0], count=s[1], damage=0, max_damage=0)
               for i, s in enumerate(self.inv) if s]
        mp = self.menu_map()
        n_slots = {"inventory": 46, "crafting": 46, "furnace": 39}[self.menu_type]
        slots = []
        for i in range(n_slots):
            s = self.get(mp[i]) if i in mp else None
            slots.append(f"minecraft:{s[0]}*{s[1]}" if s else "")
        ents = []
        for e in self.entities.values():
            if math.dist((e["x"], e["y"], e["z"]), (self.x, self.y, self.z)) <= 24:
                j = dict(id=e["id"], type="minecraft:" + e["type"], x=e["x"], y=e["y"], z=e["z"],
                         hostile=e["hostile"], player=False, health=e["health"])
                if e["type"] == "item":
                    j["item"] = "minecraft:" + e["item"]
                    j["count"] = e["count"]
                ents.append(j)
        return dict(paused=False, game_time=self.t, day_time=1000, raining=False, dimension="minecraft:overworld",
                    player=dict(x=self.x, y=self.y, z=self.z, vx=0, vy=self.vy, vz=0, yaw=self.yaw, pitch=self.pitch,
                                health=self.health, max_health=20, food=self.food, saturation=5, air=self.air,
                                max_air=300, on_ground=self.on_ground, h_collision=self.hcol,
                                in_water=self.in_water(), underwater=self.head_water(), in_lava=False,
                                on_fire=False, fall_distance=0, selected=self.selected, dead=self.dead),
                    inventory=inv,
                    menu=dict(type=self.menu_type, id=0, slots=slots,
                              cursor=(f"minecraft:{self.cursor[0]}*{self.cursor[1]}" if self.cursor else "")),
                    grid=dict(r=R, ymin=YMIN, ymax=YMAX, ox=bx, oy=by, oz=bz, pal=pal, fl=fl, d=data),
                    entities=ents, target=dict(hit=False), result=result, ticks_run=ticks)

    def scan(self, frags, r, v, mx):
        bx, by, bz = math.floor(self.x), math.floor(self.y), math.floor(self.z)
        out = []
        for (x, y, z), n in self.blocks.items():
            if abs(x - bx) <= r and abs(z - bz) <= r and abs(y - by) <= v and n != "air":
                full = "minecraft:" + n
                if any((full == f[1:]) if f.startswith("=") else (f in full) for f in frags):
                    out.append(((x - bx) ** 2 + (y - by) ** 2 + (z - bz) ** 2, dict(x=x, y=y, z=z, block=full)))
        out.sort(key=lambda t: t[0])
        return [o for _, o in out[:mx]]


def serve(mock: Mock, port: int = 5055):
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, obj):
            b = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            with lock:
                if u.path == "/ping":
                    self._send(dict(ok=True, in_world=True, paused=False))
                elif u.path == "/observation":
                    self._send(mock.observe())
                elif u.path == "/scan":
                    q = urllib.parse.parse_qs(u.query)
                    self._send(dict(blocks=mock.scan(q["names"][0].split(","), int(q["r"][0]), int(q["v"][0]),
                                                     int(q["max"][0]))))

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            a = json.loads(self.rfile.read(n))
            with lock:
                self._send(mock.step(a))

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
