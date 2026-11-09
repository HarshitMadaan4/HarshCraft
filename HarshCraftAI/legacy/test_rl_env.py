
import argparse
import math

from harshcraft_rl_env import HarshCraftRLEnv, ACTIONS


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_GOAL = (100.0, 64.0, 100.0)
DEFAULT_TEST_STEPS = 30


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Test the HarshCraftAI Minecraft RL environment."
    )

    parser.add_argument(
        "--mode",
        choices=["random"] + ACTIONS,
        default="random",
        help=(
            "Test mode. 'random' preserves the original random-action "
            "test. Other choices repeatedly execute one selected action."
        )
    )

    parser.add_argument(
        "--steps",
        type=int,
        default=DEFAULT_TEST_STEPS,
        help="Number of test steps."
    )

    parser.add_argument(
        "--goal",
        type=float,
        nargs=3,
        default=DEFAULT_GOAL,
        metavar=("X", "Y", "Z"),
        help="Target coordinates."
    )

    return parser.parse_args()


# ============================================================
# POSITION HELPERS
# ============================================================

def get_position(observation):

    if observation is None or len(observation) < 3:
        return None

    return (
        float(observation[0]),
        float(observation[1]),
        float(observation[2])
    )


def calculate_displacement(start, end):

    if start is None or end is None:
        return None

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]

    horizontal = math.sqrt(
        dx * dx + dz * dz
    )

    total = math.sqrt(
        dx * dx + dy * dy + dz * dz
    )

    return {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "horizontal": horizontal,
        "total": total
    }


# ============================================================
# MAIN TEST
# ============================================================

def main():

    args = parse_arguments()

    if args.steps <= 0:
        raise ValueError("--steps must be greater than zero.")

    env = HarshCraftRLEnv(
        goal=tuple(args.goal),
        max_episode_steps=max(args.steps, 100)
    )

    start_position = None
    final_position = None

    try:

        # ----------------------------------------------------
        # RESET
        # ----------------------------------------------------

        observation, info = env.reset()

        start_position = get_position(observation)
        final_position = start_position

        print("\n========================================")
        print("HARSHCRAFTAI RL ENVIRONMENT TEST")
        print("========================================")

        print("\nTEST CONFIGURATION")
        print("Mode:", args.mode)
        print("Steps:", args.steps)
        print("Goal:", tuple(args.goal))

        print("\nINITIAL OBSERVATION")
        print(observation)

        print("\nRESET INFO")
        print(info)

        print("\nINITIAL PLAYER POSITION")
        print(start_position)

        # ----------------------------------------------------
        # ACTION LOOP
        # ----------------------------------------------------

        print("\nSTARTING ACTION TEST\n")

        fixed_action = None

        if args.mode != "random":
            fixed_action = ACTIONS.index(args.mode)

        for step in range(args.steps):

            # ------------------------------------------------
            # Select action
            # ------------------------------------------------

            if args.mode == "random":

                action = env.action_space.sample()

            else:

                action = fixed_action

            action_name = ACTIONS[action]

            # ------------------------------------------------
            # Execute environment step
            # ------------------------------------------------

            (
                observation,
                reward,
                terminated,
                truncated,
                info
            ) = env.step(action)

            final_position = get_position(observation)

            # ------------------------------------------------
            # Print diagnostics
            # ------------------------------------------------

            print(
                f"Step={step + 1:03d} | "
                f"Action={action_name:12s} | "
                f"Reward={reward:8.3f} | "
                f"Distance={info['distance_to_goal']:8.2f} | "
                f"Position={final_position}"
            )

            if terminated or truncated:

                print("\nEPISODE FINISHED")
                print(info)

                break

        # ----------------------------------------------------
        # MOVEMENT SUMMARY
        # ----------------------------------------------------

        displacement = calculate_displacement(
            start_position,
            final_position
        )

        print("\n========================================")
        print("MOVEMENT TEST SUMMARY")
        print("========================================")

        print("Start position:", start_position)
        print("Final position:", final_position)

        if displacement is not None:

            print(
                "X displacement:",
                round(displacement["dx"], 4)
            )

            print(
                "Y displacement:",
                round(displacement["dy"], 4)
            )

            print(
                "Z displacement:",
                round(displacement["dz"], 4)
            )

            print(
                "Horizontal displacement:",
                round(displacement["horizontal"], 4)
            )

            print(
                "Total displacement:",
                round(displacement["total"], 4)
            )

            if displacement["total"] > 0.01:

                print("\nPlayer position changed during the test.")

            else:

                print(
                    "\nWARNING: No significant player displacement detected."
                )

                print(
                    "Check the Java movement Mixin, action timeout, "
                    "and Minecraft action execution."
                )

        else:

            print("Could not calculate player displacement.")

    except KeyboardInterrupt:

        print("\nTest interrupted by user.")

    except Exception as e:

        print("\nTEST ERROR:", e)

        raise

    finally:

        print("\nStopping AI movement and closing environment...")

        env.close()

        print("Environment closed.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
