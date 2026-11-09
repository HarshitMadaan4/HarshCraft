"""Fast Python simulators used to train the combat and survival PPO policies in minutes (no Minecraft needed).
Constants are approximations of Minecraft 1.21 normal-difficulty values and are domain-randomised."""
from __future__ import annotations
import math
import random

import gymnasium as gym
import numpy as np

from . import spec

DT = spec.STEP_SECONDS
# (damage, attacks/sec)
WEAPONS = [(1.0, 4.0), (4.0, 1.6), (5.0, 1.6), (6.0, 1.6), (7.0, 1.6), (7.0, 0.8), (9.0, 1.0)]


class _Mob:
    __slots__ = ("cls", "x", "z", "hp", "maxhp", "speed", "dmg", "cd", "fuse", "reach")

    def __init__(self, cls, x, z):
        self.cls, self.x, self.z = cls, x, z
        self.cd, self.fuse = 0.0, 0.0
        if cls == 0:
            self.hp = self.maxhp = 20.0; self.speed = random.uniform(2.3, 4.2); self.dmg = 3.0; self.reach = 1.9
        elif cls == 1:
            self.hp = self.maxhp = 20.0; self.speed = 2.6; self.dmg = 3.5; self.reach = 15.0
        elif cls == 2:
            self.hp = self.maxhp = 20.0; self.speed = random.uniform(2.8, 4.0); self.dmg = 0.0; self.reach = 3.0
        else:
            self.hp = self.maxhp = 16.0; self.speed = random.uniform(4.5, 5.6); self.dmg = 2.0; self.reach = 1.7


class CombatSim(gym.Env):
    metadata = {}

    def __init__(self, max_steps: int = 250, seed: int | None = None):
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (spec.COMBAT_OBS_DIM,), np.float32)
        self.action_space = gym.spaces.Discrete(len(spec.COMBAT_ACTIONS))
        self.max_steps = max_steps
        self.rng = random.Random(seed)

    def _obs(self):
        ready = min(1.0, self.since * DT * self.rate)
        mobs = [(m.cls, m.x, m.z, m.hp) for m in self.mobs]
        return np.asarray(spec.combat_obs(self.hp, self.dmg, ready, mobs), np.float32)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng = random.Random(seed)
            random.seed(seed)
        self.hp = float(self.rng.choice([20.0, 20.0, 20.0, self.rng.uniform(8, 20)]))
        self.dmg, self.rate = self.rng.choice(WEAPONS)
        self.since = 99.0
        self.t = 0
        n = self.rng.choice([1, 1, 2, 3])
        self.mobs = []
        for _ in range(n):
            a, d = self.rng.uniform(0, 2 * math.pi), self.rng.uniform(5, 16)
            cls = self.rng.choices([0, 1, 2, 3], [0.45, 0.2, 0.2, 0.15])[0]
            self.mobs.append(_Mob(cls, d * math.cos(a), d * math.sin(a)))
        return self._obs(), {}

    def step(self, action):
        a = spec.COMBAT_ACTIONS[int(action)]
        self.t += 1
        hp0 = self.hp
        r = -0.003
        mobs = self.mobs
        near = min(mobs, key=lambda m: math.hypot(m.x, m.z)) if mobs else None
        # ---- player action (player stays at the origin; the world moves)
        mv = (0.0, 0.0)
        if near is not None:
            d = math.hypot(near.x, near.z) or 1e-6
            ux, uz = near.x / d, near.z / d
            if a in ("approach", "jump_attack"):
                mv = (ux * 1.12, uz * 1.12)
            elif a == "retreat":
                mv = (-ux * 1.12, -uz * 1.12)
            elif a == "backpedal":
                mv = (-ux * 0.66, -uz * 0.66)
            elif a == "strafe_left":
                mv = (-uz * 0.86, ux * 0.86)
            elif a == "strafe_right":
                mv = (uz * 0.86, -ux * 0.86)
        for m in mobs:
            m.x -= mv[0]
            m.z -= mv[1]
        moving = a not in ("hold", "attack")
        ready = min(1.0, self.since * DT * self.rate)
        if a in ("attack", "jump_attack") and near is not None:
            if math.hypot(near.x, near.z) <= 3.0:
                crit = 1.5 if (a == "jump_attack" and ready >= 0.9) else 1.0
                dealt = self.dmg * (0.2 + 0.8 * ready * ready) * crit
                near.hp -= dealt
                r += 0.5 * min(dealt, near.maxhp) / near.maxhp
                self.since = 0.0
                d = math.hypot(near.x, near.z) or 1e-6
                kb = 1.3 if a == "jump_attack" else 0.7
                near.x += near.x / d * kb
                near.z += near.z / d * kb
                near.fuse = max(0.0, near.fuse - 0.5)
            else:
                self.since += 1.0
        else:
            self.since += 1.0
        # ---- remove dead
        alive = []
        for m in mobs:
            if m.hp <= 0:
                r += 1.0
            else:
                alive.append(m)
        self.mobs = mobs = alive
        # ---- mobs act
        for m in list(mobs):
            d = math.hypot(m.x, m.z) or 1e-6
            m.cd = max(0.0, m.cd - DT)
            if m.cls == 1:                                           # skeleton
                step = m.speed * DT
                if d > 10:
                    m.x -= m.x / d * step; m.z -= m.z / d * step
                elif d < 5:
                    m.x += m.x / d * step; m.z += m.z / d * step
                if d < 15 and m.cd <= 0:
                    m.cd = 2.0
                    p = 0.75 * math.exp(-d / 14.0) * (0.6 if a in ("strafe_left", "strafe_right") else 1.0) \
                        * (0.8 if moving else 1.0)
                    if self.rng.random() < p:
                        self.hp -= m.dmg
                continue
            if m.cls == 2:                                           # creeper
                if d > 2.2:
                    step = m.speed * DT
                    m.x -= m.x / d * step; m.z -= m.z / d * step
                if d < 3.0:
                    m.fuse += DT
                    if m.fuse >= 1.5:
                        self.hp -= max(0.0, 22.0 * (1.0 - d / 6.5)) * self.rng.uniform(0.7, 1.0)
                        self.mobs.remove(m)
                else:
                    m.fuse = max(0.0, m.fuse - DT)
                continue
            if d > m.reach * 0.9:                                    # zombie / spider
                step = min(m.speed * DT, d - m.reach * 0.8)
                m.x -= m.x / d * step; m.z -= m.z / d * step
            elif m.cd <= 0:
                self.hp -= m.dmg
                m.cd = 1.0
        dmg_taken = max(0.0, hp0 - self.hp)
        r -= 0.15 * dmg_taken
        terminated = False
        if self.hp <= 0:
            r -= 3.0
            terminated = True
        elif not self.mobs:
            r += 2.0 + self.hp / 20.0
            terminated = True
        truncated = self.t >= self.max_steps
        return self._obs(), r, terminated, truncated, {"hp": self.hp, "won": (not self.mobs) and self.hp > 0}


class SurvivalSim(gym.Env):
    """Abstract 1-second-per-step survival process: when should the bot keep working vs fight/flee/eat/shelter?"""
    metadata = {}
    SPEED = {0: 2.5, 1: 0.0, 2: 2.8, 3: 4.5}

    def __init__(self, max_steps: int = 400, seed: int | None = None):
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (spec.SURV_OBS_DIM,), np.float32)
        self.action_space = gym.spaces.Discrete(len(spec.SURV_ACTIONS))
        self.max_steps = max_steps
        self.rng = random.Random(seed)

    def _obs(self):
        th = sorted(self.threats, key=lambda t: t[0])
        nd = th[0][0] if th else 16.0
        cls = th[0][1] if th else -1
        return np.asarray(spec.surv_obs(self.hp, self.food, self.has_food > 0, 300, len(th), nd, cls == 2, cls == 1,
                                        self.dmg, self.blocks >= 12, self.night), np.float32)

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng = random.Random(seed)
        r = self.rng
        self.hp = r.choice([20.0, 20.0, r.uniform(6, 20)])
        self.food = r.uniform(5, 20)
        self.has_food = r.choice([0, 0, 1, 3])
        self.dmg, self.rate = r.choice(WEAPONS)
        self.blocks = r.choice([0, 0, 64])
        self.night = r.random() < 0.4
        self.t = 0
        self.threats = []                    # [dist, cls, hp]
        self.shelter_prog = 0
        self.sheltered = False
        return self._obs(), {}

    def step(self, action):
        a = spec.SURV_ACTIONS[int(action)]
        r_ = self.rng
        self.t += 1
        hp0 = self.hp
        reward = 0.0
        if self.t % 300 == 0:
            self.night = not self.night
        if len(self.threats) < 4 and r_.random() < (0.03 if self.night else 0.008):
            cls = r_.choices([0, 1, 2, 3], [0.45, 0.2, 0.2, 0.15])[0]
            self.threats.append([r_.uniform(10, 22), cls, 16.0 if cls == 3 else 20.0])
        dps = self.dmg * self.rate
        # ---- player action
        if a == "continue":
            reward += 0.05
            if self.sheltered:
                self.sheltered = False
        elif a == "eat":
            if self.has_food > 0 and self.food < 20:
                self.food = min(20.0, self.food + 6.0)
                self.has_food -= 1
            else:
                reward -= 0.03
            self.sheltered = False
        elif a == "flee":
            self.sheltered = False
            for t in self.threats:
                t[0] += max(0.0, 5.6 - self.SPEED[t[1]])
            reward -= 0.01
        elif a == "fight":
            self.sheltered = False
            if self.threats:
                t = min(self.threats, key=lambda x: x[0])
                if t[0] > 2.5:
                    t[0] = max(1.5, t[0] - 5.0)
                else:
                    if t[1] == 2 and r_.random() < 0.35:
                        self.hp -= 12.0 * r_.uniform(0.5, 1.0)
                        self.threats.remove(t)
                    else:
                        t[2] -= dps * r_.uniform(0.5, 0.9)
                        if t[2] <= 0:
                            self.threats.remove(t)
                            reward += 0.3
            else:
                reward -= 0.02
        elif a == "shelter":
            if self.blocks >= 12 and not self.sheltered:
                self.shelter_prog += 1
                if self.shelter_prog >= 3:
                    self.sheltered, self.shelter_prog, self.blocks = True, 0, self.blocks - 12
            else:
                reward -= 0.03
        if a != "shelter" and not self.sheltered:
            self.shelter_prog = 0
        # ---- threats act
        for t in list(self.threats):
            if self.sheltered:
                if not self.night and r_.random() < 0.15:
                    self.threats.remove(t)
                continue
            if t[1] == 1:                                           # skeleton
                t[0] = min(max(t[0] - 1.0, 8.0), 20.0) if t[0] > 8 else t[0]
                if t[0] < 15 and r_.random() < 0.5:
                    self.hp -= 3.5 * 0.5 * math.exp(-t[0] / 14.0) * 1.0
            elif t[1] == 2:
                t[0] -= self.SPEED[2]
                if t[0] <= 2.5:
                    self.hp -= r_.uniform(8, 18)
                    self.threats.remove(t)
            else:
                if a != "flee":
                    t[0] -= self.SPEED[t[1]]
                if t[0] <= 1.8:
                    t[0] = 1.8
                    self.hp -= 1.4 if t[1] == 0 else 1.0
            if t[0] > 28 and t in self.threats:
                self.threats.remove(t)
        # ---- body
        if self.t % 10 == 0:
            self.food = max(0.0, self.food - 0.6)
        if self.food >= 18 and self.hp < 20:
            self.hp = min(20.0, self.hp + 0.25)
        if self.food <= 0:
            self.hp -= 0.25
        loss = max(0.0, hp0 - self.hp)
        reward -= 0.12 * loss
        terminated = self.hp <= 0
        if terminated:
            reward -= 5.0
        return self._obs(), reward, terminated, self.t >= self.max_steps, {"won": (not terminated) and self.t >= self.max_steps}
