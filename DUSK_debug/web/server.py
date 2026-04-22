"""
DUSK - Flask Web Server

Provides a web interface for controlling the robot vacuum.
Supports mode switching (auto/manual), motor control,
camera streaming, and real-time status monitoring.
"""

import json
import time
import threading
from flask import Flask, render_template, Response, request, jsonify
import config
from web.camera import CameraStream


app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Global references to robot subsystems (set by main.py)
_robot = None
_camera = None


class RobotInterface:
    """
    Interface between the web server and robot subsystems.
    Holds references to all controllers and manages mode switching.
    """

    def __init__(self, motors, sweeper, vacuum, navigator, imu, tof, ina, encoders, oled):
        self.motors = motors
        self.sweeper = sweeper
        self.vacuum = vacuum
        self.navigator = navigator
        self.imu = imu
        self.tof = tof
        self.ina = ina
        self.encoders = encoders
        self.oled = oled
        self.mode = "manual"  # Start in manual mode for safety
        self._lock = threading.Lock()

        # Status cache to avoid redundant I2C reads on rapid polling
        self._status_cache = None
        self._status_cache_time = 0
        self._STATUS_CACHE_TTL = 0.25  # 250ms cache

    def set_mode(self, mode):
        """Switch between 'auto' and 'manual' mode."""
        with self._lock:
            if mode == self.mode:
                return

            if mode == "auto":
                # Stop any manual controls
                self.motors.stop()

                # Start sweeper and vacuum motors FIRST
                self.sweeper.start()
                self.vacuum.start()

                # Re-calibrate gyro with motors running so the bias
                # measurement includes vibration noise from vacuum/sweeper.
                # settle_time=1.5s lets vibrations reach steady state.
                print("[CAL] Re-calibrating gyro with motors running...")
                self.imu.calibrate_gyro(samples=200, settle_time=1.5)
                self.imu.reset_heading()
                print(f"[CAL] Vibration bias: {self.imu._gyro_z_bias:.4f} deg/s")

                # NOW start navigation with a clean heading
                self.navigator.start()
                self.mode = "auto"

            elif mode == "manual":
                # Stop autonomous navigation
                self.navigator.stop()
                self.motors.stop()
                # Keep sweeper and vacuum running (user controls)
                self.mode = "manual"

    def manual_control(self, command, speed=None):
        """Execute a manual drive command."""
        if self.mode != "manual":
            return False

        if speed is None:
            speed = config.MOTOR_DEFAULT_SPEED

        commands = {
            "forward": lambda: self.motors.forward(speed),
            "backward": lambda: self.motors.backward(speed),
            "left": lambda: self.motors.spin_left(speed),
            "right": lambda: self.motors.spin_right(speed),
            "stop": lambda: self.motors.stop(),
        }

        action = commands.get(command)
        if action:
            action()
            return True
        return False

    def get_status(self):
        """
        Get consolidated robot status with caching.
        Returns cached data if called within TTL to avoid
        hammering I2C bus on rapid 500ms web polling.
        """
        now = time.time()
        if self._status_cache and (now - self._status_cache_time) < self._STATUS_CACHE_TTL:
            return self._status_cache

        # Heavy I2C reads (battery, distances) are the expensive part
        try:
            battery = self.ina.get_status()
        except Exception:
            battery = {"voltage": 0, "current": 0, "percentage": 0, "low_battery": False, "critical": False}

        try:
            distances = self.tof.get_status()
        except Exception:
            distances = {"left_mm": 0, "right_mm": 0}

        # Lightweight local reads (no I2C, just cached values)
        status = {
            "mode": self.mode,
            "battery": battery,
            "navigation": self.navigator.get_status() if self.navigator else {},
            "distances": distances,
            "imu": {
                "heading": round(self.imu.get_heading(), 1),
            },
            "vacuum": self.vacuum.get_status(),
            "sweeper": self.sweeper.get_status(),
            "encoders": self.encoders.get_status(),
        }

        self._status_cache = status
        self._status_cache_time = now
        return status


def init_server(robot_interface, camera_stream=None):
    """
    Initialize the web server with robot subsystem references.
    
    Args:
        robot_interface: RobotInterface instance
        camera_stream: CameraStream instance (optional)
    """
    global _robot, _camera
    _robot = robot_interface
    _camera = camera_stream


# ===== ROUTES =====

@app.route("/")
def index():
    """Serve the main control panel page."""
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    """MJPEG camera stream endpoint."""
    if _camera and _camera.is_running():
        return Response(
            _camera.generate_mjpeg(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )
    else:
        return Response("Camera not available", status=503)


@app.route("/api/mode", methods=["POST"])
def set_mode():
    """Switch between auto and manual mode."""
    data = request.get_json()
    mode = data.get("mode", "manual")

    if mode not in ("auto", "manual"):
        return jsonify({"error": "Invalid mode. Use 'auto' or 'manual'"}), 400

    if _robot:
        _robot.set_mode(mode)

        # Start/stop camera based on mode
        if _camera:
            if mode == "manual":
                _camera.start()
            else:
                _camera.stop()

        return jsonify({"mode": mode, "success": True})
    return jsonify({"error": "Robot not initialized"}), 500


@app.route("/api/control", methods=["POST"])
def manual_control():
    """Handle manual drive commands."""
    data = request.get_json()
    command = data.get("command", "stop")
    speed = data.get("speed", None)

    if _robot:
        success = _robot.manual_control(command, speed)
        return jsonify({"command": command, "success": success})
    return jsonify({"error": "Robot not initialized"}), 500


@app.route("/api/vacuum", methods=["POST"])
def vacuum_control():
    """Control vacuum motor speed."""
    data = request.get_json()
    speed = data.get("speed", 0)
    action = data.get("action", "set")

    if _robot:
        if action == "start":
            _robot.vacuum.start(speed if speed > 0 else None)
        elif action == "stop":
            _robot.vacuum.stop()
        elif action == "set":
            _robot.vacuum.set_speed(speed)

        return jsonify({"vacuum": _robot.vacuum.get_status(), "success": True})
    return jsonify({"error": "Robot not initialized"}), 500


@app.route("/api/sweeper", methods=["POST"])
def sweeper_control():
    """Control sweeper motors."""
    data = request.get_json()
    action = data.get("action", "toggle")
    speed = data.get("speed", None)

    if _robot:
        if action == "start":
            _robot.sweeper.start(speed)
        elif action == "stop":
            _robot.sweeper.stop()
        elif action == "toggle":
            if _robot.sweeper.is_running():
                _robot.sweeper.stop()
            else:
                _robot.sweeper.start(speed)

        return jsonify({"sweeper": _robot.sweeper.get_status(), "success": True})
    return jsonify({"error": "Robot not initialized"}), 500


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get real-time robot status."""
    if _robot:
        return jsonify(_robot.get_status())
    return jsonify({"error": "Robot not initialized"}), 500


def run_server():
    """Run the Flask web server (blocking)."""
    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        threaded=True,
        debug=False,
        use_reloader=False,
    )


def start_server_thread():
    """Start the web server in a background thread."""
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread
