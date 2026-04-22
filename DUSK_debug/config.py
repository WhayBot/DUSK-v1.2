"""
DUSK - Debug/Simulation Version
Central Configuration File

Same as production config but with DEBUG_MODE flag.
All hardware constants are kept for reference even though
hardware is simulated in this version.
"""

# ==============================================================================
# DEBUG MODE FLAG
# ==============================================================================
DEBUG_MODE = True  # Enables simulated hardware

# ==============================================================================
# I2C CONFIGURATION (simulated in debug mode)
# ==============================================================================
I2C_BUS_NUMBER = 3
I2C_SDA_GPIO = 5
I2C_SCL_GPIO = 6

TCA9548A_ADDRESS = 0x70

MUX_CH_MPU6050 = 0
MUX_CH_OLED_LEFT = 1
MUX_CH_OLED_RIGHT = 2
MUX_CH_VL53L0X_LEFT = 3
MUX_CH_VL53L0X_RIGHT = 4
MUX_CH_INA219 = 5

# ==============================================================================
# SENSOR I2C ADDRESSES (reference only in debug mode)
# ==============================================================================
MPU6050_ADDRESS = 0x68
VL53L0X_ADDRESS = 0x29
INA219_ADDRESS = 0x40
OLED_ADDRESS = 0x3C

# ==============================================================================
# GPIO PIN ASSIGNMENTS (reference only in debug mode)
# ==============================================================================
ENCODER_LEFT_PIN = 14
ENCODER_RIGHT_PIN = 7

MOTOR_LEFT_ENA = 10
MOTOR_LEFT_IN1 = 12
MOTOR_LEFT_IN2 = 13
MOTOR_RIGHT_IN3 = 19
MOTOR_RIGHT_IN4 = 16
MOTOR_RIGHT_ENB = 9

SWEEPER_ENA = 26
SWEEPER_IN1 = 24
SWEEPER_IN2 = 25

ESC_GPIO = 18

# ==============================================================================
# MOTOR PARAMETERS
# ==============================================================================
MOTOR_PWM_FREQ = 1000
MOTOR_DEFAULT_SPEED = 60
MOTOR_TURN_SPEED = 50
MOTOR_MAX_SPEED = 100

ESC_MIN_PULSE = 1000
ESC_MAX_PULSE = 2000
ESC_ARM_PULSE = 1000
ESC_IDLE_PULSE = 1150
ESC_DEFAULT_SPEED = 50

SWEEPER_DEFAULT_SPEED = 70

# ==============================================================================
# NAVIGATION PARAMETERS
# ==============================================================================
ZIGZAG_STRAIGHT_DISTANCE = 1000
ZIGZAG_SHIFT_DISTANCE = 250
OBSTACLE_THRESHOLD_MM = 150
ENCODER_PULSES_PER_REV = 20
WHEEL_DIAMETER_MM = 65
WHEEL_CIRCUMFERENCE_MM = 204.2

PID_KP = 2.0
PID_KI = 0.1
PID_KD = 0.5

TURN_ANGLE_90 = 90
TURN_TOLERANCE = 3
GYRO_SCALE = 131.0

# ==============================================================================
# OLED DISPLAY PARAMETERS
# ==============================================================================
OLED_WIDTH = 128
OLED_HEIGHT = 64
BLINK_INTERVAL_MIN = 3
BLINK_INTERVAL_MAX = 7
BLINK_DURATION = 0.15

# ==============================================================================
# WEB SERVER PARAMETERS
# ==============================================================================
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
CAMERA_RESOLUTION = (480, 360)
CAMERA_FRAMERATE = 15

# ==============================================================================
# BATTERY PARAMETERS (3S LiPo - simulated)
# ==============================================================================
BATTERY_CELLS = 3
BATTERY_FULL_VOLTAGE = 12.6
BATTERY_NOMINAL_VOLTAGE = 11.1
BATTERY_LOW_VOLTAGE = 10.5
BATTERY_CRITICAL_VOLTAGE = 9.9
BATTERY_MAX_CURRENT = 10.0

INA219_SHUNT_OHMS = 0.1
INA219_MAX_EXPECTED_AMPS = 10.0
