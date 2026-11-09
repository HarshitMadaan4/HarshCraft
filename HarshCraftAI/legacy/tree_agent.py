import time
import math

from minecraft_env import MinecraftEnvironment
from test_tree_detection import find_nearest_tree


# ============================================================
# SETTINGS
# ============================================================

CONTROL_INTERVAL = 0.10

# Start precise aiming when this close to the selected log.
TREE_REACH_DISTANCE = 3.2

# Aim tolerances.
YAW_TOLERANCE = 3.0
PITCH_TOLERANCE = 4.0

# Search rotation.
MAX_SEARCH_STEPS = 90

# Movement limit.
MAX_MOVE_STEPS = 250

# Mining limit for one block.
MAX_MINE_TIME = 8.0


# ============================================================
# TREE BLOCKS
# ============================================================

TREE_BLOCKS = {
    "minecraft:oak_log",
    "minecraft:birch_log",
    "minecraft:spruce_log",
    "minecraft:jungle_log",
    "minecraft:acacia_log",
    "minecraft:dark_oak_log",
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def stop(env):
    """
    Explicitly stop the current AI action.
    """

    try:
        env.send_action("noop")
    except Exception:
        pass


def normalize_angle(angle):
    while angle > 180.0:
        angle -= 360.0

    while angle < -180.0:
        angle += 360.0

    return angle


def same_block(a, b):
    if a is None or b is None:
        return False

    return (
            int(a["x"]) == int(b["x"])
            and int(a["y"]) == int(b["y"])
            and int(a["z"]) == int(b["z"])
    )


def distance_to_block(player, block):
    dx = block["x"] - player["x"]
    dy = block["y"] - player["y"]
    dz = block["z"] - player["z"]

    return math.sqrt(
        dx * dx +
        dy * dy +
        dz * dz
    )


# ============================================================
# CURRENT CROSSHAIR TARGET
# ============================================================

def get_crosshair_target(observation):
    """
    Observation.java currently exposes:

        observation["target"]

    TargetObservation contains:

        hit
        x
        y
        z
        type
    """

    target = observation.get("target")

    if target is None:
        return None

    if not target.get("hit", False):
        return None

    return target


def is_tree_target(target):
    if target is None:
        return False

    return target.get("type") in TREE_BLOCKS


# ============================================================
# AIM CALCULATIONS
# ============================================================

def calculate_target_yaw(player, target):
    """
    Minecraft yaw required to face the center of the block.
    """

    target_x = target["x"] + 0.5
    target_z = target["z"] + 0.5

    dx = target_x - player["x"]
    dz = target_z - player["z"]

    return math.degrees(
        math.atan2(
            -dx,
            dz
        )
    )


def calculate_target_pitch(player, target):
    """
    Minecraft pitch required to look at the center of the block.

    Negative pitch = look upward.
    Positive pitch = look downward.
    """

    target_x = target["x"] + 0.5
    target_y = target["y"] + 0.5
    target_z = target["z"] + 0.5

    eye_y = player["y"] + 1.62

    dx = target_x - player["x"]
    dy = target_y - eye_y
    dz = target_z - player["z"]

    horizontal_distance = math.sqrt(
        dx * dx +
        dz * dz
    )

    if horizontal_distance < 0.001:
        return player["pitch"]

    return math.degrees(
        math.atan2(
            -dy,
            horizontal_distance
        )
    )


# ============================================================
# SELECT TREE TARGET
# ============================================================

def find_tree_target(observation, previous_target=None):
    """
    Select a log.

    Priority:

    1. Current crosshair if it is already a log.
    2. A log adjacent to the previous mined log.
    3. Nearest detected log.
    """

    target = get_crosshair_target(
        observation
    )

    if is_tree_target(target):
        return target

    blocks = observation.get(
        "nearbyBlocks",
        []
    )

    # --------------------------------------------------------
    # Prefer another log near the previous log.
    # --------------------------------------------------------

    if previous_target is not None:

        candidates = []

        for block in blocks:

            if block.get("type") not in TREE_BLOCKS:
                continue

            if same_block(
                    block,
                    previous_target
            ):
                continue

            dx = (
                    block["x"] -
                    previous_target["x"]
            )

            dy = (
                    block["y"] -
                    previous_target["y"]
            )

            dz = (
                    block["z"] -
                    previous_target["z"]
            )

            distance = math.sqrt(
                dx * dx +
                dy * dy +
                dz * dz
            )

            candidates.append(
                (distance, block)
            )

        if candidates:

            candidates.sort(
                key=lambda item: item[0]
            )

            return candidates[0][1]

    # --------------------------------------------------------
    # Otherwise use the normal tree detector.
    # --------------------------------------------------------

    return find_nearest_tree(
        observation
    )


# ============================================================
# PRECISE AIM
# ============================================================

def aim_at_tree(
        env,
        observation,
        target
):
    """
    Aim at one specific log.

    IMPORTANT:

    We do not consider the agent ready to mine merely because
    the log is nearby.

    The actual Minecraft raycast must report that the
    crosshair is on a log.
    """

    player = observation["player"]

    current_target = get_crosshair_target(
        observation
    )

    # --------------------------------------------------------
    # FIRST: check the actual crosshair.
    # --------------------------------------------------------

    if is_tree_target(current_target):

        print(
            "Crosshair verified on:",
            current_target
        )

        stop(env)

        return True

    # --------------------------------------------------------
    # Calculate yaw.
    # --------------------------------------------------------

    target_yaw = calculate_target_yaw(
        player,
        target
    )

    yaw_difference = normalize_angle(
        target_yaw -
        player["yaw"]
    )

    # --------------------------------------------------------
    # Calculate pitch.
    # --------------------------------------------------------

    target_pitch = calculate_target_pitch(
        player,
        target
    )

    pitch_difference = (
            target_pitch -
            player["pitch"]
    )

    print(
        f"Yaw difference: {yaw_difference:.2f} "
        f"Pitch difference: {pitch_difference:.2f}"
    )

    # --------------------------------------------------------
    # YAW FIRST
    # --------------------------------------------------------

    if abs(yaw_difference) > YAW_TOLERANCE:

        if yaw_difference > 0:

            env.send_action(
                "turn_right"
            )

        else:

            env.send_action(
                "turn_left"
            )

        time.sleep(
            CONTROL_INTERVAL
        )

        return False

    # --------------------------------------------------------
    # THEN PITCH
    # --------------------------------------------------------

    if abs(pitch_difference) > PITCH_TOLERANCE:

        if pitch_difference < 0:

            print(
                "Looking UP toward log."
            )

            env.send_action(
                "look_up"
            )

        else:

            print(
                "Looking DOWN toward log."
            )

            env.send_action(
                "look_down"
            )

        time.sleep(
            CONTROL_INTERVAL
        )

        return False

    # --------------------------------------------------------
    # Geometrically aimed but raycast hasn't caught it yet.
    # Give Minecraft another observation cycle.
    # --------------------------------------------------------

    stop(env)

    time.sleep(
        CONTROL_INTERVAL
    )

    return False


# ============================================================
# SEARCH
# ============================================================

def search_for_tree(env):
    """
    Rotate in small one-shot increments.

    Java handles each turn action as a short action.
    """

    print()
    print("=" * 60)
    print("SEARCHING FOR TREE")
    print("=" * 60)

    for i in range(
            MAX_SEARCH_STEPS
    ):

        observation = env.get_observation()

        if observation is None:

            stop(env)

            time.sleep(
                CONTROL_INTERVAL
            )

            continue

        target = find_tree_target(
            observation
        )

        if target is not None:

            stop(env)

            print(
                "TREE FOUND:",
                target
            )

            return target

        print(
            f"Search {i + 1}/{MAX_SEARCH_STEPS}"
        )

        env.send_action(
            "turn_right"
        )

        time.sleep(
            CONTROL_INTERVAL
        )

    stop(env)

    return None


# ============================================================
# OBSTACLE HANDLING
# ============================================================

def handle_obstacle(
        env,
        observation
):
    """
    Jump only when the player is actually blocked.

    Since the requested behavior is:

        jump + forward movement

    we use forward_jump here.

    A plain jump is NOT used for navigation.
    """

    player = observation["player"]

    collision = player.get(
        "horizontalCollision",
        False
    )

    on_ground = player.get(
        "onGround",
        True
    )

    if not collision:
        return False

    if not on_ground:
        return False

    print(
        "Obstacle detected -> FORWARD JUMP"
    )

    env.send_action(
        "forward_jump"
    )

    time.sleep(
        0.20
    )

    return True


# ============================================================
# MOVE TOWARD TREE
# ============================================================

def move_toward_tree(
        env,
        target
):
    """
    Move toward the selected log.

    The agent continuously checks the observation instead of
    blindly holding forward.
    """

    print()
    print("=" * 60)
    print("MOVING TOWARD TREE")
    print("=" * 60)

    for i in range(
            MAX_MOVE_STEPS
    ):

        observation = env.get_observation()

        if observation is None:

            stop(env)

            time.sleep(
                CONTROL_INTERVAL
            )

            continue

        # ----------------------------------------------------
        # Check that target still exists.
        # ----------------------------------------------------

        current_target = None

        for block in observation.get(
                "nearbyBlocks",
                []
        ):

            if (
                    block.get("type") in TREE_BLOCKS
                    and same_block(
                block,
                target
            )
            ):

                current_target = block
                break

        # Target disappeared.
        if current_target is None:

            print(
                "Selected log disappeared."
            )

            stop(env)

            return False

        target = current_target

        player = observation["player"]

        distance = distance_to_block(
            player,
            target
        )

        yaw = normalize_angle(
            calculate_target_yaw(
                player,
                target
            ) -
            player["yaw"]
        )

        print(
            f"Move {i + 1}: "
            f"distance={distance:.2f}, "
            f"yaw={yaw:.2f}"
        )

        # ----------------------------------------------------
        # Close enough.
        # ----------------------------------------------------

        if distance <= TREE_REACH_DISTANCE:

            stop(env)

            return True

        # ----------------------------------------------------
        # Correct horizontal direction.
        # ----------------------------------------------------

        if abs(yaw) > YAW_TOLERANCE:

            aim_at_tree(
                env,
                observation,
                target
            )

            continue

        # ----------------------------------------------------
        # Obstacle.
        # ----------------------------------------------------

        if handle_obstacle(
                env,
                observation
        ):

            continue

        # ----------------------------------------------------
        # Normal movement.
        # ----------------------------------------------------

        env.send_action(
            "forward"
        )

        time.sleep(
            CONTROL_INTERVAL
        )

    stop(env)

    print(
        "Movement timeout."
    )

    return False


# ============================================================
# MINE ONE LOG
# ============================================================

def mine_one_log(env):
    """
    Mine ONLY the block currently under the crosshair.

    This is the critical safety check.

    If the crosshair points at grass/dirt/stone/etc.,
    mining is NOT started.
    """

    start_time = time.time()

    while (
            time.time() -
            start_time <
            MAX_MINE_TIME
    ):

        observation = env.get_observation()

        if observation is None:

            stop(env)

            time.sleep(
                CONTROL_INTERVAL
            )

            continue

        target = get_crosshair_target(
            observation
        )

        # ----------------------------------------------------
        # SAFETY CHECK
        # ----------------------------------------------------

        if not is_tree_target(
                target
        ):

            print(
                "NOT MINING: "
                "crosshair is not on a log."
            )

            stop(env)

            return False

        print(
            f"Mining log: "
            f"{target['type']} "
            f"at "
            f"({target['x']}, "
            f"{target['y']}, "
            f"{target['z']})"
        )

        # ----------------------------------------------------
        # Java keeps mining continuously across client ticks.
        # ----------------------------------------------------

        env.send_action(
            "mine"
        )

        mined_position = dict(
            target
        )

        time.sleep(
            CONTROL_INTERVAL
        )

        # ----------------------------------------------------
        # Check whether the block broke.
        # ----------------------------------------------------

        after = env.get_observation()

        if after is None:
            continue

        new_target = get_crosshair_target(
            after
        )

        if (
                new_target is None
                or not same_block(
            new_target,
            mined_position
        )
        ):

            print(
                "Log broken."
            )

            stop(env)

            return True

        # ----------------------------------------------------
        # Crosshair moved onto a different block.
        # Never continue mining it automatically.
        # ----------------------------------------------------

        if (
                new_target.get("type")
                not in TREE_BLOCKS
        ):

            print(
                "Crosshair is no longer on a log."
            )

            stop(env)

            return True

    stop(env)

    print(
        "Mining timeout."
    )

    return False


# ============================================================
# TREE COLLECTION LOOP
# ============================================================

def collect_tree(env):

    previous_mined_log = None

    while True:

        observation = env.get_observation()

        if observation is None:

            stop(env)

            time.sleep(
                0.5
            )

            continue

        # ----------------------------------------------------
        # Find next log.
        # ----------------------------------------------------

        tree = find_tree_target(
            observation,
            previous_mined_log
        )

        if tree is None:

            tree = search_for_tree(
                env
            )

            if tree is None:

                print(
                    "No tree found."
                )

                time.sleep(
                    1.0
                )

                continue

        print()
        print(
            "Selected log:",
            tree
        )

        # ----------------------------------------------------
        # AIM
        # ----------------------------------------------------

        print(
            "Aiming at log..."
        )

        aimed = False

        for _ in range(
                MAX_SEARCH_STEPS
        ):

            observation = env.get_observation()

            if observation is None:
                continue

            # Make sure selected log still exists.
            current_tree = None

            for block in observation.get(
                    "nearbyBlocks",
                    []
            ):

                if (
                        block.get("type") in TREE_BLOCKS
                        and same_block(
                    block,
                    tree
                )
                ):

                    current_tree = block
                    break

            if current_tree is None:

                break

            tree = current_tree

            if aim_at_tree(
                    env,
                    observation,
                    tree
            ):

                aimed = True
                break

        # ----------------------------------------------------
        # MOVE
        # ----------------------------------------------------

        if not aimed:

            print(
                "Moving closer before final aim."
            )

        reached = move_toward_tree(
            env,
            tree
        )

        if not reached:

            stop(env)

            time.sleep(
                0.5
            )

            continue

        # ----------------------------------------------------
        # FINAL AIM
        # ----------------------------------------------------

        print(
            "Final aiming..."
        )

        aimed = False

        for _ in range(40):

            observation = env.get_observation()

            if observation is None:
                continue

            current_tree = None

            for block in observation.get(
                    "nearbyBlocks",
                    []
            ):

                if (
                        block.get("type") in TREE_BLOCKS
                        and same_block(
                    block,
                    tree
                )
                ):

                    current_tree = block
                    break

            if current_tree is None:
                break

            tree = current_tree

            if aim_at_tree(
                    env,
                    observation,
                    tree
            ):

                aimed = True
                break

        # ----------------------------------------------------
        # ABSOLUTE MINING SAFETY CHECK
        # ----------------------------------------------------

        observation = env.get_observation()

        if observation is None:

            stop(env)

            continue

        target = get_crosshair_target(
            observation
        )

        if not is_tree_target(
                target
        ):

            print()
            print(
                "SAFETY STOP:"
            )

            print(
                "Crosshair is NOT on a tree log."
            )

            print(
                "Current target:",
                target
            )

            stop(env)

            time.sleep(
                0.3
            )

            continue

        print()
        print(
            "CROSSHAIR VERIFIED:"
        )

        print(target)

        # ----------------------------------------------------
        # MINE
        # ----------------------------------------------------

        mined = mine_one_log(
            env
        )

        stop(env)

        if mined:

            previous_mined_log = dict(
                target
            )

            print()
            print(
                "Moving to next log..."
            )

            time.sleep(
                0.25
            )

            # Continue instead of returning to the old target.
            continue

        time.sleep(
            0.5
        )


# ============================================================
# MAIN
# ============================================================

def main():

    env = MinecraftEnvironment()

    print()
    print("=" * 60)
    print("HARSHCRAFT TREE AGENT")
    print("=" * 60)
    print()
    print("Minecraft must be running.")
    print("DO NOT TOUCH THE KEYBOARD.")
    print()
    print(
        "Agent controls movement, turning, jumping,"
        " looking and mining."
    )
    print()

    try:

        collect_tree(
            env
        )

    except KeyboardInterrupt:

        print()
        print(
            "Stopping agent..."
        )

        stop(env)

    except Exception as error:

        stop(env)

        print()
        print(
            "AGENT ERROR:"
        )

        print(
            repr(error)
        )

        raise

    finally:

        stop(env)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()