"""
DUSK - N20 Sweeper Motor Controller (libgpiod Version)

Controls two N20 geared motors through L298N motor driver.
Both motors are connected to the same channel (OUT1/OUT2) with
opposing polarity, so they spin in opposite directions.

Key differences from RPi.GPIO version:
  - Uses gpiod for direction pins (IN1, IN2)
  - Uses pigpio for PWM on enable pin (ENA)
"""

import gpiod
from gpiod.line import Direction, Value
import pigpio
import config


class SweeperMotors:
    """
    N20 sweeper motor controller via L298N H-bridge (gpiod version).
    
    Direction pins use gpiod, PWM uses pigpio.
    Both N20 motors share the same L298N channel with reversed polarity.
    """

    def __init__(self):
        self._speed = 0
        self._running = False

        self._setup_gpio()

    def _setup_gpio(self):
        """Initialize gpiod for direction and pigpio for PWM."""
        # Direction pin settings
        dir_settings = gpiod.LineSettings(
            direction=Direction.OUTPUT,
            output_value=Value.INACTIVE,
        )

        self._dir_pins = [config.SWEEPER_IN1, config.SWEEPER_IN2]

        self._dir_request = gpiod.request_lines(
            config.GPIO_CHIP,
            consumer="dusk-sweeper-motors-dir",
            config={pin: dir_settings for pin in self._dir_pins},
        )

        # PWM via pigpio
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("Cannot connect to pigpio daemon for sweeper PWM")

        self._pi.set_PWM_frequency(config.SWEEPER_ENA, config.MOTOR_PWM_FREQ)
        self._pi.set_PWM_dutycycle(config.SWEEPER_ENA, 0)

    def _set_pin(self, pin, high):
        """Set a direction pin high or low."""
        value = Value.ACTIVE if high else Value.INACTIVE
        self._dir_request.set_value(pin, value)

    def _set_pwm(self, speed_percent):
        """Set PWM duty cycle (0-100% mapped to 0-255)."""
        duty = int((speed_percent / 100.0) * 255)
        duty = max(0, min(255, duty))
        self._pi.set_PWM_dutycycle(config.SWEEPER_ENA, duty)

    def start(self, speed=None):
        """
        Start the sweeper motors.
        
        Args:
            speed: Speed percentage 0-100 (default: SWEEPER_DEFAULT_SPEED)
        """
        if speed is None:
            speed = config.SWEEPER_DEFAULT_SPEED

        speed = max(0, min(100, speed))
        self._speed = speed
        self._running = True

        # Set direction: IN1=HIGH, IN2=LOW
        self._set_pin(config.SWEEPER_IN1, True)
        self._set_pin(config.SWEEPER_IN2, False)

        self._set_pwm(speed)

    def stop(self):
        """Stop the sweeper motors."""
        self._set_pin(config.SWEEPER_IN1, False)
        self._set_pin(config.SWEEPER_IN2, False)
        self._set_pwm(0)
        self._speed = 0
        self._running = False

    def set_speed(self, speed):
        """
        Change the sweeper speed without stopping.
        
        Args:
            speed: Speed percentage 0-100
        """
        speed = max(0, min(100, speed))
        self._speed = speed
        if self._running:
            self._set_pwm(speed)

    def is_running(self):
        """Check if sweepers are currently running."""
        return self._running

    def get_speed(self):
        """Get current speed setting."""
        return self._speed

    def get_status(self):
        """Get sweeper status."""
        return {
            "running": self._running,
            "speed": self._speed,
        }

    def cleanup(self):
        """Stop and clean up resources."""
        self.stop()
        if self._dir_request:
            self._dir_request.release()
        if self._pi and self._pi.connected:
            self._pi.set_PWM_dutycycle(config.SWEEPER_ENA, 0)
            self._pi.stop()
