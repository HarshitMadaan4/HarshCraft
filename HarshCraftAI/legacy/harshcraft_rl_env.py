
import logging
import math
import os
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from minecraft_env import MinecraftEnvironment


# ============================================================
# CONFIGURATION
# ============================================================

ACTION_INTERVAL = 0.8
MAX_EPISODE_STEPS = 500

# Reaching within this distance counts as success.
GOAL_RADIUS = 2.0

LOG_DIRECTORY = Path("logs")
LOG_FILE = LOG_DIRECTORY / "harshcraft_rl.log"

# These actions represent continuous movement.
# They may safely be refreshed while retrieving observations.
#
# One-shot actions such as jump and turn_left are deliberately
# excluded to avoid accidentally triggering them repeatedly.
CONTINUOUS_ACTIONS = {
    "forward",
    "backward",
    "left",
    "right",
}


# ============================================================
# LOGGING
# ============================================================

LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("HarshCraftRL")
logger.setLevel(logging.INFO)

if not logger.handlers:

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


# ============================================================
# ACTION DEFINITIONS
# ============================================================

ACTIONS = [
    "noop",
    "forward",
    "backward",
    "left",
    "right",
    "turn_left",
    "turn_right",
    "jump",
    "forward_jump",
]


# ============================================================
# GOAL-CONDITIONED MINECRAFT ENVIRONMENT
# ============================================================

class HarshCraftRLEnv(gym.Env):

    """
    Goal-conditioned Minecraft environment.

    The agent receives:
        - Player position
        - Player rotation
        - Health and food
        - Ground/collision state
        - Goal coordinates
        - Distance to goal

    The agent chooses one of the primitive Minecraft actions.

    Important:
        reset() resets the Python episode only.
        It does NOT reset or teleport the Minecraft world.

    The environment supports continuous-action heartbeats
    while waiting for Minecraft observations. This helps
    prevent continuous movement actions from expiring while
    the Java mod calculates an observation.
    """

    metadata = {
        "render_modes": []
    }

    def __init__(
            self,
            goal=(100.0, 64.0, 100.0),
            max_episode_steps=MAX_EPISODE_STEPS,
            action_interval=ACTION_INTERVAL
    ):

        super().__init__()

        self.minecraft = MinecraftEnvironment()

        self.goal = np.asarray(
            goal,
            dtype=np.float32
        )

        if self.goal.shape != (3,):
            raise ValueError(
                "goal must contain exactly three coordinates: x, y, z"
            )

        self.max_episode_steps = int(max_episode_steps)
        self.action_interval = float(action_interval)

        if self.max_episode_steps <= 0:
            raise ValueError("max_episode_steps must be positive")

        if self.action_interval <= 0:
            raise ValueError("action_interval must be positive")

        self.action_space = spaces.Discrete(
            len(ACTIONS)
        )

        # 13 values:
        # x, y, z
        # yaw, pitch
        # health, food
        # on_ground, horizontal_collision
        # goal_x, goal_y, goal_z
        # distance_to_goal

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(13,),
            dtype=np.float32
        )

        self.steps = 0
        self.episode_number = 0

        self.previous_distance = None
        self.previous_health = None

        self.episode_reward = 0.0
        self.episode_finished = True

        logger.info(
            "Environment created | goal=%s | max_steps=%s",
            self.goal.tolist(),
            self.max_episode_steps
        )

    # ========================================================
    # OBSERVATION HELPERS
    # ========================================================

    @staticmethod
    def _distance(position, goal):

        dx = float(position["x"]) - float(goal[0])
        dy = float(position["y"]) - float(goal[1])
        dz = float(position["z"]) - float(goal[2])

        return math.sqrt(
            dx * dx +
            dy * dy +
            dz * dz
        )

    def _get_minecraft_observation(self):

        observation = self.minecraft.get_observation()

        if observation is None:
            raise RuntimeError(
                "Minecraft observation unavailable. "
                "Check that Minecraft is running and "
                "the HarshCraft HTTP server is active."
            )

        if not isinstance(observation, dict):
            raise RuntimeError(
                "Minecraft returned an unexpected observation format."
            )

        player = observation.get("player")

        if not isinstance(player, dict):
            raise RuntimeError(
                "Observation is missing the player information."
            )

        required_fields = [
            "x",
            "y",
            "z",
            "yaw",
            "pitch",
            "health",
            "food",
            "onGround",
            "horizontalCollision",
        ]

        missing = [
            field
            for field in required_fields
            if field not in player
        ]

        if missing:
            raise RuntimeError(
                f"Player observation is missing fields: {missing}"
            )

        return observation

    def _make_agent_observation(self, minecraft_observation):

        player = minecraft_observation["player"]

        distance = self._distance(
            player,
            self.goal
        )

        vector = np.asarray(
            [
                player["x"],
                player["y"],
                player["z"],

                player["yaw"],
                player["pitch"],

                player["health"],
                player["food"],

                float(player["onGround"]),
                float(player["horizontalCollision"]),

                self.goal[0],
                self.goal[1],
                self.goal[2],

                distance,
            ],
            dtype=np.float32
        )

        return vector, distance

    # ========================================================
    # ACTION EXECUTION AND OBSERVATION
    # ========================================================

    def _execute_action_and_observe(self, action_name):

        """
        Sends an action, waits for the configured action interval,
        and retrieves the next Minecraft observation.

        Continuous movement actions use the heartbeat support
        from MinecraftEnvironment while retrieving observations.

        One-shot actions are not repeatedly refreshed.
        """

        action_result = self.minecraft.send_action(action_name)

        time.sleep(self.action_interval)

        if (
                action_result is not None
                and action_name in CONTINUOUS_ACTIONS
                and hasattr(self.minecraft, "observe_while_holding")
        ):

            minecraft_observation = (
                self.minecraft.observe_while_holding(action_name)
            )

        else:

            minecraft_observation = (
                self.minecraft.get_observation()
            )

        if minecraft_observation is None:

            raise RuntimeError(
                "Could not retrieve Minecraft observation after "
                f"executing action: {action_name}"
            )

        return minecraft_observation, action_result

    # ========================================================
    # RESET
    # ========================================================

    def reset(self, seed=None, options=None):

        super().reset(seed=seed)

        options = options or {}

        if "goal" in options:

            new_goal = np.asarray(
                options["goal"],
                dtype=np.float32
            )

            if new_goal.shape != (3,):
                raise ValueError(
                    "The episode goal must contain x, y, z."
                )

            self.goal = new_goal

        self.episode_number += 1
        self.steps = 0
        self.episode_reward = 0.0
        self.episode_finished = False

        # Release any previously held AI action.
        self.minecraft.send_action("noop")

        time.sleep(self.action_interval)

        minecraft_observation = (
            self._get_minecraft_observation()
        )

        agent_observation, distance = (
            self._make_agent_observation(
                minecraft_observation
            )
        )

        self.previous_distance = distance

        self.previous_health = float(
            minecraft_observation["player"]["health"]
        )

        logger.info(
            "EPISODE START | episode=%s | "
            "position=(%.2f, %.2f, %.2f) | "
            "goal=(%.2f, %.2f, %.2f) | "
            "distance=%.2f | world_reset=False",
            self.episode_number,
            minecraft_observation["player"]["x"],
            minecraft_observation["player"]["y"],
            minecraft_observation["player"]["z"],
            self.goal[0],
            self.goal[1],
            self.goal[2],
            distance
        )

        info = {
            "episode": self.episode_number,
            "distance_to_goal": distance,
            "goal": self.goal.tolist(),
            "world_reset": False,
            "note": (
                "Only the Python episode was reset. "
                "The Minecraft world was not reset."
            )
        }

        return agent_observation, info

    # ========================================================
    # STEP
    # ========================================================

    def step(self, action):

        if self.episode_finished:
            raise RuntimeError(
                "Episode has ended. Call reset() before step()."
            )

        if not self.action_space.contains(action):
            raise ValueError(
                f"Invalid action index: {action}"
            )

        action_name = ACTIONS[int(action)]

        # ----------------------------------------------------
        # ACTION EXECUTION
        # ----------------------------------------------------

        minecraft_observation, action_result = (
            self._execute_action_and_observe(action_name)
        )

        agent_observation, distance = (
            self._make_agent_observation(
                minecraft_observation
            )
        )

        player = minecraft_observation["player"]

        health = float(player["health"])

        # ----------------------------------------------------
        # REWARD
        # ----------------------------------------------------

        # Positive reward when distance decreases.
        progress_reward = (
                self.previous_distance - distance
        )

        # Penalize damage and reward recovered health.
        health_change = (
                health - self.previous_health
        )

        reward = (
                progress_reward
                + 0.5 * health_change
                - 0.01
        )

        self.steps += 1

        terminated = False
        truncated = False

        success = distance <= GOAL_RADIUS
        player_dead = health <= 0.0

        if success:

            reward += 10.0
            terminated = True

        elif player_dead:

            reward -= 10.0
            terminated = True

        elif self.steps >= self.max_episode_steps:

            truncated = True

        self.episode_reward += reward

        self.previous_distance = distance
        self.previous_health = health

        if terminated or truncated:

            self.episode_finished = True

            self.minecraft.send_action("noop")

        # ----------------------------------------------------
        # LOGGING
        # ----------------------------------------------------

        logger.info(
            "STEP | episode=%s | step=%s | "
            "action=%s | distance=%.2f | "
            "progress_reward=%.3f | reward=%.3f | "
            "health=%.1f",
            self.episode_number,
            self.steps,
            action_name,
            distance,
            progress_reward,
            reward,
            health
        )

        if terminated or truncated:

            logger.info(
                "EPISODE END | episode=%s | "
                "success=%s | dead=%s | "
                "truncated=%s | steps=%s | "
                "total_reward=%.3f | final_distance=%.2f",
                self.episode_number,
                success,
                player_dead,
                truncated,
                self.steps,
                self.episode_reward,
                distance
            )

        info = {
            "action": action_name,
            "action_response": action_result,
            "distance_to_goal": distance,
            "progress_reward": progress_reward,
            "health": health,
            "success": success,
            "player_dead": player_dead,
            "episode_steps": self.steps,
            "episode_reward": self.episode_reward,
            "world_reset": False,
        }

        return (
            agent_observation,
            float(reward),
            terminated,
            truncated,
            info
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        try:

            self.minecraft.close()

        finally:

            self.episode_finished = True

            logger.info("Environment closed.")
