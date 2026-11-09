
"""
HarshCraftAI - Navigation Observation Encoder Tests

Tests the navigation observation encoder using simulated
world states. No Minecraft connection is required.
"""

import unittest
import numpy as np

from core.world_state import (
    Position,
    PlayerState,
    WorldState,
)
from observations.navigation_obs import NavigationObservationEncoder


class TestNavigationObservationEncoder(unittest.TestCase):

    def setUp(self):
        self.encoder = NavigationObservationEncoder()
        self.goal = Position(x=10.0, y=64.0, z=10.0)

    def make_world_state(
            self,
            x=0.0,
            y=64.0,
            z=0.0,
            yaw=0.0,
            pitch=0.0,
            health=20.0,
            food=20.0,
            on_ground=True,
            horizontal_collision=False,
    ):
        player = PlayerState(
            position=Position(x=x, y=y, z=z),
            yaw=yaw,
            pitch=pitch,
            health=health,
            food=food,
            on_ground=on_ground,
            horizontal_collision=horizontal_collision,
        )

        return WorldState(player=player)

    def test_observation_has_expected_shape(self):
        world_state = self.make_world_state()

        observation = self.encoder.encode(
            world_state,
            self.goal,
        )

        self.assertEqual(observation.shape, (13,))

    def test_observation_contains_finite_values(self):
        world_state = self.make_world_state()

        observation = self.encoder.encode(
            world_state,
            self.goal,
        )

        self.assertTrue(
            np.all(np.isfinite(observation)),
            "Observation contains NaN or infinite values.",
        )

    def test_observation_values_are_normalized(self):
        world_state = self.make_world_state()

        observation = self.encoder.encode(
            world_state,
            self.goal,
        )

        self.assertTrue(
            np.all(observation >= -1.0),
            "Observation contains values below -1.",
        )

        self.assertTrue(
            np.all(observation <= 1.0),
            "Observation contains values above 1.",
        )

    def test_goal_distance_decreases_when_player_moves_closer(self):
        self.encoder.reset()

        far_state = self.make_world_state(x=0.0, z=0.0)
        near_state = self.make_world_state(x=9.0, z=9.0)

        far_observation = self.encoder.encode(
            far_state,
            self.goal,
        )

        near_observation = self.encoder.encode(
            near_state,
            self.goal,
        )

        # Feature index 4 is normalized horizontal distance.
        self.assertLess(
            near_observation[4],
            far_observation[4],
            "Encoded horizontal distance did not decrease.",
        )

    def test_reset_clears_previous_position(self):
        world_state = self.make_world_state()

        self.encoder.encode(world_state, self.goal)
        self.encoder.reset()

        self.assertIsNone(
            self.encoder.previous_position,
            "Encoder reset did not clear previous position.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
