"""
DUSK Debug - Simulated Brushless Vacuum Motor (ESC)
Logs all vacuum commands with soft-start simulation.
"""

import time
import config

RAMP_STEP_PERCENT = 2
RAMP_STEP_DELAY = 0.01  # Faster in debug mode


class VacuumMotor:
    """Simulated brushless vacuum motor controller."""

    def __init__(self):
        self._speed_percent = 0
        self._armed = False
        print("[SIM] Vacuum motor initialized (no pigpio needed)")

    def arm(self):
        print("[SIM] Vacuum: ARMING ESC...")
        time.sleep(0.5)  # Shortened for debug
        self._armed = True
        print("[SIM] Vacuum: ARMED")

    def calibrate(self):
        print("[SIM] Vacuum: ESC calibration (simulated - skipped)")
        self._armed = True

    def _set_speed_raw(self, percent):
        percent = max(0, min(100, percent))
        self._speed_percent = percent

    def _ramp_to(self, target_percent):
        target_percent = max(0, min(100, target_percent))
        current = self._speed_percent

        if current < target_percent:
            while current < target_percent:
                current = min(current + RAMP_STEP_PERCENT, target_percent)
                self._set_speed_raw(current)
                time.sleep(RAMP_STEP_DELAY)
        else:
            while current > target_percent:
                current = max(current - RAMP_STEP_PERCENT, target_percent)
                self._set_speed_raw(current)
                time.sleep(RAMP_STEP_DELAY)

    def set_speed(self, percent):
        if not self._armed:
            self.arm()
        old = self._speed_percent
        self._ramp_to(percent)
        print(f"[SIM] Vacuum: SPEED {old}% -> {percent}% (ramped)")

    def start(self, speed=None):
        if speed is None:
            speed = config.ESC_DEFAULT_SPEED
        self.set_speed(speed)

    def stop(self):
        if self._speed_percent > 0:
            print(f"[SIM] Vacuum: STOPPING (ramp down from {self._speed_percent}%)")
            self._ramp_to(0)
        print("[SIM] Vacuum: STOPPED")

    def kill(self):
        self._speed_percent = 0
        self._armed = False
        print("[SIM] Vacuum: KILL (PWM off)")

    def get_speed(self):
        return self._speed_percent

    def is_running(self):
        return self._speed_percent > 0

    def get_status(self):
        return {
            "running": self._speed_percent > 0,
            "speed": self._speed_percent,
            "armed": self._armed,
        }

    def cleanup(self):
        self.stop()
        print("[SIM] Vacuum motor cleaned up")
