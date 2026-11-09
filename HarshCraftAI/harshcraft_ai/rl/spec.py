"""Observation/action specs shared by the simulators (training) and the real game (deployment).
No torch/gym imports here so the bot runs without them when no model is present."""
from __future__ import annotations
import math

# ---------------------------------------------------------------- combat
COMBAT_ACTIONS = ["attack", "approach", "retreat", "strafe_left", "strafe_right", "jump_attack", "backpedal", "hold"]
N_MOBS = 3
COMBAT_OBS_DIM = 4 + N_MOBS * 9
STEP_SECONDS = 0.2


def combat_obs(hp, weapon_dmg, ready, mobs):
    """mobs: list of (cls 0-4, x, z, hp) in WORLD coordinates relative to the player (x,z in blocks).
    Frame: +u axis points from the player to the NEAREST mob, v is 90deg to its left."""
    mobs = sorted(mobs, key=lambda t: math.hypot(t[1], t[2]))[:N_MOBS]
    o = [min(hp, 20.0) / 20.0, min(weapon_dmg, 12.0) / 12.0, min(max(ready, 0.0), 1.0), len(mobs) / N_MOBS]
    if mobs:
        ux, uz = mobs[0][1], mobs[0][2]
        n = math.hypot(ux, uz) or 1.0
        ux, uz = ux / n, uz / n
    for i in range(N_MOBS):
        if i < len(mobs):
            cls, x, z, mhp = mobs[i]
            u = x * ux + z * uz
            v = -x * uz + z * ux
            d = math.hypot(x, z)
            oh = [0.0] * 5
            oh[cls] = 1.0
            o += [1.0, max(-1.0, min(1.0, u / 16.0)), max(-1.0, min(1.0, v / 16.0)), min(d / 16.0, 1.0)] + oh[:4] \
                + [min(mhp, 20.0) / 20.0]
            # (class one-hot has 4 slots: zombie, skeleton, creeper, spider; 'other' = all zeros)
        else:
            o += [0.0] * 9
    return o


def combat_rule(obs):
    """Hand-written fallback policy over the same observation (used when no trained model exists)."""
    if obs[3] == 0:
        return 7
    d = obs[7] * 16.0
    ready = obs[2]
    creeper = obs[10] > 0.5
    skeleton = obs[9] > 0.5
    if creeper and d < 3.5:
        return 2
    if d <= 2.7 and ready >= 0.9:
        return 0
    if d <= 2.7:
        return 6 if creeper else 3
    if skeleton and d > 4:
        return 4 if int(d) % 2 else 3
    return 1


# ---------------------------------------------------------------- survival arbiter
SURV_ACTIONS = ["continue", "fight", "flee", "eat", "shelter"]
SURV_OBS_DIM = 11


def surv_obs(hp, food, has_food, air, n_threats, nearest_d, creeper, ranged, weapon, has_blocks, night):
    return [min(hp, 20.0) / 20.0, min(food, 20) / 20.0, float(has_food), min(air, 300) / 300.0,
            min(n_threats, 5) / 5.0, min(nearest_d, 16.0) / 16.0, float(creeper), float(ranged),
            min(weapon, 12.0) / 12.0, float(has_blocks), float(night)]


def surv_rule(o):
    hp, food, has_food = o[0] * 20, o[1] * 20, o[2] > 0.5
    n, d = o[4] * 5, o[5] * 16
    creeper = o[6] > 0.5
    if n > 0 and d < 7:
        if hp < 8 or creeper:
            return 2
        return 1
    if food <= 14 and has_food:
        return 3
    return 0
