"""
DUSK - Dust Unification and Sweeping Keeper
Debug / Simulation Version - Main Entry Point

Runs the full DUSK application with simulated hardware.
No Raspberry Pi, sensors, motors, or camera needed.
Works on Windows, macOS, and Linux.

The web server is fully functional and accessible at:
    http://localhost:5000

Usage:
    python main.py
"""

import sys
import signal
import time
import threading

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
    DUSK robot controller - DEBUG/SIMULATION version.
    
    All hardware is simulated. The web server, REST API,
    and navigation logic run identically to the real version.
    """

    def __init__(self):
        self._running = False
        self._shutdown_event = threading.Event()

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
        print("[INIT] I2C Multiplexer (TCA9548A) [SIMULATED]...")
        self.mux = get_mux()
        devices = self.mux.scan_all()
        for ch, addrs in devices.items():
            addr_str = [f"0x{a:02X}" for a in addrs]
            print(f"  Channel {ch}: {addr_str}")
        print("[INIT] I2C Multiplexer: OK")

    def _init_sensors(self):
        print("[INIT] MPU6050 (Gyro + Accelerometer) [SIMULATED]...")
        self.imu = MPU6050()
        print("[INIT] MPU6050: OK")

        print("[INIT] VL53L0X ToF sensors (Left + Right) [SIMULATED]...")
        self.tof = DualVL53L0X()
        distances = self.tof.get_distances()
        print(f"  Left: {distances['left']}mm, Right: {distances['right']}mm")
        print("[INIT] VL53L0X: OK")

        print("[INIT] INA219 (Power Monitor) [SIMULATED]...")
        self.ina = INA219()
        status = self.ina.get_status()
        print(f"  Battery: {status['voltage']}V, {status['percentage']}%")
        print("[INIT] INA219: OK")

        print("[INIT] Speed Encoders (Left + Right) [SIMULATED]...")
        self.encoders = DualEncoders()
        print("[INIT] Encoders: OK")

    def _init_actuators(self):
        print("[INIT] Wheel Motors (L298N) [SIMULATED]...")
        self.motors = WheelMotors()
        # Connect feedback loop: motors -> encoders + IMU
        self.motors.set_feedback_targets(self.encoders, self.imu)
        print("[INIT] Wheel Motors: OK")

        print("[INIT] Sweeper Motors (N20) [SIMULATED]...")
        self.sweeper = SweeperMotors()
        print("[INIT] Sweeper Motors: OK")

        print("[INIT] Vacuum Motor (ESC + Brushless) [SIMULATED]...")
        self.vacuum = VacuumMotor()
        self.vacuum.arm()
        print("[INIT] Vacuum Motor: OK")

    def _init_display(self):
        print("[INIT] OLED Eyes (Left + Right) [SIMULATED]...")
        self.oled = OLEDEyes()
        self.oled.show_startup()
        self.oled.start()
        print("[INIT] OLED Eyes: OK")

    def _init_navigation(self):
        print("[INIT] Navigation Controller...")
        self.navigator = ZigZagNavigator(
            self.motors, self.encoders, self.imu, self.tof
        )
        print("[INIT] Navigation: OK")

    def _init_web(self):
        print("[INIT] Camera Stream [SIMULATED - test pattern]...")
        self.camera = CameraStream()
        print("[INIT] Camera: OK")

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
        print(f"[INIT] Web Server: OK (http://localhost:{config.WEB_PORT})")

    def start(self):
        print("=" * 60)
        print("  DUSK - Dust Unification & Sweeping Keeper")
        print("  >>> DEBUG / SIMULATION MODE <<<")
        print("  No hardware required - all sensors simulated")
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
            import traceback
            traceback.print_exc()
            self.shutdown()
            raise

        print()
        print("=" * 60)
        print("  All systems initialized (SIMULATED)!")
        print(f"  Web panel: http://localhost:{config.WEB_PORT}")
        print("  Mode: Manual (switch via web panel)")
        print("  Press Ctrl+C to shutdown")
        print("=" * 60)
        print()

        self._running = True

        # Baseline gyro calibration (simulated)
        print("[CAL] Baseline gyro calibration (simulated)...")
        self.imu.calibrate_gyro(samples=10)
        self.imu.reset_heading()
        print(f"[CAL] Baseline bias: {self.imu._gyro_z_bias:.4f} deg/s")

        # Main monitoring loop
        self._main_loop()

    def _main_loop(self):
        while self._running and not self._shutdown_event.is_set():
            try:
                battery = self.ina.get_status()
                if battery["critical"]:
                    print("[!!! ] CRITICAL BATTERY (simulated)!")
                    self._emergency_stop()
                    break

                self.encoders.get_speeds()
                self.imu.update_heading()

                self._shutdown_event.wait(0.5)  # Slower loop in debug

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Main loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)

        self.shutdown()

    def _emergency_stop(self):
        print("[EMERGENCY] Stopping all motors!")
        try:
            self.motors.stop()
            self.sweeper.stop()
            self.vacuum.stop()
            self.navigator.stop()
        except Exception:
            pass

    def shutdown(self):
        if not self._running and self.motors is None:
            return

        self._running = False
        self._shutdown_event.set()
        print("\n[SHUTDOWN] Initiating graceful shutdown...")

        if self.navigator:
            self.navigator.stop()
        if self.motors:
            self.motors.stop()
            self.motors.cleanup()
        if self.sweeper:
            self.sweeper.stop()
            self.sweeper.cleanup()
        if self.vacuum:
            self.vacuum.cleanup()
        if self.camera:
            self.camera.cleanup()
        if self.oled:
            self.oled.show_shutdown()
            self.oled.cleanup()
        if self.encoders:
            self.encoders.cleanup()
        if self.mux:
            self.mux.close()

        print("[SHUTDOWN] Shutdown complete. Goodbye!")


def main():
    robot = DUSK()

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
