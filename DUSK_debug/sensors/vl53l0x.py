"""
DUSK Debug - Simulated VL53L0X ToF Distance Sensors

Returns random distance values within a realistic range.
Obstacles can be injected for testing navigation logic.
"""

import random
import config


class VL53L0X:
    """Simulated single VL53L0X ToF sensor."""

    def __init__(self, mux_channel, name=""):
        self._channel = mux_channel
        self._name = name
        self._fixed_distance = None  # Set to inject a fixed distance
        print(f"[SIM] VL53L0X ({name}) initialized on channel {mux_channel}")

    def read_distance(self):
        if self._fixed_distance is not None:
            return self._fixed_distance
        return random.randint(200, 2000)

    def set_fixed_distance(self, mm):
        """Inject a fixed distance for testing obstacle avoidance."""
        self._fixed_distance = mm

    def clear_fixed_distance(self):
        self._fixed_distance = None


class DualVL53L0X:
    """Simulated dual VL53L0X sensor manager."""

    def __init__(self):
        self.left = VL53L0X(config.MUX_CH_VL53L0X_LEFT, "Left")
        self.right = VL53L0X(config.MUX_CH_VL53L0X_RIGHT, "Right")
        print("[SIM] Dual VL53L0X initialized")

    def get_distances(self):
        return {
            "left": self.left.read_distance(),
            "right": self.right.read_distance(),
        }

    def check_obstacles(self, threshold=None):
        if threshold is None:
            threshold = config.OBSTACLE_THRESHOLD_MM

        distances = self.get_distances()
        left_blocked = distances["left"] < threshold
        right_blocked = distances["right"] < threshold

        return {
            "left": left_blocked,
            "right": right_blocked,
            "any": left_blocked or right_blocked,
            "distances": distances,
        }

    def get_status(self):
        distances = self.get_distances()
        return {
            "left_mm": distances["left"],
            "right_mm": distances["right"],
        }
