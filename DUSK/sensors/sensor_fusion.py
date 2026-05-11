"""
DUSK - Complementary Filter for Sensor Fusion

Combines gyroscope (fast, drifts over time) with magnetometer
(slow, stable reference) to produce a drift-free heading.

The complementary filter is computationally lightweight, making it
ideal for the Pi Zero 2W compared to a full Kalman filter.

How it works:
    fused = alpha * gyro_prediction + (1 - alpha) * mag_heading

    alpha close to 1.0 = trust gyro more (good short-term accuracy)
    alpha close to 0.0 = trust magnetometer more (drift-free)
    Typical: 0.95-0.98
"""

import math


class ComplementaryFilter:
    """
    Complementary filter for gyro + magnetometer heading fusion.

    Provides drift-free heading by using the magnetometer as a
    long-term reference to correct gyroscope integration drift.
    """

    def __init__(self, alpha=0.96):
        """
        Args:
            alpha: Filter coefficient (0.0 - 1.0).
                   Higher values trust the gyroscope more.
                   0.96 means 96% gyro, 4% magnetometer per update.
        """
        self.alpha = alpha
        self._fused_heading = 0.0
        self._initialized = False

    def _normalize_angle(self, angle):
        """Normalize angle to 0-360 degrees."""
        return angle % 360

    def _angle_diff(self, a, b):
        """
        Compute shortest signed difference between two angles.
        Returns value in range [-180, +180].
        """
        diff = (a - b) % 360
        if diff > 180:
            diff -= 360
        return diff

    def update(self, gyro_z, mag_heading, dt):
        """
        Update fused heading with new sensor data.

        Args:
            gyro_z: Gyroscope Z-axis rate in deg/s (bias-corrected)
            mag_heading: Magnetometer heading in degrees (0-360)
            dt: Time delta in seconds since last update

        Returns:
            float: Fused heading in degrees (0-360)
        """
        if not self._initialized:
            self._fused_heading = mag_heading
            self._initialized = True
            return self._fused_heading

        # Gyro prediction: integrate yaw rate
        gyro_prediction = self._fused_heading + gyro_z * dt

        # Complementary filter with angle wrapping awareness
        # Use shortest angular distance to avoid 359->1 jumps
        mag_correction = self._angle_diff(mag_heading, gyro_prediction)
        self._fused_heading = gyro_prediction + (1.0 - self.alpha) * mag_correction

        # Normalize to 0-360
        self._fused_heading = self._normalize_angle(self._fused_heading)

        return self._fused_heading

    def get_heading(self):
        """Get current fused heading."""
        return self._fused_heading

    def reset(self, heading=0.0):
        """Reset the filter state."""
        self._fused_heading = heading
        self._initialized = False

    def set_alpha(self, alpha):
        """Adjust filter coefficient at runtime."""
        self.alpha = max(0.0, min(1.0, alpha))
