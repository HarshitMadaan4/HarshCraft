
"""
HarshCraftAI - Navigation Evaluation

Evaluates trained PPO or DQN navigation models.

Metrics:
    - Goal success rate
    - Initial and final distance
    - Distance improvement
    - Episode reward
    - Episode length
    - Average performance

IMPORTANT:
    Evaluation does not train the model.
    Minecraft world state is not reset between episodes.
"""

import argparse
import logging
import numpy as np

from stable_baselines3 import PPO, DQN

from skills.navigation.navigation_env import NavigationEnv

from skills.navigation.navigation_config import (
    DEFAULT_GOAL,
    DEFAULT_ALGORITHM,
    MODEL_DIRECTORY,
    MAX_EPISODE_STEPS,
    ACTION_INTERVAL,
    GOAL_RADIUS,
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("HarshCraftAI.NavigationEvaluation")


# ============================================================
# MODEL LOADING
# ============================================================

def load_model(algorithm, model_path):

    algorithm = algorithm.lower()

    if algorithm == "ppo":
        return PPO.load(str(model_path))

    if algorithm == "dqn":
        return DQN.load(str(model_path))

    raise ValueError(
        "Algorithm must be either ppo or dqn."
    )


# ============================================================
# SINGLE EPISODE EVALUATION
# ============================================================

def evaluate_episode(
        model,
        env,
        deterministic=True,
        max_steps=MAX_EPISODE_STEPS,
):

    observation, reset_info = env.reset()

    initial_distance = float(
        reset_info["distance_to_goal"]
    )

    total_reward = 0.0
    success = False
    terminated = False
    truncated = False

    steps = 0
    final_distance = initial_distance

    try:

        for steps in range(1, max_steps + 1):

            action, _ = model.predict(
                observation,
                deterministic=deterministic,
            )

            (
                observation,
                reward,
                terminated,
                truncated,
                info,
            ) = env.step(int(np.asarray(action).item()))

            total_reward += float(reward)

            final_distance = float(
                info["distance_to_goal"]
            )

            success = bool(info["success"])

            if terminated or truncated:
                break

    finally:

        # Release movement after evaluation.
        env.minecraft.send_action("noop")

    distance_improvement = (
            initial_distance - final_distance
    )

    return {
        "steps": steps,
        "initial_distance": initial_distance,
        "final_distance": final_distance,
        "distance_improvement": distance_improvement,
        "total_reward": total_reward,
        "success": success,
        "terminated": terminated,
        "truncated": truncated,
    }


# ============================================================
# MULTIPLE EPISODES
# ============================================================

def evaluate_model(
        model,
        env,
        episodes,
        deterministic=True,
        max_steps=MAX_EPISODE_STEPS,
):

    results = []

    for episode in range(1, episodes + 1):

        logger.info(
            "Starting evaluation episode %s/%s",
            episode,
            episodes,
        )

        result = evaluate_episode(
            model=model,
            env=env,
            deterministic=deterministic,
            max_steps=max_steps,
        )

        results.append(result)

        logger.info(
            "EPISODE %s | success=%s | steps=%s | "
            "initial_distance=%.2f | final_distance=%.2f | "
            "improvement=%.2f | reward=%.3f",
            episode,
            result["success"],
            result["steps"],
            result["initial_distance"],
            result["final_distance"],
            result["distance_improvement"],
            result["total_reward"],
        )

    return results


# ============================================================
# SUMMARY
# ============================================================

def print_summary(results):

    if not results:
        logger.warning("No evaluation results available.")
        return

    success_rate = np.mean([
        result["success"]
        for result in results
    ]) * 100.0

    average_reward = np.mean([
        result["total_reward"]
        for result in results
    ])

    average_steps = np.mean([
        result["steps"]
        for result in results
    ])

    average_initial_distance = np.mean([
        result["initial_distance"]
        for result in results
    ])

    average_final_distance = np.mean([
        result["final_distance"]
        for result in results
    ])

    average_improvement = np.mean([
        result["distance_improvement"]
        for result in results
    ])

    logger.info("")
    logger.info("=" * 60)
    logger.info("NAVIGATION EVALUATION SUMMARY")
    logger.info("=" * 60)

    logger.info(
        "Episodes evaluated: %s",
        len(results),
    )

    logger.info(
        "Success rate: %.2f%%",
        success_rate,
    )

    logger.info(
        "Average reward: %.3f",
        average_reward,
    )

    logger.info(
        "Average episode steps: %.2f",
        average_steps,
    )

    logger.info(
        "Average initial distance: %.2f",
        average_initial_distance,
    )

    logger.info(
        "Average final distance: %.2f",
        average_final_distance,
    )

    logger.info(
        "Average distance improvement: %.2f",
        average_improvement,
    )

    logger.info("=" * 60)

    print("\nNavigation evaluation results")
    print(f"Success rate: {success_rate:.2f}%")
    print(f"Average reward: {average_reward:.3f}")
    print(f"Average steps: {average_steps:.2f}")
    print(f"Average distance improvement: {average_improvement:.2f}")


# ============================================================
# COMMAND LINE
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Evaluate a trained Minecraft navigation model."
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to the trained model ZIP file.",
    )

    parser.add_argument(
        "--algorithm",
        choices=["ppo", "dqn"],
        default=DEFAULT_ALGORITHM,
    )

    parser.add_argument(
        "--episodes",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--goal",
        type=float,
        nargs=3,
        default=DEFAULT_GOAL,
        metavar=("X", "Y", "Z"),
    )

    parser.add_argument(
        "--max-steps",
        type=int,
        default=MAX_EPISODE_STEPS,
    )

    parser.add_argument(
        "--action-interval",
        type=float,
        default=ACTION_INTERVAL,
    )

    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Use stochastic model predictions.",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_arguments()

    if args.episodes <= 0:
        raise ValueError("Episodes must be positive.")

    if args.max_steps <= 0:
        raise ValueError("Maximum steps must be positive.")

    if args.action_interval <= 0:
        raise ValueError("Action interval must be positive.")

    model_path = (
        args.model
        if args.model
        else MODEL_DIRECTORY
             / f"navigation_{args.algorithm}_final.zip"
    )

    logger.info("Loading model: %s", model_path)

    model = load_model(
        args.algorithm,
        model_path,
    )

    env = NavigationEnv(
        goal=args.goal,
        max_episode_steps=args.max_steps,
        action_interval=args.action_interval,
    )

    try:

        # Check compatibility before evaluation.
        if model.observation_space != env.observation_space:
            raise ValueError(
                "Model observation space does not match NavigationEnv."
            )

        if model.action_space != env.action_space:
            raise ValueError(
                "Model action space does not match NavigationEnv."
            )

        results = evaluate_model(
            model=model,
            env=env,
            episodes=args.episodes,
            deterministic=not args.stochastic,
            max_steps=args.max_steps,
        )

        print_summary(results)

    finally:

        env.close()


if __name__ == "__main__":
    main()
