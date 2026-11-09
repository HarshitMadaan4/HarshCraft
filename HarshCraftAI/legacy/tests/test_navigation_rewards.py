
"""
HarshCraftAI - Navigation Reward Tests

Tests the actual NavigationReward implementation.
No Minecraft connection is required.
"""

import unittest

from skills.navigation.navigation_rewards import NavigationReward
from skills.navigation.navigation_config import DEFAULT_GOAL_RADIUS


class TestNavigationRewards(unittest.TestCase):

    def setUp(self):
        self.reward_system = NavigationReward()

    def test_progress_toward_goal_gives_positive_reward(self):
        reward, details = self.reward_system.calculate(
            previous_distance=10.0,
            current_distance=8.0,
            previous_health=20.0,
            current_health=20.0,
            action_name="forward",
            movement_distance=2.0,
            horizontal_collision=False,
        )

        self.assertGreater(reward, 0.0)
        self.assertGreater(details["progress_reward"], 0.0)

    def test_moving_away_gives_negative_progress_reward(self):
        reward, details = self.reward_system.calculate(
            previous_distance=8.0,
            current_distance=10.0,
            previous_health=20.0,
            current_health=20.0,
            action_name="backward",
            movement_distance=2.0,
            horizontal_collision=False,
        )

        self.assertLess(reward, 0.0)
        self.assertLess(details["progress_reward"], 0.0)

    def test_health_loss_reduces_reward(self):
        healthy_reward, _ = self.reward_system.calculate(
            previous_distance=10.0,
            current_distance=10.0,
            previous_health=20.0,
            current_health=20.0,
            action_name="noop",
            movement_distance=0.0,
            horizontal_collision=False,
        )

        damaged_reward, details = self.reward_system.calculate(
            previous_distance=10.0,
            current_distance=10.0,
            previous_health=20.0,
            current_health=15.0,
            action_name="noop",
            movement_distance=0.0,
            horizontal_collision=False,
        )

        self.assertLess(damaged_reward, healthy_reward)
        self.assertLess(details["health_reward"], 0.0)

    def test_collision_reduces_reward(self):
        no_collision_reward, _ = self.reward_system.calculate(
            previous_distance=10.0,
            current_distance=10.0,
            previous_health=20.0,
            current_health=20.0,
            action_name="forward",
            movement_distance=0.0,
            horizontal_collision=False,
        )

        collision_reward, details = self.reward_system.calculate(
            previous_distance=10.0,
            current_distance=10.0,
            previous_health=20.0,
            current_health=20.0,
            action_name="forward",
            movement_distance=0.0,
            horizontal_collision=True,
        )

        self.assertLess(collision_reward, no_collision_reward)
        self.assertLess(details["collision_reward"], 0.0)

    def test_stuck_detection_penalizes_repeated_no_movement(self):
        self.reward_system.reset()

        rewards = []

        for _ in range(4):
            reward, details = self.reward_system.calculate(
                previous_distance=10.0,
                current_distance=10.0,
                previous_health=20.0,
                current_health=20.0,
                action_name="forward",
                movement_distance=0.0,
                horizontal_collision=False,
            )

            rewards.append(reward)

        self.assertLess(rewards[-1], rewards[0])
        self.assertLess(details["stuck_reward"], 0.0)

    def test_movement_resets_stuck_counter(self):
        self.reward_system.reset()

        for _ in range(3):
            self.reward_system.calculate(
                previous_distance=10.0,
                current_distance=10.0,
                previous_health=20.0,
                current_health=20.0,
                action_name="forward",
                movement_distance=0.0,
                horizontal_collision=False,
            )

        self.reward_system.calculate(
            previous_distance=10.0,
            current_distance=9.0,
            previous_health=20.0,
            current_health=20.0,
            action_name="forward",
            movement_distance=1.0,
            horizontal_collision=False,
        )

        self.assertEqual(self.reward_system.stuck_steps, 0)

    def test_goal_completion_gives_positive_terminal_reward(self):
        reward, terminated, success, dead = (
            self.reward_system.get_terminal_reward(
                distance=DEFAULT_GOAL_RADIUS - 0.5,
                health=20.0,
            )
        )

        self.assertGreater(reward, 0.0)
        self.assertTrue(terminated)
        self.assertTrue(success)
        self.assertFalse(dead)

    def test_player_death_gives_negative_terminal_reward(self):
        reward, terminated, success, dead = (
            self.reward_system.get_terminal_reward(
                distance=50.0,
                health=0.0,
            )
        )

        self.assertLess(reward, 0.0)
        self.assertTrue(terminated)
        self.assertFalse(success)
        self.assertTrue(dead)

    def test_non_terminal_state_returns_zero_terminal_reward(self):
        reward, terminated, success, dead = (
            self.reward_system.get_terminal_reward(
                distance=50.0,
                health=20.0,
            )
        )

        self.assertEqual(reward, 0.0)
        self.assertFalse(terminated)
        self.assertFalse(success)
        self.assertFalse(dead)


if __name__ == "__main__":
    unittest.main(verbosity=2)
