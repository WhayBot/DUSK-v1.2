"""
DUSK Debug - Simulated Wheel Motors (L298N)

Logs all motor commands to console. Feeds speed data back to
simulated encoders and yaw rate to simulated IMU for realistic
navigation testing.
"""

import config


class WheelMotors:
    """Simulated wheel motor controller with encoder/IMU feedback."""

    def __init__(self):
        self._left_speed = 0
        self._right_speed = 0
        self._encoders = None  # Set by main.py after init
        self._imu = None       # Set by main.py after init
        print("[SIM] Wheel motors initialized")

    def set_feedback_targets(self, encoders, imu):
        """Connect simulated encoders and IMU for feedback loop."""
        self._encoders = encoders
        self._imu = imu

    def _update_feedback(self):
        """Push speed data to simulated encoders and IMU."""
        if self._encoders:
            self._encoders.left.set_simulated_speed(self._left_speed)
            self._encoders.right.set_simulated_speed(self._right_speed)
        if self._imu:
            # Differential speed creates yaw rate
            yaw_rate = (self._right_speed - self._left_speed) * 0.5
            self._imu.set_simulated_yaw_rate(yaw_rate)

    def forward(self, speed=None):
        if speed is None:
            speed = config.MOTOR_DEFAULT_SPEED
        self._left_speed = speed
        self._right_speed = speed
        self._update_feedback()
        print(f"[SIM] Motors: FORWARD speed={speed}")

    def backward(self, speed=None):
        if speed is None:
            speed = config.MOTOR_DEFAULT_SPEED
        self._left_speed = -speed
        self._right_speed = -speed
        self._update_feedback()
        print(f"[SIM] Motors: BACKWARD speed={speed}")

    def turn_left(self, speed=None):
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._left_speed = 0
        self._right_speed = speed
        self._update_feedback()
        print(f"[SIM] Motors: TURN LEFT speed={speed}")

    def turn_right(self, speed=None):
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._left_speed = speed
        self._right_speed = 0
        self._update_feedback()
        print(f"[SIM] Motors: TURN RIGHT speed={speed}")

    def spin_left(self, speed=None):
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._left_speed = -speed
        self._right_speed = speed
        self._update_feedback()
        print(f"[SIM] Motors: SPIN LEFT speed={speed}")

    def spin_right(self, speed=None):
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._left_speed = speed
        self._right_speed = -speed
        self._update_feedback()
        print(f"[SIM] Motors: SPIN RIGHT speed={speed}")

    def differential_drive(self, left_speed, right_speed):
        self._left_speed = left_speed
        self._right_speed = right_speed
        self._update_feedback()

    def stop(self):
        self._left_speed = 0
        self._right_speed = 0
        self._update_feedback()

    def cleanup(self):
        self.stop()
        print("[SIM] Wheel motors cleaned up")
