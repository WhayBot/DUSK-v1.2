#!/usr/bin/env python3
"""
DUSK - I2C Bus Recovery Tool (Fast GPIO version)

Fixes "SDA stuck LOW" by sending rapid clock pulses via RPi.GPIO.
Much faster than pinctrl-based approach.

Usage:
    sudo python3 bus_recovery.py
"""

import time
import sys
import os
import subprocess

SDA_PIN = 5  # BCM 5
SCL_PIN = 6  # BCM 6

C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_RESET = "\033[0m"


def run(cmd):
    """Run a shell command."""
    if isinstance(cmd, list):
        return subprocess.run(cmd, capture_output=True, text=True)
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def pin_read_pinctrl(pin):
    """Read pin state via pinctrl (works even when overlay is active)."""
    result = run(f"pinctrl get {pin}")
    return "hi" if "hi" in result.stdout else "lo"


def do_recovery():
    """Perform I2C bus recovery using RPi.GPIO for fast toggling."""
    print(f"\n{C_CYAN}=== I2C Bus Recovery (Fast GPIO) ==={C_RESET}\n")

    sda_state = pin_read_pinctrl(SDA_PIN)
    scl_state = pin_read_pinctrl(SCL_PIN)
    print(f"  Before recovery:")
    print(f"    SDA (GPIO {SDA_PIN}): {C_GREEN if sda_state == 'hi' else C_RED}{sda_state}{C_RESET}")
    print(f"    SCL (GPIO {SCL_PIN}): {C_GREEN if scl_state == 'hi' else C_RED}{scl_state}{C_RESET}")

    if sda_state == "hi":
        print(f"\n  {C_GREEN}SDA is already HIGH. Bus looks OK!{C_RESET}")
        return True

    print(f"\n  {C_YELLOW}SDA is stuck LOW. Starting recovery...{C_RESET}")

    # Step 1: Unload i2c-gpio overlay
    print("  [1/4] Unloading i2c-gpio overlay...")
    run("dtoverlay -r i2c-gpio")
    time.sleep(0.5)

    # Step 2: Fast GPIO recovery using RPi.GPIO
    print("  [2/4] Fast clock recovery (RPi.GPIO)...")
    recovered = False
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # === PHASE 1: Standard 9 clock pulses ===
        GPIO.setup(SDA_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SCL_PIN, GPIO.OUT, initial=GPIO.HIGH)
        time.sleep(0.01)

        print("    Phase 1: 9 standard clock pulses...")
        for i in range(9):
            GPIO.output(SCL_PIN, GPIO.LOW)
            time.sleep(0.001)
            GPIO.output(SCL_PIN, GPIO.HIGH)
            time.sleep(0.001)
            if GPIO.input(SDA_PIN) == GPIO.HIGH:
                print(f"    → SDA released after {i+1} pulse(s)!")
                recovered = True
                break

        # === PHASE 2: START/STOP sequences ===
        if not recovered:
            print("    Phase 2: START/STOP sequences (5 attempts)...")
            for attempt in range(5):
                # SDA as output for START/STOP generation
                GPIO.setup(SDA_PIN, GPIO.OUT)

                # START condition: SDA HIGH→LOW while SCL HIGH
                GPIO.output(SCL_PIN, GPIO.HIGH)
                GPIO.output(SDA_PIN, GPIO.HIGH)
                time.sleep(0.001)
                GPIO.output(SDA_PIN, GPIO.LOW)  # START
                time.sleep(0.001)

                # Clock 9 bits out
                for _ in range(9):
                    GPIO.output(SCL_PIN, GPIO.LOW)
                    time.sleep(0.0005)
                    GPIO.output(SCL_PIN, GPIO.HIGH)
                    time.sleep(0.0005)

                # STOP condition: SDA LOW→HIGH while SCL HIGH
                GPIO.output(SDA_PIN, GPIO.LOW)
                time.sleep(0.001)
                GPIO.output(SCL_PIN, GPIO.HIGH)
                time.sleep(0.001)
                GPIO.output(SDA_PIN, GPIO.HIGH)  # STOP
                time.sleep(0.005)

                # Check SDA
                GPIO.setup(SDA_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                time.sleep(0.005)
                if GPIO.input(SDA_PIN) == GPIO.HIGH:
                    print(f"    → SDA released after START/STOP attempt {attempt+1}!")
                    recovered = True
                    break

        # === PHASE 3: Rapid burst (100 pulses) ===
        if not recovered:
            print("    Phase 3: Rapid burst (100 pulses)...")
            GPIO.setup(SDA_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(SCL_PIN, GPIO.OUT)
            for i in range(100):
                GPIO.output(SCL_PIN, GPIO.LOW)
                time.sleep(0.0002)
                GPIO.output(SCL_PIN, GPIO.HIGH)
                time.sleep(0.0002)
                if i % 9 == 8:
                    # Send STOP every 9 pulses
                    GPIO.setup(SDA_PIN, GPIO.OUT)
                    GPIO.output(SDA_PIN, GPIO.LOW)
                    time.sleep(0.0005)
                    GPIO.output(SDA_PIN, GPIO.HIGH)  # STOP
                    time.sleep(0.001)
                    GPIO.setup(SDA_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    time.sleep(0.001)
                    if GPIO.input(SDA_PIN) == GPIO.HIGH:
                        print(f"    → SDA released after {i+1} rapid pulses!")
                        recovered = True
                        break

        # === PHASE 4: Bus reset (both LOW then release) ===
        if not recovered:
            print("    Phase 4: Full bus reset...")
            GPIO.setup(SDA_PIN, GPIO.OUT)
            GPIO.setup(SCL_PIN, GPIO.OUT)
            GPIO.output(SDA_PIN, GPIO.LOW)
            GPIO.output(SCL_PIN, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(SCL_PIN, GPIO.HIGH)
            time.sleep(0.01)
            GPIO.output(SDA_PIN, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.setup(SDA_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            time.sleep(0.05)
            if GPIO.input(SDA_PIN) == GPIO.HIGH:
                print("    → SDA released after bus reset!")
                recovered = True

        # Final STOP if recovered
        if recovered:
            print("  [3/4] Sending final STOP condition...")
            GPIO.setup(SCL_PIN, GPIO.OUT)
            GPIO.setup(SDA_PIN, GPIO.OUT)
            GPIO.output(SCL_PIN, GPIO.HIGH)
            GPIO.output(SDA_PIN, GPIO.LOW)
            time.sleep(0.001)
            GPIO.output(SDA_PIN, GPIO.HIGH)
            time.sleep(0.001)

        GPIO.cleanup([SDA_PIN, SCL_PIN])

    except ImportError:
        print(f"    {C_RED}RPi.GPIO not available. Install: sudo apt install python3-rpi.gpio{C_RESET}")
        return False
    except Exception as e:
        print(f"    {C_RED}GPIO error: {e}{C_RESET}")
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup([SDA_PIN, SCL_PIN])
        except:
            pass

    if not recovered:
        print(f"\n  {C_RED}All recovery phases failed!{C_RESET}")
        print(f"  The TCA9548A is actively holding SDA LOW.")
        print()
        print(f"  {C_YELLOW}HARDWARE FIX NEEDED:{C_RESET}")
        print(f"    Option A: Solder 1 jumper wire from TCA9548A RST pad to a")
        print(f"              free GPIO (e.g. GPIO4). This lets us hard-reset the mux.")
        print(f"    Option B: Move I2C to hardware bus (GPIO 2/3 = bus 1).")
        print(f"              Hardware I2C has built-in bus recovery.")
        print()
        print(f"  {C_YELLOW}TEMPORARY FIX:{C_RESET}")
        print(f"    Power cycle: disconnect TCA9548A power, wait 10s, reconnect, reboot.")

    # Step 4: Reload overlay
    print("  [4/4] Reloading i2c-gpio overlay...")
    result = run([
        "dtoverlay", "i2c-gpio",
        "bus=3",
        "i2c_gpio_sda=5",
        "i2c_gpio_scl=6",
        "i2c_gpio_delay_us=5"
    ])
    if result.returncode != 0:
        print(f"  {C_YELLOW}Overlay reload failed. Reboot recommended: sudo reboot{C_RESET}")
        return recovered

    time.sleep(0.5)

    # Verify
    sda_state = pin_read_pinctrl(SDA_PIN)
    scl_state = pin_read_pinctrl(SCL_PIN)
    print(f"\n  After recovery:")
    print(f"    SDA (GPIO {SDA_PIN}): {C_GREEN if sda_state == 'hi' else C_RED}{sda_state}{C_RESET}")
    print(f"    SCL (GPIO {SCL_PIN}): {C_GREEN if scl_state == 'hi' else C_RED}{scl_state}{C_RESET}")

    if sda_state == "hi" and recovered:
        print(f"\n  {C_GREEN}Bus recovery successful!{C_RESET}")
        # Quick verify
        time.sleep(0.3)
        try:
            import smbus2
            bus = smbus2.SMBus(3)
            bus.write_byte(0x70, 0x01)
            time.sleep(0.02)
            val = bus.read_byte(0x70)
            bus.write_byte(0x70, 0x00)
            bus.close()
            if val == 0x01:
                print(f"    TCA9548A read-back: {C_GREEN}0x{val:02X} (PASS){C_RESET}")
            else:
                print(f"    TCA9548A read-back: {C_YELLOW}0x{val:02X} (expected 0x01){C_RESET}")
        except Exception as e:
            print(f"    {C_YELLOW}I2C verify: {e}{C_RESET}")
        return True
    elif not recovered:
        return False
    else:
        print(f"\n  {C_RED}SDA went LOW again after overlay reload.{C_RESET}")
        print(f"  The i2c-gpio driver itself may be causing the hang.")
        print(f"  Consider switching to hardware I2C (bus 1, GPIO 2/3).")
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
