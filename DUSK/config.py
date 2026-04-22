"""
DUSK - Dust Unification and Sweeping Keeper
Central Configuration File

All GPIO pin assignments, I2C channel mappings, and system constants.
"""

# ==============================================================================
# I2C CONFIGURATION
# ==============================================================================
# Virtual I2C bus on GPIO5(SDA) / GPIO6(SCL)
# Configured via dtoverlay=i2c-gpio in /boot/config.txt
I2C_BUS_NUMBER = 3  # Virtual I2C bus number (set in dtoverlay)
I2C_SDA_GPIO = 5
I2C_SCL_GPIO = 6

# TCA9548A I2C Multiplexer
TCA9548A_ADDRESS = 0x70

# TCA9548A Channel Assignments
MUX_CH_MPU6050 = 0       # MPU6050 Gyro + Accelerometer
MUX_CH_OLED_LEFT = 1     # OLED 1.3" Left Eye
MUX_CH_OLED_RIGHT = 2    # OLED 1.3" Right Eye
MUX_CH_VL53L0X_LEFT = 3  # ToF Sensor Left (30° left)
MUX_CH_VL53L0X_RIGHT = 4 # ToF Sensor Right (30° right)
MUX_CH_INA219 = 5        # Power Monitor

# ==============================================================================
# SENSOR I2C ADDRESSES
# ==============================================================================
MPU6050_ADDRESS = 0x68
VL53L0X_ADDRESS = 0x29
INA219_ADDRESS = 0x40
OLED_ADDRESS = 0x3C

# ==============================================================================
# GPIO PIN ASSIGNMENTS (BCM Numbering)
# ==============================================================================

# --- Speed Encoders ---
ENCODER_LEFT_PIN = 14    # GPIO14 - Left encoder DO
ENCODER_RIGHT_PIN = 7    # GPIO7  - Right encoder DO

# --- L298N Motor Driver - Geared Wheel Motors ---
MOTOR_LEFT_ENA = 10      # GPIO10 - Left motor PWM enable
MOTOR_LEFT_IN1 = 12      # GPIO12 - Left motor direction 1
MOTOR_LEFT_IN2 = 13      # GPIO13 - Left motor direction 2
MOTOR_RIGHT_IN3 = 19     # GPIO19 - Right motor direction 1
MOTOR_RIGHT_IN4 = 16     # GPIO16 - Right motor direction 2
MOTOR_RIGHT_ENB = 9      # GPIO9  - Right motor PWM enable

# --- L298N Motor Driver - N20 Sweeper Motors ---
SWEEPER_ENA = 26         # GPIO26 - Sweeper PWM enable
SWEEPER_IN1 = 24         # GPIO24 - Sweeper direction 1
SWEEPER_IN2 = 25         # GPIO25 - Sweeper direction 2

# --- ESC Brushless Vacuum Motor ---
ESC_GPIO = 18            # GPIO18 - ESC signal (Hardware PWM)

# ==============================================================================
# MOTOR PARAMETERS
# ==============================================================================
MOTOR_PWM_FREQ = 1000    # PWM frequency for DC motors (Hz)
MOTOR_DEFAULT_SPEED = 60  # Default motor speed (0-100%)
MOTOR_TURN_SPEED = 50     # Speed during turns (0-100%)
MOTOR_MAX_SPEED = 100     # Maximum motor speed (0-100%)

# ESC Parameters (pulse width in microseconds)
ESC_MIN_PULSE = 1000     # Motor off
ESC_MAX_PULSE = 2000     # Full throttle
ESC_ARM_PULSE = 1000     # Arming pulse
ESC_IDLE_PULSE = 1150    # Minimum running speed
ESC_DEFAULT_SPEED = 50   # Default vacuum speed (0-100%)

# Sweeper Parameters
SWEEPER_DEFAULT_SPEED = 70  # Default sweeper speed (0-100%)

# ==============================================================================
# NAVIGATION PARAMETERS
# ==============================================================================
ZIGZAG_STRAIGHT_DISTANCE = 1000   # mm - distance to travel in straight line
ZIGZAG_SHIFT_DISTANCE = 250       # mm - distance to shift sideways (robot width)
OBSTACLE_THRESHOLD_MM = 150       # mm - obstacle detection threshold
ENCODER_PULSES_PER_REV = 20       # Pulses per wheel revolution
WHEEL_DIAMETER_MM = 65            # Wheel diameter in mm
WHEEL_CIRCUMFERENCE_MM = 204.2    # pi * WHEEL_DIAMETER_MM

# PID Constants for straight-line driving
PID_KP = 2.0
PID_KI = 0.1
PID_KD = 0.5

# Turn parameters
TURN_ANGLE_90 = 90       # degrees
TURN_TOLERANCE = 3       # degrees tolerance for turn completion
GYRO_SCALE = 131.0       # MPU6050 gyro sensitivity at ±250°/s

# ==============================================================================
# OLED DISPLAY PARAMETERS
# ==============================================================================
OLED_WIDTH = 128
OLED_HEIGHT = 64
BLINK_INTERVAL_MIN = 3   # seconds - minimum time between blinks
BLINK_INTERVAL_MAX = 7   # seconds - maximum time between blinks
BLINK_DURATION = 0.15    # seconds - how long a blink lasts

# ==============================================================================
# WEB SERVER PARAMETERS
# ==============================================================================
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
CAMERA_RESOLUTION = (480, 360)   # Reduced for Pi Zero 2W
CAMERA_FRAMERATE = 15            # Reduced for Pi Zero 2W

# ==============================================================================
# BATTERY PARAMETERS (3S LiPo)
# ==============================================================================
BATTERY_CELLS = 3
BATTERY_FULL_VOLTAGE = 12.6      # 4.2V × 3
BATTERY_NOMINAL_VOLTAGE = 11.1   # 3.7V × 3
BATTERY_LOW_VOLTAGE = 10.5       # 3.5V × 3
BATTERY_CRITICAL_VOLTAGE = 9.9   # 3.3V × 3
BATTERY_MAX_CURRENT = 10.0       # Amps - max expected current

# INA219 Configuration
INA219_SHUNT_OHMS = 0.1          # Shunt resistor value (ohms)
INA219_MAX_EXPECTED_AMPS = 10.0
