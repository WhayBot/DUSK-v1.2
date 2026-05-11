"""
DUSK - GY-87 10-DOF IMU Driver (MPU6050 + HMC5883L + BMP180)

Drop-in replacement for the MPU6050 driver with added:
- Magnetometer (HMC5883L) for absolute heading reference
- Barometer (BMP180) for temperature compensation
- Complementary filter for drift-free heading fusion

I2C topology on GY-87 board:
    Main bus ── MPU6050 (0x68)
                  │ (bypass mode)
                  ├── HMC5883L (0x1E)
                  └── BMP180   (0x77)

All three sensors are accessed through TCA9548A Channel 0
(same channel as MPU6050 standalone).
"""

import time
import math
import struct
import config
from i2c_mux import get_mux
from sensors.sensor_fusion import ComplementaryFilter


# ===========================================================================
# MPU6050 Registers (same as mpu6050.py)
# ===========================================================================
_PWR_MGMT_1 = 0x6B
_USER_CTRL = 0x6A
_INT_PIN_CFG = 0x37
_SMPLRT_DIV = 0x19
_CONFIG = 0x1A
_GYRO_CONFIG = 0x1B
_ACCEL_CONFIG = 0x1C
_ACCEL_XOUT_H = 0x3B
_TEMP_OUT_H = 0x41
_GYRO_XOUT_H = 0x43
_GYRO_ZOUT_H = 0x47
_WHO_AM_I = 0x75

_ACCEL_SCALE_2G = 16384.0
_GYRO_SCALE_250 = 131.0


# ===========================================================================
# HMC5883L Registers
# ===========================================================================
_HMC5883L_ADDR = 0x1E
_HMC_CONFIG_A = 0x00
_HMC_CONFIG_B = 0x01
_HMC_MODE = 0x02
_HMC_DATA_X_H = 0x03       # Data: X_H, X_L, Z_H, Z_L, Y_H, Y_L
_HMC_STATUS = 0x09
_HMC_ID_A = 0x0A            # Should return 'H' (0x48)

# HMC5883L gain settings (register B)
_HMC_GAIN_1370 = 0x00       # +/- 0.88 Ga
_HMC_GAIN_1090 = 0x20       # +/- 1.3 Ga (default, good range)
_HMC_GAIN_820 = 0x40        # +/- 1.9 Ga
_HMC_GAIN_660 = 0x60        # +/- 2.5 Ga
_HMC_GAIN_440 = 0x80        # +/- 4.0 Ga
_HMC_GAIN_390 = 0xA0        # +/- 4.7 Ga
_HMC_GAIN_330 = 0xC0        # +/- 5.6 Ga
_HMC_GAIN_230 = 0xE0        # +/- 8.1 Ga


# ===========================================================================
# BMP180 Registers
# ===========================================================================
_BMP180_ADDR = 0x77
_BMP180_CHIP_ID = 0xD0      # Should return 0x55
_BMP180_CTRL = 0xF4
_BMP180_DATA = 0xF6
_BMP180_CAL_AC1 = 0xAA       # Calibration data start
_BMP180_CMD_TEMP = 0x2E      # Start temperature measurement
_BMP180_CMD_PRES_0 = 0x34    # Start pressure, oversampling 0


class GY87:
    """
    GY-87 10-DOF IMU driver with sensor fusion.

    API-compatible with MPU6050 class (drop-in replacement).
    Adds magnetometer heading and complementary filter fusion
    for drift-free navigation.
    """

    def __init__(self):
        self.mux = get_mux()
        self.channel = config.MUX_CH_MPU6050
        self.mpu_address = config.MPU6050_ADDRESS
        self.accel_scale = _ACCEL_SCALE_2G
        self.gyro_scale = _GYRO_SCALE_250

        # Heading state
        self._heading = 0.0          # Gyro-only heading (legacy compat)
        self._fused_heading = 0.0    # Fused gyro+mag heading
        self._last_time = None
        self._gyro_z_bias = 0.0

        # Magnetometer state
        self._hmc_available = False
        self._mag_declination = getattr(config, 'MAG_DECLINATION', 0.9)
        self._mag_x_offset = 0.0
        self._mag_y_offset = 0.0
        self._mag_z_offset = 0.0
        mag_cal = getattr(config, 'MAG_CALIBRATION', {})
        self._mag_x_offset = mag_cal.get('x_offset', 0.0)
        self._mag_y_offset = mag_cal.get('y_offset', 0.0)
        self._mag_z_offset = mag_cal.get('z_offset', 0.0)

        # BMP180 state
        self._bmp_available = False
        self._bmp_cal = {}
        self._last_temperature = 25.0

        # Sensor fusion
        fusion_alpha = getattr(config, 'FUSION_ALPHA', 0.96)
        self._fusion = ComplementaryFilter(alpha=fusion_alpha)

        # Initialize all sensors
        self._initialize()

    # ===================================================================
    # INITIALIZATION
    # ===================================================================

    def _initialize(self):
        """Initialize MPU6050, then enable bypass and init HMC5883L + BMP180."""
        with self.mux.channel(self.channel) as bus:
            # --- MPU6050 init ---
            who = bus.read_byte_data(self.mpu_address, _WHO_AM_I)
            if who != 0x68:
                raise RuntimeError(
                    f"MPU6050 not found! WHO_AM_I=0x{who:02X}, expected 0x68"
                )

            # Wake up
            bus.write_byte_data(self.mpu_address, _PWR_MGMT_1, 0x00)
            time.sleep(0.1)

            # Sample rate 125Hz
            bus.write_byte_data(self.mpu_address, _SMPLRT_DIV, 7)

            # DLPF ~44Hz bandwidth
            bus.write_byte_data(self.mpu_address, _CONFIG, 0x03)

            # Gyro +-250 deg/s
            bus.write_byte_data(self.mpu_address, _GYRO_CONFIG, 0x00)

            # Accel +-2g
            bus.write_byte_data(self.mpu_address, _ACCEL_CONFIG, 0x00)

            # --- Enable I2C bypass mode ---
            # This connects the aux I2C bus to the main bus,
            # making HMC5883L and BMP180 directly accessible.
            bus.write_byte_data(self.mpu_address, _USER_CTRL, 0x00)
            time.sleep(0.01)
            bus.write_byte_data(self.mpu_address, _INT_PIN_CFG, 0x02)
            time.sleep(0.01)

            print("[GY87] MPU6050 initialized, I2C bypass mode enabled")

        # Init magnetometer
        self._init_hmc5883l()

        # Init barometer
        self._init_bmp180()

        self._last_time = time.time()

    def _init_hmc5883l(self):
        """Initialize the HMC5883L magnetometer."""
        try:
            with self.mux.channel(self.channel) as bus:
                # Verify HMC5883L identity
                id_a = bus.read_byte_data(_HMC5883L_ADDR, _HMC_ID_A)
                if id_a != 0x48:  # 'H'
                    print(f"[GY87] HMC5883L not found (ID=0x{id_a:02X}), skipping magnetometer")
                    return

                # Config Register A:
                # Bits 6:5 = 01 (1 sample average)
                # Bits 4:2 = 100 (15 Hz output rate)
                # Bits 1:0 = 00 (normal measurement mode)
                bus.write_byte_data(_HMC5883L_ADDR, _HMC_CONFIG_A, 0x70)

                # Config Register B: Gain = +/- 1.3 Ga (1090 LSB/Ga)
                bus.write_byte_data(_HMC5883L_ADDR, _HMC_CONFIG_B, _HMC_GAIN_1090)

                # Mode Register: Continuous measurement mode
                bus.write_byte_data(_HMC5883L_ADDR, _HMC_MODE, 0x00)

                time.sleep(0.07)  # Wait for first measurement

                self._hmc_available = True
                print("[GY87] HMC5883L magnetometer initialized")

        except Exception as e:
            print(f"[GY87] HMC5883L init failed: {e}")
            self._hmc_available = False

    def _init_bmp180(self):
        """Initialize the BMP180 barometer and read calibration data."""
        try:
            with self.mux.channel(self.channel) as bus:
                chip_id = bus.read_byte_data(_BMP180_ADDR, _BMP180_CHIP_ID)
                if chip_id != 0x55:
                    print(f"[GY87] BMP180 not found (ID=0x{chip_id:02X}), skipping barometer")
                    return

                # Read calibration coefficients (11 x 16-bit values)
                cal_data = bus.read_i2c_block_data(_BMP180_ADDR, _BMP180_CAL_AC1, 22)
                cal = struct.unpack('>hhhHHHhhhhh', bytes(cal_data))
                self._bmp_cal = {
                    'AC1': cal[0], 'AC2': cal[1], 'AC3': cal[2],
                    'AC4': cal[3], 'AC5': cal[4], 'AC6': cal[5],
                    'B1': cal[6], 'B2': cal[7],
                    'MB': cal[8], 'MC': cal[9], 'MD': cal[10],
                }

                self._bmp_available = True
                print("[GY87] BMP180 barometer initialized")

        except Exception as e:
            print(f"[GY87] BMP180 init failed: {e}")
            self._bmp_available = False

    # ===================================================================
    # MPU6050 METHODS (identical API to mpu6050.py)
    # ===================================================================

    def _read_raw_data(self):
        """Read all 14 bytes of MPU6050 sensor data in one burst."""
        with self.mux.channel(self.channel) as bus:
            data = bus.read_i2c_block_data(self.mpu_address, _ACCEL_XOUT_H, 14)
        return struct.unpack(">hhhhhhh", bytes(data))

    def get_accel(self):
        """Get accelerometer readings in g."""
        raw = self._read_raw_data()
        return {
            "x": raw[0] / self.accel_scale,
            "y": raw[1] / self.accel_scale,
            "z": raw[2] / self.accel_scale,
        }

    def get_gyro(self):
        """Get gyroscope readings in deg/s."""
        raw = self._read_raw_data()
        return {
            "x": raw[4] / self.gyro_scale,
            "y": raw[5] / self.gyro_scale,
            "z": raw[6] / self.gyro_scale,
        }

    def get_temperature(self):
        """Get MPU6050 die temperature in Celsius."""
        raw = self._read_raw_data()
        return (raw[3] / 340.0) + 36.53

    def _read_gyro_z_fast(self):
        """Fast 2-byte read for gyro Z axis only."""
        with self.mux.channel(self.channel) as bus:
            data = bus.read_i2c_block_data(self.mpu_address, _GYRO_ZOUT_H, 2)
        raw_z = (data[0] << 8) | data[1]
        if raw_z > 32767:
            raw_z -= 65536
        return (raw_z / self.gyro_scale) - self._gyro_z_bias

    def get_gyro_z(self):
        """Get Z-axis gyroscope reading (bias-corrected)."""
        return self._read_gyro_z_fast()

    # ===================================================================
    # HMC5883L MAGNETOMETER METHODS
    # ===================================================================

    def _read_mag_raw(self):
        """
        Read raw magnetometer data (X, Y, Z).

        HMC5883L data register order: X_H, X_L, Z_H, Z_L, Y_H, Y_L
        (note: Z comes before Y in the register layout)

        Returns:
            tuple: (x, y, z) raw signed 16-bit values, or None on failure
        """
        if not self._hmc_available:
            return None

        try:
            with self.mux.channel(self.channel) as bus:
                data = bus.read_i2c_block_data(_HMC5883L_ADDR, _HMC_DATA_X_H, 6)

            # Unpack: X, Z, Y (HMC5883L register order)
            x = struct.unpack('>h', bytes(data[0:2]))[0]
            z = struct.unpack('>h', bytes(data[2:4]))[0]
            y = struct.unpack('>h', bytes(data[4:6]))[0]

            # Check for overflow (-4096 means overflow on HMC5883L)
            if x == -4096 or y == -4096 or z == -4096:
                return None

            return (x, y, z)
        except Exception:
            return None

    def get_mag(self):
        """
        Get magnetometer readings with hard-iron correction.

        Returns:
            dict: {"x": float, "y": float, "z": float} in raw units,
                  or None if magnetometer not available
        """
        raw = self._read_mag_raw()
        if raw is None:
            return None

        return {
            "x": raw[0] - self._mag_x_offset,
            "y": raw[1] - self._mag_y_offset,
            "z": raw[2] - self._mag_z_offset,
        }

    def get_mag_heading(self):
        """
        Calculate heading from magnetometer data.

        Assumes the robot is relatively level (which a vacuum robot
        on a flat floor usually is). For tilted operation, tilt
        compensation using accelerometer data would be needed.

        Returns:
            float: Heading in degrees (0-360), 0 = magnetic north,
                   or -1.0 if magnetometer not available
        """
        mag = self.get_mag()
        if mag is None:
            return -1.0

        # atan2(Y, X) gives heading relative to magnetic north
        heading_rad = math.atan2(mag["y"], mag["x"])

        # Apply magnetic declination (true north correction)
        heading_rad += math.radians(self._mag_declination)

        # Convert to degrees
        heading_deg = math.degrees(heading_rad)

        # Normalize to 0-360
        return heading_deg % 360

    # ===================================================================
    # BMP180 BAROMETER METHODS
    # ===================================================================

    def get_temperature_bmp(self):
        """
        Read temperature from BMP180 (more accurate than MPU6050 die temp).

        Returns:
            float: Temperature in Celsius, or last known value on error
        """
        if not self._bmp_available:
            return self._last_temperature

        try:
            with self.mux.channel(self.channel) as bus:
                # Start temperature measurement
                bus.write_byte_data(_BMP180_ADDR, _BMP180_CTRL, _BMP180_CMD_TEMP)

            time.sleep(0.005)  # 4.5ms conversion time

            with self.mux.channel(self.channel) as bus:
                data = bus.read_i2c_block_data(_BMP180_ADDR, _BMP180_DATA, 2)

            raw_temp = (data[0] << 8) | data[1]

            # Apply calibration
            c = self._bmp_cal
            x1 = ((raw_temp - c['AC6']) * c['AC5']) >> 15
            x2 = (c['MC'] << 11) // (x1 + c['MD'])
            b5 = x1 + x2
            temp = (b5 + 8) >> 4
            self._last_temperature = temp / 10.0

            return self._last_temperature

        except Exception:
            return self._last_temperature

    def get_pressure(self):
        """
        Read atmospheric pressure from BMP180.

        Returns:
            float: Pressure in hPa (mbar), or 0 on error
        """
        if not self._bmp_available:
            return 0.0

        try:
            # First get temperature for compensation
            with self.mux.channel(self.channel) as bus:
                bus.write_byte_data(_BMP180_ADDR, _BMP180_CTRL, _BMP180_CMD_TEMP)
            time.sleep(0.005)
            with self.mux.channel(self.channel) as bus:
                temp_data = bus.read_i2c_block_data(_BMP180_ADDR, _BMP180_DATA, 2)
            raw_temp = (temp_data[0] << 8) | temp_data[1]

            # Start pressure measurement (oversampling = 0, fastest)
            with self.mux.channel(self.channel) as bus:
                bus.write_byte_data(_BMP180_ADDR, _BMP180_CTRL, _BMP180_CMD_PRES_0)
            time.sleep(0.005)
            with self.mux.channel(self.channel) as bus:
                pres_data = bus.read_i2c_block_data(_BMP180_ADDR, _BMP180_DATA, 2)
            raw_pres = (pres_data[0] << 8) | pres_data[1]

            # Compensate using calibration
            c = self._bmp_cal
            oss = 0  # Oversampling setting

            # Temperature compensation
            x1 = ((raw_temp - c['AC6']) * c['AC5']) >> 15
            x2 = (c['MC'] << 11) // (x1 + c['MD'])
            b5 = x1 + x2

            # Pressure compensation
            b6 = b5 - 4000
            x1 = (c['B2'] * ((b6 * b6) >> 12)) >> 11
            x2 = (c['AC2'] * b6) >> 11
            x3 = x1 + x2
            b3 = (((c['AC1'] * 4 + x3) << oss) + 2) // 4
            x1 = (c['AC3'] * b6) >> 13
            x2 = (c['B1'] * ((b6 * b6) >> 12)) >> 16
            x3 = ((x1 + x2) + 2) >> 2
            b4 = (c['AC4'] * (x3 + 32768)) >> 15
            b7 = (raw_pres - b3) * (50000 >> oss)

            if b7 < 0x80000000:
                p = (b7 * 2) // b4
            else:
                p = (b7 // b4) * 2

            x1 = (p >> 8) * (p >> 8)
            x1 = (x1 * 3038) >> 16
            x2 = (-7357 * p) >> 16
            p = p + ((x1 + x2 + 3791) >> 4)

            return p / 100.0  # Convert Pa to hPa

        except Exception:
            return 0.0

    # ===================================================================
    # HEADING (compatible with MPU6050 API + sensor fusion)
    # ===================================================================

    def update_heading(self):
        """
        Update heading using sensor fusion (gyro + magnetometer).

        When magnetometer is available, uses complementary filter
        to produce drift-free heading. Falls back to gyro-only
        integration when magnetometer is unavailable.

        Returns:
            float: Current fused heading in degrees (0-360)
        """
        current_time = time.time()
        dt = current_time - self._last_time
        self._last_time = current_time

        gyro_z = self._read_gyro_z_fast()

        if self._hmc_available:
            # Sensor fusion path: gyro + magnetometer
            mag_heading = self.get_mag_heading()

            if mag_heading >= 0:
                self._fused_heading = self._fusion.update(gyro_z, mag_heading, dt)
                # Also update legacy heading for API compatibility
                self._heading = self._fused_heading
            else:
                # Mag read failed, fall back to gyro only
                self._gyro_only_update(gyro_z, dt)
        else:
            # No magnetometer, pure gyro integration
            self._gyro_only_update(gyro_z, dt)

        return self._heading

    def _gyro_only_update(self, gyro_z, dt):
        """Fallback: gyro-only heading integration."""
        if abs(gyro_z) > 0.5:
            self._heading += gyro_z * dt
        self._heading = self._heading % 360
        self._fused_heading = self._heading

    def get_heading(self):
        """Get current heading (fused if magnetometer available)."""
        return self._heading

    def get_fused_heading(self):
        """Get the complementary-filter fused heading."""
        return self._fused_heading

    def reset_heading(self, value=0.0):
        """Reset heading to a specified value."""
        self._heading = value % 360
        self._fused_heading = self._heading
        self._fusion.reset(self._heading)
        self._last_time = time.time()

    def get_all(self):
        """Get all sensor readings at once."""
        raw = self._read_raw_data()
        result = {
            "accel": {
                "x": raw[0] / self.accel_scale,
                "y": raw[1] / self.accel_scale,
                "z": raw[2] / self.accel_scale,
            },
            "gyro": {
                "x": raw[4] / self.gyro_scale,
                "y": raw[5] / self.gyro_scale,
                "z": raw[6] / self.gyro_scale,
            },
            "temperature": (raw[3] / 340.0) + 36.53,
            "heading": self._heading,
            "fused_heading": self._fused_heading,
        }

        if self._hmc_available:
            result["mag"] = self.get_mag()
            result["mag_heading"] = self.get_mag_heading()

        if self._bmp_available:
            result["temperature_bmp"] = self._last_temperature

        return result

    # ===================================================================
    # CALIBRATION
    # ===================================================================

    def calibrate_gyro(self, samples=200, settle_time=0.0):
        """
        Calibrate gyroscope Z-axis bias (identical to MPU6050 version).

        Args:
            samples: Number of samples to average
            settle_time: Seconds to wait before sampling

        Returns:
            float: Gyro Z bias in deg/s
        """
        if settle_time > 0:
            time.sleep(settle_time)

        old_bias = self._gyro_z_bias
        self._gyro_z_bias = 0.0

        bias_sum = 0.0
        for _ in range(samples):
            bias_sum += self._read_gyro_z_fast()
            time.sleep(0.005)

        self._gyro_z_bias = bias_sum / samples
        return self._gyro_z_bias

    def calibrate_magnetometer(self, duration=15):
        """
        Calibrate magnetometer hard-iron offset.

        Slowly rotate the robot 360 degrees during the calibration
        period. Records min/max for X and Y axes and computes
        the center offset.

        Args:
            duration: Calibration duration in seconds.
                      Robot should complete at least one full
                      rotation during this time.

        Returns:
            dict: Calibration offsets {"x_offset", "y_offset", "z_offset"}
        """
        if not self._hmc_available:
            print("[GY87] Magnetometer not available for calibration")
            return {"x_offset": 0, "y_offset": 0, "z_offset": 0}

        print(f"[GY87] Magnetometer calibration starting ({duration}s)")
        print("[GY87] Slowly rotate the robot 360 degrees...")

        x_min = float('inf')
        x_max = float('-inf')
        y_min = float('inf')
        y_max = float('-inf')
        z_min = float('inf')
        z_max = float('-inf')

        end_time = time.time() + duration
        sample_count = 0

        while time.time() < end_time:
            raw = self._read_mag_raw()
            if raw:
                x, y, z = raw
                x_min = min(x_min, x)
                x_max = max(x_max, x)
                y_min = min(y_min, y)
                y_max = max(y_max, y)
                z_min = min(z_min, z)
                z_max = max(z_max, z)
                sample_count += 1
            time.sleep(0.05)

        if sample_count < 10:
            print("[GY87] Not enough samples for calibration!")
            return {"x_offset": 0, "y_offset": 0, "z_offset": 0}

        # Hard-iron offset = center of the min/max ellipse
        self._mag_x_offset = (x_min + x_max) / 2
        self._mag_y_offset = (y_min + y_max) / 2
        self._mag_z_offset = (z_min + z_max) / 2

        offsets = {
            "x_offset": self._mag_x_offset,
            "y_offset": self._mag_y_offset,
            "z_offset": self._mag_z_offset,
        }

        print(f"[GY87] Magnetometer calibrated ({sample_count} samples)")
        print(f"[GY87] Offsets: X={self._mag_x_offset:.1f}, "
              f"Y={self._mag_y_offset:.1f}, Z={self._mag_z_offset:.1f}")
        print(f"[GY87] Update MAG_CALIBRATION in config.py with these values")

        return offsets

    # ===================================================================
    # STATUS
    # ===================================================================

    def is_running(self):
        """Check if the OLED animation loop is running."""
        return self._last_time is not None

    def force_blink(self):
        """Compatibility stub (not applicable for IMU)."""
        pass

    def get_sensor_info(self):
        """Get information about available sensors."""
        return {
            "type": "GY-87",
            "mpu6050": True,
            "hmc5883l": self._hmc_available,
            "bmp180": self._bmp_available,
            "fusion": self._hmc_available,
            "mag_declination": self._mag_declination,
        }
