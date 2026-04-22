"""
DUSK - Picamera2 MJPEG Camera Streaming (Optimized for Pi Zero 2W)

Provides a generator-based MJPEG stream from the Raspberry Pi Camera V2.
Used by the Flask web server for live video feed in manual mode.

Optimization strategy:
- Uses Picamera2 hardware JPEG encoder instead of numpy->PIL->JPEG.
- StreamingOutput captures JPEG bytes directly from the ISP.
- Avoids numpy and PIL imports entirely (massive memory savings).
- Lower resolution (480x360) and quality for Pi Zero 2W.
"""

import io
import time
import threading
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, Quality
from picamera2.outputs import FileOutput
import config


class StreamingOutput(io.BufferedIOBase):
    """
    Thread-safe buffer that receives JPEG frames from Picamera2's
    hardware MJPEG encoder. Replaces the numpy->PIL->JPEG pipeline.
    """

    def __init__(self):
        self.frame = None
        self._lock = threading.Lock()
        self._event = threading.Event()

    def write(self, buf):
        with self._lock:
            self.frame = bytes(buf)
        self._event.set()
        return len(buf)

    def get_frame(self):
        """Get the latest JPEG frame."""
        with self._lock:
            return self.frame

    def wait_for_frame(self, timeout=1.0):
        """Block until a new frame is available."""
        self._event.wait(timeout=timeout)
        self._event.clear()


class CameraStream:
    """
    MJPEG camera streaming using Picamera2 hardware encoder.
    
    Optimized for Pi Zero 2W:
    - Uses the GPU-accelerated MJPEG encoder (no CPU JPEG encoding)
    - Lower resolution (480x360) to reduce memory and bandwidth
    - JPEG quality set to LOW for smaller frames
    - No numpy or PIL dependency at runtime
    """

    def __init__(self):
        self._camera = None
        self._encoder = None
        self._output = None
        self._running = False

    def _initialize_camera(self):
        """Initialize the Picamera2 instance with optimized settings."""
        self._camera = Picamera2()

        # Use lower resolution for Pi Zero 2W
        cam_res = config.CAMERA_RESOLUTION

        camera_config = self._camera.create_video_configuration(
            main={"size": cam_res, "format": "YUV420"},
        )
        self._camera.configure(camera_config)

        # Hardware MJPEG encoder (GPU-accelerated on Pi)
        self._encoder = MJPEGEncoder()
        self._output = StreamingOutput()

    def start(self):
        """Start the camera capture with hardware MJPEG encoding."""
        if self._running:
            return

        try:
            self._initialize_camera()
            self._camera.start_recording(
                self._encoder,
                FileOutput(self._output),
                quality=Quality.LOW,
            )
            self._running = True
        except Exception as e:
            print(f"Camera start error: {e}")
            self._running = False

    def get_frame(self):
        """
        Get the latest JPEG frame.
        
        Returns:
            bytes: JPEG-encoded frame, or None if no frame available
        """
        if self._output:
            return self._output.get_frame()
        return None

    def generate_mjpeg(self):
        """
        Generator function for MJPEG streaming.
        Yields multipart JPEG frames for Flask Response.
        """
        while self._running:
            if self._output:
                self._output.wait_for_frame(timeout=1.0)

            frame = self.get_frame()
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )

    def stop(self):
        """Stop the camera capture."""
        self._running = False

        if self._camera:
            try:
                self._camera.stop_recording()
                self._camera.close()
            except Exception:
                pass
        self._camera = None
        self._encoder = None
        self._output = None

    def is_running(self):
        """Check if camera is currently streaming."""
        return self._running

    def cleanup(self):
        """Clean up camera resources."""
        self.stop()
