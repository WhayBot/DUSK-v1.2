"""
DUSK Debug - Simulated INA219 Power Monitor

Returns simulated battery data with gradual voltage drain.
"""

import time
import random
import config


class INA219:
    """Simulated INA219 power monitor with draining battery."""

    def __init__(self):
        self._start_voltage = 12.4  # Start near full
        self._start_time = time.time()
        self._drain_rate = 0.0001  # V per second (very slow drain)
        print("[SIM] INA219 initialized (simulated battery at 12.4V)")

    def get_bus_voltage(self):
        elapsed = time.time() - self._start_time
        voltage = self._start_voltage - (elapsed * self._drain_rate)
        voltage += random.uniform(-0.02, 0.02)  # Noise
        return max(9.0, round(voltage, 2))

    def get_current(self):
        return round(random.uniform(1.5, 3.5), 2)

    def get_power(self):
        return round(self.get_bus_voltage() * self.get_current(), 2)

    def get_percentage(self):
        voltage = self.get_bus_voltage()
        if voltage >= config.BATTERY_FULL_VOLTAGE:
            return 100
        if voltage <= config.BATTERY_CRITICAL_VOLTAGE:
            return 0
        v_range = config.BATTERY_FULL_VOLTAGE - config.BATTERY_CRITICAL_VOLTAGE
        return int(((voltage - config.BATTERY_CRITICAL_VOLTAGE) / v_range) * 100)

    def get_status(self):
        voltage = self.get_bus_voltage()
        return {
            "voltage": voltage,
            "current": self.get_current(),
            "power": self.get_power(),
            "percentage": self.get_percentage(),
            "low_battery": voltage < config.BATTERY_LOW_VOLTAGE,
            "critical": voltage < config.BATTERY_CRITICAL_VOLTAGE,
        }
