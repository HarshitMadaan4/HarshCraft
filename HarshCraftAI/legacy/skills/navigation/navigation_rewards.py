
"""
HarshCraftAI - Navigation Reward System

Calculates rewards for the navigation reinforcement learning agent.

Rewards encourage:
    - Moving closer to the goal
    - Reaching the destination
    - Avoiding repeated collisions
    - Avoiding getting stuck
    - Maintaining player health
"""

import numpy as np

from skills.navigation.navigation_config import (
    STEP_PENALTY,
    PROGRESS_REWARD_SCALE,
    HEALTH_CHANGE_REWARD_SCALE,
    COLLISION_PENALTY,
    STUCK_MOVEMENT_THRESHOLD,
    STUCK_PENALTY_AFTER,
    STUCK_PENALTY,
    SUCCESS_REWARD,
    DEATH_PENALTY,
    DEFAULT_GOAL_RADIUS,
)


class NavigationReward:

    def __init__(self):

        self.stuck_steps = 0

    def reset(self):
        """Reset reward tracking at the beginning of an episode."""
        self.stuck_steps = 0

    def calculate(
            self,
            previous_distance,
            current_distance,
            previous_health,
            current_health,
            action_name,
            movement_distance,
            horizontal_collision,
    ):
        """
        Calculate the reward for one navigation step.

        Returns:
            reward: Total scalar reward.
            details: Dictionary explaining each reward component.
        """

        # ----------------------------------------------------
        # DISTANCE PROGRESS
        # ----------------------------------------------------

        progress = (
                float(previous_distance) - float(current_distance)
        )

        progress = float(
            np.clip(progress, -1.0, 1.0)
        )

        progress_reward = (
                progress * PROGRESS_REWARD_SCALE
        )

        # ----------------------------------------------------
        # HEALTH CHANGE
        # ----------------------------------------------------

        health_change = (
                float(current_health) - float(previous_health)
        )

        health_reward = (
                health_change * HEALTH_CHANGE_REWARD_SCALE
        )

        # ----------------------------------------------------
        # BASIC STEP COST
        # ----------------------------------------------------

        step_reward = -STEP_PENALTY

        # ----------------------------------------------------
        # STUCK DETECTION
        # ----------------------------------------------------

        movement_actions = {
            "forward",
            "backward",
            "left",
            "right",
            "forward_jump",
        }

        stuck_reward = 0.0

        if action_name in movement_actions:

            if movement_distance < STUCK_MOVEMENT_THRESHOLD:
                self.stuck_steps += 1
            else:
                self.stuck_steps = 0

            if self.stuck_steps >= STUCK_PENALTY_AFTER:
                stuck_reward = -STUCK_PENALTY

        else:
            self.stuck_steps = 0

        # ----------------------------------------------------
        # COLLISION PENALTY
        # ----------------------------------------------------

        collision_reward = 0.0

        if (
                action_name in movement_actions
                and horizontal_collision
        ):
            collision_reward = -COLLISION_PENALTY

        # ----------------------------------------------------
        # TOTAL REWARD
        # ----------------------------------------------------

        reward = (
                progress_reward
                + health_reward
                + step_reward
                + stuck_reward
                + collision_reward
        )

        details = {
            "progress": progress,
            "progress_reward": progress_reward,
            "health_change": health_change,
            "health_reward": health_reward,
            "step_reward": step_reward,
            "stuck_reward": stuck_reward,
            "collision_reward": collision_reward,
            "stuck_steps": self.stuck_steps,
        }

        return float(reward), details

    # --------------------------------------------------------
    # TERMINAL REWARDS
    # --------------------------------------------------------

    @staticmethod
    def get_terminal_reward(
            distance,
            health,
    ):
        """
        Calculate terminal reward and termination status.

        Returns:
            terminal_reward, terminated, success, dead
        """

        success = float(distance) <= DEFAULT_GOAL_RADIUS
        dead = float(health) <= 0.0

        if success:
            return SUCCESS_REWARD, True, True, False

        if dead:
            return -DEATH_PENALTY, True, False, True

        return 0.0, False, False, False
