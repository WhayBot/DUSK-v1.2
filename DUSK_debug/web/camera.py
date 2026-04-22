"""
DUSK Debug - Simulated Camera Stream

Generates a simple test pattern image as JPEG for the MJPEG stream.
No picamera2 or camera hardware needed. Works on any platform.
"""

import io
import time
import threading
import struct
import zlib


def _create_test_frame(width, height, frame_num):
    """
    Generate a simple test pattern JPEG-like frame.
    Creates a minimal BMP and converts it via a solid color
    pattern that changes with frame_num for visual feedback.
    
    Returns raw JPEG bytes.
    """
    # Create a simple solid-color image that shifts hue
    r = (frame_num * 3) % 256
    g = (100 + frame_num * 2) % 256
    b = (200 - frame_num) % 256

    # Build a minimal BMP in memory
    row_size = (width * 3 + 3) & ~3  # Row padding to 4 bytes
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size

    bmp = bytearray(file_size)
    # BMP header
    bmp[0:2] = b'BM'
    struct.pack_into('<I', bmp, 2, file_size)
    struct.pack_into('<I', bmp, 10, 54)  # Pixel data offset
    # DIB header
    struct.pack_into('<I', bmp, 14, 40)
    struct.pack_into('<i', bmp, 18, width)
    struct.pack_into('<i', bmp, 22, -height)  # Top-down
    struct.pack_into('<H', bmp, 26, 1)   # Color planes
    struct.pack_into('<H', bmp, 28, 24)  # Bits per pixel
    struct.pack_into('<I', bmp, 34, pixel_data_size)

    # Fill with gradient pattern
    offset = 54
    for y in range(height):
        for x in range(width):
            pr = (r + x) % 256
            pg = (g + y) % 256
            pb = b
            bmp[offset] = pb
            bmp[offset + 1] = pg
            bmp[offset + 2] = pr
            offset += 3
        offset += row_size - width * 3  # Padding

    # Convert BMP to JPEG using PIL if available, otherwise return BMP
    try:
        from PIL import Image
        img = Image.frombytes('RGB', (width, height),
                              bytes(bmp[54:54 + width * height * 3]))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=50)
        return buf.getvalue()
    except ImportError:
        # If PIL not available, return BMP bytes (browser may not render)
        return bytes(bmp)


class CameraStream:
    """
    Simulated camera stream using generated test patterns.
    Works on any platform without picamera2.
    """

    def __init__(self):
        self._running = False
        self._frame = None
        self._frame_lock = threading.Lock()
        self._frame_event = threading.Event()
        self._frame_num = 0
        print("[SIM] Camera initialized (test pattern mode)")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("[SIM] Camera: STARTED (generating test frames)")

    def _capture_loop(self):
        import config
        width, height = config.CAMERA_RESOLUTION
        # Pre-generate a smaller test frame for speed
        small_w = min(width, 160)
        small_h = min(height, 120)

        while self._running:
            try:
                frame = _create_test_frame(small_w, small_h, self._frame_num)
                self._frame_num += 1

                with self._frame_lock:
                    self._frame = frame
                self._frame_event.set()

                time.sleep(1.0 / config.CAMERA_FRAMERATE)
            except Exception as e:
                print(f"[SIM] Camera frame error: {e}")
                time.sleep(0.5)

    def get_frame(self):
        with self._frame_lock:
            return self._frame

    def generate_mjpeg(self):
        while self._running:
            self._frame_event.wait(timeout=1.0)
            self._frame_event.clear()
            frame = self.get_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

    def stop(self):
        self._running = False
        self._frame_event.set()
        print("[SIM] Camera: STOPPED")

    def is_running(self):
        return self._running

    def cleanup(self):
        self.stop()
