from minecraft_env import MinecraftEnvironment
from test_tree_detection import debug_tree_detection


env = MinecraftEnvironment()


print("Getting Minecraft observation...")

observation = env.get_observation()


print()
print("Observation keys:")
print(observation.keys())


debug_tree_detection(
    observation
)