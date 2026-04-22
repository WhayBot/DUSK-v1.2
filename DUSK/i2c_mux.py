"""
DUSK - TCA9548A I2C Multiplexer Driver

Thread-safe I2C multiplexer control for routing communication
to different sensor channels.
"""

import threading
import smbus2
import time
import config


class TCA9548A:
    """
    TCA9548A I2C Multiplexer Driver.
    
    Routes I2C communication to one of 8 channels (0-7).
    Each channel has its own SDA/SCL pair on the multiplexer.
    Thread-safe: uses a lock to prevent concurrent channel switching.
    """

    def __init__(self, bus_number=None, address=None):
        self.bus_number = bus_number or config.I2C_BUS_NUMBER
        self.address = address or config.TCA9548A_ADDRESS
        self.bus = smbus2.SMBus(self.bus_number)
        self._lock = threading.Lock()
        self._current_channel = -1

    def select_channel(self, channel):
        """
        Select the active channel on the TCA9548A.
        
        Args:
            channel: Channel number 0-7
        """
        if not (0 <= channel <= 7):
            raise ValueError(f"Channel must be between 0 and 7, got {channel}")
        
        if self._current_channel != channel:
            self.bus.write_byte(self.address, 1 << channel)
            self._current_channel = channel
            time.sleep(0.005)

    def disable_all(self):
        """Disable all channels."""
        self.bus.write_byte(self.address, 0x00)
        self._current_channel = -1

    def get_bus(self):
        """Get the underlying SMBus instance."""
        return self.bus

    def acquire(self):
        """Acquire the thread lock."""
        self._lock.acquire()

    def release(self):
        """Release the thread lock."""
        self._lock.release()

    class ChannelContext:
        """Context manager for safe channel access with locking."""

        def __init__(self, mux, channel):
            self._mux = mux
            self._channel = channel

        def __enter__(self):
            self._mux.acquire()
            self._mux.select_channel(self._channel)
            return self._mux.bus

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._mux.release()
            return False

    def channel(self, ch):
        """
        Context manager for accessing a specific channel.
        Acquires lock, selects channel, and returns the bus.
        
        Usage:
            with mux.channel(0) as bus:
                data = bus.read_byte_data(0x68, 0x00)
        """
        return self.ChannelContext(self, ch)

    def scan_channel(self, channel):
        """
        Scan a specific channel for I2C devices.
        
        Returns:
            list: List of detected I2C addresses on the channel
        """
        devices = []
        with self.channel(channel) as bus:
            for addr in range(0x08, 0x78):
                try:
                    bus.read_byte(addr)
                    devices.append(hex(addr))
                except Exception:
                    pass
        return devices

    def scan_all(self):
        """
        Scan all channels for I2C devices.
        
        Returns:
            dict: Channel number -> list of detected addresses
        """
        results = {}
        for ch in range(8):
            devices = self.scan_channel(ch)
            if devices:
                results[ch] = devices
        return results

    def close(self):
        """Close the I2C bus."""
        self.disable_all()
        self.bus.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# Global multiplexer instance (singleton)
_mux_instance = None
_mux_lock = threading.Lock()


def get_mux():
    """
    Get or create the global TCA9548A multiplexer instance.
    Thread-safe singleton pattern.
    """
    global _mux_instance
    if _mux_instance is None:
        with _mux_lock:
            if _mux_instance is None:
                _mux_instance = TCA9548A()
    return _mux_instance
