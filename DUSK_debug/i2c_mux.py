"""
DUSK Debug - Simulated I2C Multiplexer (TCA9548A)

Provides the same API as the real i2c_mux.py but without
any hardware dependencies. All operations are logged to console.
"""

import threading


class _FakeBus:
    """Simulated SMBus that logs all read/write operations."""

    def read_byte_data(self, addr, reg):
        return 0x68 if reg == 0x75 else 0x00

    def write_byte_data(self, addr, reg, value):
        pass

    def read_i2c_block_data(self, addr, reg, length):
        return [0] * length

    def write_i2c_block_data(self, addr, reg, data):
        pass

    def read_word_data(self, addr, reg):
        return 0


class _FakeChannel:
    """Context manager that returns a FakeBus."""

    def __init__(self):
        self._bus = _FakeBus()

    def __enter__(self):
        return self._bus

    def __exit__(self, *args):
        pass


class TCA9548A:
    """Simulated TCA9548A I2C multiplexer."""

    def __init__(self, bus_number=3, address=0x70):
        self._lock = threading.Lock()
        self._current_channel = -1
        print(f"[SIM] I2C Mux TCA9548A initialized (bus={bus_number}, addr=0x{address:02X})")

    def select_channel(self, channel):
        self._current_channel = channel

    def channel(self, ch):
        self._current_channel = ch
        return _FakeChannel()

    def acquire(self):
        self._lock.acquire()

    def release(self):
        self._lock.release()

    def scan_all(self):
        """Return simulated device scan results."""
        print("[SIM] Scanning I2C bus (simulated)...")
        return {
            0: [0x68],       # MPU6050
            1: [0x3C],       # OLED Left
            2: [0x3C],       # OLED Right
            3: [0x29],       # VL53L0X Left
            4: [0x29],       # VL53L0X Right
            5: [0x40],       # INA219
        }

    def close(self):
        print("[SIM] I2C bus closed")


_instance = None

def get_mux():
    global _instance
    if _instance is None:
        import config
        _instance = TCA9548A(config.I2C_BUS_NUMBER, config.TCA9548A_ADDRESS)
    return _instance
