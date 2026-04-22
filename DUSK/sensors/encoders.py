"""
DUSK - Speed Encoder Driver (RPi.GPIO Version)

Reads digital output from two speed encoder sensors attached to the wheel motors.
Uses interrupt-based pulse counting for accurate distance/speed measurement.
Left encoder: GPIO14, Right encoder: GPIO7
"""

import time
import threading
import RPi.GPIO as GPIO
import config


class SpeedEncoder:
    """
    Speed encoder pulse counter for a single wheel.
    
    Uses GPIO interrupt (edge detection) to count pulses from the
    encoder's digital output pin. Each pulse corresponds to one
    slot passing through the optical/magnetic sensor.
    """

    def __init__(self, gpio_pin, name="Encoder"):
        self.pin = gpio_pin
        self.name = name
        self._pulse_count = 0
        self._last_count = 0
        self._last_time = time.time()
        self._speed = 0.0  # mm/s
        self._lock = threading.Lock()

        self._setup_gpio()

    def _setup_gpio(self):
        """Configure GPIO pin with interrupt-based edge detection."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            self.pin,
            GPIO.FALLING,
            callback=self._pulse_callback,
            bouncetime=1,
        )

    def _pulse_callback(self, channel):
        """Interrupt callback for each encoder pulse."""
        with self._lock:
            self._pulse_count += 1

    def get_pulse_count(self):
        """
        Get the total pulse count since last reset.
        
        Returns:
            int: Total accumulated pulses
        """
        with self._lock:
            return self._pulse_count

    def get_distance_mm(self):
        """
        Calculate distance traveled based on pulse count.
        
        Returns:
            float: Distance in millimeters
        """
        pulses = self.get_pulse_count()
        revolutions = pulses / config.ENCODER_PULSES_PER_REV
        return revolutions * config.WHEEL_CIRCUMFERENCE_MM

    def calculate_speed(self):
        """
        Calculate current speed in mm/s.
        Should be called periodically (e.g., every 100ms).
        
        Returns:
            float: Speed in mm/s
        """
        current_time = time.time()
        with self._lock:
            current_count = self._pulse_count
        
        dt = current_time - self._last_time
        if dt <= 0:
            return self._speed

        delta_pulses = current_count - self._last_count
        revolutions = delta_pulses / config.ENCODER_PULSES_PER_REV
        distance = revolutions * config.WHEEL_CIRCUMFERENCE_MM
        self._speed = distance / dt

        self._last_count = current_count
        self._last_time = current_time

        return self._speed

    def get_speed(self):
        """
        Get the last calculated speed.
        
        Returns:
            float: Speed in mm/s
        """
        return self._speed

    def reset(self):
        """Reset the pulse counter and speed measurement."""
        with self._lock:
            self._pulse_count = 0
            self._last_count = 0
            self._last_time = time.time()
            self._speed = 0.0

    def cleanup(self):
        """Remove edge detection and clean up GPIO."""
        GPIO.remove_event_detect(self.pin)


class DualEncoders:
    """
    Manager for both wheel encoders (left and right).
    Provides consolidated speed and distance data.
    """

    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        self.left = SpeedEncoder(config.ENCODER_LEFT_PIN, "Left")
        self.right = SpeedEncoder(config.ENCODER_RIGHT_PIN, "Right")

    def get_distances(self):
        """
        Get distance traveled by both wheels.
        
        Returns:
            dict: {"left": float, "right": float, "average": float} in mm
        """
        left_dist = self.left.get_distance_mm()
        right_dist = self.right.get_distance_mm()
        return {
            "left": left_dist,
            "right": right_dist,
            "average": (left_dist + right_dist) / 2.0,
        }

    def get_speeds(self):
        """
        Calculate and return current speeds for both wheels.
        
        Returns:
            dict: {"left": float, "right": float, "average": float} in mm/s
        """
        left_speed = self.left.calculate_speed()
        right_speed = self.right.calculate_speed()
        return {
            "left": left_speed,
            "right": right_speed,
            "average": (left_speed + right_speed) / 2.0,
        }

    def get_pulse_counts(self):
        """
        Get pulse counts for both encoders.
        
        Returns:
            dict: {"left": int, "right": int}
        """
        return {
            "left": self.left.get_pulse_count(),
            "right": self.right.get_pulse_count(),
        }

    def reset_all(self):
        """Reset both encoders."""
        self.left.reset()
        self.right.reset()

    def get_status(self):
        """Get complete encoder status."""
        return {
            "distances": self.get_distances(),
            "speeds": self.get_speeds(),
            "pulses": self.get_pulse_counts(),
        }

    def cleanup(self):
        """Clean up both encoders."""
        self.left.cleanup()
        self.right.cleanup()
