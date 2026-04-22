"""
DUSK - Speed Encoder Driver (libgpiod Version)

Reads digital output from two speed encoder sensors attached to the wheel motors.
Uses gpiod edge events for interrupt-based pulse counting.
Left encoder: GPIO14, Right encoder: GPIO7

Key differences from RPi.GPIO version:
  - Uses gpiod.request_lines() with edge detection
  - Uses wait_edge_events() / read_edge_events() in a thread
  - No GPIO.setmode() or GPIO.cleanup() needed
"""

import time
import threading
import gpiod
from gpiod.line import Direction, Edge, Bias
import config


class SpeedEncoder:
    """
    Speed encoder pulse counter for a single wheel (gpiod version).
    
    Uses gpiod edge detection events to count pulses from the
    encoder's digital output pin.
    """

    def __init__(self, gpio_pin, name="Encoder"):
        self.pin = gpio_pin
        self.name = name
        self._pulse_count = 0
        self._last_count = 0
        self._last_time = time.time()
        self._speed = 0.0  # mm/s
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._request = None

        self._setup_gpiod()

    def _setup_gpiod(self):
        """Configure gpiod line with edge detection."""
        line_settings = gpiod.LineSettings(
            direction=Direction.INPUT,
            edge_detection=Edge.FALLING,
            bias=Bias.PULL_UP,
        )

        self._request = gpiod.request_lines(
            config.GPIO_CHIP,
            consumer=f"dusk-encoder-{self.name}",
            config={self.pin: line_settings},
        )

        # Start edge event monitoring thread
        self._running = True
        self._thread = threading.Thread(
            target=self._edge_monitor_loop, daemon=True
        )
        self._thread.start()

    def _edge_monitor_loop(self):
        """Monitor edge events in a dedicated thread."""
        while self._running:
            try:
                # Wait for edge events (timeout 1 second)
                if self._request.wait_edge_events(timeout=1.0):
                    events = self._request.read_edge_events()
                    with self._lock:
                        self._pulse_count += len(events)
            except Exception:
                if self._running:
                    time.sleep(0.01)

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
        """Stop monitoring and release gpiod resources."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._request:
            self._request.release()
            self._request = None


class DualEncoders:
    """
    Manager for both wheel encoders (left and right).
    Provides consolidated speed and distance data.
    """

    def __init__(self):
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
