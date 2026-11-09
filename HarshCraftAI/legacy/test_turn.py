from minecraft_env import MinecraftEnvironment
import time

env = MinecraftEnvironment()

print("Turning left...")
env.send_action("left")

time.sleep(2)

print("Turning right...")
env.send_action("right")