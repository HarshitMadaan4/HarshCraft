"""Central configuration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

HOST, PORT = "127.0.0.1", 5000
BASE_URL = f"http://{HOST}:{PORT}"

WALK_TICKS = 4            # ticks per movement step (0.2 blocks/tick walking)
COMBAT_TICKS = 4          # ticks per combat decision (matches the combat simulator: 0.2 s)
REACH = 4.2               # blocks, eye -> block centre, for mining / placing
ATTACK_REACH = 2.9
SCAN_RADIUS, SCAN_VERTICAL = 24, 12

# reflex thresholds
AIR_PANIC = 120           # ticks of air left (max 300) -> swim up
LOW_HEALTH = 8.0
HUNGRY = 14               # eat when food <= this and food available
STARVING = 6
THREAT_RADIUS = 7.0
MAX_STEPS_PER_SKILL = 4000
