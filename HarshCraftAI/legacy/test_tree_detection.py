import math


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
    "minecraft:mangrove_log",
    "minecraft:cherry_log",
    "minecraft:crimson_stem",
    "minecraft:warped_stem",
}


# ============================================================
# SETTINGS
# ============================================================

DETECTION_RADIUS = 32.0

VERTICAL_PREFERENCE = 0.35


# ============================================================
# BLOCK CHECK
# ============================================================

def is_tree_block(block_type):

    if not isinstance(
            block_type,
            str
    ):
        return False

    return block_type in TREE_BLOCKS


# ============================================================
# DISTANCE
# ============================================================

def distance_to_block(
        player,
        block
):

    dx = (
            block["x"] -
            player["x"]
    )

    dy = (
            block["y"] -
            player["y"]
    )

    dz = (
            block["z"] -
            player["z"]
    )

    return math.sqrt(
        dx * dx +
        dy * dy +
        dz * dz
    )


# ============================================================
# SCORE TREE TARGET
# ============================================================

def tree_score(
        player,
        block
):
    """
    Lower score = better target.

    Distance is the main factor.

    A small vertical penalty prevents the agent from constantly
    selecting a log far above/below itself when another log is
    nearby.

    Logs above and below the player are still valid targets.
    """

    distance = distance_to_block(
        player,
        block
    )

    vertical_difference = abs(
        block["y"] -
        player["y"]
    )

    return (
            distance +
            vertical_difference *
            VERTICAL_PREFERENCE
    )


# ============================================================
# FIND NEAREST TREE
# ============================================================

def find_nearest_tree(
        observation
):

    if observation is None:
        return None

    player = observation.get(
        "player"
    )

    if player is None:
        return None

    blocks = observation.get(
        "nearbyBlocks",
        []
    )

    if not isinstance(
            blocks,
            list
    ):
        return None

    nearest = None

    best_score = float(
        "inf"
    )

    for block in blocks:

        if not isinstance(
                block,
                dict
        ):
            continue

        block_type = block.get(
            "type"
        )

        # ----------------------------------------------------
        # ONLY TREE LOGS/STEMS
        # ----------------------------------------------------

        if not is_tree_block(
                block_type
        ):
            continue

        try:

            distance = distance_to_block(
                player,
                block
            )

        except (
                KeyError,
                TypeError
        ):

            continue

        # ----------------------------------------------------
        # PYTHON DETECTION RADIUS
        # ----------------------------------------------------

        if distance > DETECTION_RADIUS:
            continue

        score = tree_score(
            player,
            block
        )

        if score < best_score:

            best_score = score

            nearest = block

    return nearest


# ============================================================
# FIND ALL TREE BLOCKS
# ============================================================

def find_tree_blocks(
        observation
):
    """
    Return all detected logs/stems inside the configured radius.

    The result is sorted from best target to worst target.
    """

    if observation is None:
        return []

    player = observation.get(
        "player"
    )

    if player is None:
        return []

    # --------------------------------------------------------
    # FIXED:
    #
    # observation.get("nearbyBlocks", [])
    #
    # --------------------------------------------------------

    blocks = observation.get(
        "nearbyBlocks",
        []
    )

    if not isinstance(
            blocks,
            list
    ):
        return []

    trees = []

    for block in blocks:

        if not isinstance(
                block,
                dict
        ):
            continue

        if not is_tree_block(
                block.get("type")
        ):
            continue

        try:

            distance = distance_to_block(
                player,
                block
            )

        except (
                KeyError,
                TypeError
        ):

            continue

        if distance <= DETECTION_RADIUS:

            trees.append(
                block
            )

    trees.sort(
        key=lambda block:
        tree_score(
            player,
            block
        )
    )

    return trees