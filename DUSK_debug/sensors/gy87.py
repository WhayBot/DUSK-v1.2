"""
DUSK Debug - Simulated GY-87 (MPU6050 + HMC5883L + BMP180)

Extends the simulated MPU6050 with fake magnetometer and barometer data.
API-compatible with the real GY87 class.
"""

import time
import math
import random
import config
from sensors.sensor_fusion import ComplementaryFilter


class GY87:
    """Simulated GY-87 10-DOF IMU."""

    def __init__(self):
        self._heading = 0.0
        self._fused_heading = 0.0
        self._last_time = time.time()
        self._gyro_z_bias = 0.0
        self._simulated_yaw_rate = 0.0
        self._simulated_mag_heading = 0.0

        self._hmc_available = True
        self._bmp_available = True
        self._last_temperature = 27.5

        self._mag_x_offset = 0.0
        self._mag_y_offset = 0.0
        self._mag_z_offset = 0.0
        self._mag_declination = getattr(config, 'MAG_DECLINATION', 0.9)

        fusion_alpha = getattr(config, 'FUSION_ALPHA', 0.96)
        self._fusion = ComplementaryFilter(alpha=fusion_alpha)

        print("[SIM] GY-87 initialized (MPU6050 + HMC5883L + BMP180)")

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

    def set_simulated_yaw_rate(self, rate):
        self._simulated_yaw_rate = rate

    # --- Magnetometer ---

    def get_mag(self):
        if not self._hmc_available:
            return None
        angle_rad = math.radians(self._heading)
        return {
            "x": math.cos(angle_rad) * 300 + random.uniform(-5, 5),
            "y": math.sin(angle_rad) * 300 + random.uniform(-5, 5),
            "z": random.uniform(-50, 50),
        }

    def get_mag_heading(self):
        if not self._hmc_available:
            return -1.0
        # Simulated heading tracks the gyro heading with noise
        return (self._heading + random.uniform(-1.0, 1.0) + self._mag_declination) % 360

    # --- Barometer ---

    def get_temperature_bmp(self):
        if not self._bmp_available:
            return self._last_temperature
        self._last_temperature = 27.5 + random.uniform(-0.3, 0.3)
        return self._last_temperature

    def get_pressure(self):
        if not self._bmp_available:
            return 0.0
        return 1013.25 + random.uniform(-0.5, 0.5)

    # --- Heading ---

    def update_heading(self):
        current_time = time.time()
        dt = current_time - self._last_time
        self._last_time = current_time

        gyro_z = self._read_gyro_z_fast()

        if self._hmc_available:
            mag_heading = self.get_mag_heading()
            if mag_heading >= 0:
                self._fused_heading = self._fusion.update(gyro_z, mag_heading, dt)
                self._heading = self._fused_heading
            else:
                if abs(gyro_z) > 0.5:
                    self._heading += gyro_z * dt
                self._heading = self._heading % 360
                self._fused_heading = self._heading
        else:
            if abs(gyro_z) > 0.5:
                self._heading += gyro_z * dt
            self._heading = self._heading % 360
            self._fused_heading = self._heading

        return self._heading

    def get_heading(self):
        return self._heading

    def get_fused_heading(self):
        return self._fused_heading

    def reset_heading(self, value=0.0):
        self._heading = value % 360
        self._fused_heading = self._heading
        self._fusion.reset(self._heading)
        self._last_time = time.time()

    def get_all(self):
        result = {
            "accel": self.get_accel(),
            "gyro": self.get_gyro(),
            "temperature": self.get_temperature(),
            "heading": self._heading,
            "fused_heading": self._fused_heading,
        }
        if self._hmc_available:
            result["mag"] = self.get_mag()
            result["mag_heading"] = self.get_mag_heading()
        if self._bmp_available:
            result["temperature_bmp"] = self._last_temperature
        return result

    # --- Calibration ---

    def calibrate_gyro(self, samples=200, settle_time=0.0):
        if settle_time > 0:
            time.sleep(min(settle_time, 0.5))
        self._gyro_z_bias = random.uniform(-0.1, 0.1)
        print(f"[SIM] Gyro calibrated (bias={self._gyro_z_bias:.4f} deg/s)")
        return self._gyro_z_bias

    def calibrate_magnetometer(self, duration=15):
        print(f"[SIM] Magnetometer calibration ({duration}s) - simulated")
        time.sleep(min(duration, 1))
        offsets = {"x_offset": 12.3, "y_offset": -8.7, "z_offset": 3.1}
        self._mag_x_offset = offsets["x_offset"]
        self._mag_y_offset = offsets["y_offset"]
        self._mag_z_offset = offsets["z_offset"]
        print(f"[SIM] Magnetometer calibrated: {offsets}")
        return offsets

    def get_sensor_info(self):
        return {
            "type": "GY-87",
            "mpu6050": True,
            "hmc5883l": self._hmc_available,
            "bmp180": self._bmp_available,
            "fusion": self._hmc_available,
            "mag_declination": self._mag_declination,
        }
