"""
DUSK Debug - Complementary Filter for Sensor Fusion
(Same as production version - no hardware dependency)
"""

import math


class ComplementaryFilter:
    """Complementary filter for gyro + magnetometer heading fusion."""

    def __init__(self, alpha=0.96):
        self.alpha = alpha
        self._fused_heading = 0.0
        self._initialized = False

    def _normalize_angle(self, angle):
        return angle % 360

    def _angle_diff(self, a, b):
        diff = (a - b) % 360
        if diff > 180:
            diff -= 360
        return diff

    def update(self, gyro_z, mag_heading, dt):
        if not self._initialized:
            self._fused_heading = mag_heading
            self._initialized = True
            return self._fused_heading

        gyro_prediction = self._fused_heading + gyro_z * dt
        mag_correction = self._angle_diff(mag_heading, gyro_prediction)
        self._fused_heading = gyro_prediction + (1.0 - self.alpha) * mag_correction
        self._fused_heading = self._normalize_angle(self._fused_heading)
        return self._fused_heading

    def get_heading(self):
        return self._fused_heading

    def reset(self, heading=0.0):
        self._fused_heading = heading
        self._initialized = False

    def set_alpha(self, alpha):
        self.alpha = max(0.0, min(1.0, alpha))
