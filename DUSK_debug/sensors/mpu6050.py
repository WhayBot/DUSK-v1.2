"""
DUSK Debug - Simulated MPU6050 Gyroscope + Accelerometer

Returns plausible fake sensor data. Heading tracks simulated
turns from the motor controller for realistic navigation testing.
"""

import time
import random
import config


class MPU6050:
    """Simulated MPU6050 IMU with heading tracking."""

    def __init__(self):
        self._heading = 0.0
        self._last_time = time.time()
        self._gyro_z_bias = 0.0
        self._simulated_yaw_rate = 0.0  # Set by motors for simulation
        print("[SIM] MPU6050 initialized (simulated)")

    def get_accel(self):
        return {
            "x": random.uniform(-0.02, 0.02),
            "y": random.uniform(-0.02, 0.02),
            "z": random.uniform(0.98, 1.02),
        }

    def get_gyro(self):
        return {
            "x": random.uniform(-0.5, 0.5),
            "y": random.uniform(-0.5, 0.5),
            "z": self._simulated_yaw_rate + random.uniform(-0.3, 0.3),
        }

    def get_temperature(self):
        return 36.5 + random.uniform(-0.5, 0.5)

    def _read_gyro_z_fast(self):
        return self._simulated_yaw_rate + random.uniform(-0.2, 0.2) - self._gyro_z_bias

    def get_gyro_z(self):
        return self._read_gyro_z_fast()

    def update_heading(self):
        current_time = time.time()
        dt = current_time - self._last_time
        self._last_time = current_time

        gyro_z = self._read_gyro_z_fast()
        if abs(gyro_z) > 0.5:
            self._heading += gyro_z * dt

        self._heading = self._heading % 360
        return self._heading

    def get_heading(self):
        return self._heading

    def reset_heading(self, value=0.0):
        self._heading = value % 360
        self._last_time = time.time()

    def get_all(self):
        return {
            "accel": self.get_accel(),
            "gyro": self.get_gyro(),
            "temperature": self.get_temperature(),
            "heading": self._heading,
        }

    def set_simulated_yaw_rate(self, rate):
        """Called by simulated motors to update yaw rate."""
        self._simulated_yaw_rate = rate

    def calibrate_gyro(self, samples=200, settle_time=0.0):
        if settle_time > 0:
            print(f"[SIM] Gyro settling for {settle_time}s...")
            time.sleep(min(settle_time, 0.5))  # Shortened for debug

        self._gyro_z_bias = random.uniform(-0.1, 0.1)
        print(f"[SIM] Gyro calibrated (bias={self._gyro_z_bias:.4f} deg/s, samples={samples})")
        return self._gyro_z_bias
