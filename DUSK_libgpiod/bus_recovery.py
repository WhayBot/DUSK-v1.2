#!/usr/bin/env python3
"""
DUSK - I2C Bus Recovery Tool

Fixes "SDA stuck LOW" condition by sending 9 clock pulses on SCL.
This is the standard I2C bus recovery procedure (per I2C specification).

Run this whenever sensors stop responding or reads return all 0x00.

Usage:
    sudo python3 bus_recovery.py

How it works:
    1. Temporarily unloads the i2c-gpio overlay to free GPIO 5/6
    2. Manually toggles SCL (GPIO 6) up to 9 times
    3. Sends STOP condition (SDA LOW→HIGH while SCL HIGH)
    4. Reloads the i2c-gpio overlay
"""

import subprocess
import time
import sys
import os


SDA_PIN = 5
SCL_PIN = 6
OVERLAY_NAME = "i2c-gpio"
OVERLAY_PARAMS = "bus=3,i2c_gpio_sda=5,i2c_gpio_scl=6,i2c_gpio_delay_us=5"

C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_RESET = "\033[0m"


def run(cmd):
    """Run a shell command."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def pin_read(pin):
    """Read GPIO pin state. Returns 'hi' or 'lo'."""
    result = run(f"pinctrl get {pin}")
    if "hi" in result.stdout:
        return "hi"
    return "lo"


def pin_set(pin, mode, level=None):
    """Set GPIO pin mode and level."""
    if level:
        run(f"pinctrl set {pin} {mode} {level}")
    else:
        run(f"pinctrl set {pin} {mode}")


def check_sda():
    """Check if SDA is stuck LOW."""
    state = pin_read(SDA_PIN)
    return state == "hi"


def do_recovery():
    """Perform I2C bus recovery by clocking SCL 9 times."""
    print(f"\n{C_CYAN}=== I2C Bus Recovery ==={C_RESET}\n")

    # Check current state
    sda_state = pin_read(SDA_PIN)
    scl_state = pin_read(SCL_PIN)
    print(f"  Before recovery:")
    print(f"    SDA (GPIO {SDA_PIN}): {C_GREEN if sda_state == 'hi' else C_RED}{sda_state}{C_RESET}")
    print(f"    SCL (GPIO {SCL_PIN}): {C_GREEN if scl_state == 'hi' else C_RED}{scl_state}{C_RESET}")

    if sda_state == "hi":
        print(f"\n  {C_GREEN}SDA is already HIGH. Bus looks OK!{C_RESET}")
        return True

    print(f"\n  {C_YELLOW}SDA is stuck LOW. Starting recovery...{C_RESET}")

    # Step 1: Unload i2c-gpio overlay to free the pins
    print("  [1/4] Unloading i2c-gpio overlay...")
    run(f"dtoverlay -r {OVERLAY_NAME}")
    time.sleep(0.5)

    # Step 2: Set SCL as output HIGH, SDA as input
    print("  [2/4] Sending 9 clock pulses on SCL...")
    pin_set(SDA_PIN, "ip", "pu")  # SDA as input with pull-up
    time.sleep(0.01)

    recovered = False
    for i in range(9):
        pin_set(SCL_PIN, "op", "dl")  # SCL LOW
        time.sleep(0.005)
        pin_set(SCL_PIN, "op", "dh")  # SCL HIGH
        time.sleep(0.005)

        # Check if SDA released
        if pin_read(SDA_PIN) == "hi":
            print(f"    SDA released after {i + 1} clock pulse(s)")
            recovered = True
            break

    if not recovered:
        # Try more aggressive: 18 pulses
        print("    SDA still LOW after 9 pulses. Trying 9 more...")
        for i in range(9):
            pin_set(SCL_PIN, "op", "dl")
            time.sleep(0.01)
            pin_set(SCL_PIN, "op", "dh")
            time.sleep(0.01)
            if pin_read(SDA_PIN) == "hi":
                print(f"    SDA released after {9 + i + 1} clock pulse(s)")
                recovered = True
                break

    # Step 3: Send STOP condition (SDA LOW→HIGH while SCL HIGH)
    if recovered:
        print("  [3/4] Sending STOP condition...")
        pin_set(SCL_PIN, "op", "dh")  # SCL HIGH
        time.sleep(0.002)
        pin_set(SDA_PIN, "op", "dl")  # SDA LOW
        time.sleep(0.002)
        pin_set(SDA_PIN, "op", "dh")  # SDA HIGH (STOP)
        time.sleep(0.002)
    else:
        print(f"  {C_RED}[3/4] SDA still stuck after 18 pulses!{C_RESET}")
        print(f"       Try power cycling the sensor board.")

    # Step 4: Set pins back to input and reload overlay
    print("  [4/4] Reloading i2c-gpio overlay...")
    pin_set(SDA_PIN, "ip")
    pin_set(SCL_PIN, "ip")
    time.sleep(0.2)

    result = run(f"dtoverlay {OVERLAY_NAME} {OVERLAY_PARAMS}")
    if result.returncode != 0:
        print(f"  {C_RED}Failed to reload overlay: {result.stderr}{C_RESET}")
        print(f"  Try rebooting: sudo reboot")
        return False

    time.sleep(0.5)

    # Verify
    sda_state = pin_read(SDA_PIN)
    scl_state = pin_read(SCL_PIN)
    print(f"\n  After recovery:")
    print(f"    SDA (GPIO {SDA_PIN}): {C_GREEN if sda_state == 'hi' else C_RED}{sda_state}{C_RESET}")
    print(f"    SCL (GPIO {SCL_PIN}): {C_GREEN if scl_state == 'hi' else C_RED}{scl_state}{C_RESET}")

    if sda_state == "hi":
        print(f"\n  {C_GREEN}Bus recovery successful!{C_RESET}")

        # Quick I2C verify
        print("  Verifying I2C communication...")
        time.sleep(0.3)
        try:
            import smbus2
            bus = smbus2.SMBus(3)
            # Try reading TCA9548A
            bus.write_byte(0x70, 0x01)  # Select channel 0
            time.sleep(0.02)
            val = bus.read_byte(0x70)
            bus.write_byte(0x70, 0x00)  # Disable all
            bus.close()
            if val == 0x01:
                print(f"    TCA9548A read-back: {C_GREEN}0x{val:02X} (OK!){C_RESET}")
            else:
                print(f"    TCA9548A read-back: {C_YELLOW}0x{val:02X} (expected 0x01){C_RESET}")
        except Exception as e:
            print(f"    {C_YELLOW}I2C verify: {e}{C_RESET}")

        return True
    else:
        print(f"\n  {C_RED}Recovery failed. SDA still stuck.{C_RESET}")
        print(f"  Suggestions:")
        print(f"    1. Power cycle all sensors (disconnect and reconnect power)")
        print(f"    2. Check for short circuits on SDA line")
        print(f"    3. sudo reboot")
        return False


def main():
    if not os.path.exists("/proc/device-tree/model"):
        print("Not running on Raspberry Pi.")
        sys.exit(1)

    if os.geteuid() != 0:
        print(f"{C_RED}Must run as root: sudo python3 bus_recovery.py{C_RESET}")
        sys.exit(1)

    success = do_recovery()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
