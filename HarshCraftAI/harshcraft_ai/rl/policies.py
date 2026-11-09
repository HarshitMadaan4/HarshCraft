"""Loads trained PPO policies if present; otherwise falls back to the rule policies in spec.py."""
from __future__ import annotations
import numpy as np

from .. import config as C
from . import spec


class _Policy:
    def __init__(self, name: str, rule):
        self.name, self.rule, self.model = name, rule, None
        path = C.MODELS / f"{name}.zip"
        if path.exists():
            try:
                from stable_baselines3 import PPO
                self.model = PPO.load(str(path), device="cpu")
            except Exception as e:           # torch/sb3 missing or incompatible -> rules
                print(f"[policy] could not load {path.name}: {e}; using rule policy")

    @property
    def learned(self) -> bool:
        return self.model is not None

    def act(self, obs) -> int:
        if self.model is None:
            return int(self.rule(obs))
        a, _ = self.model.predict(np.asarray(obs, dtype=np.float32), deterministic=True)
        return int(a)


def combat_policy() -> _Policy:
    return _Policy("combat_ppo", spec.combat_rule)


def survival_policy() -> _Policy:
    return _Policy("survival_ppo", spec.surv_rule)
