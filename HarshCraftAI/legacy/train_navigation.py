
"""
HarshCraftAI - Navigation Training
===================================

Algorithms:
    PPO - Proximal Policy Optimization
    DQN - Deep Q-Network

Uses:
    harshcraft_rl_env.py
    minecraft_env.py

Examples:
    python train_navigation.py
    python train_navigation.py --algorithm ppo
    python train_navigation.py --algorithm dqn
    python train_navigation.py --algorithm dqn --timesteps 100000

IMPORTANT:
    The Minecraft world is not reset between episodes.
"""

import argparse
import logging
from pathlib import Path

from stable_baselines3 import PPO, DQN
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import set_random_seed

from harshcraft_rl_env import HarshCraftRLEnv


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_ALGORITHM = "ppo"

DEFAULT_TIMESTEPS = 50000

DEFAULT_SEED = 42

DEFAULT_GOAL = (100.0, 64.0, 100.0)

MAX_EPISODE_STEPS = 500

ACTION_INTERVAL = 0.8

MODEL_DIR = Path("models")

CHECKPOINT_DIR = MODEL_DIR / "checkpoints"

LOG_DIR = Path("logs")

TENSORBOARD_DIR = Path("runs/harshcraft_navigation")


# ============================================================
# LOGGING
# ============================================================

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),

        logging.FileHandler(
            LOG_DIR / "train_navigation.log",
            encoding="utf-8"
        )
    ],
    force=True
)

logger = logging.getLogger(
    "HarshCraftNavigation"
)


# ============================================================
# ARGUMENT PARSER
# ============================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="HarshCraftAI RL Navigation Trainer"
    )

    parser.add_argument(
        "--algorithm",
        choices=["ppo", "dqn"],
        default=DEFAULT_ALGORITHM
    )

    parser.add_argument(
        "--timesteps",
        type=int,
        default=DEFAULT_TIMESTEPS
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED
    )

    parser.add_argument(
        "--goal",
        type=float,
        nargs=3,
        default=DEFAULT_GOAL,
        metavar=("X", "Y", "Z")
    )

    parser.add_argument(
        "--max-episode-steps",
        type=int,
        default=MAX_EPISODE_STEPS
    )

    parser.add_argument(
        "--action-interval",
        type=float,
        default=ACTION_INTERVAL
    )

    parser.add_argument(
        "--checkpoint-freq",
        type=int,
        default=5000
    )

    parser.add_argument(
        "--resume",
        type=str,
        default=None
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto"
    )

    return parser.parse_args()


# ============================================================
# ENVIRONMENT CREATION
# ============================================================

def create_environment(args):

    logger.info(
        "Creating HarshCraftRL environment..."
    )

    env = HarshCraftRLEnv(

        goal=tuple(args.goal),

        max_episode_steps=args.max_episode_steps,

        action_interval=args.action_interval
    )

    env = Monitor(
        env,
        filename=str(
            LOG_DIR / "navigation_monitor.csv"
        )
    )

    logger.info(
        "Observation space: %s",
        env.observation_space
    )

    logger.info(
        "Action space: %s",
        env.action_space
    )

    return env


# ============================================================
# PPO MODEL
# ============================================================

def create_ppo_model(env, args):

    logger.info(
        "Initializing PPO..."
    )

    model = PPO(

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
                "vf": [128, 128]
            }
        },

        tensorboard_log=str(
            TENSORBOARD_DIR
        ),

        verbose=1,

        seed=args.seed,

        device=args.device
    )

    return model


# ============================================================
# DQN MODEL
# ============================================================

def create_dqn_model(env, args):

    logger.info(
        "Initializing DQN..."
    )

    model = DQN(

        policy="MlpPolicy",

        env=env,

        learning_rate=1e-4,

        buffer_size=100000,

        learning_starts=2000,

        batch_size=64,

        tau=1.0,

        gamma=0.99,

        train_freq=4,

        gradient_steps=1,

        target_update_interval=1000,

        exploration_fraction=0.30,

        exploration_initial_eps=1.0,

        exploration_final_eps=0.05,

        policy_kwargs={
            "net_arch": [128, 128]
        },

        tensorboard_log=str(
            TENSORBOARD_DIR
        ),

        verbose=1,

        seed=args.seed,

        device=args.device
    )

    return model


# ============================================================
# MODEL LOADING
# ============================================================

def load_model(args, env):

    model_path = Path(args.resume)

    if not model_path.is_file():

        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    logger.info(
        "Loading existing model: %s",
        model_path
    )

    if args.algorithm == "ppo":

        model = PPO.load(
            str(model_path),
            env=env,
            device=args.device,
            tensorboard_log=str(TENSORBOARD_DIR)
        )

    else:

        model = DQN.load(
            str(model_path),
            env=env,
            device=args.device,
            tensorboard_log=str(TENSORBOARD_DIR)
        )

    return model


# ============================================================
# TRAINING FUNCTION
# ============================================================

def train(args):

    if args.timesteps <= 0:
        raise ValueError("Timesteps must be positive.")

    if args.checkpoint_freq <= 0:
        raise ValueError("Checkpoint frequency must be positive.")

    if args.max_episode_steps <= 0:
        raise ValueError("Maximum episode steps must be positive.")

    if args.action_interval <= 0:
        raise ValueError("Action interval must be positive.")

    # --------------------------------------------------------
    # Create directories
    # --------------------------------------------------------

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    CHECKPOINT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    TENSORBOARD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    set_random_seed(
        args.seed
    )

    logger.info("========================================")

    logger.info(
        "HARSHCRAFTAI NAVIGATION TRAINING"
    )

    logger.info(
        "Algorithm: %s",
        args.algorithm.upper()
    )

    logger.info(
        "Timesteps: %s",
        args.timesteps
    )

    logger.info(
        "Goal: %s",
        tuple(args.goal)
    )

    logger.info(
        "Seed: %s",
        args.seed
    )

    logger.info("========================================")

    # --------------------------------------------------------
    # Create environment
    # --------------------------------------------------------

    env = create_environment(args)

    try:

        # ----------------------------------------------------
        # Create or load model
        # ----------------------------------------------------

        if args.resume:

            model = load_model(
                args,
                env
            )

        elif args.algorithm == "ppo":

            model = create_ppo_model(
                env,
                args
            )

        else:

            model = create_dqn_model(
                env,
                args
            )

        # ----------------------------------------------------
        # Checkpoint callback
        # ----------------------------------------------------

        checkpoint_callback = CheckpointCallback(

            save_freq=args.checkpoint_freq,

            save_path=str(
                CHECKPOINT_DIR
            ),

            name_prefix=(
                f"harshcraft_{args.algorithm}_navigation"
            ),

            save_replay_buffer=(
                    args.algorithm == "dqn"
            ),

            save_vecnormalize=False
        )

        # ----------------------------------------------------
        # Start training
        # ----------------------------------------------------

        logger.info(
            "Starting RL training..."
        )

        model.learn(

            total_timesteps=args.timesteps,

            callback=checkpoint_callback,

            log_interval=10,

            tb_log_name=(
                f"harshcraft_{args.algorithm}_navigation"
            ),

            reset_num_timesteps=(
                    args.resume is None
            ),

            progress_bar=False
        )

        # ----------------------------------------------------
        # Save final model
        # ----------------------------------------------------

        final_model_path = (
                MODEL_DIR /
                f"harshcraft_{args.algorithm}_navigation_final"
        )

        model.save(
            str(final_model_path)
        )

        logger.info(
            "Final model saved: %s.zip",
            final_model_path
        )

        # ----------------------------------------------------
        # Save DQN replay buffer
        # ----------------------------------------------------

        if args.algorithm == "dqn":

            replay_path = (
                    MODEL_DIR /
                    "harshcraft_dqn_navigation_replay_buffer"
            )

            model.save_replay_buffer(
                str(replay_path)
            )

            logger.info(
                "DQN replay buffer saved."
            )

        logger.info(
            "Training completed successfully."
        )

    finally:

        logger.info(
            "Closing Minecraft environment..."
        )

        env.close()


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
            "Training failed."
        )

        raise


if __name__ == "__main__":

    main()
