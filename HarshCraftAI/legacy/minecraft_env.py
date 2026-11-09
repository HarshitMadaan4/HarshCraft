import requests
import time
import threading


BASE_URL = "http://127.0.0.1:5000"

# Observation scans can take several seconds in Minecraft.
REQUEST_TIMEOUT = 15.0

# Action requests should normally complete quickly.
ACTION_REQUEST_TIMEOUT = 2.0

ACTION_DELAY = 0.1
DEFAULT_MAX_STEPS = 1000

# Refresh continuous actions before the Java action timeout expires.
ACTION_HEARTBEAT_INTERVAL = 0.75
HEARTBEAT_REQUEST_TIMEOUT = 1.5


class MinecraftEnvironment:

    def __init__(
            self,
            reward_fn=None,
            done_fn=None,
            max_episode_steps=DEFAULT_MAX_STEPS
    ):

        self.session = requests.Session()

        self.reward_fn = reward_fn
        self.done_fn = done_fn

        self.max_episode_steps = max_episode_steps

        self.current_step = 0
        self.last_observation = None

        self.connection_failed = False

        # Heartbeat diagnostics
        self.last_heartbeat_count = 0
        self.last_heartbeat_error = None

    # ========================================================
    # OBSERVATION
    # ========================================================

    def get_observation(self):

        try:

            response = self.session.get(
                BASE_URL + "/observation",
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            observation = response.json()

            if not isinstance(observation, dict):
                print("Invalid observation: expected a JSON object.")
                return None

            self.connection_failed = False

            return observation

        except requests.RequestException as e:

            self.connection_failed = True

            print("Observation error:", e)

            return None

        except ValueError as e:

            print("Invalid observation JSON:", e)

            return None

    # ========================================================
    # ACTION
    # ========================================================

    def send_action(self, action):

        if not isinstance(action, str) or not action.strip():

            print("Invalid action:", action)

            return None

        try:

            response = self.session.post(
                BASE_URL + "/action",
                json={
                    "type": action
                },
                timeout=ACTION_REQUEST_TIMEOUT
            )

            response.raise_for_status()

            if not response.content:
                return {
                    "status": "ok"
                }

            try:

                return response.json()

            except ValueError:

                return {
                    "status": "ok",
                    "raw": response.text
                }

        except requests.RequestException as e:

            self.connection_failed = True

            print("Action error:", e)

            return None

    # ========================================================
    # ACTION HEARTBEAT
    # ========================================================

    def _action_heartbeat_worker(self, action, stop_event):

        """
        Refreshes the current Minecraft action while Python waits
        for a potentially slow observation response.

        A separate requests.post call is used here instead of the
        shared Session because requests.Session is not guaranteed
        to be thread-safe.
        """

        while not stop_event.wait(ACTION_HEARTBEAT_INTERVAL):

            try:

                response = requests.post(
                    BASE_URL + "/action",
                    json={
                        "type": action
                    },
                    timeout=HEARTBEAT_REQUEST_TIMEOUT
                )

                response.raise_for_status()

                self.last_heartbeat_count += 1

            except requests.RequestException as e:

                self.last_heartbeat_error = str(e)

                print("Action heartbeat error:", e)

                # Continue attempting heartbeats.
                continue

    # ========================================================
    # OBSERVATION WHILE HOLDING ACTION
    # ========================================================

    def observe_while_holding(self, action):

        """
        Retrieves an observation while periodically refreshing
        the current action.

        This helps prevent continuous movement actions from
        expiring while Minecraft calculates a large observation.
        """

        self.last_heartbeat_count = 0
        self.last_heartbeat_error = None

        stop_event = threading.Event()

        heartbeat_thread = threading.Thread(
            target=self._action_heartbeat_worker,
            args=(action, stop_event),
            daemon=True
        )

        heartbeat_thread.start()

        try:

            observation = self.get_observation()

            return observation

        finally:

            # Stop the heartbeat when observation retrieval ends.
            stop_event.set()

            heartbeat_thread.join(
                timeout=HEARTBEAT_REQUEST_TIMEOUT + 0.5
            )

    # ========================================================
    # STEP
    # ========================================================

    def step(self, action):

        previous_observation = self.last_observation

        action_result = self.send_action(action)

        time.sleep(ACTION_DELAY)

        # ----------------------------------------------------
        # Keep the action refreshed during observation retrieval
        # ----------------------------------------------------

        if action_result is not None:

            observation = self.observe_while_holding(action)

        else:

            observation = self.get_observation()

        self.current_step += 1

        info = {
            "action": action,
            "action_response": action_result,
            "step": self.current_step,
            "connection_failed": self.connection_failed,
            "reward_source": "not_configured",
            "heartbeats_sent": self.last_heartbeat_count,
            "heartbeat_error": self.last_heartbeat_error
        }

        # ----------------------------------------------------
        # Connection failure
        # ----------------------------------------------------

        if observation is None:

            info["truncated"] = True
            info["termination_reason"] = "observation_unavailable"

            return (
                None,
                0.0,
                True,
                info
            )

        # ----------------------------------------------------
        # Reward calculation
        # ----------------------------------------------------

        reward = 0.0

        if self.reward_fn is not None:

            try:

                reward = float(
                    self.reward_fn(
                        previous_observation,
                        observation,
                        action,
                        action_result
                    )
                )

                info["reward_source"] = "custom_reward_function"

            except Exception as e:

                print("Reward calculation error:", e)

                info["reward_error"] = str(e)

                reward = 0.0

        # ----------------------------------------------------
        # Task completion
        # ----------------------------------------------------

        done = False

        if self.done_fn is not None:

            try:

                done = bool(
                    self.done_fn(
                        observation
                    )
                )

                if done:
                    info["termination_reason"] = "task_completed"

            except Exception as e:

                print("Completion check error:", e)

                info["completion_error"] = str(e)

        # ----------------------------------------------------
        # Episode time limit
        # ----------------------------------------------------

        truncated = False

        if self.current_step >= self.max_episode_steps:

            truncated = True

            info["termination_reason"] = "maximum_episode_steps"

        info["truncated"] = truncated

        self.last_observation = observation

        return (
            observation,
            reward,
            done or truncated,
            info
        )

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):

        self.stop()

        time.sleep(ACTION_DELAY)

        observation = self.get_observation()

        if observation is None:

            raise RuntimeError(
                "Could not retrieve Minecraft observation during reset."
            )

        self.current_step = 0

        self.last_observation = observation

        self.connection_failed = False

        return observation

    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        return self.send_action("noop")

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.stop()

        self.session.close()