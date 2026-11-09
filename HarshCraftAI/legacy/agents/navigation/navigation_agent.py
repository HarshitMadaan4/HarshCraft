
"""
HarshCraftAI - Navigation Agent

Loads and executes a trained PPO or DQN navigation policy.

Responsibilities:
    - Load trained navigation models
    - Select navigation actions
    - Execute actions through NavigationEnv
    - Run goal-directed navigation episodes
    - Report navigation progress

This file performs inference, not training.
"""

import argparse
import logging
from pathlib import Path

import numpy as np

from stable_baselines3 import PPO, DQN

from skills.navigation.navigation_env import NavigationEnv
from skills.navigation.navigation_config import (
    DEFAULT_GOAL,
    DEFAULT_ALGORITHM,
    MODEL_DIRECTORY,
    MAX_EPISODE_STEPS,
    ACTION_INTERVAL,
)


logger = logging.getLogger("HarshCraftAI.NavigationAgent")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ============================================================
# NAVIGATION AGENT
# ============================================================

class NavigationAgent:

    def __init__(
            self,
            model_path,
            algorithm=DEFAULT_ALGORITHM,
            goal=DEFAULT_GOAL,
            device="auto",
            deterministic=True,
    ):

        self.model_path = Path(model_path)

        self.algorithm = algorithm.lower()
        self.goal = tuple(goal)
        self.device = device
        self.deterministic = deterministic

        self.env = None
        self.model = None

        if self.algorithm not in ("ppo", "dqn"):
            raise ValueError(
                "Algorithm must be either 'ppo' or 'dqn'."
            )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Navigation model not found: {self.model_path}"
            )

        logger.info(
            "Initializing navigation agent | algorithm=%s",
            self.algorithm.upper(),
        )

        self._load_model()

    # ========================================================
    # MODEL LOADING
    # ========================================================

    def _load_model(self):

        if self.algorithm == "ppo":

            self.model = PPO.load(
                str(self.model_path),
                device=self.device,
            )

        elif self.algorithm == "dqn":

            self.model = DQN.load(
                str(self.model_path),
                device=self.device,
            )

        logger.info(
            "Navigation model loaded: %s",
            self.model_path,
        )

    # ========================================================
    # ENVIRONMENT
    # ========================================================

    def _create_environment(self):

        if self.env is not None:
            return

        self.env = NavigationEnv(
            goal=self.goal,
            max_episode_steps=MAX_EPISODE_STEPS,
            action_interval=ACTION_INTERVAL,
        )

        # Verify that the loaded policy matches this environment.
        if self.model.observation_space != self.env.observation_space:
            raise ValueError(
                "Model observation space does not match NavigationEnv. "
                "This can happen when loading an older model."
            )

        if self.model.action_space != self.env.action_space:
            raise ValueError(
                "Model action space does not match NavigationEnv."
            )

        self.model.set_env(self.env)

    # ========================================================
    # ACTION PREDICTION
    # ========================================================

    def predict_action(self, observation):

        action, _state = self.model.predict(
            observation,
            deterministic=self.deterministic,
        )

        return int(np.asarray(action).item())

    # ========================================================
    # SINGLE NAVIGATION STEP
    # ========================================================

    def step(self, observation):

        action = self.predict_action(observation)

        next_observation, reward, terminated, truncated, info = (
            self.env.step(action)
        )

        return (
            next_observation,
            reward,
            terminated,
            truncated,
            info,
        )

    # ========================================================
    # NAVIGATION EPISODE
    # ========================================================

    def navigate(self, max_steps=None):

        self._create_environment()

        max_steps = (
            MAX_EPISODE_STEPS
            if max_steps is None
            else int(max_steps)
        )

        if max_steps <= 0:
            raise ValueError("max_steps must be positive.")

        observation, reset_info = self.env.reset()

        total_reward = 0.0
        terminated = False
        truncated = False

        logger.info(
            "Navigation started | goal=%s | initial_distance=%.2f",
            self.goal,
            reset_info["distance_to_goal"],
        )

        try:

            for step_number in range(1, max_steps + 1):

                (
                    observation,
                    reward,
                    terminated,
                    truncated,
                    info,
                ) = self.step(observation)

                total_reward += reward

                logger.info(
                    "AGENT STEP | step=%s | "
                    "action=%s | distance=%.2f | reward=%.3f",
                    step_number,
                    info["action"],
                    info["distance_to_goal"],
                    reward,
                )

                if terminated or truncated:
                    break

        finally:
            # Always release movement when this run ends.
            self.env.minecraft.send_action("noop")

        result = {
            "steps": step_number,
            "total_reward": total_reward,
            "final_distance": info["distance_to_goal"],
            "success": info["success"],
            "terminated": terminated,
            "truncated": truncated,
            "goal": self.goal,
        }

        logger.info(
            "NAVIGATION FINISHED | success=%s | "
            "steps=%s | total_reward=%.3f | "
            "final_distance=%.2f",
            result["success"],
            result["steps"],
            result["total_reward"],
            result["final_distance"],
        )

        return result

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        if self.env is not None:
            self.env.close()
            self.env = None


# ============================================================
# COMMAND LINE
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Run the HarshCraftAI navigation agent."
    )

    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to the trained model ZIP file.",
    )

    parser.add_argument(
        "--algorithm",
        choices=["ppo", "dqn"],
        default=DEFAULT_ALGORITHM,
    )

    parser.add_argument(
        "--goal",
        type=float,
        nargs=3,
        default=DEFAULT_GOAL,
        metavar=("X", "Y", "Z"),
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=MAX_EPISODE_STEPS,
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
    )

    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Use stochastic rather than deterministic predictions.",
    )

    args = parser.parse_args()

    agent = NavigationAgent(
        model_path=args.model,
        algorithm=args.algorithm,
        goal=args.goal,
        device=args.device,
        deterministic=not args.stochastic,
    )

    try:

        result = agent.navigate(
            max_steps=args.steps
        )

        print("\nNavigation result:")
        for key, value in result.items():
            print(f"{key}: {value}")

    finally:
        agent.close()


if __name__ == "__main__":
    main()
