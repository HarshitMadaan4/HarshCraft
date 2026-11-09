# HarshCraft - voice/NLP controlled Minecraft agent

Say or type: *"get a stone pickaxe"*, *"kill the zombies"*, *"build a house"*, *"go to 100 64 -200"*, *"get 5 iron ingots and then craft an iron sword"*, *"survive for 10 minutes"*, *"stop"*.

## Layout
- `HarshCraft/` - Fabric mod (Minecraft 1.21.1, Mojang mappings). New AI bridge in `src/client/.../ai/`.
- `HarshCraftAI/` - Python bot.
  - `harshcraft_ai/nlp.py`, `llm.py` (optional), `voice.py` - speech/text -> tasks
  - `planner.py` - tech-tree planner (log -> planks -> sticks -> table -> pickaxe -> ... -> smelting)
  - `skills/` - navigate, mine, craft(+smelt), build, combat, survive
  - `pathfinding.py` - 3-D A* (walk/jump/drop/swim/dig, avoids lava), `motor.py` - body, reflexes, stuck recovery
  - `rl/` - combat + survival PPO policies, fast simulators, trainer. Trained models are in `models/`.
  - `sim/mock_server.py` + `tests/` - fake Minecraft and 24 tests.

## Run
1. Build/run the mod: `cd HarshCraft && ./gradlew runClient`, open a **singleplayer world with cheats allowed**.
   Press **F3+P** once so the game does not pause when the window loses focus (otherwise steps time out).
2. `cd HarshCraftAI && pip install -r requirements.txt`
3. `python run_bot.py` (typed), `python run_bot.py --voice [--wake "bot"] [--tts]`, `python run_bot.py --llm` (needs `ANTHROPIC_API_KEY`).
   Voice needs `faster-whisper sounddevice` (offline) or `SpeechRecognition pyaudio` (online).
4. Retrain RL: `python -m harshcraft_ai.rl.train all` (about 4 minutes on one CPU core).
5. Tests: `python -m pytest tests -q`

## Architecture
Java executes one action for N ticks and returns the new observation (synchronous, no overshoot). Movement/look are injected once per tick in the keyboard mixin; mining/attack/place/clicks run in the end-of-tick handler (the old double application is gone). Observation = 21x10x21 voxel window + inventory + entities + container slots; `/scan` finds resource blocks within 24 blocks.
Deterministic skills do navigation, mining, crafting, building. RL is used where tactics matter: **combat policy** (8 tactical actions) and **survival arbiter** (continue/fight/flee/eat/shelter). If a model file is missing the bot falls back to rule policies.

## Honest status
- Python: 24 tests pass against the mock server (movement, jumping, digging, collecting, crafting 2x2/3x3, smelting, building walls/houses, combat, eating, drowning reflex, full "stone pickaxe" chain).
- Java: passes a javac syntax/type check against hand-written API stubs only. It has NOT been built against real Minecraft here (no Gradle/Mojang downloads possible). Calls most likely to need a small fix on first build: `MultiPlayerGameMode.handleInventoryMouseClick/useItemOn/startDestroyBlock`, `Direction.getNearest`, `Player.pick`, `LocalPlayer.respawn`.
- RL results are in simulators (approximate vanilla constants), not in real Minecraft. Combat sim: PPO win rate 0.98 vs rule 0.46 vs random 0.41. Survival sim (harsh): PPO return 2.04 vs rule 1.03 vs random -8.0; only 26% of episodes survive the full period. Real-world transfer is unverified.
- Not implemented: farming, villager trading, nether/end navigation, bows, bed/sleep, tall-tree climbing (pillar_up exists but mining does not use it automatically). `/scan` sees through rock (X-ray); set `XRAY=False` in `skills/mine.py` to restrict to exposed blocks.
