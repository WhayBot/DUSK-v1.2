#!/usr/bin/env python3
"""
DUSK - Hardware Diagnostic Tool

Scans all connected components and reports their status.
Run this on the Raspberry Pi BEFORE starting the main application
to verify wiring and connections.

Usage:
    sudo python3 hw_check.py

Output:
    A table showing every expected component, whether it was
    detected, its I2C address (if applicable), and any errors.
"""

import sys
import time
import os

# ===========================================================================
# ANSI colors for terminal output
# ===========================================================================
class _C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# ===========================================================================
# Test result tracking
# ===========================================================================
class DiagResult:
    def __init__(self):
        self.results = []

    def ok(self, component, detail="", address=""):
        self.results.append(("OK", component, detail, address))

    def fail(self, component, detail="", address=""):
        self.results.append(("FAIL", component, detail, address))

    def warn(self, component, detail="", address=""):
        self.results.append(("WARN", component, detail, address))

    def skip(self, component, detail="", address=""):
        self.results.append(("SKIP", component, detail, address))

    def print_report(self):
        ok_count = sum(1 for r in self.results if r[0] == "OK")
        fail_count = sum(1 for r in self.results if r[0] == "FAIL")
        warn_count = sum(1 for r in self.results if r[0] == "WARN")
        skip_count = sum(1 for r in self.results if r[0] == "SKIP")
        total = len(self.results)

        print()
        print(f"{_C.BOLD}{'=' * 70}{_C.RESET}")
        print(f"{_C.BOLD}  DIAGNOSTIC REPORT{_C.RESET}")
        print(f"{'=' * 70}")
        print()
        print(f"  {'STATUS':<8} {'COMPONENT':<30} {'ADDRESS':<12} {'DETAIL'}")
        print(f"  {'------':<8} {'-----------------------------':<30} {'----------':<12} {'------'}")

        for status, component, detail, address in self.results:
            if status == "OK":
                icon = f"{_C.GREEN}[  OK  ]{_C.RESET}"
            elif status == "FAIL":
                icon = f"{_C.RED}[ FAIL ]{_C.RESET}"
            elif status == "WARN":
                icon = f"{_C.YELLOW}[ WARN ]{_C.RESET}"
            else:
                icon = f"{_C.DIM}[ SKIP ]{_C.RESET}"

            addr_str = address if address else "-"
            det_str = detail if detail else ""
            print(f"  {icon} {component:<30} {addr_str:<12} {det_str}")

        print()
        print(f"{'=' * 70}")
        summary_parts = []
        if ok_count:
            summary_parts.append(f"{_C.GREEN}{ok_count} OK{_C.RESET}")
        if fail_count:
            summary_parts.append(f"{_C.RED}{fail_count} FAIL{_C.RESET}")
        if warn_count:
            summary_parts.append(f"{_C.YELLOW}{warn_count} WARN{_C.RESET}")
        if skip_count:
            summary_parts.append(f"{_C.DIM}{skip_count} SKIP{_C.RESET}")
        print(f"  Total: {total} components | {' | '.join(summary_parts)}")
        print(f"{'=' * 70}")
        print()

        if fail_count == 0:
            print(f"  {_C.GREEN}{_C.BOLD}All critical components detected. Ready to run!{_C.RESET}")
        else:
            print(f"  {_C.RED}{_C.BOLD}{fail_count} component(s) not detected. Check wiring!{_C.RESET}")
        print()

        return fail_count == 0


# ===========================================================================
# I2C Bus Check
# ===========================================================================
def check_i2c_bus(diag):
    """Check if the I2C bus is accessible."""
    print(f"\n{_C.CYAN}[1/6] I2C Bus{_C.RESET}")
    print(f"      Checking virtual I2C bus 3 (GPIO 5/6)...")

    try:
        import smbus2
        bus = smbus2.SMBus(3)
        bus.close()
        diag.ok("I2C Bus 3 (GPIO 5/6)", "Virtual bus accessible")
        return True
    except FileNotFoundError:
        diag.fail("I2C Bus 3 (GPIO 5/6)",
                  "Bus not found. Check dtoverlay=i2c-gpio in /boot/config.txt")
        return False
    except PermissionError:
        diag.fail("I2C Bus 3 (GPIO 5/6)",
                  "Permission denied. Run with sudo")
        return False
    except Exception as e:
        diag.fail("I2C Bus 3 (GPIO 5/6)", str(e))
        return False


# ===========================================================================
# TCA9548A Multiplexer Check
# ===========================================================================
def check_multiplexer(diag):
    """Check if the TCA9548A multiplexer responds."""
    print(f"\n{_C.CYAN}[2/6] I2C Multiplexer (TCA9548A){_C.RESET}")

    try:
        import smbus2
        bus = smbus2.SMBus(3)

        # Try to read from TCA9548A at 0x70
        try:
            bus.read_byte(0x70)
            diag.ok("TCA9548A Multiplexer", "Responding", "0x70")
            bus.close()
            return True
        except Exception:
            diag.fail("TCA9548A Multiplexer",
                      "No response at 0x70. Check power and SDA/SCL wiring", "0x70")
            bus.close()
            return False

    except Exception as e:
        diag.fail("TCA9548A Multiplexer", str(e), "0x70")
        return False


# ===========================================================================
# I2C Device Scan (through multiplexer)
# ===========================================================================
def check_i2c_devices(diag):
    """Scan each TCA9548A channel for expected I2C devices."""
    print(f"\n{_C.CYAN}[3/6] I2C Devices (via TCA9548A){_C.RESET}")

    # Expected devices per channel
    expected = {
        0: {"name": "MPU6050 / GY-87 (IMU)", "addr": 0x68,
            "bypass_addrs": [
                (0x1E, "HMC5883L (Magnetometer)"),
                (0x77, "BMP180 (Barometer)"),
            ]},
        1: {"name": "OLED Left Eye (SSD1306)", "addr": 0x3C},
        2: {"name": "OLED Right Eye (SSD1306)", "addr": 0x3C},
        3: {"name": "VL53L0X Left (ToF)", "addr": 0x29},
        4: {"name": "VL53L0X Right (ToF)", "addr": 0x29},
        5: {"name": "INA219 (Power Monitor)", "addr": 0x40},
    }

    try:
        import smbus2
        bus = smbus2.SMBus(3)
    except Exception as e:
        for ch, info in expected.items():
            diag.skip(info["name"], "I2C bus unavailable", f"0x{info['addr']:02X}")
        return

    for ch in range(6):
        info = expected[ch]
        addr = info["addr"]
        name = info["name"]

        print(f"      Channel {ch}: scanning for {name} (0x{addr:02X})...")

        try:
            # Select channel
            bus.write_byte(0x70, 1 << ch)
            time.sleep(0.01)

            # Probe expected address
            try:
                bus.read_byte(addr)
                diag.ok(name, f"Channel {ch}", f"0x{addr:02X}")

                # For channel 0 (MPU6050), try enabling bypass and checking GY-87 extras
                if ch == 0 and "bypass_addrs" in info:
                    _check_gy87_bypass(bus, addr, info["bypass_addrs"], diag)

            except Exception:
                diag.fail(name, f"No response on channel {ch}", f"0x{addr:02X}")

        except Exception as e:
            diag.fail(name, f"Channel select failed: {e}", f"0x{addr:02X}")

    # Disable all mux channels before closing
    try:
        bus.write_byte(0x70, 0x00)
    except Exception:
        pass

    bus.close()


def _check_gy87_bypass(bus, mpu_addr, bypass_addrs, diag):
    """Enable MPU6050 I2C bypass mode and check for HMC5883L / BMP180."""
    print(f"      Enabling MPU6050 bypass mode for GY-87 detection...")

    try:
        # Disable I2C master
        bus.write_byte_data(mpu_addr, 0x6A, 0x00)
        time.sleep(0.01)
        # Enable bypass
        bus.write_byte_data(mpu_addr, 0x37, 0x02)
        time.sleep(0.05)  # Give bypass more time to settle

        for addr, name in bypass_addrs:
            try:
                bus.read_byte(addr)
                diag.ok(name, "GY-87 bypass (Ch0)", f"0x{addr:02X}")
            except Exception:
                # Also check QMC5883L at 0x0D if HMC5883L not found
                if addr == 0x1E:
                    try:
                        bus.read_byte(0x0D)
                        diag.ok("QMC5883L (Magnetometer)",
                                "GY-87 bypass (Ch0)", "0x0D")
                    except Exception:
                        diag.warn(name,
                                  "Not found (standalone MPU6050?)", f"0x{addr:02X}")
                else:
                    diag.warn(name,
                              "Not found (standalone MPU6050?)", f"0x{addr:02X}")

        # Disable bypass mode to prevent phantom devices on subsequent scans
        bus.write_byte_data(mpu_addr, 0x37, 0x00)
        time.sleep(0.01)

    except Exception as e:
        print(f"      Bypass mode failed: {e}")
        # Try to disable bypass even on error
        try:
            bus.write_byte_data(mpu_addr, 0x37, 0x00)
        except Exception:
            pass


# ===========================================================================
# GPIO Check
# ===========================================================================
def check_gpio(diag):
    """Check if GPIO pins can be configured."""
    print(f"\n{_C.CYAN}[4/6] GPIO Pins{_C.RESET}")

    # Try RPi.GPIO first, then gpiod
    gpio_lib = None

    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        gpio_lib = "RPi.GPIO"
    except ImportError:
        try:
            import gpiod
            gpio_lib = "gpiod"
        except ImportError:
            diag.skip("GPIO System", "No GPIO library (RPi.GPIO or gpiod)")
            return

    if gpio_lib == "RPi.GPIO":
        import RPi.GPIO as GPIO
        pins = {
            "Encoder Left":    (14, "IN"),
            "Encoder Right":   (7,  "IN"),
            "Motor Left ENA":  (10, "OUT"),
            "Motor Left IN1":  (12, "OUT"),
            "Motor Left IN2":  (13, "OUT"),
            "Motor Right IN3": (19, "OUT"),
            "Motor Right IN4": (16, "OUT"),
            "Motor Right ENB": (9,  "OUT"),
            "Sweeper ENA":     (26, "OUT"),
            "Sweeper IN1":     (24, "OUT"),
            "Sweeper IN2":     (25, "OUT"),
        }

        for name, (pin, direction) in pins.items():
            try:
                if direction == "OUT":
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
                else:
                    GPIO.setup(pin, GPIO.IN)
                diag.ok(f"GPIO {pin} ({name})", f"{direction} configured", f"BCM {pin}")
            except Exception as e:
                diag.fail(f"GPIO {pin} ({name})", str(e), f"BCM {pin}")

        # Clean up without resetting
        try:
            GPIO.cleanup()
        except Exception:
            pass

    elif gpio_lib == "gpiod":
        diag.ok("GPIO System", "gpiod available (pin-level test skipped)")


# ===========================================================================
# pigpiod Check (for ESC hardware PWM)
# ===========================================================================
def check_pigpiod(diag):
    """Check if pigpiod is running (needed for ESC PWM on GPIO 18)."""
    print(f"\n{_C.CYAN}[5/6] pigpiod (Hardware PWM){_C.RESET}")

    try:
        import pigpio
        pi = pigpio.pi()
        if pi.connected:
            diag.ok("pigpiod daemon", "Running and connected")
            # Test GPIO 18 access
            try:
                pi.set_servo_pulsewidth(18, 0)
                diag.ok("ESC PWM (GPIO 18)", "Hardware PWM available", "BCM 18")
            except Exception as e:
                diag.warn("ESC PWM (GPIO 18)", str(e), "BCM 18")
            pi.stop()
        else:
            diag.fail("pigpiod daemon",
                      "Not running. Start with: sudo pigpiod")
    except ImportError:
        diag.fail("pigpiod daemon", "pigpio library not installed")
    except Exception as e:
        diag.fail("pigpiod daemon", str(e))


# ===========================================================================
# Camera Check
# ===========================================================================
def check_camera(diag):
    """Check if the camera is accessible."""
    print(f"\n{_C.CYAN}[6/6] Camera{_C.RESET}")

    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam_info = cam.camera_properties
        diag.ok("Pi Camera (Picamera2)",
                f"Model: {cam_info.get('Model', 'unknown')}")
        cam.close()
    except ImportError:
        diag.warn("Pi Camera (Picamera2)", "picamera2 not installed")
    except Exception as e:
        err = str(e)
        if "no cameras" in err.lower():
            diag.fail("Pi Camera", "No camera detected. Check ribbon cable")
        else:
            diag.warn("Pi Camera", err)


# ===========================================================================
# SPI/UART Conflict Check
# ===========================================================================
def check_conflicts(diag):
    """Check for known pin conflicts (SPI, UART enabled)."""
    print(f"\n{_C.CYAN}[BONUS] Pin Conflict Check{_C.RESET}")

    # Check if SPI is enabled (conflicts with GPIO 7, 9, 10)
    spi_enabled = os.path.exists("/dev/spidev0.0") or os.path.exists("/dev/spidev0.1")
    if spi_enabled:
        diag.warn("SPI0 Enabled",
                  "Conflicts with GPIO 7 (encoder), 9/10 (motors). Disable with dtparam=spi=off")
    else:
        diag.ok("SPI0 Disabled", "No conflict with GPIO 7, 9, 10")

    # Check if serial console is on GPIO 14
    try:
        with open("/boot/cmdline.txt", "r") as f:
            cmdline = f.read()
        if "ttyAMA0" in cmdline or "serial0" in cmdline:
            diag.warn("Serial Console",
                      "May conflict with GPIO 14 (encoder). Disable via raspi-config")
        else:
            diag.ok("Serial Console", "Not using GPIO 14")
    except FileNotFoundError:
        # Try /boot/firmware/cmdline.txt for newer Pi OS
        try:
            with open("/boot/firmware/cmdline.txt", "r") as f:
                cmdline = f.read()
            if "ttyAMA0" in cmdline or "serial0" in cmdline:
                diag.warn("Serial Console",
                          "May conflict with GPIO 14 (encoder)")
            else:
                diag.ok("Serial Console", "Not using GPIO 14")
        except Exception:
            diag.skip("Serial Console", "Could not check /boot/cmdline.txt")

    # Check I2C virtual bus overlay
    try:
        for cfg_path in ["/boot/config.txt", "/boot/firmware/config.txt"]:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    config_txt = f.read()
                if "i2c-gpio" in config_txt and "bus=3" in config_txt:
                    diag.ok("I2C GPIO Overlay", f"dtoverlay=i2c-gpio found in {cfg_path}")
                else:
                    diag.warn("I2C GPIO Overlay",
                              f"dtoverlay=i2c-gpio,bus=3 not found in {cfg_path}")
                break
        else:
            diag.skip("I2C GPIO Overlay", "Could not find config.txt")
    except Exception:
        diag.skip("I2C GPIO Overlay", "Could not read config.txt")


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print()
    print(f"{_C.BOLD}{'=' * 70}{_C.RESET}")
    print(f"{_C.BOLD}  DUSK - Hardware Diagnostic Tool{_C.RESET}")
    print(f"  Scanning all connected components...")
    print(f"{'=' * 70}")

    diag = DiagResult()

    # Check if running on Raspberry Pi
    is_pi = os.path.exists("/proc/device-tree/model")
    if is_pi:
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read().strip().rstrip('\x00')
            print(f"\n  Board: {_C.GREEN}{model}{_C.RESET}")
        except Exception:
            print(f"\n  Board: {_C.YELLOW}Unknown Pi model{_C.RESET}")
    else:
        print(f"\n  {_C.YELLOW}Not running on Raspberry Pi.{_C.RESET}")
        print(f"  {_C.YELLOW}This tool requires physical hardware.{_C.RESET}")
        print(f"  {_C.YELLOW}Use 'python validate.py' for software testing.{_C.RESET}")
        print()
        sys.exit(0)

    # Check if running as root
    if os.geteuid() != 0:
        print(f"\n  {_C.RED}WARNING: Not running as root.{_C.RESET}")
        print(f"  {_C.RED}Some tests may fail. Run with: sudo python3 hw_check.py{_C.RESET}")

    # Run all checks
    i2c_ok = check_i2c_bus(diag)

    if i2c_ok:
        mux_ok = check_multiplexer(diag)
        if mux_ok:
            check_i2c_devices(diag)
        else:
            # Skip I2C device checks if mux is not found
            for name in ["MPU6050 / GY-87 (IMU)", "OLED Left Eye (SSD1306)",
                         "OLED Right Eye (SSD1306)", "VL53L0X Left (ToF)",
                         "VL53L0X Right (ToF)", "INA219 (Power Monitor)"]:
                diag.skip(name, "Multiplexer not available")

    check_gpio(diag)
    check_pigpiod(diag)
    check_camera(diag)
    check_conflicts(diag)

    # Print final report
    all_ok = diag.print_report()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
