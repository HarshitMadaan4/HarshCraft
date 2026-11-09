"""Train the PPO policies in the fast simulators.

    python -m harshcraft_ai.rl.train combat   --steps 400000
    python -m harshcraft_ai.rl.train survival --steps 300000
    python -m harshcraft_ai.rl.train all
Saved to models/combat_ppo.zip and models/survival_ppo.zip (loaded automatically by the bot).
"""
from __future__ import annotations
import argparse
import time

import numpy as np

from .. import config as C
from . import spec
from .sims import CombatSim, SurvivalSim


def evaluate(env_cls, act_fn, episodes: int = 200, seed: int = 1234):
    env = env_cls(seed=seed)
    rets, wins, hps = [], 0, []
    for ep in range(episodes):
        obs, _ = env.reset(seed=seed + ep)
        done, ret, info = False, 0.0, {}
        while not done:
            obs, r, term, trunc, info = env.step(act_fn(obs))
            ret += r
            done = term or trunc
        rets.append(ret)
        wins += int(info.get("won", False))
        hps.append(getattr(env, "hp", 0.0))
    return float(np.mean(rets)), wins / episodes, float(np.mean(hps))


def train(kind: str, steps: int, n_envs: int = 4, seed: int = 0):
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env
    cls = CombatSim if kind == "combat" else SurvivalSim
    rule = spec.combat_rule if kind == "combat" else spec.surv_rule
    venv = make_vec_env(cls, n_envs=n_envs, seed=seed)
    model = PPO("MlpPolicy", venv, n_steps=512, batch_size=256, n_epochs=8, learning_rate=3e-4, gamma=0.99,
                gae_lambda=0.95, ent_coef=0.01, policy_kwargs=dict(net_arch=[128, 128]), seed=seed, verbose=0,
                device="cpu")
    t0 = time.time()
    model.learn(total_timesteps=steps)
    path = C.MODELS / f"{kind}_ppo.zip"
    model.save(str(path))
    rng = np.random.default_rng(0)
    n_act = len(spec.COMBAT_ACTIONS if kind == "combat" else spec.SURV_ACTIONS)
    res = {
        "random": evaluate(cls, lambda o: int(rng.integers(n_act))),
        "rule": evaluate(cls, lambda o: rule(list(o))),
        "ppo": evaluate(cls, lambda o: int(model.predict(o, deterministic=True)[0])),
    }
    print(f"\n== {kind}: trained {steps} steps in {time.time() - t0:.0f}s -> {path}")
    print(f"{'policy':8s} {'mean return':>12s} {'win rate':>9s} {'final hp':>9s}")
    for k, (r, w, h) in res.items():
        print(f"{k:8s} {r:12.2f} {w:9.2f} {h:9.1f}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["combat", "survival", "all"])
    ap.add_argument("--steps", type=int, default=None)
    a = ap.parse_args()
    if a.which in ("combat", "all"):
        train("combat", a.steps or 400_000)
    if a.which in ("survival", "all"):
        train("survival", a.steps or 300_000)
