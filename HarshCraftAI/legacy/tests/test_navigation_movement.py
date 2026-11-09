
"""
HarshCraftAI - Navigation Movement Test

Checks whether movement and turning actions produce
actual changes in the Minecraft player's state.
"""

import time
import unittest

from minecraft_env import MinecraftEnvironment


class TestNavigationMovement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.minecraft = MinecraftEnvironment()

        # Verify connection before running movement tests.
        observation = cls.minecraft.get_observation()

        if not observation or "player" not in observation:
            raise RuntimeError(
                "Cannot read Minecraft player observation. "
                "Check that Minecraft and HarshCraft are running."
            )

    @classmethod
    def tearDownClass(cls):
        cls.minecraft.send_action("noop")
        cls.minecraft.close()

    def get_player(self):
        observation = self.minecraft.get_observation()
        self.assertIn("player", observation)
        return observation["player"]

    def stop_and_wait(self):
        self.minecraft.send_action("noop")
        time.sleep(0.2)

    def test_forward_movement(self):

        try:
            before = self.get_player()

            self.minecraft.send_action("forward")
            time.sleep(0.8)

            self.stop_and_wait()
            after = self.get_player()

            dx = after["x"] - before["x"]
            dz = after["z"] - before["z"]
            distance = (dx ** 2 + dz ** 2) ** 0.5

            print(
                f"\nForward movement: "
                f"dx={dx:.3f}, dz={dz:.3f}, "
                f"distance={distance:.3f}"
            )

            self.assertGreater(
                distance,
                0.01,
                "Forward action did not move the player."
            )

        finally:
            self.stop_and_wait()

    def test_backward_movement(self):

        try:
            before = self.get_player()

            self.minecraft.send_action("backward")
            time.sleep(0.8)

            self.stop_and_wait()
            after = self.get_player()

            dx = after["x"] - before["x"]
            dz = after["z"] - before["z"]
            distance = (dx ** 2 + dz ** 2) ** 0.5

            print(
                f"\nBackward movement: "
                f"dx={dx:.3f}, dz={dz:.3f}, "
                f"distance={distance:.3f}"
            )

            self.assertGreater(
                distance,
                0.01,
                "Backward action did not move the player."
            )

        finally:
            self.stop_and_wait()

    def test_turn_left(self):

        try:
            before = self.get_player()

            self.minecraft.send_action("turn_left")
            time.sleep(0.3)

            self.stop_and_wait()
            after = self.get_player()

            yaw_change = (
                                 (after["yaw"] - before["yaw"] + 180) % 360
                         ) - 180

            print(f"\nTurn-left yaw change: {yaw_change:.2f}")

            self.assertNotAlmostEqual(
                yaw_change,
                0.0,
                delta=0.1,
                msg="Turn-left action did not change player yaw."
            )

        finally:
            self.stop_and_wait()

    def test_turn_right(self):

        try:
            before = self.get_player()

            self.minecraft.send_action("turn_right")
            time.sleep(0.3)

            self.stop_and_wait()
            after = self.get_player()

            yaw_change = (
                                 (after["yaw"] - before["yaw"] + 180) % 360
                         ) - 180

            print(f"\nTurn-right yaw change: {yaw_change:.2f}")

            self.assertNotAlmostEqual(
                yaw_change,
                0.0,
                delta=0.1,
                msg="Turn-right action did not change player yaw."
            )

        finally:
            self.stop_and_wait()


if __name__ == "__main__":
    unittest.main(verbosity=2)
