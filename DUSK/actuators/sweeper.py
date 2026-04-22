"""
DUSK - N20 Sweeper Motor Controller (RPi.GPIO Version)

Controls two N20 geared motors through L298N motor driver.
Both motors are connected to the same channel (OUT1/OUT2) with
opposing polarity, so they spin in opposite directions to sweep
dust inward toward the vacuum intake.

L298N connections:
  ENA = GPIO26 (PWM speed control)
  IN1 = GPIO24 (direction)
  IN2 = GPIO25 (direction)
"""

import RPi.GPIO as GPIO
import config


class SweeperMotors:
    """
    N20 sweeper motor controller via L298N H-bridge.
    
    Both N20 motors share the same L298N channel with reversed polarity,
    causing them to rotate in opposite directions for inward sweeping.
    """

    def __init__(self):
        self._speed = 0
        self._running = False

        self._setup_gpio()

    def _setup_gpio(self):
        """Initialize GPIO pins and PWM."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        GPIO.setup(config.SWEEPER_ENA, GPIO.OUT)
        GPIO.setup(config.SWEEPER_IN1, GPIO.OUT)
        GPIO.setup(config.SWEEPER_IN2, GPIO.OUT)

        GPIO.output(config.SWEEPER_IN1, GPIO.LOW)
        GPIO.output(config.SWEEPER_IN2, GPIO.LOW)

        self._pwm = GPIO.PWM(config.SWEEPER_ENA, config.MOTOR_PWM_FREQ)
        self._pwm.start(0)

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
        # Due to opposing polarity wiring, one motor spins CW and other CCW
        GPIO.output(config.SWEEPER_IN1, GPIO.HIGH)
        GPIO.output(config.SWEEPER_IN2, GPIO.LOW)

        self._pwm.ChangeDutyCycle(speed)

    def stop(self):
        """Stop the sweeper motors."""
        GPIO.output(config.SWEEPER_IN1, GPIO.LOW)
        GPIO.output(config.SWEEPER_IN2, GPIO.LOW)
        self._pwm.ChangeDutyCycle(0)
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
            self._pwm.ChangeDutyCycle(speed)

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
        """Stop and clean up."""
        self.stop()
        self._pwm.stop()
