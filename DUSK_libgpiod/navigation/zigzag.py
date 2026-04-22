"""
DUSK - Zig-Zag Navigation Controller

Implements a zig-zag cleaning pattern using encoder distance tracking
and MPU6050 gyroscope heading control. Includes obstacle avoidance
using dual VL53L0X ToF sensors.

Pattern:
  →→→→→→→→→→→→→→→→→→→→→→ (straight)
                          ↓ (shift)
  ←←←←←←←←←←←←←←←←←←←←←← (straight reverse)
  ↓ (shift)
  →→→→→→→→→→→→→→→→→→→→→→ (straight)
  ...
"""

import time
import threading
import config


class NavigationState:
    """Enumeration of navigation states."""
    IDLE = "IDLE"
    DRIVE_STRAIGHT = "DRIVE_STRAIGHT"
    TURN_FIRST = "TURN_FIRST"
    SHIFT_FORWARD = "SHIFT_FORWARD"
    TURN_SECOND = "TURN_SECOND"
    AVOIDING_OBSTACLE = "AVOIDING_OBSTACLE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class PIDController:
    """
    Simple PID controller for straight-line driving correction.
    Uses gyro heading error as input, motor speed offset as output.
    """

    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = time.time()

    def compute(self, error):
        """
        Compute PID output from heading error.
        
        Args:
            error: Heading deviation in degrees
            
        Returns:
            float: Correction value to apply to motor differential
        """
        current_time = time.time()
        dt = current_time - self._last_time
        if dt <= 0:
            dt = 0.01
        self._last_time = current_time

        # Proportional
        p = self.kp * error

        # Integral (with anti-windup)
        self._integral += error * dt
        self._integral = max(-50, min(50, self._integral))
        i = self.ki * self._integral

        # Derivative
        derivative = (error - self._prev_error) / dt
        d = self.kd * derivative
        self._prev_error = error

        return p + i + d

    def reset(self):
        """Reset PID state."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = time.time()


class ZigZagNavigator:
    """
    Zig-zag cleaning pattern navigation controller.
    
    Coordinates wheel motors, encoders, gyroscope, and ToF sensors
    to drive the robot in a systematic cleaning pattern while
    avoiding obstacles.
    """

    def __init__(self, motors, encoders, imu, tof_sensors):
        """
        Args:
            motors: WheelMotors instance
            encoders: DualEncoders instance
            imu: MPU6050 instance
            tof_sensors: DualVL53L0X instance
        """
        self.motors = motors
        self.encoders = encoders
        self.imu = imu
        self.tof = tof_sensors

        self._state = NavigationState.IDLE
        self._running = False
        self._thread = None

        # Navigation parameters
        self._straight_distance = config.ZIGZAG_STRAIGHT_DISTANCE
        self._shift_distance = config.ZIGZAG_SHIFT_DISTANCE
        self._turn_direction = 1  # 1 = turn right, -1 = turn left
        self._target_heading = 0.0

        # PID controller for straight-line correction
        self._pid = PIDController(config.PID_KP, config.PID_KI, config.PID_KD)

    def _normalize_angle(self, angle):
        """Normalize angle to -180 to +180 degrees."""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle

    def _get_heading_error(self):
        """Get heading deviation from target."""
        current = self.imu.update_heading()
        error = self._normalize_angle(self._target_heading - current)
        return error

    def _drive_straight_distance(self, distance_mm, speed=None):
        """
        Drive straight for a specified distance using encoder feedback.
        PID correction keeps the heading straight using the gyroscope.
        
        Returns:
            bool: True if completed, False if interrupted (obstacle)
        """
        if speed is None:
            speed = config.MOTOR_DEFAULT_SPEED

        self.encoders.reset_all()
        self._pid.reset()

        while self._running:
            # Check for obstacles
            obstacles = self.tof.check_obstacles()
            if obstacles["any"]:
                self.motors.stop()
                return False

            # Check distance
            distances = self.encoders.get_distances()
            if distances["average"] >= distance_mm:
                self.motors.stop()
                return True

            # PID heading correction
            error = self._get_heading_error()
            correction = self._pid.compute(error)

            # Apply differential drive
            left_speed = speed + correction
            right_speed = speed - correction

            # Clamp speeds
            left_speed = max(20, min(100, left_speed))
            right_speed = max(20, min(100, right_speed))

            self.motors.differential_drive(left_speed, right_speed)
            time.sleep(0.02)

        self.motors.stop()
        return False

    def _turn_degrees(self, degrees):
        """
        Turn the robot by a specified number of degrees.
        Positive = right, Negative = left.
        Uses gyroscope for accurate turn measurement.
        
        Returns:
            bool: True if completed successfully
        """
        start_heading = self.imu.get_heading()
        target = (start_heading + degrees) % 360
        self._target_heading = target

        # Choose turn direction
        if degrees > 0:
            self.motors.spin_right(config.MOTOR_TURN_SPEED)
        else:
            self.motors.spin_left(config.MOTOR_TURN_SPEED)

        # Wait until we reach the target heading
        timeout = time.time() + 5.0  # 5 second timeout
        while self._running:
            self.imu.update_heading()
            error = abs(self._normalize_angle(target - self.imu.get_heading()))

            if error < config.TURN_TOLERANCE:
                self.motors.stop()
                time.sleep(0.1)
                return True

            if time.time() > timeout:
                self.motors.stop()
                return True

            # Slow down as we approach the target
            if error < 15:
                slow_speed = max(25, int(config.MOTOR_TURN_SPEED * (error / 15)))
                if degrees > 0:
                    self.motors.spin_right(slow_speed)
                else:
                    self.motors.spin_left(slow_speed)

            time.sleep(0.01)

        self.motors.stop()
        return False

    def _avoid_obstacle(self):
        """
        Obstacle avoidance routine.
        Backs up, turns away from obstacle, then resumes.
        """
        prev_state = self._state
        self._state = NavigationState.AVOIDING_OBSTACLE

        obstacles = self.tof.check_obstacles()

        # Back up a bit
        self.motors.backward(config.MOTOR_TURN_SPEED)
        time.sleep(0.5)
        self.motors.stop()
        time.sleep(0.2)

        # Turn away from obstacle
        if obstacles["left"] and not obstacles["right"]:
            self._turn_degrees(45)  # Turn right
        elif obstacles["right"] and not obstacles["left"]:
            self._turn_degrees(-45)  # Turn left
        else:
            # Both sides blocked, turn 90°
            self._turn_degrees(90 * self._turn_direction)

        self._state = prev_state

    def _zigzag_loop(self):
        """Main zig-zag navigation loop."""
        self._state = NavigationState.DRIVE_STRAIGHT
        self.imu.reset_heading()
        self._target_heading = 0.0

        while self._running:
            if self._state == NavigationState.PAUSED:
                time.sleep(0.1)
                continue

            # --- STEP 1: Drive straight ---
            self._state = NavigationState.DRIVE_STRAIGHT
            success = self._drive_straight_distance(self._straight_distance)

            if not self._running:
                break

            if not success:
                self._avoid_obstacle()
                continue

            # --- STEP 2: First 90° turn ---
            self._state = NavigationState.TURN_FIRST
            turn_angle = 90 * self._turn_direction
            self._turn_degrees(turn_angle)

            if not self._running:
                break

            # --- STEP 3: Short shift forward ---
            self._state = NavigationState.SHIFT_FORWARD
            success = self._drive_straight_distance(self._shift_distance)

            if not self._running:
                break

            if not success:
                self._avoid_obstacle()
                continue

            # --- STEP 4: Second 90° turn (same direction) ---
            self._state = NavigationState.TURN_SECOND
            self._turn_degrees(turn_angle)

            if not self._running:
                break

            # Alternate turn direction for next row
            self._turn_direction *= -1

        self.motors.stop()
        self._state = NavigationState.IDLE

    def start(self):
        """Start the zig-zag navigation in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._zigzag_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop navigation and motors."""
        self._running = False
        self.motors.stop()
        if self._thread:
            self._thread.join(timeout=3)
        self._state = NavigationState.IDLE

    def pause(self):
        """Pause navigation (motors stop but state preserved)."""
        self.motors.stop()
        self._state = NavigationState.PAUSED

    def resume(self):
        """Resume navigation from paused state."""
        if self._state == NavigationState.PAUSED:
            self._state = NavigationState.DRIVE_STRAIGHT

    def get_state(self):
        """Get current navigation state."""
        return self._state

    def is_running(self):
        """Check if navigation is active."""
        return self._running

    def get_status(self):
        """Get complete navigation status."""
        return {
            "state": self._state,
            "running": self._running,
            "turn_direction": "right" if self._turn_direction > 0 else "left",
            "heading": self.imu.get_heading(),
            "target_heading": self._target_heading,
        }
