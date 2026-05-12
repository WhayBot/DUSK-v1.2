#!/usr/bin/env python3
"""
DUSK - Interactive Hardware Test Tool

Tests each component individually with live feedback.
Run this AFTER hw_check.py confirms all components are detected.

Usage:
    cd DUSK
    sudo python3 hw_test.py

Controls:
    Select a test by number from the menu.
    Press Ctrl+C to stop any running test and return to menu.
"""

import sys
import os
import time
import signal
import threading

# Ensure we can import project modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import i2c_mux
from i2c_mux import get_mux


def _reset_mux():
    """
    Reset the I2C mux singleton so the next test gets a fresh connection.
    Needed because some drivers (luma.oled) close the I2C bus on cleanup,
    which corrupts the shared mux connection.
    """
    if i2c_mux._mux_instance is not None:
        try:
            i2c_mux._mux_instance.close()
        except Exception:
            pass
        i2c_mux._mux_instance = None

# Auto-select IMU driver
if config.IMU_TYPE == "gy87":
    from sensors.gy87 import GY87 as IMUDriver
else:
    from sensors.mpu6050 import MPU6050 as IMUDriver


class _C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# Flag to stop running test
_stop_test = threading.Event()


def _clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


def _wait_or_stop(seconds):
    """Sleep that can be interrupted by Ctrl+C."""
    _stop_test.wait(seconds)
    return _stop_test.is_set()


def _print_header(title):
    print()
    print(f"{_C.CYAN}{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}{_C.RESET}")
    print(f"  {_C.DIM}Press Ctrl+C to stop and return to menu{_C.RESET}")
    print()


# ===================================================================
# TEST 1: OLED Eyes
# ===================================================================
def test_oled():
    _print_header("OLED Eyes Test (SSD1306)")
    from display.oled_eyes import OLEDEyes

    oled = None
    try:
        print("  Initializing OLED displays...")
        oled = OLEDEyes()

        print("  [1/4] Startup animation (eyes opening)...")
        oled.show_startup()
        if _wait_or_stop(2): return

        print("  [2/4] Blinking animation (10 seconds)...")
        oled.start()
        for i in range(10):
            if _wait_or_stop(1): break
            print(f"         Animating... {10-i}s remaining", end="\r")
        print()

        print("  [3/4] Force blink...")
        oled.force_blink()
        if _wait_or_stop(2): return

        print("  [4/4] Shutdown animation (eyes closing)...")
        oled.stop()
        oled.show_shutdown()

        print(f"\n  {_C.GREEN}OLED test complete!{_C.RESET}")

    except Exception as e:
        print(f"\n  {_C.RED}OLED test failed: {e}{_C.RESET}")
    finally:
        if oled:
            oled.stop()
            # Don't call oled.cleanup() -- it closes the I2C bus
            # and breaks other tests. Clear the displays instead.
            try:
                oled._device_left.clear()
                oled._device_right.clear()
            except Exception:
                pass


# ===================================================================
# TEST 2: VL53L0X ToF Sensors
# ===================================================================
def test_tof():
    _print_header("VL53L0X Time-of-Flight Test")

    # Raw diagnostic probe first (same method as hw_check)
    print("  [PRE-CHECK] Raw I2C probe (like hw_check)...")
    try:
        import smbus2
        bus = smbus2.SMBus(3)

        for ch, name in [(3, "Left"), (4, "Right")]:
            bus.write_byte(0x70, 1 << ch)
            time.sleep(0.02)  # Extra settle time for bit-banged I2C
            try:
                bus.read_byte(0x29)
                # Now try register read (this is what the driver does)
                time.sleep(0.01)
                model_id = bus.read_byte_data(0x29, 0xC0)
                print(f"    Ch{ch} ({name}): ACK=OK, Model ID=0x{model_id:02X} "
                      f"{'OK' if model_id == 0xEE else 'MISMATCH!'}")
            except Exception as e:
                print(f"    Ch{ch} ({name}): {_C.RED}FAIL - {e}{_C.RESET}")

        bus.write_byte(0x70, 0x00)  # Disable all channels
        bus.close()
    except Exception as e:
        print(f"    {_C.RED}Raw probe failed: {e}{_C.RESET}")

    print()

    from sensors.vl53l0x import DualVL53L0X

    tof = None
    try:
        print("  Initializing ToF sensors via driver...")
        tof = DualVL53L0X()

        print("  Reading live distances (move your hand in front of sensors):")
        print()

        while not _stop_test.is_set():
            distances = tof.get_distances()
            left = distances.get("left", 0)
            right = distances.get("right", 0)

            # Visual bar
            bar_l = "#" * min(50, left // 20)
            bar_r = "#" * min(50, right // 20)

            print(f"  LEFT:  {left:5d} mm  |{bar_l:<50}|")
            print(f"  RIGHT: {right:5d} mm  |{bar_r:<50}|")
            print(f"\033[2A", end="")  # Move cursor up 2 lines

            _stop_test.wait(0.2)

    except Exception as e:
        print(f"\n\n  {_C.RED}ToF test failed: {e}{_C.RESET}")
    finally:
        print("\n\n")


# ===================================================================
# TEST 3: GY-87 / MPU6050 IMU
# ===================================================================
def test_imu():
    imu_name = "GY-87" if config.IMU_TYPE == "gy87" else "MPU6050"
    _print_header(f"{imu_name} IMU Test")

    imu = None
    try:
        print(f"  Initializing {imu_name}...")
        imu = IMUDriver()

        # Show sensor info if GY-87
        if hasattr(imu, 'get_sensor_info'):
            info = imu.get_sensor_info()
            print(f"  Type: {info['type']}")
            print(f"  HMC5883L: {'Available' if info.get('hmc5883l') else 'N/A'}")
            print(f"  BMP180:   {'Available' if info.get('bmp180') else 'N/A'}")
            print(f"  Fusion:   {'Enabled' if info.get('fusion') else 'Disabled'}")
            print()

        print("  [1/3] Calibrating gyroscope (keep still for 2 seconds)...")
        bias = imu.calibrate_gyro(samples=200, settle_time=0.5)
        print(f"         Gyro Z bias: {bias:.4f} deg/s")
        imu.reset_heading()

        if hasattr(imu, 'calibrate_magnetometer'):
            print()
            print("  [2/3] Magnetometer calibration...")
            print(f"        {_C.YELLOW}Skip? Press Ctrl+C to skip, or wait to start.{_C.RESET}")
            if not _wait_or_stop(3):
                print("        Slowly rotate the robot 360 degrees over 15 seconds...")
                offsets = imu.calibrate_magnetometer(duration=15)
                print(f"        Offsets: X={offsets['x_offset']:.1f}, "
                      f"Y={offsets['y_offset']:.1f}, Z={offsets['z_offset']:.1f}")
        else:
            print("  [2/3] (Magnetometer: N/A - standalone MPU6050)")

        print()
        print("  [3/3] Live sensor data (rotate the robot to see changes):")
        print()

        # Print header
        if config.IMU_TYPE == "gy87":
            print(f"  {'HEADING':>8} {'MAG_HDG':>8} {'FUSED':>8} "
                  f"{'GYRO_Z':>8} {'TEMP':>6} {'PRESSURE':>10}")
            print(f"  {'-------':>8} {'-------':>8} {'-----':>8} "
                  f"{'------':>8} {'----':>6} {'--------':>10}")
        else:
            print(f"  {'HEADING':>8} {'GYRO_Z':>8} {'ACCEL_Z':>8} {'TEMP':>6}")
            print(f"  {'-------':>8} {'------':>8} {'-------':>8} {'----':>6}")

        line_count = 0
        while not _stop_test.is_set():
            imu.update_heading()

            if config.IMU_TYPE == "gy87" and hasattr(imu, 'get_fused_heading'):
                heading = imu.get_heading()
                mag_h = imu.get_mag_heading() if hasattr(imu, 'get_mag_heading') else -1
                fused = imu.get_fused_heading()
                gyro_z = imu.get_gyro_z()
                temp = imu.get_temperature_bmp() if hasattr(imu, 'get_temperature_bmp') else 0
                pres = imu.get_pressure() if hasattr(imu, 'get_pressure') else 0

                mag_str = f"{mag_h:8.1f}" if mag_h >= 0 else "    N/A "
                print(f"\r  {heading:8.1f} {mag_str} {fused:8.1f} "
                      f"{gyro_z:8.2f} {temp:5.1f}C {pres:9.1f}hPa", end="")
            else:
                heading = imu.get_heading()
                gyro_z = imu.get_gyro_z()
                accel = imu.get_accel()
                temp = imu.get_temperature()

                print(f"\r  {heading:8.1f} {gyro_z:8.2f} {accel['z']:8.3f} "
                      f"{temp:5.1f}C", end="")

            sys.stdout.flush()
            _stop_test.wait(0.1)

    except Exception as e:
        print(f"\n\n  {_C.RED}IMU test failed: {e}{_C.RESET}")
    finally:
        print("\n")


# ===================================================================
# TEST 4: INA219 Power Monitor
# ===================================================================
def test_ina():
    _print_header("INA219 Power Monitor Test")
    from sensors.ina219 import INA219

    ina = None
    try:
        print("  Initializing INA219...")
        ina = INA219()

        print("  Live battery readings:")
        print()
        print(f"  {'VOLTAGE':>8} {'CURRENT':>8} {'POWER':>8} "
              f"{'PERCENT':>8} {'STATUS':>12}")
        print(f"  {'-------':>8} {'-------':>8} {'-----':>8} "
              f"{'-------':>8} {'------':>12}")

        while not _stop_test.is_set():
            status = ina.get_status()
            v = status.get("voltage", 0)
            i = status.get("current", 0)
            p = v * i
            pct = status.get("percentage", 0)

            if status.get("critical"):
                state = f"{_C.RED}CRITICAL{_C.RESET}"
            elif status.get("low_battery"):
                state = f"{_C.YELLOW}LOW{_C.RESET}"
            else:
                state = f"{_C.GREEN}OK{_C.RESET}"

            print(f"\r  {v:7.2f}V {i:7.2f}A {p:7.2f}W "
                  f"{pct:7.1f}% {state:>20}", end="")
            sys.stdout.flush()
            _stop_test.wait(0.5)

    except Exception as e:
        print(f"\n\n  {_C.RED}INA219 test failed: {e}{_C.RESET}")
    finally:
        print("\n")


# ===================================================================
# TEST 5: Wheel Motors
# ===================================================================
def test_motors():
    _print_header("Wheel Motors Test (L298N)")
    from actuators.motors import WheelMotors

    motors = None
    try:
        print("  Initializing motors...")
        motors = WheelMotors()
        speed = 40  # Safe test speed

        tests = [
            ("Forward", lambda: motors.forward(speed)),
            ("Backward", lambda: motors.backward(speed)),
            ("Spin Left", lambda: motors.spin_left(speed)),
            ("Spin Right", lambda: motors.spin_right(speed)),
        ]

        print(f"  Test speed: {speed}%")
        print(f"  {_C.YELLOW}Each direction runs for 2 seconds.{_C.RESET}")
        print()

        for name, action in tests:
            if _stop_test.is_set():
                break
            print(f"  Testing: {name}...", end=" ", flush=True)
            action()
            if _wait_or_stop(2):
                motors.stop()
                break
            motors.stop()
            print(f"{_C.GREEN}OK{_C.RESET}")
            _wait_or_stop(0.5)

        motors.stop()
        print(f"\n  {_C.GREEN}Motor test complete!{_C.RESET}")

    except Exception as e:
        print(f"\n  {_C.RED}Motor test failed: {e}{_C.RESET}")
    finally:
        if motors:
            motors.stop()
            motors.cleanup()


# ===================================================================
# TEST 6: Sweeper Motors
# ===================================================================
def test_sweeper():
    _print_header("Sweeper Motors Test (N20)")
    from actuators.sweeper import SweeperMotors

    sweeper = None
    try:
        print("  Initializing sweeper...")
        sweeper = SweeperMotors()

        print(f"  Starting sweeper at 50% speed for 5 seconds...")
        sweeper.start(50)

        for i in range(5):
            if _wait_or_stop(1): break
            status = sweeper.get_status()
            print(f"    Running: speed={status.get('speed', 0)}%, "
                  f"{5-i}s remaining...")

        sweeper.stop()
        print(f"\n  {_C.GREEN}Sweeper test complete!{_C.RESET}")

    except Exception as e:
        print(f"\n  {_C.RED}Sweeper test failed: {e}{_C.RESET}")
    finally:
        if sweeper:
            sweeper.stop()
            sweeper.cleanup()


# ===================================================================
# TEST 7: Vacuum Motor (ESC)
# ===================================================================
def test_vacuum():
    _print_header("Vacuum Motor Test (ESC + Brushless)")
    from actuators.vacuum import VacuumMotor

    vacuum = None
    try:
        print(f"  {_C.YELLOW}WARNING: The vacuum motor will spin!{_C.RESET}")
        print(f"  {_C.YELLOW}Make sure nothing is near the impeller.{_C.RESET}")
        print()
        print("  Waiting 3 seconds before starting (Ctrl+C to cancel)...")
        if _wait_or_stop(3): return

        print("  Initializing ESC...")
        vacuum = VacuumMotor()

        print("  Arming ESC (wait for beeps)...")
        vacuum.arm()
        print("  ESC armed.")

        print("  Starting vacuum at 30% (soft-start ramp)...")
        vacuum.start(30)

        for i in range(5):
            if _wait_or_stop(1): break
            status = vacuum.get_status()
            print(f"    Running: speed={status.get('speed', 0)}%, "
                  f"{5-i}s remaining...")

        print("  Stopping (soft-stop ramp)...")
        vacuum.stop()

        print(f"\n  {_C.GREEN}Vacuum test complete!{_C.RESET}")

    except Exception as e:
        print(f"\n  {_C.RED}Vacuum test failed: {e}{_C.RESET}")
    finally:
        if vacuum:
            vacuum.stop()
            vacuum.cleanup()


# ===================================================================
# TEST 8: Speed Encoders
# ===================================================================
def test_encoders():
    _print_header("Speed Encoders Test")
    from sensors.encoders import DualEncoders

    encoders = None
    try:
        print("  Initializing encoders...")
        encoders = DualEncoders()

        print("  Manually rotate each wheel to see pulse count:")
        print()
        print(f"  {'LEFT_PULSES':>12} {'RIGHT_PULSES':>13} "
              f"{'LEFT_RPM':>10} {'RIGHT_RPM':>10}")
        print(f"  {'-----------':>12} {'------------':>13} "
              f"{'--------':>10} {'---------':>10}")

        while not _stop_test.is_set():
            status = encoders.get_status()
            speeds = encoders.get_speeds()

            left_p = status.get("left_count", 0)
            right_p = status.get("right_count", 0)
            left_rpm = speeds.get("left_rpm", 0)
            right_rpm = speeds.get("right_rpm", 0)

            print(f"\r  {left_p:12d} {right_p:13d} "
                  f"{left_rpm:9.1f} {right_rpm:10.1f}", end="")
            sys.stdout.flush()
            _stop_test.wait(0.2)

    except Exception as e:
        print(f"\n\n  {_C.RED}Encoder test failed: {e}{_C.RESET}")
    finally:
        if encoders:
            encoders.cleanup()
        print("\n")


# ===================================================================
# TEST 9: Camera
# ===================================================================
def test_camera():
    _print_header("Pi Camera Test (Picamera2)")

    try:
        from picamera2 import Picamera2

        print("  Initializing camera...")
        cam = Picamera2()
        cam_config = cam.create_still_configuration(
            main={"size": (640, 480)}
        )
        cam.configure(cam_config)
        cam.start()
        time.sleep(2)

        # Capture test image
        test_path = os.path.join(os.path.dirname(__file__), "test_capture.jpg")
        cam.capture_file(test_path)
        cam.stop()
        cam.close()

        file_size = os.path.getsize(test_path) / 1024
        print(f"  Captured test image: {test_path}")
        print(f"  File size: {file_size:.1f} KB")
        print(f"\n  {_C.GREEN}Camera test complete!{_C.RESET}")
        print(f"  {_C.DIM}View the image: feh {test_path}{_C.RESET}")

    except Exception as e:
        print(f"\n  {_C.RED}Camera test failed: {e}{_C.RESET}")


# ===================================================================
# TEST 10: Full Integration (all sensors reading simultaneously)
# ===================================================================
def test_integration():
    _print_header("Full Integration Test (All Sensors)")
    from sensors.vl53l0x import DualVL53L0X
    from sensors.ina219 import INA219

    imu = None
    tof = None
    ina = None

    try:
        print("  Initializing all sensors...")
        imu = IMUDriver()
        tof = DualVL53L0X()
        ina = INA219()

        imu.calibrate_gyro(samples=100, settle_time=0.3)
        imu.reset_heading()

        print("  All sensors active. Live dashboard:")
        print()

        while not _stop_test.is_set():
            # Read all sensors
            imu.update_heading()
            heading = imu.get_heading()
            distances = tof.get_distances()
            battery = ina.get_status()

            left_d = distances.get("left", 0)
            right_d = distances.get("right", 0)
            volts = battery.get("voltage", 0)
            amps = battery.get("current", 0)
            pct = battery.get("percentage", 0)

            line1 = (f"  Heading: {heading:6.1f} deg  |  "
                     f"ToF L: {left_d:4d} mm  R: {right_d:4d} mm  |  "
                     f"Batt: {volts:.1f}V {pct:.0f}%")

            print(f"\r{line1}", end="")
            sys.stdout.flush()
            _stop_test.wait(0.2)

    except Exception as e:
        print(f"\n\n  {_C.RED}Integration test failed: {e}{_C.RESET}")
    finally:
        print("\n")


# ===================================================================
# MENU
# ===================================================================
TESTS = [
    ("OLED Eyes (blink animation)", test_oled),
    ("VL53L0X ToF (live distance)", test_tof),
    ("IMU Gyro/Accel/Mag (live data)", test_imu),
    ("INA219 Battery (voltage/current)", test_ina),
    ("Wheel Motors (forward/back/turn)", test_motors),
    ("Sweeper Motors (N20)", test_sweeper),
    ("Vacuum Motor (ESC brushless)", test_vacuum),
    ("Speed Encoders (pulse count)", test_encoders),
    ("Camera (capture test image)", test_camera),
    ("Full Integration (all sensors)", test_integration),
]


def print_menu():
    _clear_screen()
    print()
    print(f"{_C.BOLD}{'=' * 60}")
    print(f"  DUSK - Interactive Hardware Test Tool")
    print(f"{'=' * 60}{_C.RESET}")
    print()
    for i, (name, _) in enumerate(TESTS, 1):
        print(f"  {_C.CYAN}{i:2d}{_C.RESET}. {name}")
    print()
    print(f"  {_C.CYAN} 0{_C.RESET}. Exit")
    print()


def main():
    # Check if running on Pi
    if not os.path.exists("/proc/device-tree/model"):
        print(f"\n  {_C.YELLOW}Not running on Raspberry Pi.{_C.RESET}")
        print(f"  {_C.YELLOW}Use DUSK_debug/ for simulation testing.{_C.RESET}\n")
        sys.exit(0)

    # Initialize I2C mux once
    print("Initializing I2C multiplexer...")
    try:
        mux = get_mux()
        print("I2C multiplexer ready.")
    except Exception as e:
        print(f"{_C.RED}Failed to initialize I2C: {e}{_C.RESET}")
        sys.exit(1)

    while True:
        print_menu()
        try:
            choice = input(f"  Select test (0-{len(TESTS)}): ").strip()
            if not choice:
                continue
            num = int(choice)
        except (ValueError, EOFError):
            continue
        except KeyboardInterrupt:
            print("\n")
            break

        if num == 0:
            break

        if 1 <= num <= len(TESTS):
            _stop_test.clear()
            name, func = TESTS[num - 1]
            _reset_mux()  # Fresh I2C connection for each test
            try:
                func()
            except KeyboardInterrupt:
                _stop_test.set()
                print(f"\n\n  {_C.YELLOW}Test stopped.{_C.RESET}")

            print(f"\n  {_C.DIM}Press Enter to return to menu...{_C.RESET}")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass

    print(f"\n  {_C.GREEN}Goodbye!{_C.RESET}\n")


if __name__ == "__main__":
    main()
