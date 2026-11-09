
"""
HarshCraftAI - Navigation Utility Tests

Tests the helper functions used by the navigation skill.
No Minecraft connection is required.
"""

import math
import unittest

from core.world_state import Position

from skills.navigation.navigation_utils import (
    distance_3d,
    distance_2d,
    vertical_distance,
    normalize_angle,
    degrees_to_radians,
    radians_to_degrees,
    angle_difference,
    direction_to_target,
    relative_direction,
    goal_relative_coordinates,
    movement_distance,
    is_position_reached,
    clamp,
    classify_direction,
)


class TestNavigationUtils(unittest.TestCase):

    def setUp(self):
        self.origin = Position(0.0, 64.0, 0.0)
        self.target = Position(3.0, 68.0, 4.0)

    def test_distance_3d(self):
        self.assertAlmostEqual(
            distance_3d(self.origin, self.target),
            math.sqrt(41.0),
        )

    def test_distance_2d(self):
        self.assertAlmostEqual(
            distance_2d(self.origin, self.target),
            5.0,
        )

    def test_vertical_distance(self):
        self.assertAlmostEqual(
            vertical_distance(self.origin, self.target),
            4.0,
        )

    def test_normalize_angle(self):
        self.assertAlmostEqual(normalize_angle(360.0), 0.0)
        self.assertAlmostEqual(normalize_angle(450.0), 90.0)
        self.assertAlmostEqual(normalize_angle(-90.0), -90.0)

    def test_degree_radian_conversion(self):
        self.assertAlmostEqual(
            radians_to_degrees(degrees_to_radians(90.0)),
            90.0,
        )

    def test_angle_difference(self):
        self.assertAlmostEqual(
            abs(angle_difference(350.0, 10.0)),
            20.0,
        )

    def test_direction_to_target(self):
        angle = direction_to_target(
            self.origin,
            Position(0.0, 64.0, 10.0),
        )

        self.assertAlmostEqual(angle, 0.0, delta=0.001)

    def test_relative_direction(self):
        self.assertAlmostEqual(
            relative_direction(0.0, 90.0),
            90.0,
        )

    def test_goal_relative_coordinates(self):
        forward, right = goal_relative_coordinates(
            self.origin,
            0.0,
            Position(5.0, 64.0, 0.0),
        )

        self.assertAlmostEqual(forward, 0.0, delta=0.001)
        self.assertAlmostEqual(right, 5.0, delta=0.001)

    def test_movement_distance(self):
        self.assertAlmostEqual(
            movement_distance(self.origin, self.target),
            math.sqrt(41.0),
        )

    def test_is_position_reached(self):
        self.assertTrue(
            is_position_reached(
                self.origin,
                Position(1.0, 64.0, 1.0),
                2.0,
            )
        )

        self.assertFalse(
            is_position_reached(
                self.origin,
                Position(10.0, 64.0, 10.0),
                2.0,
            )
        )

    def test_clamp(self):
        self.assertEqual(clamp(5.0, 0.0, 1.0), 1.0)
        self.assertEqual(clamp(-5.0, 0.0, 1.0), 0.0)
        self.assertEqual(clamp(0.5, 0.0, 1.0), 0.5)

    def test_classify_direction(self):
        self.assertEqual(classify_direction(90.0), "left")
        self.assertEqual(classify_direction(-90.0), "right")
        self.assertEqual(classify_direction(0.0), "forward")


if __name__ == "__main__":
    unittest.main(verbosity=2)
