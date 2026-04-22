"""
DUSK - VL53L0X Time-of-Flight Distance Sensor Driver

Raw I2C register access implementation (no external library needed).
Two sensors: left (30° left) and right (30° right) mounted on the robot.
Connected through TCA9548A Channels 3 (left) and 4 (right).
"""

import time
import config
from i2c_mux import get_mux


# VL53L0X Register Map
_SYSRANGE_START = 0x00
_SYSTEM_THRESH_HIGH = 0x0C
_SYSTEM_THRESH_LOW = 0x0E
_SYSTEM_SEQUENCE_CONFIG = 0x01
_SYSTEM_INTERMEASUREMENT_PERIOD = 0x04
_SYSTEM_INTERRUPT_CONFIG_GPIO = 0x0A
_GPIO_HV_MUX_ACTIVE_HIGH = 0x84
_SYSTEM_INTERRUPT_CLEAR = 0x0B
_RESULT_INTERRUPT_STATUS = 0x13
_RESULT_RANGE_STATUS = 0x14
_RESULT_CORE_AMBIENT_WINDOW_EVENTS_RTN = 0xBC
_RESULT_CORE_RANGING_TOTAL_EVENTS_RTN = 0xC0
_RESULT_CORE_AMBIENT_WINDOW_EVENTS_REF = 0xD0
_RESULT_CORE_RANGING_TOTAL_EVENTS_REF = 0xD4
_RESULT_PEAK_SIGNAL_RATE_REF = 0xB6
_ALGO_PART_TO_PART_RANGE_OFFSET_MM = 0x28
_I2C_SLAVE_DEVICE_ADDRESS = 0x8A
_MSRC_CONFIG_CONTROL = 0x60
_PRE_RANGE_CONFIG_MIN_SNR = 0x27
_PRE_RANGE_CONFIG_VALID_PHASE_LOW = 0x56
_PRE_RANGE_CONFIG_VALID_PHASE_HIGH = 0x57
_PRE_RANGE_MIN_COUNT_RATE_RTN_LIMIT = 0x64
_FINAL_RANGE_CONFIG_MIN_SNR = 0x67
_FINAL_RANGE_CONFIG_VALID_PHASE_LOW = 0x47
_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH = 0x48
_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT = 0x44
_PRE_RANGE_CONFIG_SIGMA_THRESH_HI = 0x61
_PRE_RANGE_CONFIG_SIGMA_THRESH_LO = 0x62
_PRE_RANGE_CONFIG_VCSEL_PERIOD = 0x50
_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI = 0x51
_PRE_RANGE_CONFIG_TIMEOUT_MACROP_LO = 0x52
_SYSTEM_HISTOGRAM_BIN = 0x81
_HISTOGRAM_CONFIG_INITIAL_PHASE_SELECT = 0x33
_HISTOGRAM_CONFIG_READOUT_CTRL = 0x55
_FINAL_RANGE_CONFIG_VCSEL_PERIOD = 0x70
_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI = 0x71
_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_LO = 0x72
_CROSSTALK_COMPENSATION_PEAK_RATE_MCPS = 0x20
_MSRC_CONFIG_TIMEOUT_MACROP = 0x46
_SOFT_RESET_GO2_SOFT_RESET_N = 0xBF
_IDENTIFICATION_MODEL_ID = 0xC0
_IDENTIFICATION_REVISION_ID = 0xC2
_OSC_CALIBRATE_VAL = 0xF8
_GLOBAL_CONFIG_VCSEL_WIDTH = 0x32
_GLOBAL_CONFIG_SPAD_ENABLES_REF_0 = 0xB0
_GLOBAL_CONFIG_SPAD_ENABLES_REF_1 = 0xB1
_GLOBAL_CONFIG_SPAD_ENABLES_REF_2 = 0xB2
_GLOBAL_CONFIG_SPAD_ENABLES_REF_3 = 0xB3
_GLOBAL_CONFIG_SPAD_ENABLES_REF_4 = 0xB4
_GLOBAL_CONFIG_SPAD_ENABLES_REF_5 = 0xB5
_GLOBAL_CONFIG_REF_EN_START_SELECT = 0xB6
_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD = 0x4E
_DYNAMIC_SPAD_REF_EN_START_OFFSET = 0x4F
_POWER_MANAGEMENT_GO1_POWER_FORCE = 0x80
_VHV_CONFIG_PAD_SCL_SDA__EXTSUP_HV = 0x89
_ALGO_PHASECAL_LIM = 0x30
_ALGO_PHASECAL_CONFIG_TIMEOUT = 0x30


class VL53L0X:
    """
    VL53L0X Time-of-Flight distance sensor driver.
    
    Uses simplified initialization and single-shot ranging.
    Each instance manages one sensor through the I2C multiplexer.
    """

    def __init__(self, mux_channel, name="VL53L0X"):
        self.mux = get_mux()
        self.channel = mux_channel
        self.address = config.VL53L0X_ADDRESS
        self.name = name
        self._initialized = False
        self._last_distance = 0

        self._initialize()

    def _write_byte(self, bus, reg, value):
        """Write a single byte to a register."""
        bus.write_byte_data(self.address, reg, value)

    def _read_byte(self, bus, reg):
        """Read a single byte from a register."""
        return bus.read_byte_data(self.address, reg)

    def _write_word(self, bus, reg, value):
        """Write a 16-bit word to a register (big-endian)."""
        bus.write_byte_data(self.address, reg, (value >> 8) & 0xFF)
        bus.write_byte_data(self.address, reg + 1, value & 0xFF)

    def _read_word(self, bus, reg):
        """Read a 16-bit word from a register (big-endian)."""
        high = bus.read_byte_data(self.address, reg)
        low = bus.read_byte_data(self.address, reg + 1)
        return (high << 8) | low

    def _initialize(self):
        """Initialize the VL53L0X sensor with default settings."""
        with self.mux.channel(self.channel) as bus:
            # Check model ID
            model_id = self._read_byte(bus, _IDENTIFICATION_MODEL_ID)
            if model_id != 0xEE:
                raise RuntimeError(
                    f"{self.name}: VL53L0X not found! Model ID: 0x{model_id:02X}, expected 0xEE"
                )

            # Set 2.8V mode
            val = self._read_byte(bus, _VHV_CONFIG_PAD_SCL_SDA__EXTSUP_HV)
            self._write_byte(bus, _VHV_CONFIG_PAD_SCL_SDA__EXTSUP_HV, val | 0x01)

            # Standard I2C mode
            self._write_byte(bus, 0x88, 0x00)
            self._write_byte(bus, 0x80, 0x01)
            self._write_byte(bus, 0xFF, 0x01)
            self._write_byte(bus, 0x00, 0x00)

            self._stop_variable = self._read_byte(bus, 0x91)

            self._write_byte(bus, 0x00, 0x01)
            self._write_byte(bus, 0xFF, 0x00)
            self._write_byte(bus, 0x80, 0x00)

            # Set signal rate limit to 0.25 MCPS
            self._write_word(bus, _FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT, 
                           int(0.25 * (1 << 7)))

            self._write_byte(bus, _SYSTEM_SEQUENCE_CONFIG, 0xFF)

            # Set measurement timing budget to ~33ms (default)
            self._write_byte(bus, _SYSTEM_SEQUENCE_CONFIG, 0xE8)

            # Set VCSEL periods
            self._write_byte(bus, _PRE_RANGE_CONFIG_VCSEL_PERIOD, 0x0C)  # 14 clocks
            self._write_byte(bus, _FINAL_RANGE_CONFIG_VCSEL_PERIOD, 0x08)  # 10 clocks

            self._initialized = True

    def read_distance(self):
        """
        Perform a single-shot range measurement.
        
        Returns:
            int: Distance in millimeters. Returns 8190 if out of range.
        """
        if not self._initialized:
            return 8190

        try:
            with self.mux.channel(self.channel) as bus:
                # Start single-shot measurement
                self._write_byte(bus, 0x80, 0x01)
                self._write_byte(bus, 0xFF, 0x01)
                self._write_byte(bus, 0x00, 0x00)
                self._write_byte(bus, 0x91, self._stop_variable)
                self._write_byte(bus, 0x00, 0x01)
                self._write_byte(bus, 0xFF, 0x00)
                self._write_byte(bus, 0x80, 0x00)

                self._write_byte(bus, _SYSRANGE_START, 0x01)

                # Wait for measurement start
                timeout = time.time() + 0.5
                while True:
                    val = self._read_byte(bus, _SYSRANGE_START)
                    if val & 0x01 == 0:
                        break
                    if time.time() > timeout:
                        return self._last_distance
                    time.sleep(0.001)

                # Wait for measurement complete
                timeout = time.time() + 0.5
                while True:
                    val = self._read_byte(bus, _RESULT_INTERRUPT_STATUS)
                    if val & 0x07 != 0:
                        break
                    if time.time() > timeout:
                        return self._last_distance
                    time.sleep(0.001)

                # Read range result (mm)
                distance = self._read_word(bus, _RESULT_RANGE_STATUS + 10)

                # Clear interrupt
                self._write_byte(bus, _SYSTEM_INTERRUPT_CLEAR, 0x01)

                # Validate range
                if distance > 0 and distance < 8190:
                    self._last_distance = distance
                    return distance
                else:
                    return self._last_distance

        except Exception:
            return self._last_distance

    def is_obstacle_detected(self, threshold_mm=None):
        """
        Check if an obstacle is within the threshold distance.
        
        Args:
            threshold_mm: Detection threshold in mm (default from config)
            
        Returns:
            bool: True if obstacle detected
        """
        if threshold_mm is None:
            threshold_mm = config.OBSTACLE_THRESHOLD_MM
        
        distance = self.read_distance()
        return 0 < distance < threshold_mm


class DualVL53L0X:
    """
    Manager for the two VL53L0X sensors (left and right).
    Provides convenience methods for obstacle detection.
    """

    def __init__(self):
        self.left = VL53L0X(config.MUX_CH_VL53L0X_LEFT, "VL53L0X_Left")
        self.right = VL53L0X(config.MUX_CH_VL53L0X_RIGHT, "VL53L0X_Right")

    def get_distances(self):
        """
        Read both sensor distances.
        
        Returns:
            dict: {"left": int, "right": int} distances in mm
        """
        return {
            "left": self.left.read_distance(),
            "right": self.right.read_distance(),
        }

    def check_obstacles(self, threshold_mm=None):
        """
        Check both sensors for obstacles.
        
        Returns:
            dict: {"left": bool, "right": bool, "any": bool}
        """
        left_obs = self.left.is_obstacle_detected(threshold_mm)
        right_obs = self.right.is_obstacle_detected(threshold_mm)
        return {
            "left": left_obs,
            "right": right_obs,
            "any": left_obs or right_obs,
        }

    def get_status(self):
        """Get complete sensor status."""
        distances = self.get_distances()
        return {
            "left_mm": distances["left"],
            "right_mm": distances["right"],
            "left_obstacle": distances["left"] < config.OBSTACLE_THRESHOLD_MM,
            "right_obstacle": distances["right"] < config.OBSTACLE_THRESHOLD_MM,
        }
