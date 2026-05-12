#!/usr/bin/env python3
"""
DUSK - I2C Bus Recovery Tool

Fixes "SDA stuck LOW" condition by sending clock pulses on SCL.
This is the standard I2C bus recovery procedure (per I2C specification).

Run this whenever sensors stop responding or reads return all 0x00.

Usage:
    sudo python3 bus_recovery.py

How it works:
    1. Temporarily unloads the i2c-gpio overlay to free GPIO 5/6
    2. Manually toggles SCL (GPIO 6) with various patterns
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

C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_RESET = "\033[0m"


def run(cmd):
    """Run a shell command (as list or string)."""
    if isinstance(cmd, list):
        return subprocess.run(cmd, capture_output=True, text=True)
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


def reload_overlay():
    """Reload the i2c-gpio overlay with correct parameters."""
    pin_set(SDA_PIN, "ip")
    pin_set(SCL_PIN, "ip")
    time.sleep(0.2)

    # dtoverlay command-line expects space-separated params, NOT comma
    result = run([
        "dtoverlay", OVERLAY_NAME,
        "bus=3",
        "i2c_gpio_sda=5",
        "i2c_gpio_scl=6",
        "i2c_gpio_delay_us=5"
    ])
    if result.returncode != 0:
        print(f"  {C_RED}Failed to reload overlay: {result.stderr.strip()}{C_RESET}")
        print(f"  Try rebooting: sudo reboot")
        return False

    time.sleep(0.5)
    return True


def do_recovery():
    """Perform I2C bus recovery by clocking SCL."""
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
    print("  [1/5] Unloading i2c-gpio overlay...")
    run(f"dtoverlay -r {OVERLAY_NAME}")
    time.sleep(0.5)

    # Make sure pins are in the right mode
    pin_set(SDA_PIN, "ip", "pu")  # SDA = input with pull-up
    pin_set(SCL_PIN, "op", "dh")  # SCL = output HIGH
    time.sleep(0.05)

    # Step 2: Standard recovery - 9 clock pulses
    print("  [2/5] Sending 9 clock pulses...")
    recovered = False
    for i in range(9):
        pin_set(SCL_PIN, "op", "dl")
        time.sleep(0.005)
        pin_set(SCL_PIN, "op", "dh")
        time.sleep(0.005)
        if pin_read(SDA_PIN) == "hi":
            print(f"    SDA released after {i + 1} clock pulse(s)")
            recovered = True
            break

    # Step 3: If still stuck, try toggling SDA too (force START+STOP)
    if not recovered:
        print("  [3/5] Trying START/STOP conditions...")
        for attempt in range(5):
            # Generate START: SDA HIGH→LOW while SCL HIGH
            pin_set(SCL_PIN, "op", "dh")
            time.sleep(0.002)
            pin_set(SDA_PIN, "op", "dh")
            time.sleep(0.002)
            pin_set(SDA_PIN, "op", "dl")  # START
            time.sleep(0.002)

            # Clock 9 bits
            for j in range(9):
                pin_set(SCL_PIN, "op", "dl")
                time.sleep(0.002)
                pin_set(SCL_PIN, "op", "dh")
                time.sleep(0.002)

            # Generate STOP: SDA LOW→HIGH while SCL HIGH
            pin_set(SDA_PIN, "op", "dl")
            time.sleep(0.002)
            pin_set(SCL_PIN, "op", "dh")
            time.sleep(0.002)
            pin_set(SDA_PIN, "op", "dh")  # STOP
            time.sleep(0.01)

            # Check
            pin_set(SDA_PIN, "ip", "pu")
            time.sleep(0.01)
            if pin_read(SDA_PIN) == "hi":
                print(f"    SDA released after START/STOP attempt {attempt + 1}")
                recovered = True
                break
    else:
        print("  [3/5] (skipped - already recovered)")

    # Step 4: If STILL stuck, try bus reset (both lines LOW then HIGH)
    if not recovered:
        print("  [4/5] Trying full bus reset...")
        # Pull both lines LOW
        pin_set(SDA_PIN, "op", "dl")
        pin_set(SCL_PIN, "op", "dl")
        time.sleep(0.1)
        # Release both lines HIGH
        pin_set(SCL_PIN, "op", "dh")
        time.sleep(0.01)
        pin_set(SDA_PIN, "op", "dh")
        time.sleep(0.1)
        # Set SDA as input and check
        pin_set(SDA_PIN, "ip", "pu")
        time.sleep(0.05)
        if pin_read(SDA_PIN) == "hi":
            print(f"    SDA released after bus reset!")
            recovered = True
        else:
            print(f"  {C_RED}[4/5] SDA still stuck LOW after all recovery attempts!{C_RESET}")
            print(f"       A device is actively holding SDA LOW.")
            print()
            print(f"  {C_YELLOW}TROUBLESHOOTING:{C_RESET}")
            print(f"    1. Power cycle: disconnect ALL sensor power, wait 10s, reconnect")
            print(f"    2. Disconnect SDA wire from TCA9548A board, run this again")
            print(f"       - If SDA goes HIGH: a sensor/mux is the problem")
            print(f"       - If SDA stays LOW: wiring issue (short to GND?)")
            print(f"    3. Check solder joints on TCA9548A SDA pin")
    else:
        print("  [4/5] (skipped - already recovered)")

    # Step 5: Send final STOP and reload overlay
    if recovered:
        print("  [5/5] Sending STOP condition and reloading overlay...")
        pin_set(SCL_PIN, "op", "dh")
        time.sleep(0.002)
        pin_set(SDA_PIN, "op", "dl")
        time.sleep(0.002)
        pin_set(SDA_PIN, "op", "dh")  # STOP
        time.sleep(0.01)
    else:
        print("  [5/5] Reloading overlay anyway...")

    if not reload_overlay():
        return False

    # Verify
    sda_state = pin_read(SDA_PIN)
    scl_state = pin_read(SCL_PIN)
    print(f"\n  After recovery:")
    print(f"    SDA (GPIO {SDA_PIN}): {C_GREEN if sda_state == 'hi' else C_RED}{sda_state}{C_RESET}")
    print(f"    SCL (GPIO {SCL_PIN}): {C_GREEN if scl_state == 'hi' else C_RED}{scl_state}{C_RESET}")

    if sda_state == "hi":
        print(f"\n  {C_GREEN}Bus recovery successful!{C_RESET}")

        # Quick I2C verify
        print("  Verifying I2C register read...")
        time.sleep(0.3)
        try:
            import smbus2
            bus = smbus2.SMBus(3)
            bus.write_byte(0x70, 0x01)  # Select channel 0
            time.sleep(0.02)
            val = bus.read_byte(0x70)
            bus.write_byte(0x70, 0x00)
            bus.close()
            if val == 0x01:
                print(f"    TCA9548A read-back: {C_GREEN}0x{val:02X} (PASS){C_RESET}")
            else:
                print(f"    TCA9548A read-back: {C_YELLOW}0x{val:02X} (expected 0x01){C_RESET}")
        except Exception as e:
            print(f"    {C_YELLOW}I2C verify failed: {e}{C_RESET}")

        return True
    else:
        print(f"\n  {C_RED}Recovery failed. SDA still stuck.{C_RESET}")
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
