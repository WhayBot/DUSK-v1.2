"""
DUSK - Production Code Validator

Validates the REAL production code (DUSK/ and DUSK_libgpiod/) by:
1. Injecting mock hardware libraries into sys.modules
2. Importing every production module to catch syntax/import errors
3. Instantiating key classes to test initialization logic
4. Running basic method calls to verify API contracts

Usage:
    python validate.py              # Test DUSK/ (RPi.GPIO version)
    python validate.py --libgpiod   # Test DUSK_libgpiod/ version
    python validate.py --all        # Test both versions

No Raspberry Pi or hardware needed. Only requires: flask, Pillow
"""

import sys
import os
import types
import importlib
import traceback
import argparse
import time


# ==========================================================================
# MOCK HARDWARE LIBRARIES
# ==========================================================================

def _create_mock_module(name, attrs=None):
    """Create a fake module with optional attributes."""
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    return mod


def _mock_class_factory(class_name):
    """Create a class that accepts any args and has no-op methods."""
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        return lambda *a, **kw: None
    cls = type(class_name, (), {"__init__": __init__, "__getattr__": __getattr__})
    return cls


def inject_mock_libraries():
    """Inject all Raspberry Pi hardware libraries as mocks into sys.modules."""

    # --- RPi.GPIO ---
    rpi = _create_mock_module("RPi")
    rpi_gpio = _create_mock_module("RPi.GPIO", {
        "BCM": 11, "BOARD": 10, "OUT": 0, "IN": 1,
        "HIGH": 1, "LOW": 0, "PUD_UP": 22, "PUD_DOWN": 21,
        "FALLING": 32, "RISING": 31, "BOTH": 33,
        "setmode": lambda *a: None,
        "setwarnings": lambda *a: None,
        "setup": lambda *a, **kw: None,
        "output": lambda *a: None,
        "input": lambda *a: 0,
        "cleanup": lambda *a: None,
        "add_event_detect": lambda *a, **kw: None,
        "remove_event_detect": lambda *a: None,
        "PWM": _mock_class_factory("PWM"),
    })
    sys.modules["RPi"] = rpi
    sys.modules["RPi.GPIO"] = rpi_gpio

    # --- pigpio ---
    pigpio_mod = _create_mock_module("pigpio")
    class MockPi:
        connected = True
        def __init__(self, *a, **kw): pass
        def set_servo_pulsewidth(self, *a): pass
        def set_PWM_frequency(self, *a): pass
        def set_PWM_dutycycle(self, *a): pass
        def set_PWM_range(self, *a): pass
        def stop(self): pass
    pigpio_mod.pi = MockPi
    sys.modules["pigpio"] = pigpio_mod

    # --- smbus2 ---
    class MockSMBus:
        def __init__(self, bus_number=1): pass
        def read_byte_data(self, addr, reg):
            # Return correct WHO_AM_I / Model ID values
            if reg == 0x75:   # MPU6050 WHO_AM_I
                return 0x68
            if reg == 0xC0:   # VL53L0X IDENTIFICATION_MODEL_ID
                return 0xEE
            return 0
        def write_byte_data(self, addr, reg, val): pass
        def write_byte(self, addr, val): pass
        def read_byte(self, addr): return 0
        def read_i2c_block_data(self, addr, reg, length): return [0] * length
        def write_i2c_block_data(self, addr, reg, data): pass
        def read_word_data(self, addr, reg): return 0
        def close(self): pass
    smbus2 = _create_mock_module("smbus2", {"SMBus": MockSMBus})
    sys.modules["smbus2"] = smbus2

    # --- luma.core + luma.oled ---
    luma = _create_mock_module("luma")
    luma_core = _create_mock_module("luma.core")
    luma_core_iface = _create_mock_module("luma.core.interface")
    luma_core_serial = _create_mock_module("luma.core.interface.serial")
    class MockLumaI2C:
        def __init__(self, *a, **kw): pass
        def command(self, *a): pass
        def data(self, *a): pass
        def cleanup(self): pass
    luma_core_serial.i2c = MockLumaI2C
    luma_core_render = _create_mock_module("luma.core.render")
    class MockCanvas:
        def __init__(self, device, **kw):
            from PIL import Image, ImageDraw
            self._img = Image.new("1", (128, 64), "black")
            self._draw = ImageDraw.Draw(self._img)
        def __enter__(self): return self._draw
        def __exit__(self, *a): pass
    luma_core_render.canvas = MockCanvas

    luma_oled = _create_mock_module("luma.oled")
    luma_oled_device = _create_mock_module("luma.oled.device")
    class MockSSD1306:
        def __init__(self, serial_interface=None, *a, **kw): pass
        def display(self, img): pass
        def clear(self): pass
        def hide(self): pass
        def show(self): pass
    luma_oled_device.ssd1306 = MockSSD1306
    luma_oled_device.sh1106 = MockSSD1306  # In case any reference remains

    sys.modules["luma"] = luma
    sys.modules["luma.core"] = luma_core
    sys.modules["luma.core.interface"] = luma_core_iface
    sys.modules["luma.core.interface.serial"] = luma_core_serial
    sys.modules["luma.core.render"] = luma_core_render
    sys.modules["luma.oled"] = luma_oled
    sys.modules["luma.oled.device"] = luma_oled_device

    # --- picamera2 ---
    picamera2_mod = _create_mock_module("picamera2")
    class MockPicamera2:
        def __init__(self, *a): pass
        def create_video_configuration(self, **kw): return {}
        def configure(self, cfg): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def capture_array(self, name=""): 
            import numpy as np
            return np.zeros((360, 480, 3), dtype="uint8")
        def start_recording(self, *a, **kw): pass
        def stop_recording(self): pass
    picamera2_mod.Picamera2 = MockPicamera2

    picamera2_enc = _create_mock_module("picamera2.encoders")
    picamera2_enc.MJPEGEncoder = _mock_class_factory("MJPEGEncoder")
    class MockQuality:
        LOW = 1
        MEDIUM = 2
        HIGH = 3
    picamera2_enc.Quality = MockQuality

    picamera2_out = _create_mock_module("picamera2.outputs")
    picamera2_out.FileOutput = _mock_class_factory("FileOutput")

    sys.modules["picamera2"] = picamera2_mod
    sys.modules["picamera2.encoders"] = picamera2_enc
    sys.modules["picamera2.outputs"] = picamera2_out

    # --- gpiod (for libgpiod version) ---
    gpiod_mod = _create_mock_module("gpiod")
    class MockDirection:
        OUTPUT = 1
        INPUT = 2
    class MockValue:
        ACTIVE = 1
        INACTIVE = 0
    class MockEdge:
        FALLING = 1
        RISING = 2
        BOTH = 3
    class MockBias:
        PULL_UP = 1
        PULL_DOWN = 2
        DISABLED = 0
    class MockLineRequest:
        def set_value(self, line, val): pass
        def get_value(self, line): return 0
        def release(self): pass
        def wait_edge_events(self, timeout=None): return True
        def read_edge_events(self): return []
    class MockChip:
        def __init__(self, path="/dev/gpiochip0"): pass
        def request_lines(self, *a, **kw): return MockLineRequest()
    gpiod_mod.Chip = MockChip
    gpiod_mod.LineSettings = _mock_class_factory("LineSettings")
    gpiod_mod.request_lines = lambda *a, **kw: MockLineRequest()

    gpiod_line = _create_mock_module("gpiod.line")
    gpiod_line.Direction = MockDirection
    gpiod_line.Value = MockValue
    gpiod_line.Edge = MockEdge
    gpiod_line.Bias = MockBias

    sys.modules["gpiod"] = gpiod_mod
    sys.modules["gpiod.line"] = gpiod_line

    # --- numpy (lightweight mock if not installed) ---
    try:
        import numpy
    except ImportError:
        np_mod = _create_mock_module("numpy")
        np_mod.zeros = lambda shape, **kw: [[0]*shape[1] for _ in range(shape[0])]
        np_mod.uint8 = int
        sys.modules["numpy"] = np_mod


# ==========================================================================
# VALIDATION ENGINE
# ==========================================================================

class ValidationResult:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def ok(self, test_name):
        self.passed.append(test_name)
        print(f"  [PASS] {test_name}")

    def fail(self, test_name, error):
        self.failed.append((test_name, error))
        print(f"  [FAIL] {test_name}")
        print(f"         {error}")

    def warn(self, test_name, message):
        self.warnings.append((test_name, message))
        print(f"  [WARN] {test_name}: {message}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print()
        print("=" * 60)
        print(f"  RESULTS: {len(self.passed)}/{total} passed, "
              f"{len(self.failed)} failed, {len(self.warnings)} warnings")
        print("=" * 60)

        if self.failed:
            print()
            print("FAILURES:")
            for name, err in self.failed:
                print(f"  - {name}: {err}")

        if self.warnings:
            print()
            print("WARNINGS:")
            for name, msg in self.warnings:
                print(f"  - {name}: {msg}")

        print()
        return len(self.failed) == 0


def validate_version(version_dir, version_name, result):
    """Validate a single DUSK version directory."""
    print()
    print(f"{'=' * 60}")
    print(f"  Validating: {version_name}")
    print(f"  Path: {version_dir}")
    print(f"{'=' * 60}")
    print()

    # Add version dir to Python path
    if version_dir not in sys.path:
        sys.path.insert(0, version_dir)

    # Clear any previously imported DUSK modules
    # Preserve critical Python internals and third-party libs
    _preserve = {
        "_", "flask", "werkzeug", "jinja2", "markupsafe", "click",
        "itsdangerous", "blinker", "PIL", "numpy", "RPi", "pigpio",
        "smbus2", "luma", "picamera2", "gpiod", "os", "sys", "time",
        "threading", "struct", "io", "builtins", "random", "math",
        "signal", "json", "types", "importlib", "traceback", "argparse",
        "collections", "functools", "re", "abc", "enum", "copy",
        "pathlib", "colorama", "encodings", "codecs", "locale",
        "zipimport", "inspect", "tokenize", "token", "keyword",
        "_thread", "queue", "socket", "ssl", "http", "email",
        "urllib", "html", "logging", "warnings", "contextlib",
        "dataclasses", "decimal", "datetime", "hashlib", "hmac",
        "secrets", "string", "textwrap", "operator", "itertools",
        "weakref", "genericpath", "posixpath", "ntpath", "stat",
        "fnmatch", "shutil", "tempfile", "glob", "linecache",
        "dis", "opcode", "ast", "pdb", "pprint", "heapq", "bisect",
        "array", "zlib", "gzip", "bz2", "lzma", "zipfile",
        "csv", "configparser", "difflib", "textwrap", "unicodedata",
        "stringprep", "atexit", "tracemalloc", "gc", "sre_compile",
        "sre_parse", "sre_constants", "copyreg", "pickle",
    }
    mods_to_remove = [
        m for m in list(sys.modules.keys())
        if not any(m == p or m.startswith(p + ".") for p in _preserve)
    ]
    for m in mods_to_remove:
        del sys.modules[m]

    # ---- Test 1: Import config ----
    try:
        import config
        importlib.reload(config)
        result.ok(f"{version_name}/config.py - import")
    except Exception as e:
        result.fail(f"{version_name}/config.py - import", str(e))
        traceback.print_exc()
        return

    # ---- Test 2: Import i2c_mux ----
    try:
        import i2c_mux
        importlib.reload(i2c_mux)
        result.ok(f"{version_name}/i2c_mux.py - import")
    except Exception as e:
        result.fail(f"{version_name}/i2c_mux.py - import", str(e))
        traceback.print_exc()

    # ---- Test 3: Import all sensor modules ----
    sensor_modules = [
        "sensors.mpu6050",
        "sensors.vl53l0x",
        "sensors.ina219",
        "sensors.encoders",
    ]
    for mod_name in sensor_modules:
        try:
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            result.ok(f"{version_name}/{mod_name} - import")
        except Exception as e:
            result.fail(f"{version_name}/{mod_name} - import", str(e))
            traceback.print_exc()

    # ---- Test 4: Import all actuator modules ----
    actuator_modules = [
        "actuators.motors",
        "actuators.sweeper",
        "actuators.vacuum",
    ]
    for mod_name in actuator_modules:
        try:
            mod = importlib.import_module(mod_name)
            importlib.reload(mod)
            result.ok(f"{version_name}/{mod_name} - import")
        except Exception as e:
            result.fail(f"{version_name}/{mod_name} - import", str(e))
            traceback.print_exc()

    # ---- Test 5: Import display module ----
    try:
        mod = importlib.import_module("display.oled_eyes")
        importlib.reload(mod)
        result.ok(f"{version_name}/display.oled_eyes - import")
    except Exception as e:
        result.fail(f"{version_name}/display.oled_eyes - import", str(e))
        traceback.print_exc()

    # ---- Test 6: Import navigation ----
    try:
        mod = importlib.import_module("navigation.zigzag")
        importlib.reload(mod)
        result.ok(f"{version_name}/navigation.zigzag - import")
    except Exception as e:
        result.fail(f"{version_name}/navigation.zigzag - import", str(e))
        traceback.print_exc()

    # ---- Test 7: Import web server ----
    try:
        mod = importlib.import_module("web.server")
        importlib.reload(mod)
        result.ok(f"{version_name}/web.server - import")
    except Exception as e:
        result.fail(f"{version_name}/web.server - import", str(e))
        traceback.print_exc()

    # ---- Test 8: Import camera ----
    try:
        mod = importlib.import_module("web.camera")
        importlib.reload(mod)
        result.ok(f"{version_name}/web.camera - import")
    except Exception as e:
        result.fail(f"{version_name}/web.camera - import", str(e))
        traceback.print_exc()

    # ---- Test 9: Import main ----
    try:
        mod = importlib.import_module("main")
        importlib.reload(mod)
        result.ok(f"{version_name}/main.py - import")
    except Exception as e:
        result.fail(f"{version_name}/main.py - import", str(e))
        traceback.print_exc()

    # ---- Test 10: Instantiate key classes ----
    print()
    print(f"  --- Class Instantiation Tests ---")

    # MPU6050
    try:
        from sensors.mpu6050 import MPU6050
        imu = MPU6050()
        h = imu.update_heading()
        imu.calibrate_gyro(samples=5, settle_time=0)
        imu.reset_heading()
        assert isinstance(imu.get_heading(), float), "get_heading() should return float"
        result.ok(f"{version_name}/MPU6050 - instantiate + heading")
    except Exception as e:
        result.fail(f"{version_name}/MPU6050 - instantiate", str(e))
        traceback.print_exc()

    # VL53L0X
    try:
        from sensors.vl53l0x import DualVL53L0X
        tof = DualVL53L0X()
        d = tof.get_distances()
        assert "left" in d and "right" in d, "get_distances() missing keys"
        obs = tof.check_obstacles()
        assert "any" in obs, "check_obstacles() missing 'any' key"
        result.ok(f"{version_name}/DualVL53L0X - instantiate + read")
    except Exception as e:
        result.fail(f"{version_name}/DualVL53L0X - instantiate", str(e))
        traceback.print_exc()

    # INA219
    try:
        from sensors.ina219 import INA219
        ina = INA219()
        status = ina.get_status()
        assert "voltage" in status, "get_status() missing 'voltage'"
        assert "percentage" in status, "get_status() missing 'percentage'"
        assert "critical" in status, "get_status() missing 'critical'"
        result.ok(f"{version_name}/INA219 - instantiate + status")
    except Exception as e:
        result.fail(f"{version_name}/INA219 - instantiate", str(e))
        traceback.print_exc()

    # Encoders
    try:
        from sensors.encoders import DualEncoders
        enc = DualEncoders()
        d = enc.get_distances()
        assert "average" in d, "get_distances() missing 'average'"
        s = enc.get_status()
        enc.reset_all()
        enc.cleanup()
        result.ok(f"{version_name}/DualEncoders - instantiate + API")
    except Exception as e:
        result.fail(f"{version_name}/DualEncoders - instantiate", str(e))
        traceback.print_exc()

    # Motors
    try:
        from actuators.motors import WheelMotors
        motors = WheelMotors()
        motors.forward(50)
        motors.backward(50)
        motors.spin_left(40)
        motors.spin_right(40)
        motors.differential_drive(60, 40)
        motors.stop()
        motors.cleanup()
        result.ok(f"{version_name}/WheelMotors - all commands")
    except Exception as e:
        result.fail(f"{version_name}/WheelMotors - commands", str(e))
        traceback.print_exc()

    # Sweeper
    try:
        from actuators.sweeper import SweeperMotors
        sw = SweeperMotors()
        sw.start()
        assert sw.is_running(), "should be running after start()"
        s = sw.get_status()
        assert "running" in s, "get_status() missing 'running'"
        sw.stop()
        sw.cleanup()
        result.ok(f"{version_name}/SweeperMotors - start/stop/status")
    except Exception as e:
        result.fail(f"{version_name}/SweeperMotors - API", str(e))
        traceback.print_exc()

    # Vacuum
    try:
        from actuators.vacuum import VacuumMotor
        vac = VacuumMotor()
        vac.arm()
        vac.set_speed(30)
        assert vac.get_speed() == 30, f"expected speed 30, got {vac.get_speed()}"
        assert vac.is_running(), "should be running at speed 30"
        s = vac.get_status()
        assert "armed" in s, "get_status() missing 'armed'"
        vac.stop()
        assert not vac.is_running(), "should not be running after stop()"
        vac.cleanup()
        result.ok(f"{version_name}/VacuumMotor - arm/speed/stop")
    except Exception as e:
        result.fail(f"{version_name}/VacuumMotor - API", str(e))
        traceback.print_exc()

    # OLED Eyes
    try:
        from display.oled_eyes import OLEDEyes
        oled = OLEDEyes()
        oled.show_startup()
        oled.start()
        assert oled.is_running(), "should be running after start()"
        time.sleep(0.2)
        oled.force_blink()
        oled.stop()
        oled.cleanup()
        result.ok(f"{version_name}/OLEDEyes - startup/blink/stop")
    except Exception as e:
        result.fail(f"{version_name}/OLEDEyes - lifecycle", str(e))
        traceback.print_exc()

    # Navigation
    try:
        from navigation.zigzag import ZigZagNavigator, PIDController
        pid = PIDController(2.0, 0.1, 0.5)
        out = pid.compute(5.0)
        assert isinstance(out, float), "PID output should be float"
        pid.reset()
        result.ok(f"{version_name}/PIDController - compute + reset")
    except Exception as e:
        result.fail(f"{version_name}/PIDController - API", str(e))
        traceback.print_exc()

    # Web server RobotInterface
    try:
        from web.server import RobotInterface
        from sensors.mpu6050 import MPU6050
        from sensors.vl53l0x import DualVL53L0X
        from sensors.ina219 import INA219
        from sensors.encoders import DualEncoders
        from actuators.motors import WheelMotors
        from actuators.sweeper import SweeperMotors
        from actuators.vacuum import VacuumMotor
        from display.oled_eyes import OLEDEyes
        from navigation.zigzag import ZigZagNavigator

        ri = RobotInterface(
            motors=WheelMotors(),
            sweeper=SweeperMotors(),
            vacuum=VacuumMotor(),
            navigator=ZigZagNavigator(WheelMotors(), DualEncoders(), MPU6050(), DualVL53L0X()),
            imu=MPU6050(),
            tof=DualVL53L0X(),
            ina=INA219(),
            encoders=DualEncoders(),
            oled=OLEDEyes(),
        )
        status = ri.get_status()
        assert "mode" in status, "status missing 'mode'"
        assert "battery" in status, "status missing 'battery'"
        result.ok(f"{version_name}/RobotInterface - full integration")
    except Exception as e:
        result.fail(f"{version_name}/RobotInterface - integration", str(e))
        traceback.print_exc()

    # Clean up sys.path
    if version_dir in sys.path:
        sys.path.remove(version_dir)


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    parser = argparse.ArgumentParser(description="DUSK Production Code Validator")
    parser.add_argument("--libgpiod", action="store_true", help="Test DUSK_libgpiod version")
    parser.add_argument("--all", action="store_true", help="Test all versions")
    args = parser.parse_args()

    print("=" * 60)
    print("  DUSK - Production Code Validator")
    print("  Tests real production code with mocked hardware")
    print("=" * 60)

    # Inject mocks ONCE before any imports
    inject_mock_libraries()

    result = ValidationResult()
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.all:
        # Test both versions
        dusk_dir = os.path.join(base_dir, "DUSK")
        if os.path.isdir(dusk_dir):
            validate_version(dusk_dir, "DUSK (RPi.GPIO)", result)

        libgpiod_dir = os.path.join(base_dir, "DUSK_libgpiod")
        if os.path.isdir(libgpiod_dir):
            validate_version(libgpiod_dir, "DUSK_libgpiod", result)
    elif args.libgpiod:
        libgpiod_dir = os.path.join(base_dir, "DUSK_libgpiod")
        validate_version(libgpiod_dir, "DUSK_libgpiod", result)
    else:
        dusk_dir = os.path.join(base_dir, "DUSK")
        validate_version(dusk_dir, "DUSK (RPi.GPIO)", result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
