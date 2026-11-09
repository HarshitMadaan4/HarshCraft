
"""
HarshCraftAI - Minecraft Connection Test

Tests:
    - HTTP connection to HarshCraft
    - Observation retrieval
    - Player observation structure
    - Required player fields

This test does not move the Minecraft player.
"""

import unittest
from minecraft_env import MinecraftEnvironment


class TestMinecraftConnection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minecraft = MinecraftEnvironment()

    @classmethod
    def tearDownClass(cls):
        cls.minecraft.close()

    def setUp(self):
        self.observation = self.minecraft.get_observation()

        if self.observation is None:
            self.fail(
                "Could not retrieve Minecraft observation. "
                "Check the HTTP server and Python response parsing."
            )

    def test_observation_connection(self):
        self.assertIsInstance(
            self.observation,
            dict,
            f"Expected dict, received {type(self.observation)}"
        )

    def test_player_information(self):
        self.assertIn("player", self.observation)

        player = self.observation["player"]

        self.assertIsInstance(player, dict)

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

        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, player)

    def test_player_values_are_valid(self):
        player = self.observation["player"]

        numeric_fields = [
            "x",
            "y",
            "z",
            "yaw",
            "pitch",
            "health",
            "food",
        ]

        for field in numeric_fields:
            with self.subTest(field=field):
                self.assertIsInstance(
                    player[field],
                    (int, float),
                    f"{field} must be numeric."
                )

        self.assertGreaterEqual(player["health"], 0)
        self.assertGreaterEqual(player["food"], 0)

        self.assertIsInstance(player["onGround"], bool)
        self.assertIsInstance(
            player["horizontalCollision"],
            bool
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
