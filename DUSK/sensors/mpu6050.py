"""
DUSK - MPU6050 Gyroscope + Accelerometer Driver

Provides heading (yaw) tracking and tilt detection via I2C.
Connected through TCA9548A Channel 0.
"""

import time
import struct
import config
from i2c_mux import get_mux


# MPU6050 Register Map
_PWR_MGMT_1 = 0x6B
_SMPLRT_DIV = 0x19
_CONFIG = 0x1A
_GYRO_CONFIG = 0x1B
_ACCEL_CONFIG = 0x1C
_ACCEL_XOUT_H = 0x3B
_TEMP_OUT_H = 0x41
_GYRO_XOUT_H = 0x43
_GYRO_ZOUT_H = 0x47
_WHO_AM_I = 0x75

# Sensitivity scale factors
_ACCEL_SCALE_2G = 16384.0
_ACCEL_SCALE_4G = 8192.0
_ACCEL_SCALE_8G = 4096.0
_ACCEL_SCALE_16G = 2048.0

_GYRO_SCALE_250 = 131.0
_GYRO_SCALE_500 = 65.5
_GYRO_SCALE_1000 = 32.8
_GYRO_SCALE_2000 = 16.4


class MPU6050:
    """
    MPU6050 6-axis IMU driver.
    
    Provides accelerometer (X, Y, Z) and gyroscope (X, Y, Z) readings.
    Uses complementary filter for heading estimation.
    """

    def __init__(self):
        self.mux = get_mux()
        self.channel = config.MUX_CH_MPU6050
        self.address = config.MPU6050_ADDRESS
        self.accel_scale = _ACCEL_SCALE_2G
        self.gyro_scale = _GYRO_SCALE_250

        self._heading = 0.0
        self._last_time = None
        self._gyro_z_bias = 0.0  # Set by calibrate_gyro()

        self._initialize()

    def _initialize(self):
        """Wake up the MPU6050 and configure it."""
        with self.mux.channel(self.channel) as bus:
            # Check WHO_AM_I register
            who = bus.read_byte_data(self.address, _WHO_AM_I)
            if who != 0x68:
                raise RuntimeError(
                    f"MPU6050 not found! WHO_AM_I returned 0x{who:02X}, expected 0x68"
                )

            # Wake up from sleep mode
            bus.write_byte_data(self.address, _PWR_MGMT_1, 0x00)
            time.sleep(0.1)

            # Set sample rate divisor: Sample Rate = 1kHz / (1 + SMPLRT_DIV)
            # SMPLRT_DIV = 7 → 125 Hz sample rate
            bus.write_byte_data(self.address, _SMPLRT_DIV, 7)

            # Set DLPF (Digital Low Pass Filter) to ~44Hz bandwidth
            bus.write_byte_data(self.address, _CONFIG, 0x03)

            # Set gyroscope range to ±250°/s
            bus.write_byte_data(self.address, _GYRO_CONFIG, 0x00)

            # Set accelerometer range to ±2g
            bus.write_byte_data(self.address, _ACCEL_CONFIG, 0x00)

            time.sleep(0.05)

        self._last_time = time.time()

    def _read_raw_data(self):
        """
        Read all 14 bytes of sensor data in one burst.
        
        Returns:
            tuple: (accel_x, accel_y, accel_z, temp, gyro_x, gyro_y, gyro_z)
                   All values are raw 16-bit signed integers.
        """
        with self.mux.channel(self.channel) as bus:
            data = bus.read_i2c_block_data(self.address, _ACCEL_XOUT_H, 14)

        values = struct.unpack(">hhhhhhh", bytes(data))
        return values

    def get_accel(self):
        """
        Get accelerometer readings in g (gravitational acceleration).
        
        Returns:
            dict: {"x": float, "y": float, "z": float} in g units
        """
        raw = self._read_raw_data()
        return {
            "x": raw[0] / self.accel_scale,
            "y": raw[1] / self.accel_scale,
            "z": raw[2] / self.accel_scale,
        }

    def get_gyro(self):
        """
        Get gyroscope readings in degrees/second.
        
        Returns:
            dict: {"x": float, "y": float, "z": float} in °/s
        """
        raw = self._read_raw_data()
        return {
            "x": raw[4] / self.gyro_scale,
            "y": raw[5] / self.gyro_scale,
            "z": raw[6] / self.gyro_scale,
        }

    def get_temperature(self):
        """
        Get temperature reading in Celsius.
        
        Returns:
            float: Temperature in °C
        """
        raw = self._read_raw_data()
        return (raw[3] / 340.0) + 36.53

    def _read_gyro_z_fast(self):
        """
        Fast path: read only the 2 gyro-Z bytes instead of all 14.
        Reduces I2C transaction size by 85% for heading updates.
        
        Returns:
            float: Yaw rate in deg/s (bias-corrected)
        """
        with self.mux.channel(self.channel) as bus:
            data = bus.read_i2c_block_data(self.address, _GYRO_ZOUT_H, 2)
        raw_z = (data[0] << 8) | data[1]
        if raw_z > 32767:
            raw_z -= 65536
        return (raw_z / self.gyro_scale) - self._gyro_z_bias

    def get_gyro_z(self):
        """
        Get only the Z-axis gyroscope reading (yaw rate).
        Uses fast 2-byte read path.
        
        Returns:
            float: Yaw rate in deg/s (bias-corrected)
        """
        return self._read_gyro_z_fast()

    def update_heading(self):
        """
        Update the integrated heading using gyroscope Z-axis.
        Must be called frequently (in the main loop) for accuracy.
        
        Returns:
            float: Current heading in degrees (0-360)
        """
        current_time = time.time()
        dt = current_time - self._last_time
        self._last_time = current_time

        gyro_z = self._read_gyro_z_fast()

        # Dead-zone filter: ignore very small rotations (noise)
        if abs(gyro_z) > 0.5:
            self._heading += gyro_z * dt

        # Normalize to 0-360°
        self._heading = self._heading % 360

        return self._heading

    def get_heading(self):
        """
        Get the current integrated heading.
        
        Returns:
            float: Current heading in degrees (0-360)
        """
        return self._heading

    def reset_heading(self, value=0.0):
        """
        Reset the heading to a specified value.
        
        Args:
            value: New heading value in degrees
        """
        self._heading = value % 360
        self._last_time = time.time()

    def get_all(self):
        """
        Get all sensor readings at once.
        
        Returns:
            dict: All accelerometer, gyroscope, temperature, and heading data
        """
        raw = self._read_raw_data()
        return {
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
        }

    def calibrate_gyro(self, samples=200, settle_time=0.0):
        """
        Calibrate gyroscope by measuring Z-axis bias at rest.
        Robot must be stationary during calibration.
        Uses fast 2-byte reads for efficiency.
        
        For best results during auto mode, call this AFTER starting
        vacuum and sweeper motors so the bias measurement includes
        motor vibration noise. Use settle_time to let vibrations
        stabilize before sampling begins.
        
        Args:
            samples: Number of samples to average
            settle_time: Seconds to wait before sampling starts.
                         Use 1-2s after motors start to let
                         vibrations reach steady state.
            
        Returns:
            float: Gyro Z bias in deg/s
        """
        # Wait for vibrations to reach steady state
        if settle_time > 0:
            time.sleep(settle_time)

        # Temporarily zero the bias for raw readings
        old_bias = self._gyro_z_bias
        self._gyro_z_bias = 0.0

        bias_sum = 0.0
        for _ in range(samples):
            bias_sum += self._read_gyro_z_fast()
            time.sleep(0.005)

        self._gyro_z_bias = bias_sum / samples
        return self._gyro_z_bias
