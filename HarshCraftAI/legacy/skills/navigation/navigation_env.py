
"""
HarshCraftAI - Navigation Environment

Gymnasium environment for goal-directed Minecraft navigation.

Uses:
    - Shared Minecraft HTTP connection
    - Shared WorldState representation
    - Navigation-specific observation encoder
    - Navigation-specific reward system

This environment is exclusively for navigation.
Other skills will have their own environments.
"""

import logging
import time

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from minecraft_env import MinecraftEnvironment

from core.world_state import WorldState, Position

from observations.navigation_obs import (
    NavigationObservationEncoder,
)

from skills.navigation.navigation_config import (
    NAVIGATION_ACTIONS,
    OBSERVATION_SIZE,
    DEFAULT_GOAL,
    DEFAULT_GOAL_RADIUS,
    ACTION_INTERVAL,
    MAX_EPISODE_STEPS,
)

from skills.navigation.navigation_rewards import (
    NavigationReward,
)


logger = logging.getLogger("HarshCraftAI.Navigation")


# ============================================================
# NAVIGATION ENVIRONMENT
# ============================================================

class NavigationEnv(gym.Env):
    """
    Goal-conditioned Minecraft navigation environment.

    Action space:
        Discrete(9)

    Observation space:
        Box(shape=(13,), dtype=float32)

    Actions:
        0 noop
        1 forward
        2 backward
        3 left
        4 right
        5 turn_left
        6 turn_right
        7 jump
        8 forward_jump

    reset() resets the Python episode only.
    It does not reset or teleport the Minecraft player.
    """

    metadata = {"render_modes": []}

    CONTINUOUS_ACTIONS = {
        "forward",
        "backward",
        "left",
        "right",
    }

    def __init__(
            self,
            goal=DEFAULT_GOAL,
            max_episode_steps=MAX_EPISODE_STEPS,
            action_interval=ACTION_INTERVAL,
    ):

        super().__init__()

        self.minecraft = MinecraftEnvironment()

        self.goal = self._validate_goal(goal)

        self.max_episode_steps = int(max_episode_steps)
        self.action_interval = float(action_interval)

        if self.max_episode_steps <= 0:
            raise ValueError(
                "max_episode_steps must be positive."
            )

        if self.action_interval <= 0:
            raise ValueError(
                "action_interval must be positive."
            )

        self.action_space = spaces.Discrete(
            len(NAVIGATION_ACTIONS)
        )

        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(OBSERVATION_SIZE,),
            dtype=np.float32,
        )

        self.observation_encoder = (
            NavigationObservationEncoder()
        )

        self.reward_system = NavigationReward()

        self.steps = 0
        self.episode_number = 0

        self.previous_distance = None
        self.previous_health = None
        self.previous_position = None

        self.episode_reward = 0.0
        self.episode_finished = True

        logger.info(
            "Navigation environment initialized | "
            "goal=%s | max_steps=%s",
            self.goal.to_dict(),
            self.max_episode_steps,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_goal(goal):
        """Convert a goal tuple or Position into Position."""

        if isinstance(goal, Position):
            return Position(
                x=float(goal.x),
                y=float(goal.y),
                z=float(goal.z),
            )

        goal_array = np.asarray(
            goal,
            dtype=np.float32,
        )

        if goal_array.shape != (3,):
            raise ValueError(
                "Goal must contain exactly three coordinates: x, y, z."
            )

        return Position(
            x=float(goal_array[0]),
            y=float(goal_array[1]),
            z=float(goal_array[2]),
        )

    # ========================================================
    # MINECRAFT CONNECTION
    # ========================================================

    def _get_world_state(self):
        """Retrieve and validate the current Minecraft world state."""

        observation = self.minecraft.get_observation()

        if observation is None:
            raise RuntimeError(
                "Minecraft observation unavailable. "
                "Check Minecraft and the HarshCraft HTTP server."
            )

        return WorldState.from_dict(observation)

    # ========================================================
    # OBSERVATION
    # ========================================================

    def _get_agent_observation(self, world):
        """Encode shared world state for the navigation policy."""

        observation = self.observation_encoder.encode(
            world,
            self.goal,
        )

        if observation.shape != (OBSERVATION_SIZE,):
            raise RuntimeError(
                "Unexpected navigation observation shape: "
                f"{observation.shape}"
            )

        if not np.all(np.isfinite(observation)):
            raise RuntimeError(
                "Navigation observation contains invalid numeric values."
            )

        return observation.astype(np.float32)

    # ========================================================
    # ACTION EXECUTION
    # ========================================================

    def _execute_action(self, action_name):
        """
        Send an action and retrieve the next world state.

        Continuous actions may use the heartbeat method from
        MinecraftEnvironment while observations are retrieved.

        One-shot actions are never repeatedly refreshed here.
        """

        action_result = self.minecraft.send_action(
            action_name
        )

        time.sleep(self.action_interval)

        if (
                action_result is not None
                and action_name in self.CONTINUOUS_ACTIONS
                and hasattr(
            self.minecraft,
            "observe_while_holding",
        )
        ):

            observation = (
                self.minecraft.observe_while_holding(
                    action_name
                )
            )

        else:

            observation = (
                self.minecraft.get_observation()
            )

        if observation is None:
            raise RuntimeError(
                "Could not retrieve Minecraft observation "
                f"after action: {action_name}"
            )

        world = WorldState.from_dict(observation)

        return world, action_result

    # ========================================================
    # RESET
    # ========================================================

    def reset(self, seed=None, options=None):

        super().reset(seed=seed)

        options = options or {}

        if "goal" in options:
            self.goal = self._validate_goal(
                options["goal"]
            )

        self.episode_number += 1
        self.steps = 0
        self.episode_reward = 0.0
        self.episode_finished = False

        self.previous_distance = None
        self.previous_health = None
        self.previous_position = None

        self.observation_encoder.reset()
        self.reward_system.reset()

        # Release any previous movement command.
        self.minecraft.send_action("noop")

        time.sleep(self.action_interval)

        world = self._get_world_state()

        observation = self._get_agent_observation(world)

        self.previous_distance = (
            world.player_position.distance_to(self.goal)
        )

        self.previous_health = world.player.health

        self.previous_position = Position(
            world.player_position.x,
            world.player_position.y,
            world.player_position.z,
        )

        logger.info(
            "EPISODE START | episode=%s | "
            "position=%s | goal=%s | distance=%.2f",
            self.episode_number,
            world.player_position.to_dict(),
            self.goal.to_dict(),
            self.previous_distance,
        )

        info = {
            "episode": self.episode_number,
            "distance_to_goal": self.previous_distance,
            "goal": self.goal.to_dict(),
            "world_reset": False,
        }

        return observation, info

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
                f"Invalid navigation action: {action}"
            )

        action_name = NAVIGATION_ACTIONS[int(action)]

        # ----------------------------------------------------
        # EXECUTE ACTION
        # ----------------------------------------------------

        world, action_result = self._execute_action(
            action_name
        )

        player = world.player

        current_position = Position(
            player.position.x,
            player.position.y,
            player.position.z,
        )

        current_distance = (
            current_position.distance_to(self.goal)
        )

        movement_distance = (
            current_position.distance_to(
                self.previous_position
            )
        )

        # ----------------------------------------------------
        # ENCODE OBSERVATION
        # ----------------------------------------------------

        observation = self._get_agent_observation(world)

        # ----------------------------------------------------
        # CALCULATE REWARD
        # ----------------------------------------------------

        reward, reward_details = (
            self.reward_system.calculate(
                previous_distance=self.previous_distance,
                current_distance=current_distance,
                previous_health=self.previous_health,
                current_health=player.health,
                action_name=action_name,
                movement_distance=movement_distance,
                horizontal_collision=player.horizontal_collision,
            )
        )

        # ----------------------------------------------------
        # TERMINAL CONDITIONS
        # ----------------------------------------------------

        terminal_reward, terminated, success, dead = (
            self.reward_system.get_terminal_reward(
                distance=current_distance,
                health=player.health,
            )
        )

        reward += terminal_reward

        self.steps += 1

        truncated = (
                not terminated
                and self.steps >= self.max_episode_steps
        )

        self.episode_reward += reward

        # ----------------------------------------------------
        # UPDATE EPISODE STATE
        # ----------------------------------------------------

        self.previous_distance = current_distance
        self.previous_health = player.health

        self.previous_position = current_position

        if terminated or truncated:

            self.episode_finished = True

            # Stop movement when an episode finishes.
            self.minecraft.send_action("noop")

        # ----------------------------------------------------
        # LOGGING
        # ----------------------------------------------------

        logger.info(
            "NAV STEP | episode=%s | step=%s | "
            "action=%s | distance=%.2f | "
            "movement=%.3f | reward=%.3f",
            self.episode_number,
            self.steps,
            action_name,
            current_distance,
            movement_distance,
            reward,
        )

        if terminated or truncated:

            logger.info(
                "NAV EPISODE END | episode=%s | "
                "success=%s | dead=%s | "
                "truncated=%s | steps=%s | "
                "total_reward=%.3f | distance=%.2f",
                self.episode_number,
                success,
                dead,
                truncated,
                self.steps,
                self.episode_reward,
                current_distance,
            )

        # ----------------------------------------------------
        # INFO
        # ----------------------------------------------------

        info = {
            "action": action_name,
            "action_response": action_result,
            "distance_to_goal": current_distance,
            "movement_distance": movement_distance,
            "reward_details": reward_details,
            "health": player.health,
            "success": success,
            "player_dead": dead,
            "episode_steps": self.steps,
            "episode_reward": self.episode_reward,
            "world_reset": False,
        }

        return (
            observation,
            float(reward),
            terminated,
            truncated,
            info,
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        try:
            self.minecraft.send_action("noop")
            self.minecraft.close()

        finally:
            self.episode_finished = True
            logger.info("Navigation environment closed.")
