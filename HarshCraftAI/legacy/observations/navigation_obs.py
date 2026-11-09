
"""
HarshCraftAI - Navigation Observation Encoder

Converts shared Minecraft world state into a numerical
observation for the navigation reinforcement learning agent.

Observation shape: 13

Features:
    0. Goal direction forward
    1. Goal direction right
    2. Vertical difference to goal
    3. Horizontal distance to goal
    4. Total distance to goal
    5. Sine of player yaw
    6. Cosine of player yaw
    7. Player health
    8. Player food
    9. On-ground state
    10. Horizontal collision state
    11. Forward movement
    12. Sideways movement
"""

import math

import numpy as np

from core.world_state import WorldState, Position


class NavigationObservationEncoder:

    OBSERVATION_SIZE = 13

    HORIZONTAL_SCALE = 100.0
    VERTICAL_SCALE = 20.0
    VELOCITY_SCALE = 1.0

    def __init__(self):
        self.previous_position = None

    def reset(self):
        """Reset movement history at the start of an episode."""
        self.previous_position = None

    def encode(
            self,
            world: WorldState,
            goal: Position
    ) -> np.ndarray:
        """
        Convert Minecraft world state into a navigation observation.

        Args:
            world: Current shared Minecraft world state.
            goal: Navigation target position.

        Returns:
            A float32 NumPy array with 13 values.
        """

        player = world.player
        position = player.position

        dx = goal.x - position.x
        dy = goal.y - position.y
        dz = goal.z - position.z

        horizontal_distance = math.sqrt(
            dx * dx + dz * dz
        )

        total_distance = math.sqrt(
            dx * dx + dy * dy + dz * dz
        )

        yaw = math.radians(player.yaw)

        # Convert world-relative direction into
        # player-relative forward and right directions.

        goal_forward = (
                -dx * math.sin(yaw)
                + dz * math.cos(yaw)
        )

        goal_right = (
                dx * math.cos(yaw)
                + dz * math.sin(yaw)
        )

        # Calculate movement since the last observation.

        if self.previous_position is None:

            forward_movement = 0.0
            sideways_movement = 0.0

        else:

            movement_x = (
                    position.x - self.previous_position.x
            )

            movement_z = (
                    position.z - self.previous_position.z
            )

            forward_movement = (
                    -movement_x * math.sin(yaw)
                    + movement_z * math.cos(yaw)
            )

            sideways_movement = (
                    movement_x * math.cos(yaw)
                    + movement_z * math.sin(yaw)
            )

        self.previous_position = Position(
            x=position.x,
            y=position.y,
            z=position.z
        )

        observation = np.asarray(
            [
                np.clip(
                    goal_forward / self.HORIZONTAL_SCALE,
                    -1.0, 1.0
                ),

                np.clip(
                    goal_right / self.HORIZONTAL_SCALE,
                    -1.0, 1.0
                ),

                np.clip(
                    dy / self.VERTICAL_SCALE,
                    -1.0, 1.0
                ),

                np.clip(
                    horizontal_distance / self.HORIZONTAL_SCALE,
                    0.0, 1.0
                ),

                np.clip(
                    total_distance / self.HORIZONTAL_SCALE,
                    0.0, 1.0
                ),

                math.sin(yaw),
                math.cos(yaw),

                np.clip(
                    player.health / 20.0,
                    0.0, 1.0
                ),

                np.clip(
                    player.food / 20.0,
                    0.0, 1.0
                ),

                float(player.on_ground),
                float(player.horizontal_collision),

                np.clip(
                    forward_movement / self.VELOCITY_SCALE,
                    -1.0, 1.0
                ),

                np.clip(
                    sideways_movement / self.VELOCITY_SCALE,
                    -1.0, 1.0
                ),
            ],
            dtype=np.float32
        )

        return observation

    def get_distance(
            self,
            world: WorldState,
            goal: Position
    ) -> float:
        """Return the actual 3D distance to the goal."""

        return world.player_position.distance_to(goal)
