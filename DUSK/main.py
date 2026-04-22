"""
DUSK - Dust Unification and Sweeping Keeper
Main Entry Point

Initializes all subsystems and runs the robot vacuum cleaner.
Supports two operating modes:
  - Automatic: Zig-zag cleaning with obstacle avoidance
  - Manual: Web-based remote control with camera streaming

Usage:
    sudo python3 main.py
"""

import sys
import signal
import time
import threading
import RPi.GPIO as GPIO

import config
from i2c_mux import get_mux
from sensors.mpu6050 import MPU6050
from sensors.vl53l0x import DualVL53L0X
from sensors.ina219 import INA219
from sensors.encoders import DualEncoders
from actuators.motors import WheelMotors
from actuators.sweeper import SweeperMotors
from actuators.vacuum import VacuumMotor
from display.oled_eyes import OLEDEyes
from navigation.zigzag import ZigZagNavigator
from web.server import RobotInterface, init_server, start_server_thread
from web.camera import CameraStream


class DUSK:
    """
    Main DUSK robot vacuum controller.
    
    Initializes and coordinates all subsystems:
    - I2C Multiplexer (TCA9548A)
    - Sensors (MPU6050, VL53L0X×2, INA219, Encoders×2)
    - Actuators (Wheel Motors, Sweeper Motors, Vacuum Motor)
    - Display (OLED Eyes×2)
    - Navigation (Zig-zag pattern)
    - Web Server (Flask + Camera)
    """

    def __init__(self):
        self._running = False
        self._shutdown_event = threading.Event()

        # Subsystem references (initialized in start())
        self.mux = None
        self.imu = None
        self.tof = None
        self.ina = None
        self.encoders = None
        self.motors = None
        self.sweeper = None
        self.vacuum = None
        self.oled = None
        self.navigator = None
        self.camera = None
        self.robot_interface = None

    def _init_i2c(self):
        """Initialize I2C multiplexer."""
        print("[INIT] I2C Multiplexer (TCA9548A)...")
        self.mux = get_mux()
        
        # Scan for devices
        print("[INIT] Scanning I2C bus...")
        devices = self.mux.scan_all()
        for ch, addrs in devices.items():
            print(f"  Channel {ch}: {addrs}")
        print("[INIT] I2C Multiplexer: OK")

    def _init_sensors(self):
        """Initialize all sensors."""
        print("[INIT] MPU6050 (Gyro + Accelerometer)...")
        self.imu = MPU6050()
        print("[INIT] MPU6050: OK")

        print("[INIT] VL53L0X ToF sensors (Left + Right)...")
        self.tof = DualVL53L0X()
        distances = self.tof.get_distances()
        print(f"  Left: {distances['left']}mm, Right: {distances['right']}mm")
        print("[INIT] VL53L0X: OK")

        print("[INIT] INA219 (Power Monitor)...")
        self.ina = INA219()
        status = self.ina.get_status()
        print(f"  Battery: {status['voltage']}V, {status['percentage']}%")
        print("[INIT] INA219: OK")

        print("[INIT] Speed Encoders (Left + Right)...")
        self.encoders = DualEncoders()
        print("[INIT] Encoders: OK")

    def _init_actuators(self):
        """Initialize all actuators."""
        print("[INIT] Wheel Motors (L298N)...")
        self.motors = WheelMotors()
        print("[INIT] Wheel Motors: OK")

        print("[INIT] Sweeper Motors (N20 + L298N)...")
        self.sweeper = SweeperMotors()
        print("[INIT] Sweeper Motors: OK")

        print("[INIT] Vacuum Motor (ESC + Brushless)...")
        self.vacuum = VacuumMotor()
        print("[INIT] Arming ESC...")
        self.vacuum.arm()
        print("[INIT] Vacuum Motor: OK")

    def _init_display(self):
        """Initialize OLED eye displays."""
        print("[INIT] OLED Eyes (Left + Right)...")
        self.oled = OLEDEyes()
        print("[INIT] Showing startup animation...")
        self.oled.show_startup()
        self.oled.start()
        print("[INIT] OLED Eyes: OK")

    def _init_navigation(self):
        """Initialize navigation controller."""
        print("[INIT] Navigation Controller...")
        self.navigator = ZigZagNavigator(
            self.motors, self.encoders, self.imu, self.tof
        )
        print("[INIT] Navigation: OK")

    def _init_web(self):
        """Initialize web server and camera."""
        print("[INIT] Camera Stream (Pi Cam V2)...")
        self.camera = CameraStream()
        print("[INIT] Camera: OK (will start in manual mode)")

        print("[INIT] Web Server...")
        self.robot_interface = RobotInterface(
            motors=self.motors,
            sweeper=self.sweeper,
            vacuum=self.vacuum,
            navigator=self.navigator,
            imu=self.imu,
            tof=self.tof,
            ina=self.ina,
            encoders=self.encoders,
            oled=self.oled,
        )
        init_server(self.robot_interface, self.camera)
        start_server_thread()
        print(f"[INIT] Web Server: OK (http://0.0.0.0:{config.WEB_PORT})")

    def start(self):
        """Initialize all subsystems and start the robot."""
        print("=" * 60)
        print("  DUSK - Dust Unification & Sweeping Keeper")
        print("  Smart Vacuum Cleaner Robot v1.0")
        print("=" * 60)
        print()

        try:
            self._init_i2c()
            self._init_sensors()
            self._init_actuators()
            self._init_display()
            self._init_navigation()
            self._init_web()
        except Exception as e:
            print(f"\n[ERROR] Initialization failed: {e}")
            self.shutdown()
            raise

        print()
        print("=" * 60)
        print("  All systems initialized successfully!")
        print(f"  Web panel: http://<raspberry-pi-ip>:{config.WEB_PORT}")
        print("  Mode: Manual (switch via web panel)")
        print("  Press Ctrl+C to shutdown")
        print("=" * 60)
        print()

        self._running = True

        # Baseline gyro calibration (motors off)
        # This sets a rough bias with no vibration.
        # A second, vibration-aware calibration runs automatically
        # when auto mode is activated (motors on + settle_time).
        print("[CAL] Baseline gyro calibration (keep robot still)...")
        self.imu.calibrate_gyro(samples=100)
        self.imu.reset_heading()
        print(f"[CAL] Baseline bias: {self.imu._gyro_z_bias:.4f} deg/s")
        print("[CAL] Full re-calibration will run when auto mode starts")

        # Main monitoring loop
        self._main_loop()

    def _main_loop(self):
        """
        Main loop that monitors battery and system health.
        Navigation and web server run in their own threads.
        """
        while self._running and not self._shutdown_event.is_set():
            try:
                # Monitor battery
                battery = self.ina.get_status()
                if battery["critical"]:
                    print("[!!! ] CRITICAL BATTERY! Initiating emergency shutdown...")
                    self._emergency_stop()
                    break
                elif battery["low_battery"]:
                    print(f"[WARN] Low battery: {battery['voltage']}V ({battery['percentage']}%)")

                # Update encoder speeds
                self.encoders.get_speeds()

                # Update IMU heading
                self.imu.update_heading()

                # Sleep to prevent CPU hogging
                self._shutdown_event.wait(0.1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Main loop error: {e}")
                time.sleep(1)

        self.shutdown()

    def _emergency_stop(self):
        """Emergency stop all motors."""
        print("[EMERGENCY] Stopping all motors!")
        try:
            self.motors.stop()
            self.sweeper.stop()
            self.vacuum.stop()
            self.navigator.stop()
        except Exception:
            pass

    def shutdown(self):
        """Graceful shutdown of all subsystems."""
        if not self._running and self.motors is None:
            return

        self._running = False
        self._shutdown_event.set()
        print("\n[SHUTDOWN] Initiating graceful shutdown...")

        # Stop navigation
        if self.navigator:
            print("[SHUTDOWN] Stopping navigation...")
            self.navigator.stop()

        # Stop all motors
        if self.motors:
            print("[SHUTDOWN] Stopping wheel motors...")
            self.motors.stop()
            self.motors.cleanup()

        if self.sweeper:
            print("[SHUTDOWN] Stopping sweeper motors...")
            self.sweeper.stop()
            self.sweeper.cleanup()

        if self.vacuum:
            print("[SHUTDOWN] Stopping vacuum motor...")
            self.vacuum.cleanup()

        # Stop camera
        if self.camera:
            print("[SHUTDOWN] Stopping camera...")
            self.camera.cleanup()

        # Shutdown OLED display
        if self.oled:
            print("[SHUTDOWN] OLED shutdown animation...")
            self.oled.show_shutdown()
            self.oled.cleanup()

        # Clean up encoders
        if self.encoders:
            print("[SHUTDOWN] Cleaning up encoders...")
            self.encoders.cleanup()

        # Close I2C
        if self.mux:
            print("[SHUTDOWN] Closing I2C bus...")
            self.mux.close()

        # Clean up GPIO
        print("[SHUTDOWN] Cleaning up GPIO...")
        try:
            GPIO.cleanup()
        except Exception:
            pass

        print("[SHUTDOWN] Shutdown complete. Goodbye!")


def main():
    """Main entry point."""
    robot = DUSK()

    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n[SIGNAL] Received signal {signum}")
        robot.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        robot.start()
    except Exception as e:
        print(f"\n[FATAL] {e}")
        robot.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
