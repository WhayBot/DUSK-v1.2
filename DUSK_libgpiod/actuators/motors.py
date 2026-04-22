"""
DUSK - Wheel Motor Controller (libgpiod Version)

Controls two geared DC motors through L298N motor driver.
Left motor:  ENA=GPIO10, IN1=GPIO12, IN2=GPIO13
Right motor: IN3=GPIO19, IN4=GPIO16, ENB=GPIO9

Key differences from RPi.GPIO version:
  - Uses gpiod for direction pins (IN1-IN4)
  - Uses pigpio for PWM on enable pins (ENA, ENB) since
    gpiod does not support PWM output
"""

import gpiod
from gpiod.line import Direction, Value
import pigpio
import config


class WheelMotors:
    """
    Dual DC motor controller via L298N H-bridge driver (gpiod version).
    
    Direction pins use gpiod, PWM pins use pigpio.
    Supports differential drive with independent speed control.
    """

    def __init__(self):
        self._speed_left = 0
        self._speed_right = 0

        self._setup_gpio()

    def _setup_gpio(self):
        """Initialize gpiod for direction pins and pigpio for PWM."""
        # Direction pin settings (OUTPUT)
        dir_settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE,
        )

        # Request all direction pins
        self._dir_pins = [
            config.MOTOR_LEFT_IN1,
            config.MOTOR_LEFT_IN2,
            config.MOTOR_RIGHT_IN3,
            config.MOTOR_RIGHT_IN4,
        ]

        self._dir_request = gpiod.request_lines(
            config.GPIO_CHIP,
            consumer="dusk-wheel-motors-dir",
            config={pin: dir_settings for pin in self._dir_pins},
        )

        # PWM via pigpio (for ENA and ENB)
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("Cannot connect to pigpio daemon for motor PWM")

        # Set PWM frequency
        self._pi.set_PWM_frequency(config.MOTOR_LEFT_ENA, config.MOTOR_PWM_FREQ)
        self._pi.set_PWM_frequency(config.MOTOR_RIGHT_ENB, config.MOTOR_PWM_FREQ)

        # Start with 0 duty cycle
        self._pi.set_PWM_dutycycle(config.MOTOR_LEFT_ENA, 0)
        self._pi.set_PWM_dutycycle(config.MOTOR_RIGHT_ENB, 0)

    def _set_pin(self, pin, high):
        """Set a direction pin high or low."""
        value = Value.ACTIVE if high else Value.INACTIVE
        self._dir_request.set_value(pin, value)

    def _set_pwm(self, gpio, speed_percent):
        """Set PWM duty cycle (0-100% mapped to 0-255)."""
        duty = int((speed_percent / 100.0) * 255)
        duty = max(0, min(255, duty))
        self._pi.set_PWM_dutycycle(gpio, duty)

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
            self._set_pin(config.MOTOR_LEFT_IN1, True)
            self._set_pin(config.MOTOR_LEFT_IN2, False)
        else:
            self._set_pin(config.MOTOR_LEFT_IN1, False)
            self._set_pin(config.MOTOR_LEFT_IN2, True)

        self._set_pwm(config.MOTOR_LEFT_ENA, speed)

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
            self._set_pin(config.MOTOR_RIGHT_IN3, True)
            self._set_pin(config.MOTOR_RIGHT_IN4, False)
        else:
            self._set_pin(config.MOTOR_RIGHT_IN3, False)
            self._set_pin(config.MOTOR_RIGHT_IN4, True)

        self._set_pwm(config.MOTOR_RIGHT_ENB, speed)

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
        for pin in self._dir_pins:
            self._set_pin(pin, False)
        self._set_pwm(config.MOTOR_LEFT_ENA, 0)
        self._set_pwm(config.MOTOR_RIGHT_ENB, 0)
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
        """Stop motors and clean up resources."""
        self.stop()
        if self._dir_request:
            self._dir_request.release()
        if self._pi and self._pi.connected:
            self._pi.set_PWM_dutycycle(config.MOTOR_LEFT_ENA, 0)
            self._pi.set_PWM_dutycycle(config.MOTOR_RIGHT_ENB, 0)
            self._pi.stop()
