"""
DUSK - INA219 Current/Voltage/Power Monitor Driver

Monitors the 3S LiPo battery voltage, current draw, and power consumption.
Connected through TCA9548A Channel 5.
"""

import time
import config
from i2c_mux import get_mux


# INA219 Register Map
_REG_CONFIG = 0x00
_REG_SHUNT_VOLTAGE = 0x01
_REG_BUS_VOLTAGE = 0x02
_REG_POWER = 0x03
_REG_CURRENT = 0x04
_REG_CALIBRATION = 0x05

# Configuration bits
_CONFIG_RESET = 0x8000
_CONFIG_BUS_VOLTAGE_RANGE_32V = 0x2000
_CONFIG_BUS_VOLTAGE_RANGE_16V = 0x0000
_CONFIG_GAIN_8_320MV = 0x1800
_CONFIG_GAIN_4_160MV = 0x1000
_CONFIG_GAIN_2_80MV = 0x0800
_CONFIG_GAIN_1_40MV = 0x0000
_CONFIG_BADC_12BIT = 0x0180
_CONFIG_SADC_12BIT = 0x0018
_CONFIG_MODE_SANDBVOLT_CONTINUOUS = 0x07


class INA219:
    """
    INA219 High-Side Current/Power Monitor.
    
    Measures bus voltage (V+), shunt voltage, and calculates current and power.
    Configured for a 3S LiPo battery monitoring setup.
    """

    def __init__(self):
        self.mux = get_mux()
        self.channel = config.MUX_CH_INA219
        self.address = config.INA219_ADDRESS
        self.shunt_ohms = config.INA219_SHUNT_OHMS
        self.max_expected_amps = config.INA219_MAX_EXPECTED_AMPS

        self._current_lsb = 0
        self._power_lsb = 0

        self._initialize()

    def _write_register(self, bus, reg, value):
        """Write a 16-bit value to a register (big-endian)."""
        data = [(value >> 8) & 0xFF, value & 0xFF]
        bus.write_i2c_block_data(self.address, reg, data)

    def _read_register(self, bus, reg):
        """Read a 16-bit value from a register (big-endian)."""
        data = bus.read_i2c_block_data(self.address, reg, 2)
        value = (data[0] << 8) | data[1]
        return value

    def _to_signed(self, value):
        """Convert unsigned 16-bit to signed."""
        if value > 32767:
            value -= 65536
        return value

    def _initialize(self):
        """Configure the INA219 for 3S LiPo monitoring."""
        with self.mux.channel(self.channel) as bus:
            # Reset
            self._write_register(bus, _REG_CONFIG, _CONFIG_RESET)
            time.sleep(0.05)

            # Calculate calibration value
            # Current_LSB = Max_Expected_Current / 2^15
            self._current_lsb = self.max_expected_amps / 32768.0
            # Power_LSB = 20 * Current_LSB
            self._power_lsb = 20 * self._current_lsb
            # Calibration = trunc(0.04096 / (Current_LSB * R_shunt))
            cal = int(0.04096 / (self._current_lsb * self.shunt_ohms))

            # Write calibration register
            self._write_register(bus, _REG_CALIBRATION, cal)

            # Configure: 32V bus range, 320mV shunt range, 12-bit ADC, continuous mode
            config_value = (
                _CONFIG_BUS_VOLTAGE_RANGE_32V
                | _CONFIG_GAIN_8_320MV
                | _CONFIG_BADC_12BIT
                | _CONFIG_SADC_12BIT
                | _CONFIG_MODE_SANDBVOLT_CONTINUOUS
            )
            self._write_register(bus, _REG_CONFIG, config_value)
            time.sleep(0.01)

    def get_bus_voltage(self):
        """
        Read the bus voltage (V+ terminal).
        This is the battery voltage after the shunt resistor.
        
        Returns:
            float: Voltage in Volts
        """
        with self.mux.channel(self.channel) as bus:
            raw = self._read_register(bus, _REG_BUS_VOLTAGE)

        # Check for overflow
        overflow = raw & 0x01
        # Shift right by 3 bits (per datasheet), multiply by 4mV LSB
        voltage = (raw >> 3) * 0.004

        return voltage

    def get_shunt_voltage(self):
        """
        Read the shunt voltage (voltage across the shunt resistor).
        
        Returns:
            float: Shunt voltage in millivolts
        """
        with self.mux.channel(self.channel) as bus:
            raw = self._read_register(bus, _REG_SHUNT_VOLTAGE)

        # Convert to signed, LSB = 10µV
        return self._to_signed(raw) * 0.01

    def get_current(self):
        """
        Read the current flowing through the shunt resistor.
        
        Returns:
            float: Current in Amps
        """
        with self.mux.channel(self.channel) as bus:
            raw = self._read_register(bus, _REG_CURRENT)

        return self._to_signed(raw) * self._current_lsb

    def get_power(self):
        """
        Read the calculated power.
        
        Returns:
            float: Power in Watts
        """
        with self.mux.channel(self.channel) as bus:
            raw = self._read_register(bus, _REG_POWER)

        return raw * self._power_lsb

    def get_battery_percentage(self):
        """
        Estimate battery percentage based on voltage.
        Uses a simple linear approximation for 3S LiPo.
        
        Returns:
            int: Battery percentage (0-100%)
        """
        voltage = self.get_bus_voltage()

        if voltage >= config.BATTERY_FULL_VOLTAGE:
            return 100
        elif voltage <= config.BATTERY_CRITICAL_VOLTAGE:
            return 0
        else:
            voltage_range = config.BATTERY_FULL_VOLTAGE - config.BATTERY_CRITICAL_VOLTAGE
            voltage_offset = voltage - config.BATTERY_CRITICAL_VOLTAGE
            return int((voltage_offset / voltage_range) * 100)

    def is_battery_low(self):
        """
        Check if battery voltage is below the low threshold.
        
        Returns:
            bool: True if battery is low
        """
        return self.get_bus_voltage() < config.BATTERY_LOW_VOLTAGE

    def is_battery_critical(self):
        """
        Check if battery voltage is critically low.
        
        Returns:
            bool: True if battery is critically low
        """
        return self.get_bus_voltage() < config.BATTERY_CRITICAL_VOLTAGE

    def get_status(self):
        """
        Get complete power monitoring status.
        
        Returns:
            dict: Voltage, current, power, and battery info
        """
        voltage = self.get_bus_voltage()
        current = self.get_current()
        
        return {
            "voltage": round(voltage, 2),
            "current": round(current, 3),
            "power": round(voltage * current, 2),
            "percentage": self.get_battery_percentage(),
            "low_battery": voltage < config.BATTERY_LOW_VOLTAGE,
            "critical": voltage < config.BATTERY_CRITICAL_VOLTAGE,
        }
