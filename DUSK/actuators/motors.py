"""
DUSK - Wheel Motor Controller (RPi.GPIO Version)

Controls two geared DC motors through L298N motor driver.
Left motor:  ENA=GPIO10, IN1=GPIO12, IN2=GPIO13
Right motor: IN3=GPIO19, IN4=GPIO16, ENB=GPIO9

Uses differential drive for forward, backward, turning, and spinning.
"""

import RPi.GPIO as GPIO
import config


class WheelMotors:
    """
    Dual DC motor controller via L298N H-bridge driver.
    
    Supports differential drive with independent speed control
    for each wheel. PWM frequency is configurable.
    """

    def __init__(self):
        self._speed_left = 0
        self._speed_right = 0

        self._setup_gpio()

    def _setup_gpio(self):
        """Initialize GPIO pins and PWM channels."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Left motor pins
        GPIO.setup(config.MOTOR_LEFT_ENA, GPIO.OUT)
        GPIO.setup(config.MOTOR_LEFT_IN1, GPIO.OUT)
        GPIO.setup(config.MOTOR_LEFT_IN2, GPIO.OUT)

        # Right motor pins
        GPIO.setup(config.MOTOR_RIGHT_ENB, GPIO.OUT)
        GPIO.setup(config.MOTOR_RIGHT_IN3, GPIO.OUT)
        GPIO.setup(config.MOTOR_RIGHT_IN4, GPIO.OUT)

        # Initialize all direction pins LOW
        GPIO.output(config.MOTOR_LEFT_IN1, GPIO.LOW)
        GPIO.output(config.MOTOR_LEFT_IN2, GPIO.LOW)
        GPIO.output(config.MOTOR_RIGHT_IN3, GPIO.LOW)
        GPIO.output(config.MOTOR_RIGHT_IN4, GPIO.LOW)

        # Setup PWM on enable pins
        self._pwm_left = GPIO.PWM(config.MOTOR_LEFT_ENA, config.MOTOR_PWM_FREQ)
        self._pwm_right = GPIO.PWM(config.MOTOR_RIGHT_ENB, config.MOTOR_PWM_FREQ)
        self._pwm_left.start(0)
        self._pwm_right.start(0)

    def _set_left_motor(self, speed, forward=True):
        """
        Set left motor speed and direction.
        
        Args:
            speed: Speed percentage (0-100)
            forward: True for forward, False for backward
        """
        speed = max(0, min(100, speed))
        self._speed_left = speed

        if forward:
            GPIO.output(config.MOTOR_LEFT_IN1, GPIO.HIGH)
            GPIO.output(config.MOTOR_LEFT_IN2, GPIO.LOW)
        else:
            GPIO.output(config.MOTOR_LEFT_IN1, GPIO.LOW)
            GPIO.output(config.MOTOR_LEFT_IN2, GPIO.HIGH)

        self._pwm_left.ChangeDutyCycle(speed)

    def _set_right_motor(self, speed, forward=True):
        """
        Set right motor speed and direction.
        
        Args:
            speed: Speed percentage (0-100)
            forward: True for forward, False for backward
        """
        speed = max(0, min(100, speed))
        self._speed_right = speed

        if forward:
            GPIO.output(config.MOTOR_RIGHT_IN3, GPIO.HIGH)
            GPIO.output(config.MOTOR_RIGHT_IN4, GPIO.LOW)
        else:
            GPIO.output(config.MOTOR_RIGHT_IN3, GPIO.LOW)
            GPIO.output(config.MOTOR_RIGHT_IN4, GPIO.HIGH)

        self._pwm_right.ChangeDutyCycle(speed)

    def forward(self, speed=None):
        """
        Drive both motors forward.
        
        Args:
            speed: Speed percentage 0-100 (default: MOTOR_DEFAULT_SPEED)
        """
        if speed is None:
            speed = config.MOTOR_DEFAULT_SPEED
        self._set_left_motor(speed, forward=True)
        self._set_right_motor(speed, forward=True)

    def backward(self, speed=None):
        """
        Drive both motors backward.
        
        Args:
            speed: Speed percentage 0-100 (default: MOTOR_DEFAULT_SPEED)
        """
        if speed is None:
            speed = config.MOTOR_DEFAULT_SPEED
        self._set_left_motor(speed, forward=False)
        self._set_right_motor(speed, forward=False)

    def turn_left(self, speed=None):
        """
        Turn left: right motor forward, left motor stopped.
        
        Args:
            speed: Speed percentage 0-100 (default: MOTOR_TURN_SPEED)
        """
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._set_left_motor(0, forward=True)
        self._set_right_motor(speed, forward=True)

    def turn_right(self, speed=None):
        """
        Turn right: left motor forward, right motor stopped.
        
        Args:
            speed: Speed percentage 0-100 (default: MOTOR_TURN_SPEED)
        """
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._set_left_motor(speed, forward=True)
        self._set_right_motor(0, forward=True)

    def spin_left(self, speed=None):
        """
        Spin left in place: right forward, left backward.
        
        Args:
            speed: Speed percentage 0-100 (default: MOTOR_TURN_SPEED)
        """
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._set_left_motor(speed, forward=False)
        self._set_right_motor(speed, forward=True)

    def spin_right(self, speed=None):
        """
        Spin right in place: left forward, right backward.
        
        Args:
            speed: Speed percentage 0-100 (default: MOTOR_TURN_SPEED)
        """
        if speed is None:
            speed = config.MOTOR_TURN_SPEED
        self._set_left_motor(speed, forward=True)
        self._set_right_motor(speed, forward=False)

    def differential_drive(self, left_speed, right_speed):
        """
        Set independent speeds for each motor.
        Positive = forward, Negative = backward.
        
        Args:
            left_speed: Left motor speed (-100 to 100)
            right_speed: Right motor speed (-100 to 100)
        """
        left_forward = left_speed >= 0
        right_forward = right_speed >= 0
        self._set_left_motor(abs(left_speed), left_forward)
        self._set_right_motor(abs(right_speed), right_forward)

    def stop(self):
        """Stop both motors immediately."""
        GPIO.output(config.MOTOR_LEFT_IN1, GPIO.LOW)
        GPIO.output(config.MOTOR_LEFT_IN2, GPIO.LOW)
        GPIO.output(config.MOTOR_RIGHT_IN3, GPIO.LOW)
        GPIO.output(config.MOTOR_RIGHT_IN4, GPIO.LOW)
        self._pwm_left.ChangeDutyCycle(0)
        self._pwm_right.ChangeDutyCycle(0)
        self._speed_left = 0
        self._speed_right = 0

    def get_speeds(self):
        """
        Get current motor speed settings.
        
        Returns:
            dict: {"left": int, "right": int} speed percentages
        """
        return {
            "left": self._speed_left,
            "right": self._speed_right,
        }

    def cleanup(self):
        """Stop motors and clean up PWM."""
        self.stop()
        self._pwm_left.stop()
        self._pwm_right.stop()
