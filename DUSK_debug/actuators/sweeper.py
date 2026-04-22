"""
DUSK Debug - Simulated Sweeper Motors (N20)
Logs all sweeper commands to console.
"""

import config


class SweeperMotors:
    """Simulated N20 sweeper motor controller."""

    def __init__(self):
        self._running = False
        self._speed = 0
        print("[SIM] Sweeper motors initialized")

    def start(self, speed=None):
        if speed is None:
            speed = config.SWEEPER_DEFAULT_SPEED
        self._speed = speed
        self._running = True
        print(f"[SIM] Sweeper: START speed={speed}")

    def stop(self):
        self._speed = 0
        self._running = False
        print("[SIM] Sweeper: STOP")

    def set_speed(self, speed):
        self._speed = max(0, min(100, speed))
        print(f"[SIM] Sweeper: SET SPEED={self._speed}")

    def is_running(self):
        return self._running

    def get_status(self):
        return {
            "running": self._running,
            "speed": self._speed,
        }

    def cleanup(self):
        self.stop()
        print("[SIM] Sweeper motors cleaned up")
