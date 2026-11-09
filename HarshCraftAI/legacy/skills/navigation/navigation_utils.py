
"""
HarshCraftAI - Navigation Utilities

Reusable mathematical helpers for Minecraft navigation.

Includes:
    - 2D and 3D distance calculations
    - Horizontal distance
    - Angle normalization
    - Relative goal direction
    - Yaw conversion
    - Direction calculations
"""

import math

from core.world_state import Position


# ============================================================
# DISTANCE CALCULATIONS
# ============================================================

def distance_3d(a: Position, b: Position) -> float:
    """Calculate Euclidean distance between two 3D positions."""

    dx = b.x - a.x
    dy = b.y - a.y
    dz = b.z - a.z

    return math.sqrt(dx * dx + dy * dy + dz * dz)


def distance_2d(a: Position, b: Position) -> float:
    """Calculate horizontal distance, ignoring height."""

    dx = b.x - a.x
    dz = b.z - a.z

    return math.sqrt(dx * dx + dz * dz)


def vertical_distance(a: Position, b: Position) -> float:
    """Calculate vertical difference between positions."""

    return b.y - a.y


# ============================================================
# ANGLE UTILITIES
# ============================================================

def normalize_angle(angle: float) -> float:
    """
    Normalize an angle to the range [-180, 180).
    """

    return (angle + 180.0) % 360.0 - 180.0


def degrees_to_radians(angle: float) -> float:
    """Convert degrees to radians."""

    return math.radians(angle)


def radians_to_degrees(angle: float) -> float:
    """Convert radians to degrees."""

    return math.degrees(angle)


def angle_difference(
        current_angle: float,
        target_angle: float
) -> float:
    """
    Calculate the shortest signed angle from current to target.

    Positive means rotate in the positive angular direction.
    Negative means rotate in the negative angular direction.
    """

    return normalize_angle(target_angle - current_angle)


# ============================================================
# MINECRAFT DIRECTION UTILITIES
# ============================================================

def direction_to_target(
        player_position: Position,
        target_position: Position
) -> float:
    """
    Calculate Minecraft yaw required to face a target.

    Minecraft convention:
        yaw 0   = +Z
        yaw 90  = -X
        yaw -90 = +X
        yaw 180 = -Z
    """

    dx = target_position.x - player_position.x
    dz = target_position.z - player_position.z

    return math.degrees(
        math.atan2(-dx, dz)
    )


def relative_direction(
        player_yaw: float,
        target_yaw: float
) -> float:
    """
    Calculate target direction relative to player facing.

    Returns an angle in degrees:
        0    = directly ahead
        90   = to the player's left
        -90  = to the player's right
        180  = directly behind

    Sign convention follows Minecraft yaw.
    """

    return normalize_angle(target_yaw - player_yaw)


def goal_relative_coordinates(
        player_position: Position,
        player_yaw: float,
        goal: Position
) -> tuple[float, float]:
    """
    Convert goal coordinates into player-relative coordinates.

    Returns:
        forward_distance, right_distance
    """

    dx = goal.x - player_position.x
    dz = goal.z - player_position.z

    yaw = math.radians(player_yaw)

    forward = (
            -dx * math.sin(yaw)
            + dz * math.cos(yaw)
    )

    right = (
            dx * math.cos(yaw)
            + dz * math.sin(yaw)
    )

    return forward, right


# ============================================================
# MOVEMENT UTILITIES
# ============================================================

def movement_distance(
        previous_position: Position,
        current_position: Position
) -> float:
    """Calculate distance moved between two observations."""

    return distance_3d(previous_position, current_position)


def is_position_reached(
        current_position: Position,
        target_position: Position,
        radius: float = 2.0
) -> bool:
    """Check whether the target has been reached."""

    if radius < 0:
        raise ValueError("radius cannot be negative")

    return distance_3d(
        current_position,
        target_position
    ) <= radius


def clamp(
        value: float,
        minimum: float,
        maximum: float
) -> float:
    """Restrict a numeric value to a specified range."""

    if minimum > maximum:
        raise ValueError("minimum cannot exceed maximum")

    return max(
        minimum,
        min(maximum, value)
    )


# ============================================================
# DIRECTION CLASSIFICATION
# ============================================================

def classify_direction(
        relative_angle: float
) -> str:
    """
    Convert a relative angle into a simple direction label.
    """

    angle = normalize_angle(relative_angle)

    if -45.0 <= angle <= 45.0:
        return "forward"

    if 45.0 < angle < 135.0:
        return "left"

    if -135.0 < angle < -45.0:
        return "right"

    return "backward"
