"""
DUSK Debug - Simulated OLED Eye Display

Logs animation events to console instead of rendering to
OLED hardware. No luma.oled or PIL dependencies needed.
"""

import time
import threading
import random
import config


class OLEDEyes:
    """Simulated dual OLED eye display."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._next_blink_time = time.time() + random.uniform(
            config.BLINK_INTERVAL_MIN, config.BLINK_INTERVAL_MAX
        )
        print("[SIM] OLED Eyes initialized (no display hardware)")

    def _animation_loop(self):
        while self._running:
            current_time = time.time()
            if current_time >= self._next_blink_time:
                print("[SIM] OLED: *blink*")
                time.sleep(config.BLINK_DURATION)

                if random.random() < 0.2:
                    time.sleep(0.15)
                    print("[SIM] OLED: *double blink*")
                    time.sleep(config.BLINK_DURATION)

                self._next_blink_time = current_time + random.uniform(
                    config.BLINK_INTERVAL_MIN, config.BLINK_INTERVAL_MAX
                )
            else:
                sleep_time = min(0.5, self._next_blink_time - current_time)
                time.sleep(sleep_time)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._thread.start()
        print("[SIM] OLED: Animation started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        print("[SIM] OLED: Animation stopped")

    def show_startup(self):
        print("[SIM] OLED: Startup animation (eyes opening)")

    def show_shutdown(self):
        print("[SIM] OLED: Shutdown animation (eyes closing)")

    def force_blink(self):
        self._next_blink_time = time.time()

    def is_running(self):
        return self._running

    def cleanup(self):
        self.stop()
        print("[SIM] OLED: Cleaned up")
