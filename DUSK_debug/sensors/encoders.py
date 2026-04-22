"""
DUSK Debug - Simulated Speed Encoders

Generates simulated encoder pulses based on motor speed commands.
Distance increases proportionally to simulated motor activity.
"""

import time
import threading
import config


class SpeedEncoder:
    """Simulated single speed encoder."""

    def __init__(self, name=""):
        self._name = name
        self._pulse_count = 0
        self._distance_mm = 0.0
        self._speed = 0.0  # Simulated motor speed (0-100)
        self._last_time = time.time()
        self._running = True
        self._thread = threading.Thread(target=self._simulate_loop, daemon=True)
        self._thread.start()

    def _simulate_loop(self):
        """Simulate encoder pulses based on motor speed."""
        while self._running:
            now = time.time()
            dt = now - self._last_time
            self._last_time = now

            if self._speed > 0:
                # Simulate distance based on speed
                # At 100% speed, ~500mm/s
                mm_per_sec = (self._speed / 100.0) * 500
                distance_delta = mm_per_sec * dt
                self._distance_mm += distance_delta

                # Simulate pulse count
                pulses = distance_delta / (config.WHEEL_CIRCUMFERENCE_MM / config.ENCODER_PULSES_PER_REV)
                self._pulse_count += int(pulses)

            time.sleep(0.05)

    def set_simulated_speed(self, speed):
        """Set simulated motor speed (called by motor controller)."""
        self._speed = abs(speed)

    def get_pulse_count(self):
        return self._pulse_count

    def get_distance(self):
        return round(self._distance_mm, 1)

    def get_speed_mm_per_sec(self):
        return round((self._speed / 100.0) * 500, 1)

    def reset(self):
        self._pulse_count = 0
        self._distance_mm = 0.0

    def cleanup(self):
        self._running = False


class DualEncoders:
    """Simulated dual encoder manager."""

    def __init__(self):
        self.left = SpeedEncoder("Left")
        self.right = SpeedEncoder("Right")
        print("[SIM] Dual speed encoders initialized")

    def get_distances(self):
        left_d = self.left.get_distance()
        right_d = self.right.get_distance()
        return {
            "left": left_d,
            "right": right_d,
            "average": (left_d + right_d) / 2,
        }

    def get_speeds(self):
        return {
            "left": self.left.get_speed_mm_per_sec(),
            "right": self.right.get_speed_mm_per_sec(),
        }

    def reset_all(self):
        self.left.reset()
        self.right.reset()

    def get_status(self):
        return {
            "left_distance": self.left.get_distance(),
            "right_distance": self.right.get_distance(),
            "left_speed": self.left.get_speed_mm_per_sec(),
            "right_speed": self.right.get_speed_mm_per_sec(),
            "left_pulses": self.left.get_pulse_count(),
            "right_pulses": self.right.get_pulse_count(),
        }

    def cleanup(self):
        self.left.cleanup()
        self.right.cleanup()
