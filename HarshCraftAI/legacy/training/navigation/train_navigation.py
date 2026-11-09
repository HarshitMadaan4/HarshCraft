
"""
HarshCraftAI - Navigation Training

Trains a goal-directed Minecraft navigation policy using
Stable-Baselines3 PPO or DQN.

Uses:
    - NavigationEnv
    - Navigation configuration
    - Navigation-specific observations
    - Navigation-specific rewards

Run from the HarshCraftAI project root:

    python -m training.navigation.train_navigation --algorithm ppo

    python -m training.navigation.train_navigation --algorithm dqn
"""

import argparse
import logging
from pathlib import Path

from stable_baselines3 import PPO, DQN
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed

from skills.navigation.navigation_env import NavigationEnv

from skills.navigation.navigation_config import (
    DEFAULT_ALGORITHM,
    DEFAULT_TOTAL_TIMESTEPS,
    DEFAULT_RANDOM_SEED,
    DEFAULT_GOAL,
    MAX_EPISODE_STEPS,
    ACTION_INTERVAL,
    MODEL_DIRECTORY,
    LOG_DIRECTORY,
)


# ============================================================
# PATHS
# ============================================================

CHECKPOINT_DIRECTORY = MODEL_DIRECTORY / "checkpoints"
TENSORBOARD_DIRECTORY = LOG_DIRECTORY / "navigation_tensorboard"

CHECKPOINT_DIRECTORY.mkdir(parents=True, exist_ok=True)
TENSORBOARD_DIRECTORY.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("HarshCraftAI.NavigationTraining")
logger.setLevel(logging.INFO)

if not logger.handlers:

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        LOG_DIRECTORY / "navigation_training.log",
        encoding="utf-8",
        )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


# ============================================================
# ENVIRONMENT
# ============================================================

def create_environment(args):
    """Create the dedicated navigation Gymnasium environment."""

    env = NavigationEnv(
        goal=args.goal,
        max_episode_steps=args.max_episode_steps,
        action_interval=args.action_interval,
    )

    return Monitor(env)


# ============================================================
# PPO MODEL
# ============================================================

def create_ppo_model(env, args):

    logger.info("Creating PPO navigation model.")

    return PPO(
        policy="MlpPolicy",
        env=env,

        learning_rate=3e-4,

        n_steps=256,
        batch_size=64,
        n_epochs=10,

        gamma=0.99,
        gae_lambda=0.95,

        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,

        max_grad_norm=0.5,

        policy_kwargs={
            "net_arch": {
                "pi": [128, 128],
                "vf": [128, 128],
            }
        },

        tensorboard_log=str(TENSORBOARD_DIRECTORY),

        seed=args.seed,
        device=args.device,

        verbose=1,
    )


# ============================================================
# DQN MODEL
# ============================================================

def create_dqn_model(env, args):

    logger.info("Creating DQN navigation model.")

    return DQN(
        policy="MlpPolicy",
        env=env,

        learning_rate=1e-4,

        buffer_size=100_000,
        learning_starts=2_000,
        batch_size=64,

        tau=1.0,
        gamma=0.99,

        train_freq=4,
        gradient_steps=1,

        target_update_interval=1_000,

        exploration_fraction=0.30,
        exploration_initial_eps=1.0,
        exploration_final_eps=0.05,

        policy_kwargs={
            "net_arch": [128, 128],
        },

        tensorboard_log=str(TENSORBOARD_DIRECTORY),

        seed=args.seed,
        device=args.device,

        verbose=1,
    )


# ============================================================
# MODEL LOADING
# ============================================================

def load_model(algorithm, model_path, env, args):

    logger.info(
        "Loading existing %s model: %s",
        algorithm.upper(),
        model_path,
    )

    if algorithm == "ppo":

        model = PPO.load(
            str(model_path),
            env=env,
            device=args.device,
        )

    else:

        model = DQN.load(
            str(model_path),
            env=env,
            device=args.device,
        )

    return model


# ============================================================
# ARGUMENTS
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Train the HarshCraftAI navigation skill."
    )

    parser.add_argument(
        "--algorithm",
        choices=["ppo", "dqn"],
        default=DEFAULT_ALGORITHM,
        help="Reinforcement learning algorithm.",
    )

    parser.add_argument(
        "--timesteps",
        type=int,
        default=DEFAULT_TOTAL_TIMESTEPS,
        help="Number of environment training steps.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
    )

    parser.add_argument(
        "--goal",
        type=float,
        nargs=3,
        default=DEFAULT_GOAL,
        metavar=("X", "Y", "Z"),
    )

    parser.add_argument(
        "--max-episode-steps",
        type=int,
        default=MAX_EPISODE_STEPS,
    )

    parser.add_argument(
        "--action-interval",
        type=float,
        default=ACTION_INTERVAL,
    )

    parser.add_argument(
        "--checkpoint-freq",
        type=int,
        default=5_000,
    )

    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Optional existing model ZIP path.",
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
    )

    return parser.parse_args()


# ============================================================
# VALIDATION
# ============================================================

def validate_arguments(args):

    if args.timesteps <= 0:
        raise ValueError("timesteps must be positive.")

    if args.max_episode_steps <= 0:
        raise ValueError("max_episode_steps must be positive.")

    if args.action_interval <= 0:
        raise ValueError("action_interval must be positive.")

    if args.checkpoint_freq <= 0:
        raise ValueError("checkpoint-freq must be positive.")

    if len(args.goal) != 3:
        raise ValueError("Goal must contain X, Y and Z.")


# ============================================================
# TRAINING
# ============================================================

def train(args):

    validate_arguments(args)

    set_random_seed(args.seed)

    logger.info("=" * 60)
    logger.info("HARSHCRAFTAI NAVIGATION TRAINING")
    logger.info("=" * 60)

    logger.info("Algorithm: %s", args.algorithm.upper())
    logger.info("Timesteps: %s", args.timesteps)
    logger.info("Goal: %s", args.goal)
    logger.info("Seed: %s", args.seed)
    logger.info("Device: %s", args.device)

    env = None
    model = None

    try:

        # ----------------------------------------------------
        # CREATE ENVIRONMENT
        # ----------------------------------------------------

        env = create_environment(args)

        # ----------------------------------------------------
        # LOAD OR CREATE MODEL
        # ----------------------------------------------------

        if args.resume:

            model_path = Path(args.resume)

            if not model_path.exists():
                raise FileNotFoundError(
                    f"Resume model not found: {model_path}"
                )

            model = load_model(
                args.algorithm,
                model_path,
                env,
                args,
            )

            # A checkpoint trained with a different observation
            # meaning or action space must not be reused.
            if model.observation_space != env.observation_space:
                raise ValueError(
                    "Checkpoint observation space does not match "
                    "the current NavigationEnv."
                )

            if model.action_space != env.action_space:
                raise ValueError(
                    "Checkpoint action space does not match "
                    "the current NavigationEnv."
                )

        elif args.algorithm == "ppo":

            model = create_ppo_model(env, args)

        else:

            model = create_dqn_model(env, args)

        # ----------------------------------------------------
        # CHECKPOINT CALLBACK
        # ----------------------------------------------------

        checkpoint_callback = CheckpointCallback(
            save_freq=args.checkpoint_freq,
            save_path=str(CHECKPOINT_DIRECTORY),
            name_prefix=f"navigation_{args.algorithm}",
            save_replay_buffer=(args.algorithm == "dqn"),
            save_vecnormalize=False,
        )

        # ----------------------------------------------------
        # TRAIN
        # ----------------------------------------------------

        logger.info("Starting navigation training.")

        model.learn(
            total_timesteps=args.timesteps,
            callback=checkpoint_callback,
            tb_log_name=f"navigation_{args.algorithm}",
            reset_num_timesteps=(args.resume is None),
            progress_bar=True,
        )

        # ----------------------------------------------------
        # SAVE FINAL MODEL
        # ----------------------------------------------------

        final_model_path = (
                MODEL_DIRECTORY
                / f"navigation_{args.algorithm}_final"
        )

        model.save(str(final_model_path))

        logger.info(
            "Final model saved: %s.zip",
            final_model_path,
        )

        # Save DQN replay buffer separately.
        if args.algorithm == "dqn":

            replay_buffer_path = (
                    MODEL_DIRECTORY
                    / "navigation_dqn_replay_buffer"
            )

            model.save_replay_buffer(
                str(replay_buffer_path)
            )

            logger.info(
                "DQN replay buffer saved: %s.pkl",
                replay_buffer_path,
            )

        logger.info("Navigation training completed.")

    finally:

        if env is not None:
            env.close()

        logger.info("Navigation training environment closed.")


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_arguments()

    try:

        train(args)

    except KeyboardInterrupt:

        logger.warning(
            "Training interrupted by user."
        )

    except Exception:

        logger.exception(
            "Navigation training failed."
        )

        raise


if __name__ == "__main__":
    main()
