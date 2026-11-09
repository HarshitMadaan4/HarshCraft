from minecraft_env import MinecraftEnvironment
import json

env = MinecraftEnvironment()

obs = env.get_observation()

print(json.dumps(obs, indent=4))
print(obs.keys())