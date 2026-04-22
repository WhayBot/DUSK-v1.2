"""
DUSK - OLED Eye Animation Display (Optimized for Pi Zero 2W)

Controls two 1.3" SSD1306 OLED displays showing animated eyes.
Left eye on TCA9548A Channel 1, Right eye on Channel 2.

Optimization strategy:
- All eye frames are pre-rendered at init and stored as raw bytes.
- Animation loop only pushes cached framebuffers to OLED (no PIL per frame).
- Open-eye state does NOT re-send data; display retains last image.
"""

import time
import threading
import random
from PIL import Image, ImageDraw
from luma.core.interface.serial import i2c as luma_i2c
from luma.oled.device import ssd1306

import config
from i2c_mux import get_mux


class MuxedSerial:
    """
    Custom serial interface for luma.oled that routes through TCA9548A.
    
    Selects the appropriate mux channel before any I2C communication.
    This allows two OLED displays with the same I2C address to coexist
    on different mux channels.
    """

    def __init__(self, mux, mux_channel, port, address):
        self._mux = mux
        self._mux_channel = mux_channel

        # Select channel first, then create luma serial
        self._mux.acquire()
        self._mux.select_channel(self._mux_channel)
        self._serial = luma_i2c(port=port, address=address)
        self._mux.release()

    def command(self, *cmd):
        """Send command bytes to the OLED."""
        self._mux.acquire()
        try:
            self._mux.select_channel(self._mux_channel)
            self._serial.command(*cmd)
        finally:
            self._mux.release()

    def data(self, data):
        """Send data bytes to the OLED."""
        self._mux.acquire()
        try:
            self._mux.select_channel(self._mux_channel)
            self._serial.data(data)
        finally:
            self._mux.release()

    def cleanup(self):
        """Clean up the serial interface."""
        self._serial.cleanup()


class EyeRenderer:
    """
    Pre-renders all eye animation frames into cached PIL images.
    
    At construction time, generates frames for every blink step
    so the animation loop never needs to call PIL drawing functions.
    """

    # Number of discrete openness steps for blink animation
    BLINK_STEPS = 4

    def __init__(self, is_left_eye=True):
        self.is_left = is_left_eye
        self.width = config.OLED_WIDTH
        self.height = config.OLED_HEIGHT

        # Eye geometry
        self._cx = self.width // 2
        self._cy = self.height // 2
        self._eye_rx = 56
        self._eye_ry = 28
        self._iris_r = 20
        self._pupil_r = 10
        self._highlight_r = 4
        self._hl_ox = -6 if is_left_eye else 6
        self._hl_oy = -6

        # Pre-render all frames: index 0 = closed, index BLINK_STEPS = fully open
        self._frames = []
        for i in range(self.BLINK_STEPS + 1):
            openness = i / self.BLINK_STEPS
            self._frames.append(self._render_frame(openness))

    def _render_frame(self, openness):
        """Render a single eye frame and return the PIL Image."""
        img = Image.new("1", (self.width, self.height), "black")
        draw = ImageDraw.Draw(img)

        cx, cy = self._cx, self._cy

        if openness <= 0.05:
            draw.line(
                [(cx - self._eye_rx, cy), (cx + self._eye_rx, cy)],
                fill="white",
                width=3,
            )
            return img

        current_ry = max(2, int(self._eye_ry * openness))

        # Outer eye ellipse
        draw.ellipse(
            [cx - self._eye_rx, cy - current_ry, cx + self._eye_rx, cy + current_ry],
            outline="white", fill="black", width=2,
        )

        if openness > 0.3:
            # Iris
            ir = int(self._iris_r * min(1.0, openness))
            draw.ellipse(
                [cx - ir, cy - ir, cx + ir, cy + ir],
                outline="white", fill="white",
            )
            # Pupil
            pr = int(self._pupil_r * min(1.0, openness))
            draw.ellipse(
                [cx - pr, cy - pr, cx + pr, cy + pr],
                outline="black", fill="black",
            )
            # Highlight
            if openness > 0.5:
                hx = cx + self._hl_ox
                hy = cy + self._hl_oy
                hr = self._highlight_r
                draw.ellipse(
                    [hx - hr, hy - hr, hx + hr, hy + hr],
                    outline="white", fill="white",
                )

        return img

    def get_frame(self, step_index):
        """
        Return a pre-rendered frame by step index.
        
        Args:
            step_index: 0 (closed) to BLINK_STEPS (fully open)
        """
        idx = max(0, min(self.BLINK_STEPS, step_index))
        return self._frames[idx]


class OLEDEyes:
    """
    Manages both OLED eye displays with animated blinking.
    
    Optimized for Pi Zero 2W:
    - Frames are pre-rendered at init (one-time PIL cost)
    - Animation loop only pushes cached images to displays
    - Open-eye idle state does NOT re-render or re-send data
    - Blink interval increased to reduce unnecessary I2C traffic
    """

    def __init__(self):
        self.mux = get_mux()
        self._running = False
        self._thread = None

        # Create custom serial interfaces for each OLED
        self._serial_left = MuxedSerial(
            self.mux,
            config.MUX_CH_OLED_LEFT,
            config.I2C_BUS_NUMBER,
            config.OLED_ADDRESS,
        )
        self._serial_right = MuxedSerial(
            self.mux,
            config.MUX_CH_OLED_RIGHT,
            config.I2C_BUS_NUMBER,
            config.OLED_ADDRESS,
        )

        # Create OLED device instances
        self._device_left = ssd1306(self._serial_left)
        self._device_right = ssd1306(self._serial_right)

        # Pre-render all eye frames (one-time cost)
        self._eye_left = EyeRenderer(is_left_eye=True)
        self._eye_right = EyeRenderer(is_left_eye=False)

        # Animation state
        self._next_blink_time = time.time() + random.uniform(
            config.BLINK_INTERVAL_MIN, config.BLINK_INTERVAL_MAX
        )

    def _display_frame(self, device, frame_img):
        """Push a pre-rendered PIL image to an OLED device."""
        device.display(frame_img)

    def _display_both(self, step_index):
        """Display the same blink step on both eyes."""
        self._display_frame(self._device_left, self._eye_left.get_frame(step_index))
        self._display_frame(self._device_right, self._eye_right.get_frame(step_index))

    def _blink_animation(self):
        """Perform a single blink using pre-rendered frames."""
        steps = EyeRenderer.BLINK_STEPS
        step_delay = config.BLINK_DURATION / (steps * 2)

        # Close eyes: steps -> 0
        for i in range(steps, -1, -1):
            self._display_both(i)
            time.sleep(step_delay)

        # Open eyes: 0 -> steps
        for i in range(0, steps + 1):
            self._display_both(i)
            time.sleep(step_delay)

    def _animation_loop(self):
        """Main animation loop running in a daemon thread."""
        # Draw initial open eyes (once)
        self._display_both(EyeRenderer.BLINK_STEPS)

        while self._running:
            current_time = time.time()

            if current_time >= self._next_blink_time:
                self._blink_animation()

                # 20% chance of double-blink
                if random.random() < 0.2:
                    time.sleep(0.15)
                    self._blink_animation()

                self._next_blink_time = current_time + random.uniform(
                    config.BLINK_INTERVAL_MIN, config.BLINK_INTERVAL_MAX
                )
            else:
                # Idle: sleep until next blink (no re-rendering needed)
                sleep_time = min(0.5, self._next_blink_time - current_time)
                time.sleep(sleep_time)

    def start(self):
        """Start the eye animation thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the animation and clear displays."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

        try:
            self._device_left.clear()
            self._device_right.clear()
        except Exception:
            pass

    def show_startup(self):
        """Show a startup animation (eyes opening from closed)."""
        steps = EyeRenderer.BLINK_STEPS
        for i in range(0, steps + 1):
            self._display_both(i)
            time.sleep(0.08)

    def show_shutdown(self):
        """Show a shutdown animation (eyes closing)."""
        steps = EyeRenderer.BLINK_STEPS
        for i in range(steps, -1, -1):
            self._display_both(i)
            time.sleep(0.08)

        self._device_left.clear()
        self._device_right.clear()

    def force_blink(self):
        """Force an immediate blink."""
        self._next_blink_time = time.time()

    def is_running(self):
        """Check if animation is running."""
        return self._running

    def cleanup(self):
        """Stop animation and clean up resources."""
        self.stop()
        try:
            self._serial_left.cleanup()
            self._serial_right.cleanup()
        except Exception:
            pass
