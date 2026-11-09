import requests
import time

BASE_URL = "http://127.0.0.1:5000"


def get_observation():

    response = requests.get(
        BASE_URL + "/observation"
    )

    if response.status_code != 200:
        print("Observation failed:", response.status_code)
        return None

    return response.json()


def send_action(action):

    response = requests.post(
        BASE_URL + "/action",
        json={
            "type": action
        }
    )

    print(
        f"ACTION [{action}] ->",
        response.status_code,
        response.text
    )


print("=" * 50)
print("INITIAL OBSERVATION")
print("=" * 50)

obs = get_observation()

if obs is None:
    exit()

print(obs["player"])

print("\nSending FORWARD...")
send_action("forward")

print(
    "\nDO NOT TOUCH THE KEYBOARD.\n"
    "Watch Minecraft and console output.\n"
)

for second in range(10):

    time.sleep(1)

    obs = get_observation()

    if obs is None:
        continue

    player = obs["player"]

    print(
        f"[{second + 1:02d}s] "
        f"x={player['x']:.3f} "
        f"y={player['y']:.3f} "
        f"z={player['z']:.3f} "
        f"yaw={player['yaw']:.2f}"
    )

print("\nSending NOOP...")
send_action("noop")

print("\nFinal observation:")

obs = get_observation()

if obs:
    print(obs["player"])

print("\nTEST COMPLETE")