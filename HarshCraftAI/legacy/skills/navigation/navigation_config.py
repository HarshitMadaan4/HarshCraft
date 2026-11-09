
"""
HarshCraftAI - Navigation Configuration

Central configuration for the navigation reinforcement
learning skill.
"""

from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIRECTORY = PROJECT_ROOT / "models" / "navigation"
LOG_DIRECTORY = PROJECT_ROOT / "logs"

MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)


# ============================================================
# MINECRAFT CONNECTION
# ============================================================

MINECRAFT_HOST = "127.0.0.1"
MINECRAFT_PORT = 5000

MINECRAFT_BASE_URL = (
    f"http://{MINECRAFT_HOST}:{MINECRAFT_PORT}"
)


# ============================================================
# NAVIGATION ACTIONS
# ============================================================

NAVIGATION_ACTIONS = [
    "noop",
    "forward",
    "backward",
    "left",
    "right",
    "turn_left",
    "turn_right",
    "jump",
    "forward_jump",
]

NUMBER_OF_ACTIONS = len(NAVIGATION_ACTIONS)


# ============================================================
# OBSERVATION CONFIGURATION
# ============================================================

OBSERVATION_SIZE = 13

HORIZONTAL_DISTANCE_SCALE = 100.0
VERTICAL_DISTANCE_SCALE = 20.0
MOVEMENT_SCALE = 1.0

PLAYER_MAX_HEALTH = 20.0
PLAYER_MAX_FOOD = 20.0


# ============================================================
# NAVIGATION GOAL
# ============================================================

DEFAULT_GOAL = (100.0, 64.0, 100.0)

DEFAULT_GOAL_RADIUS = 2.0


# ============================================================
# EPISODE CONFIGURATION
# ============================================================

ACTION_INTERVAL = 0.8

MAX_EPISODE_STEPS = 500

MAX_EPISODE_SECONDS = (
        ACTION_INTERVAL * MAX_EPISODE_STEPS
)


# ============================================================
# REWARD CONFIGURATION
# ============================================================

STEP_PENALTY = 0.01

PROGRESS_REWARD_SCALE = 1.0

HEALTH_CHANGE_REWARD_SCALE = 0.5

COLLISION_PENALTY = 0.05

STUCK_MOVEMENT_THRESHOLD = 0.03

STUCK_PENALTY_AFTER = 3

STUCK_PENALTY = 0.05

SUCCESS_REWARD = 10.0

DEATH_PENALTY = 10.0


# ============================================================
# REINFORCEMENT LEARNING CONFIGURATION
# ============================================================

DEFAULT_ALGORITHM = "ppo"

SUPPORTED_ALGORITHMS = [
    "ppo",
    "dqn",
]

DEFAULT_TOTAL_TIMESTEPS = 50_000

DEFAULT_RANDOM_SEED = 42


# ============================================================
# PPO CONFIGURATION
# ============================================================

PPO_LEARNING_RATE = 3e-4

PPO_N_STEPS = 256

PPO_BATCH_SIZE = 64

PPO_EPOCHS = 10

PPO_GAMMA = 0.99

PPO_GAE_LAMBDA = 0.95

PPO_CLIP_RANGE = 0.2

PPO_ENTROPY_COEFFICIENT = 0.01


# ============================================================
# DQN CONFIGURATION
# ============================================================

DQN_LEARNING_RATE = 1e-4

DQN_BUFFER_SIZE = 100_000

DQN_LEARNING_STARTS = 2_000

DQN_BATCH_SIZE = 64

DQN_GAMMA = 0.99

DQN_TRAIN_FREQUENCY = 4

DQN_EXPLORATION_FRACTION = 0.30

DQN_EXPLORATION_INITIAL_EPSILON = 1.0

DQN_EXPLORATION_FINAL_EPSILON = 0.05
