import gymnasium as gym
from gymnasium import spaces

from minecraft_env import MinecraftEnvironment


class HarshCraftGymEnv(
    gym.Env):

    def __init__(self):

        super().__init__()

        self.minecraft = \
            MinecraftEnvironment()

        self.action_space = \
            spaces.Discrete(6)

        self.observation_space = \
            spaces.Box(
                low=-10000,
                high=10000,
                shape=(10,),
                dtype=float
            )

    def reset(
            self,
            seed=None,
            options=None
    ):

        observation = \
            self.minecraft.reset()

        return (
            self.convert(
                observation
            ),
            {}
        )

    def step(self, action):

        actions = {

            0: "forward",
            1: "backward",
            2: "left",
            3: "right",
            4: "jump",
            5: "noop"
        }

        observation, _, _, _ = \
            self.minecraft.step(
                actions[action]
            )

        reward = 0

        terminated = False

        truncated = False

        return (

            self.convert(
                observation
            ),

            reward,

            terminated,

            truncated,

            {}
        )

    def convert(
            self,
            observation
    ):

        player = \
            observation["player"]

        return [

            player["x"],
            player["y"],
            player["z"],

            player["yaw"],
            player["pitch"],

            player["health"],
            player["food"],

            0,
            0,
            0
        ]