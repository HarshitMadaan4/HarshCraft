from minecraft_env import MinecraftEnvironment
import time

env = MinecraftEnvironment()

print("Mining...")

env.send_action("mine")