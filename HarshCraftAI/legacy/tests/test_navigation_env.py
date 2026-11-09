
"""
HarshCraftAI - Navigation Environment Tests

Integration tests for the Gymnasium navigation environment.
Requires Minecraft and the HarshCraft HTTP server to be running.
"""

import unittest
import numpy as np

from skills.navigation.navigation_env import NavigationEnv
from skills.navigation.navigation_config import (
    DEFAULT_GOAL,
    MAX_EPISODE_STEPS,
    OBSERVATION_SIZE,
)


class TestNavigationEnvironment(unittest.TestCase):

    def setUp(self):
        self.env = NavigationEnv(
            goal=DEFAULT_GOAL,
            max_episode_steps=MAX_EPISODE_STEPS,
        )

    def tearDown(self):
        if hasattr(self, "env"):
            self.env.close()

    def test_reset_returns_valid_observation(self):
        observation, info = self.env.reset()

        self.assertEqual(
            observation.shape,
            (OBSERVATION_SIZE,),
        )

        self.assertTrue(np.all(np.isfinite(observation)))
        self.assertIsInstance(info, dict)

        self.assertTrue(
            self.env.observation_space.contains(observation),
            "Reset observation is outside the declared observation space.",
        )

    def test_step_returns_gymnasium_values(self):
        self.env.reset()

        # Action 0 is noop in the navigation action configuration.
        result = self.env.step(0)

        self.assertEqual(
            len(result),
            5,
            "Gymnasium step() must return five values.",
        )

        observation, reward, terminated, truncated, info = result

        self.assertEqual(
            observation.shape,
            (OBSERVATION_SIZE,),
        )

        self.assertTrue(np.all(np.isfinite(observation)))
        self.assertIsInstance(reward, (int, float, np.number))
        self.assertIsInstance(terminated, (bool, np.bool_))
        self.assertIsInstance(truncated, (bool, np.bool_))
        self.assertIsInstance(info, dict)

    def test_action_space_contains_noop(self):
        self.assertTrue(
            self.env.action_space.contains(0),
            "Action space does not contain noop action 0.",
        )

    def test_observation_space_has_expected_shape(self):
        self.assertEqual(
            self.env.observation_space.shape,
            (OBSERVATION_SIZE,),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
