"""
DUSK - Brushless Vacuum Motor Controller (ESC via pigpio)

Controls a 980kV brushless motor through a 20A ESC.
Uses pigpio for precise servo-style PWM on GPIO18 (hardware PWM capable).

The ESC interprets pulse widths:
  1000us = motor off
  1150us = minimum running speed
  2000us = full throttle

Includes soft-start and soft-stop ramp control to prevent
vibration spikes and reduce mechanical stress on the motor.
"""

import time
import pigpio
import config


# Soft-start / soft-stop configuration
RAMP_STEP_PERCENT = 2      # Increment per ramp step (%)
RAMP_STEP_DELAY = 0.05     # Delay between ramp steps (seconds)
# At 2% steps with 50ms delay: 0->50% takes ~1.25 seconds


class VacuumMotor:
    """
    Brushless motor controller via ESC + pigpio.
    
    Uses pigpio daemon for jitter-free PWM control.
    Requires pigpiod to be running: sudo pigpiod
    
    Features soft-start/soft-stop ramp to avoid vibration spikes
    and reduce stress on the motor and ESC.
    """

    def __init__(self):
        self.gpio = config.ESC_GPIO
        self._speed_percent = 0
        self._target_percent = 0
        self._armed = False

        # Connect to pigpio daemon
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError(
                "Cannot connect to pigpio daemon. "
                "Make sure pigpiod is running: sudo pigpiod"
            )

    def arm(self):
        """
        Arm the ESC by sending minimum throttle signal.
        Must be called before setting any speed.
        Wait for ESC initialization beeps to complete.
        """
        self.pi.set_servo_pulsewidth(self.gpio, config.ESC_ARM_PULSE)
        time.sleep(3)
        self._armed = True

    def calibrate(self):
        """
        Calibrate ESC throttle range.
        
        Steps:
        1. Send max throttle before powering ESC
        2. Power on ESC, wait for calibration beeps
        3. Send min throttle
        4. Wait for confirmation beeps
        
        NOTE: ESC must be powered off before calling this.
        """
        print("ESC Calibration Mode")
        print("1. Disconnect ESC battery power")
        print("2. Press Enter when ready...")
        input()

        # Send maximum throttle
        self.pi.set_servo_pulsewidth(self.gpio, config.ESC_MAX_PULSE)
        print("3. Connect ESC battery power now")
        print("4. Wait for calibration beeps, then press Enter...")
        input()

        # Send minimum throttle
        self.pi.set_servo_pulsewidth(self.gpio, config.ESC_MIN_PULSE)
        print("5. Wait for confirmation beeps...")
        time.sleep(3)
        print("Calibration complete!")
        self._armed = True

    def _set_speed_raw(self, percent):
        """
        Set the ESC pulse width directly without ramp (internal use).
        
        Args:
            percent: Speed percentage 0-100
        """
        percent = max(0, min(100, percent))
        self._speed_percent = percent

        if percent == 0:
            pulse = config.ESC_MIN_PULSE
        else:
            pulse_range = config.ESC_MAX_PULSE - config.ESC_IDLE_PULSE
            pulse = config.ESC_IDLE_PULSE + int((percent / 100.0) * pulse_range)

        self.pi.set_servo_pulsewidth(self.gpio, pulse)

    def _ramp_to(self, target_percent):
        """
        Gradually ramp the motor speed from current to target.
        
        Steps up or down in RAMP_STEP_PERCENT increments with
        RAMP_STEP_DELAY between each step. This prevents sudden
        current spikes, reduces vibration transients, and is
        gentler on the motor bearings and ESC.
        
        Args:
            target_percent: Target speed percentage 0-100
        """
        target_percent = max(0, min(100, target_percent))
        current = self._speed_percent

        if current == target_percent:
            return

        if current < target_percent:
            # Ramp up
            step = RAMP_STEP_PERCENT
            while current < target_percent:
                current = min(current + step, target_percent)
                self._set_speed_raw(current)
                time.sleep(RAMP_STEP_DELAY)
        else:
            # Ramp down
            step = RAMP_STEP_PERCENT
            while current > target_percent:
                current = max(current - step, target_percent)
                self._set_speed_raw(current)
                time.sleep(RAMP_STEP_DELAY)

        self._target_percent = target_percent

    def set_speed(self, percent):
        """
        Set vacuum motor speed with soft ramp.
        
        Args:
            percent: Speed percentage 0-100.
                     0 = off, 100 = full throttle
        """
        if not self._armed:
            self.arm()

        self._ramp_to(percent)

    def start(self, speed=None):
        """
        Start the vacuum motor with soft-start ramp.
        
        The motor gradually accelerates from 0% to the target speed
        to prevent vibration spikes and current surges.
        
        Args:
            speed: Speed percentage 0-100 (default: ESC_DEFAULT_SPEED)
        """
        if speed is None:
            speed = config.ESC_DEFAULT_SPEED
        self.set_speed(speed)

    def stop(self):
        """
        Stop the vacuum motor with soft-stop ramp.
        
        Gradually reduces speed to 0 before sending the
        minimum pulse, preventing abrupt deceleration.
        """
        if self._speed_percent > 0:
            self._ramp_to(0)
        if self.pi.connected:
            self.pi.set_servo_pulsewidth(self.gpio, config.ESC_MIN_PULSE)

    def kill(self):
        """Emergency stop - turn off PWM completely (no ramp)."""
        self._speed_percent = 0
        self._target_percent = 0
        self._armed = False
        if self.pi.connected:
            self.pi.set_servo_pulsewidth(self.gpio, 0)

    def get_speed(self):
        """Get current speed setting."""
        return self._speed_percent

    def is_running(self):
        """Check if motor is currently running."""
        return self._speed_percent > 0

    def get_status(self):
        """Get vacuum motor status."""
        return {
            "running": self._speed_percent > 0,
            "speed": self._speed_percent,
            "armed": self._armed,
        }

    def cleanup(self):
        """Stop motor with ramp-down and release pigpio resources."""
        self.stop()
        time.sleep(0.5)
        self.kill()
        if self.pi.connected:
            self.pi.stop()
