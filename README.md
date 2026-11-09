# HarshCraftAI

### A voice- and natural-language-controlled Minecraft automation bot

HarshCraftAI is a Python-powered Minecraft bot connected to a custom
Fabric mod. It lets a player issue typed or spoken instructions such as:

-   `get a stone pickaxe`
-   `kill the zombies`
-   `build a house`
-   `go to 100 64 -200`
-   `get 5 iron ingots and then craft an iron sword`
-   `survive for 10 minutes`
-   `stop`

The Python side interprets commands, plans task sequences, and
coordinates gameplay skills. The Fabric mod exposes Minecraft state and
executes the bot's actions through a local HTTP interface.

> **Project status:** This repository contains a working prototype with
> command parsing, a task/recipe planner, gameplay skills, a Minecraft
> bridge, mock-server tests, and simulator-based reinforcement-learning
> policies. Some capabilities are experimental; real-world behavior and
> transfer from the RL simulators are not guaranteed. See [Current
> status and limitations](#current-status-and-limitations).

------------------------------------------------------------------------

## Contents

-   [Features](#features)
-   [Architecture](#architecture)
-   [Repository layout](#repository-layout)
-   [Requirements](#requirements)
-   [Setup](#setup)
-   [Run the bot](#run-the-bot)
-   [Example commands](#example-commands)
-   [Reinforcement learning](#reinforcement-learning)
-   [Run tests](#run-tests)
-   [Configuration](#configuration)
-   [Current status and limitations](#current-status-and-limitations)
-   [Troubleshooting](#troubleshooting)
-   [Safety and usage notes](#safety-and-usage-notes)
-   [Contributing](#contributing)
-   [License](#license)

## Features

### Natural-language command input

-   Rule-based, offline command parsing converts supported phrases into
    structured tasks.
-   Optional LLM-based parsing can handle commands the rule parser does
    not recognize. It uses the Anthropic Messages API and requires an
    API key.
-   Commands can be entered through the terminal or spoken through an
    optional speech-recognition backend.
-   Optional text-to-speech can speak bot replies.

### Task planning

The planner expands item-acquisition goals into prerequisite tasks using
the project's item, recipe, smelting, and tool knowledge. For example, a
request for a tool can be expanded into gathering logs, making planks
and sticks, crafting a table, and acquiring the required materials.

### Gameplay skills

The Python skill modules cover:

-   **Navigation:** movement toward goals using 3D pathfinding and a
    movement controller.
-   **Mining and gathering:** locating blocks, checking tool
    requirements, mining, and collecting drops.
-   **Crafting and smelting:** using the inventory crafting grid and
    crafting-table/furnace interfaces.
-   **Building:** placing blocks from simple blueprints such as walls,
    platforms, houses, towers, and shelters.
-   **Combat:** target selection and tactical actions, using a PPO
    policy when available or a rule-based fallback.
-   **Survival:** eating, fleeing, sheltering, and waiting to recover
    health; a survival arbiter can interrupt other tasks.

### Minecraft integration

The Fabric mod provides a local bridge between Minecraft and Python. The
bridge exposes:

-   `GET /ping` --- check that the mod is running and whether the player
    is in a world.
-   `GET /observation` --- retrieve the current observation.
-   `POST /step` --- execute an action for a requested number of client
    ticks and return the resulting observation.
-   `GET /scan` --- search nearby blocks by block-name fragments.

The bridge binds to `127.0.0.1:5000` by default.

### Reinforcement learning

The repository includes combat and survival simulators, PPO policy
training, evaluation against random and rule-based policies, and saved
model files. These policies are used for tactical decisions; navigation,
mining, crafting, and building are primarily implemented as
deterministic skills.

------------------------------------------------------------------------

## Architecture

``` text
                 Player instruction
                 (typed or spoken)
                         |
                         v
              NLP / command parsing
               rule parser or LLM
                         |
                         v
                 Structured tasks
                         |
                         v
                Task / recipe planner
                         |
                         v
                Bot + survival arbiter
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
         Navigation    Mining      Combat
             |           |           |
             +-----------+-----------+
                         |
                 Craft / Build /
                  Gather / Survive
                         |
                         v
                Python MC client
                         |
                   HTTP + JSON
                         |
                         v
                HarshCraft Fabric
                  client-side mod
                         |
                         v
                  Minecraft world
                         |
                         +---- observations ---->
```

The two projects are kept separate:

-   **`HarshCraftAI/`** contains Python command processing, planning,
    skills, pathfinding, the HTTP client, RL policies, simulators, and
    tests.
-   **`HarshCraft/`** contains the Java Fabric mod that reads game state
    and performs in-game actions.

The mod marshals Minecraft-state operations onto the client thread.
Python sends actions through the HTTP bridge and receives the resulting
observation.

## Repository layout

``` text
Harshcraft_Complete/
├── README.md
├── .gitignore
├── HarshCraft/
│   ├── build.gradle
│   ├── gradle.properties
│   ├── gradlew
│   └── src/
│       ├── main/                 # Mod entry point, items, entities, resources
│       └── client/               # AI bridge, client entry point, mixins
└── HarshCraftAI/
    ├── run_bot.py                # Main Python entry point
    ├── requirements.txt
    ├── harshcraft_ai/
    │   ├── nlp.py                # Rule-based command parser
    │   ├── llm.py                # Optional Anthropic parser
    │   ├── voice.py              # Optional speech input/output
    │   ├── planner.py            # Task and recipe planning
    │   ├── agent.py              # Bot orchestration and survival arbiter
    │   ├── client.py             # HTTP client for the Fabric bridge
    │   ├── world.py              # World and inventory state
    │   ├── pathfinding.py        # 3D pathfinding
    │   ├── motor.py              # Movement and action controller
    │   ├── skills/               # Navigation, mining, combat, crafting,
    │   │                         # building, and survival
    │   └── rl/                   # Policies, simulators, and trainer
    ├── sim/                      # Mock Minecraft server
    ├── tests/                    # Automated tests
    └── models/                   # Saved RL policies
```

## Requirements

-   Minecraft **1.21.1**
-   Java **21**
-   Fabric Loader and Fabric API versions specified in
    `HarshCraft/gradle.properties`
-   Python **3.10+** (the committed bytecode artifacts indicate Python
    3.11 was used during development; Python 3.11 is a sensible choice)
-   Windows, Linux, or macOS; commands below use Windows PowerShell

The Python core uses the standard library and NumPy. Gymnasium,
Stable-Baselines3, and PyTorch are needed for RL training/loading. Voice
packages are optional.

## Setup

### 1. Build and launch the Fabric mod

Open PowerShell in the repository root:

``` powershell
cd .\HarshCraft
.\gradlew.bat runClient
```

Wait for Minecraft to launch, then enter a **single-player world**. The
bot expects the player to be in a loaded world before it starts.

If the game pauses when its window loses focus, press **F3+P** in
Minecraft to toggle pause-on-lost-focus off. This is useful because the
Python bot communicates with the running client while you may be using
the terminal.

### 2. Install Python dependencies

Open a second PowerShell window in the repository root:

``` powershell
cd .\HarshCraftAI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, either adjust the
execution policy for your user according to your organization's policy,
or invoke the environment's Python directly:

``` powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Optional voice dependencies

Choose a speech-recognition backend.

**Offline transcription (faster-whisper + sounddevice):**

``` powershell
pip install faster-whisper sounddevice
```

**Online SpeechRecognition backend:**

``` powershell
pip install SpeechRecognition pyaudio
```

For spoken replies, install:

``` powershell
pip install pyttsx3
```

Voice support depends on a working microphone, audio drivers, and the
selected backend. If no backend is available, the program can still
accept typed commands.

### 4. Optional LLM command parsing

The rule-based parser works without an API key. To enable the optional
Anthropic parser, set an API key in the environment before launching the
bot:

``` powershell
$env:ANTHROPIC_API_KEY = "your-api-key"
python run_bot.py --llm
```

You can optionally choose a model with `HARSHCRAFT_LLM_MODEL`. Keep API
keys private; do not commit them to Git or put them in source files.

## Run the bot

Make sure Minecraft is running with the HarshCraft mod, and that you
have entered a world.

From `HarshCraftAI/`:

**Typed commands:**

``` powershell
python run_bot.py
```

**Voice commands:**

``` powershell
python run_bot.py --voice
```

**Voice commands with a wake word and spoken replies:**

``` powershell
python run_bot.py --voice --wake "bot" --tts
```

**Enable optional LLM parsing:**

``` powershell
python run_bot.py --llm
```

**Run one command and exit after it completes:**

``` powershell
python run_bot.py --say "get a stone pickaxe"
```

**Use a custom bridge URL:**

``` powershell
python run_bot.py --url http://127.0.0.1:5000
```

The bot's default bridge address is `http://127.0.0.1:5000`.

## Example commands

The parser and planner support a range of task phrases. Examples
include:

  Goal                         Example instruction
  ---------------------------- --------------------------------------------------
  Acquire materials            `get 16 oak planks`
  Prepare a tool               `get a stone pickaxe`
  Chain tasks                  `get 5 iron ingots and then craft an iron sword`
  Navigate                     `go to 100 64 -200`
  Combat                       `kill the zombies`
  Hunt animals                 `hunt 3 cows`
  Build                        `build a house`
  Explore                      `explore`
  Survival                     `survive for 10 minutes`
  Return to a saved location   `go home`
  Stop                         `stop`
  Inspect bot state            `status`

Exact phrasing and supported item/mob names depend on the parser
vocabulary and planner knowledge. If a command is not recognized, try a
simpler instruction or enable the optional LLM parser.

## Reinforcement learning

The RL code currently focuses on **combat** and **survival** policies
trained in lightweight Python simulators. It does not train the full
Minecraft navigation or building stack end-to-end.

From `HarshCraftAI/`:

``` powershell
# Train both policies
python -m harshcraft_ai.rl.train all

# Train combat only
python -m harshcraft_ai.rl.train combat --steps 400000

# Train survival only
python -m harshcraft_ai.rl.train survival --steps 300000
```

The trainer compares random, rule-based, and PPO policies and saves
models under `HarshCraftAI/models/`.

**Important:** Simulator performance is not proof of equivalent
performance in a live Minecraft world. Real-game transfer,
generalization to arbitrary terrain, and long-horizon task reliability
still require testing.

## Run tests

From `HarshCraftAI/`:

``` powershell
python -m pytest tests -q
```

The repository also includes a mock server under `sim/` for exercising
the Python client and gameplay logic without connecting to a live
Minecraft instance.

A passing mock-server test suite validates the tested Python behavior
against that mock environment. It does not prove that every action works
correctly in every live Minecraft world or that the Fabric mod builds
successfully against the installed toolchain.

## Configuration

Central Python settings are in `HarshCraftAI/harshcraft_ai/config.py`.
They include:

-   HTTP host and port
-   Movement and combat action tick durations
-   Block interaction and attack reach
-   Block scan radius and vertical range
-   Survival reflex thresholds
-   Maximum steps per skill

The Minecraft/Fabric versions and dependency versions are configured in
`HarshCraft/gradle.properties`.

## Current status and limitations

HarshCraftAI is an active prototype. The repository includes the
components described above, but capability maturity varies.

-   **Implemented in the codebase:** typed command entry, rule-based NLP
    parsing, optional Anthropic parsing, optional voice input/output,
    task/recipe planning, Python-to-Fabric HTTP client, gameplay skill
    modules, mock server, tests, and combat/survival RL simulators.
-   **Python testing:** the project README in `HarshCraftAI/` reports 24
    passing tests against the mock server, covering selected movement,
    mining, collection, crafting, smelting, building, combat, survival,
    and planning flows. Re-run the test command on your machine to
    confirm the current checkout.
-   **Java build status:** the existing project notes state that Java
    was checked against hand-written API stubs, but was not verified
    with a full Gradle build against the actual Minecraft/Fabric
    dependencies. Run the Gradle build locally before treating the mod
    as release-ready.
-   **RL status:** saved PPO models and simulator results are included,
    but simulator results use approximate game constants. Transfer to
    real Minecraft has not been established.
-   **Known scope gaps:** the existing project notes list farming,
    villager trading, Nether/End navigation, bows, bed/sleep, and
    automatic tall-tree climbing as not implemented. Mining currently
    has an X-ray-style scan mode enabled (`XRAY = True` in
    `skills/mine.py`); set it to `False` to restrict selection to blocks
    exposed to air.
-   **Reliability:** pathfinding, block interaction, combat, and
    survival behavior can fail in unusual terrain, modded worlds, or
    situations not represented by the mock server and simulators. Back
    up important worlds and supervise the bot.

Do not interpret the feature list as a claim that every skill is
production-grade or fully autonomous.

## Troubleshooting

**The bot cannot connect to Minecraft**

1.  Confirm the Fabric mod loaded successfully.
2.  Enter a world; the title screen is not sufficient.
3.  Check that the bridge is listening at `127.0.0.1:5000`.
4.  If you changed the port or URL, pass the matching URL with `--url`.

**A `/step` request times out**

-   Make sure the world is not paused.
-   Press F3+P to disable pause-on-lost-focus.
-   Check that Minecraft is responsive and not blocked by another screen
    or dialog.

**Voice input is unavailable**

-   Install one of the optional voice backends.
-   Check microphone permissions and input-device selection.
-   Run without `--voice` to use typed commands.

**The LLM parser is not enabled**

-   Set `ANTHROPIC_API_KEY` in the same terminal session.
-   Start the bot with `--llm`.
-   If the key is missing, the bot falls back to rule-based parsing.

**A command is not understood**

-   Use a simpler phrase with an item, mob, action, or coordinate
    explicitly stated.
-   Check the aliases and vocabulary in `harshcraft_ai/knowledge.py`.
-   Optionally enable LLM parsing.

## Safety and usage notes

-   Use a test world or make a backup before allowing the bot to mine,
    place, or fight.
-   The mod bridge binds to localhost (`127.0.0.1`) by default and is
    intended for local use. Do not expose it to an untrusted network
    without adding authentication and appropriate access controls.
-   The bot can alter terrain, consume items, take damage, and die.
    Supervise it, especially in survival worlds.
-   Keep API keys and other credentials out of commits.

## Contributing

Issues and pull requests are welcome. When reporting a bug, include:

-   Minecraft version and Fabric Loader/API versions
-   Java and Python versions
-   The exact command that was issued
-   Relevant terminal output and Minecraft logs
-   Whether the problem reproduces with the mock server or only in a
    live world

For code changes, add or update tests where practical and describe which
behavior was tested.

## License

The Fabric mod currently includes a `CC0-1.0` license file. Check the
license and any third-party dependency terms before redistributing the
complete combined repository. The Python project should also have its
intended license stated explicitly if it is to be distributed
independently.

------------------------------------------------------------------------

**HarshCraftAI --- From natural-language instructions to autonomous
Minecraft gameplay.**
