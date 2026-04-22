# DUSK - Dust Unification and Sweeping Keeper

## Complete Project Documentation

DUSK is a smart robot vacuum cleaner powered by a Raspberry Pi Zero 2W. It operates in two modes: an automatic zig-zag cleaning mode using gyroscope and encoder-based navigation with obstacle avoidance, and a manual mode controllable through a web interface with live camera streaming. The robot features animated eye displays on dual OLED screens, dual counter-rotating sweeper brushes, and a brushless motor vacuum system.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component List](#2-component-list)
3. [Wiring Diagram](#3-wiring-diagram)
4. [Power Distribution](#4-power-distribution)
5. [Software Architecture](#5-software-architecture)
6. [File Structure](#6-file-structure)
7. [Module Descriptions](#7-module-descriptions)
8. [Libraries and Dependencies](#8-libraries-and-dependencies)
9. [Setup and Installation](#9-setup-and-installation)
10. [Running the Robot](#10-running-the-robot)
11. [Web Control Panel](#11-web-control-panel)
12. [Operating Modes](#12-operating-modes)
13. [Calibration](#13-calibration)
14. [Troubleshooting](#14-troubleshooting)
15. [Version Differences (RPi.GPIO vs libgpiod)](#15-version-differences)
16. [Safety Notes](#16-safety-notes)

---

## 1. System Overview

DUSK is a differential-drive robot vacuum with the following capabilities:

- Automatic zig-zag cleaning pattern with PID-controlled straight-line driving
- Obstacle detection using two Time-of-Flight sensors mounted at 30 degrees left and right
- Heading control via MPU6050 gyroscope with integrated yaw tracking
- Distance measurement using optical speed encoders on both drive wheels
- Web-based control panel accessible from any device on the same network
- Live MJPEG camera streaming from a Raspberry Pi Camera V2
- Animated blinking eyes displayed on two 1.3-inch OLED screens
- Brushless vacuum motor controlled through a 20A ESC
- Dual N20 sweeper motors rotating in opposite directions to funnel debris
- Real-time battery monitoring via INA219 current/voltage sensor
- All I2C devices routed through a TCA9548A multiplexer using a virtual I2C bus

The Raspberry Pi Zero 2W uses a software-bitbanged I2C bus on GPIO5 (SDA) and GPIO6 (SCL) because the built-in hardware I2C pins are damaged. This is configured via the i2c-gpio device tree overlay.

---

## 2. Component List

### Processing and Communication

| Component | Quantity | Function |
|:--|:--|:--|
| Raspberry Pi Zero 2W | 1 | Main controller, web server, camera host |
| Raspberry Pi Camera V2 | 1 | Live video feed for manual mode |

### Sensors

| Component | Quantity | Interface | Function |
|:--|:--|:--|:--|
| MPU6050 | 1 | I2C (TCA Ch.0) | Gyroscope and accelerometer for heading control |
| TOF-200C VL53L0X | 2 | I2C (TCA Ch.3, Ch.4) | Time-of-flight distance sensors for obstacle detection |
| INA219 | 1 | I2C (TCA Ch.5) | Battery voltage, current, and power monitoring |
| Speed Encoder (4-pin, optical) | 2 | GPIO digital | Wheel rotation pulse counting for distance and speed |

### Actuators

| Component | Quantity | Driver | Function |
|:--|:--|:--|:--|
| Geared DC Motor (wheels) | 2 | L298N | Left and right drive wheels |
| N20 Geared Motor (sweepers) | 2 | L298N | Counter-rotating front sweeper brushes |
| Brushless Motor 980kV (vacuum) | 1 | ESC 20A | Vacuum suction fan |

### Display

| Component | Quantity | Interface | Function |
|:--|:--|:--|:--|
| OLED 1.3" I2C (SSD1306) | 2 | I2C (TCA Ch.1, Ch.2) | Left and right animated eye displays |

### Motor Drivers and ESC

| Component | Quantity | Function |
|:--|:--|:--|
| L298N Motor Driver | 1 | Drives both geared wheel motors |
| L298N Motor Driver | 1 | Drives both N20 sweeper motors (single channel) |
| ESC 20A | 1 | Controls the brushless vacuum motor via PWM |

### Power Management

| Component | Quantity | Function |
|:--|:--|:--|
| Li-Po Battery 3S 12V | 1 | Main power source (11.1V nominal, 12.6V full) |
| BMS 3S 12V | 1 | Battery charge/discharge protection |
| LM2596 DC-DC (3.3V output) | 1 | Powers sensors and multiplexer |
| LM2596 DC-DC (5.1V output) | 1 | Powers Raspberry Pi and OLED displays |

### Passive Components and Interconnects

| Component | Quantity | Function |
|:--|:--|:--|
| TCA9548A I2C Multiplexer | 1 | Routes I2C bus to 6 device channels |
| 4.7k Ohm Resistor | 1 | TCA9548A RST pin pull-up to 3.3V |
| 4.7k Ohm Resistor | 2 | I2C SDA and SCL pull-up resistors (recommended) |

---

## 3. Wiring Diagram

### Important Notes

- The 3.3V and 5V rails come from the two LM2596 buck converters, NOT from the Raspberry Pi.
- All component GND pins are connected together to a common ground bus.
- "Channel" refers to the I2C sub-bus on the TCA9548A multiplexer (e.g., Channel 0 means SDA0/SCL0 on the TCA9548A).
- The Raspberry Pi uses Virtual I2C on GPIO5 (SDA) and GPIO6 (SCL) because the hardware I2C pins (GPIO2/GPIO3) are not functional.

### Raspberry Pi Zero 2W

| Pi Pin | Connection |
|:--|:--|
| 5V | 5.1V rail (from LM2596) |
| GND | Common ground bus |

### TCA9548A I2C Multiplexer

| TCA9548A Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| SDA | Raspberry Pi GPIO5 (Virtual I2C SDA) |
| SCL | Raspberry Pi GPIO6 (Virtual I2C SCL) |
| RST | 3.3V rail via 4.7k Ohm resistor |

### MPU6050 (Gyroscope and Accelerometer)

| MPU6050 Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| SDA | TCA9548A Channel 0 SDA |
| SCL | TCA9548A Channel 0 SCL |
| Other pins | Not connected |

### OLED 1.3" Left Eye

| OLED Pin | Connection |
|:--|:--|
| VCC | 5V rail |
| GND | Common ground bus |
| SDA | TCA9548A Channel 1 SDA |
| SCL | TCA9548A Channel 1 SCL |

### OLED 1.3" Right Eye

| OLED Pin | Connection |
|:--|:--|
| VCC | 5V rail |
| GND | Common ground bus |
| SDA | TCA9548A Channel 2 SDA |
| SCL | TCA9548A Channel 2 SCL |

### VL53L0X Left (30 degrees left)

| VL53L0X Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| SDA | TCA9548A Channel 3 SDA |
| SCL | TCA9548A Channel 3 SCL |

### VL53L0X Right (30 degrees right)

| VL53L0X Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| SDA | TCA9548A Channel 4 SDA |
| SCL | TCA9548A Channel 4 SCL |

### INA219 (Power Monitor)

| INA219 Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| SDA | TCA9548A Channel 5 SDA |
| SCL | TCA9548A Channel 5 SCL |
| VIN+ | Battery positive terminal |
| VIN- | LM2596 input positive (IN+) |

### Speed Encoder Left

| Encoder Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| DO | Raspberry Pi GPIO14 |
| AO | Not connected |

### Speed Encoder Right

| Encoder Pin | Connection |
|:--|:--|
| VCC | 3.3V rail |
| GND | Common ground bus |
| DO | Raspberry Pi GPIO7 |
| AO | Not connected |

### L298N Motor Driver - Geared Wheel Motors

| L298N Pin | Connection |
|:--|:--|
| ENA | Raspberry Pi GPIO10 (PWM - left motor speed) |
| IN1 | Raspberry Pi GPIO12 (left motor direction) |
| IN2 | Raspberry Pi GPIO13 (left motor direction) |
| IN3 | Raspberry Pi GPIO19 (right motor direction) |
| IN4 | Raspberry Pi GPIO16 (right motor direction) |
| ENB | Raspberry Pi GPIO9 (PWM - right motor speed) |
| 12V | Battery positive (through BMS) |
| GND | Common ground bus |
| OUT1/OUT2 | Left geared motor terminals |
| OUT3/OUT4 | Right geared motor terminals |

### L298N Motor Driver - N20 Sweeper Motors

| L298N Pin | Connection |
|:--|:--|
| ENA | Raspberry Pi GPIO26 (PWM - sweeper speed) |
| IN1 | Raspberry Pi GPIO24 (sweeper direction) |
| IN2 | Raspberry Pi GPIO25 (sweeper direction) |
| IN3 | Not connected |
| IN4 | Not connected |
| ENB | Not connected |
| OUT1/OUT2 | Both N20 motors (wired with opposing polarity) |

Both N20 sweeper motors are connected to the same L298N output channel (OUT1 and OUT2). One motor has its terminals reversed relative to the other, causing them to spin in opposite directions. This creates an inward sweeping motion that funnels dust toward the vacuum intake.

### ESC 20A (Brushless Vacuum Motor)

| ESC Pin | Connection |
|:--|:--|
| Battery VCC | Battery positive terminal |
| Battery GND | Common ground bus |
| Signal (Data) | Raspberry Pi GPIO18 |
| UBEC 5V | Not connected |
| UBEC GND | Common ground bus |
| Motor wires (3) | Brushless motor 980kV (3 phases) |

### BMS 3S 12V

| BMS Pin | Connection |
|:--|:--|
| 4.2V | Battery cell 1 positive |
| 8.4V | Battery cell 2 positive |
| 12.6V | Battery cell 3 positive |
| GND | Battery negative |
| I/O Positive | LM2596 3.3V input + LM2596 5.1V input + Charging port positive |
| I/O Negative | LM2596 3.3V GND + LM2596 5.1V GND + Charging port negative |

---

## 4. Power Distribution

```
Li-Po 3S Battery (12.6V max)
    |
    +-- BMS 3S (protection)
         |
         +-- ESC 20A --> Brushless Motor 980kV
         |
         +-- L298N #1 (12V input) --> Geared Wheel Motors
         |
         +-- L298N #2 (12V input) --> N20 Sweeper Motors
         |
         +-- INA219 (VIN+ / VIN-) --> monitoring
         |
         +-- LM2596 #1 --> 3.3V rail
         |    +-- TCA9548A
         |    +-- MPU6050
         |    +-- VL53L0X (x2)
         |    +-- INA219
         |    +-- Speed Encoders (x2)
         |
         +-- LM2596 #2 --> 5.1V rail
              +-- Raspberry Pi Zero 2W
              +-- OLED 1.3" (x2)
```

---

## 5. Software Architecture

The software is organized into six subsystem packages coordinated by a central main controller:

- **config** - All hardware pin definitions, I2C addresses, channel assignments, motor parameters, navigation constants, and system settings centralized in one file.

- **i2c_mux** - Thread-safe TCA9548A driver with context manager pattern. All I2C sensor and display access goes through this module to avoid bus contention.

- **sensors** - MPU6050 gyroscope/accelerometer with integrated heading tracking, VL53L0X time-of-flight distance measurement (raw register access), INA219 battery monitoring with percentage estimation, and speed encoder pulse counting.

- **actuators** - L298N-based differential drive for wheel motors, N20 sweeper motor control, and ESC-based brushless vacuum motor control via pigpio PWM.

- **display** - Dual OLED eye animation system running in a daemon thread. Each eye is drawn using PIL (Pillow) with an elliptical outline, iris, pupil, and highlight reflection. Periodic blinking occurs at random intervals.

- **navigation** - Zig-zag cleaning pattern state machine with PID-controlled straight-line correction. Uses encoder distance feedback for lane length, gyroscope heading for turn accuracy, and ToF sensors for obstacle avoidance.

- **web** - Flask-based REST API server with MJPEG camera streaming. Provides mode switching, manual drive controls, vacuum/sweeper controls, and real-time status monitoring.

---

## 6. File Structure

```
DUSK/
|-- config.py                  Configuration constants and pin assignments
|-- i2c_mux.py                 TCA9548A I2C multiplexer driver
|-- main.py                    Main entry point and system orchestrator
|-- requirements.txt           Python package dependencies
|-- setup.sh                   One-time system setup script
|
|-- sensors/
|   |-- __init__.py
|   |-- mpu6050.py             MPU6050 gyroscope and accelerometer
|   |-- vl53l0x.py             VL53L0X time-of-flight distance sensors
|   |-- ina219.py              INA219 current and voltage monitor
|   |-- encoders.py            Speed encoder pulse counters
|
|-- actuators/
|   |-- __init__.py
|   |-- motors.py              Geared wheel motor controller (L298N)
|   |-- sweeper.py             N20 sweeper motor controller (L298N)
|   |-- vacuum.py              Brushless vacuum motor controller (ESC)
|
|-- display/
|   |-- __init__.py
|   |-- oled_eyes.py           Dual OLED animated eye display
|
|-- navigation/
|   |-- __init__.py
|   |-- zigzag.py              Zig-zag cleaning pattern with obstacle avoidance
|
|-- web/
    |-- __init__.py
    |-- server.py              Flask web server and REST API
    |-- camera.py              Picamera2 MJPEG streaming
    |-- templates/
    |   |-- index.html         Web control panel page
    |-- static/
        |-- style.css          Web UI styling
        |-- script.js          Web UI client-side logic
```

The `DUSK_libgpiod/` directory has an identical structure with modified files for the libgpiod version (see Section 15).

---

## 7. Module Descriptions

### config.py

Centralizes all configurable values. No hardcoded pin numbers or addresses exist elsewhere in the code. Key sections:

- I2C bus number (3, for the virtual bus) and TCA9548A address (0x70)
- TCA9548A channel-to-device mapping (channels 0 through 5)
- All GPIO pin numbers in BCM numbering
- Motor PWM frequency (1000 Hz), default speeds, and max speeds
- ESC pulse width range (1000-2000 microseconds)
- Navigation parameters: straight distance, shift distance, obstacle threshold
- PID constants (Kp, Ki, Kd) for straight-line driving correction
- OLED dimensions (128x64) and blink timing
- Battery voltage thresholds for 3S LiPo
- Web server host, port, camera resolution

### i2c_mux.py

The TCA9548A multiplexer allows multiple I2C devices with overlapping addresses to coexist. This driver provides:

- `select_channel(n)` - Writes the channel selection byte to the mux
- `channel(n)` - Context manager that acquires a thread lock, selects the channel, returns the SMBus instance, and releases the lock on exit
- `scan_all()` - Scans all 8 channels and reports detected devices
- Singleton pattern via `get_mux()` for global access

### sensors/mpu6050.py

Communicates with the MPU6050 at address 0x68 on TCA9548A Channel 0. Key features:

- Reads all 14 bytes of sensor data in a single burst read from register 0x3B
- Provides accelerometer (g) and gyroscope (degrees/second) readings
- Integrates the Z-axis gyroscope over time to produce a heading (yaw) angle
- Dead-zone filter ignores gyroscope noise below 0.5 degrees/second
- Calibration routine averages 200 samples at rest to measure gyro bias

### sensors/vl53l0x.py

Raw I2C register access implementation for the VL53L0X time-of-flight sensor. No external C library compilation is required. Each sensor instance is bound to a specific TCA9548A channel:

- Left sensor on Channel 3 (mounted 30 degrees to the left)
- Right sensor on Channel 4 (mounted 30 degrees to the right)
- Single-shot ranging mode with 500ms timeout
- Returns distance in millimeters (0 to 8190 mm range)
- `DualVL53L0X` class provides combined obstacle detection for both sensors

### sensors/ina219.py

Monitors battery voltage (bus voltage), current draw, and power consumption through a shunt resistor. Connected on TCA9548A Channel 5.

- Configured for 32V bus range and 320mV shunt range
- Calibration value computed from shunt resistance (0.1 ohm) and max expected current (10A)
- Battery percentage calculated by linear interpolation between critical voltage (9.9V) and full voltage (12.6V)
- Low battery and critical battery threshold checks

### sensors/encoders.py

Counts digital pulses from optical speed encoders attached to the drive wheels. Left encoder on GPIO14, right encoder on GPIO7.

- RPi.GPIO version uses `add_event_detect` with FALLING edge callbacks
- libgpiod version uses `wait_edge_events` in a dedicated thread
- Calculates distance from pulse count, wheel circumference, and pulses per revolution
- Speed calculated as distance delta over time delta

### actuators/motors.py

Controls two geared DC motors through an L298N H-bridge driver. Provides differential drive capability:

- `forward(speed)`, `backward(speed)` - Both motors same direction
- `turn_left(speed)`, `turn_right(speed)` - One motor active, one stopped
- `spin_left(speed)`, `spin_right(speed)` - Motors in opposite directions (in-place rotation)
- `differential_drive(left, right)` - Independent speed and direction per motor
- PWM on ENA/ENB pins at 1000 Hz for speed control

### actuators/sweeper.py

Controls two N20 geared motors connected to a single L298N output channel with reversed polarity wiring. When IN1 is HIGH and IN2 is LOW, one motor spins clockwise and the other counter-clockwise, sweeping debris inward.

### actuators/vacuum.py

Controls the 980kV brushless motor through a 20A ESC using pigpio for precise PWM timing on GPIO18.

- ESC communication uses servo-style pulsewidths: 1000 microseconds (off) to 2000 microseconds (full throttle)
- Arming sequence sends minimum throttle for 3 seconds
- Speed control maps 0-100 percent to the 1150-2000 microsecond range
- Includes an ESC calibration routine for setting throttle endpoints

### display/oled_eyes.py

Manages two 1.3-inch SSD1306 OLED displays showing animated eyes. Each display is accessed through a custom `MuxedSerial` wrapper that switches the TCA9548A channel before each I2C transaction.

Eye anatomy (drawn with PIL/Pillow):
- Outer ellipse (fills most of the 128x64 screen)
- White iris circle (radius 20 pixels)
- Black pupil circle (radius 10 pixels)
- Small white highlight circle (offset for reflection effect)

Blinking animation:
- Random interval between 3 and 7 seconds
- 4-step close animation followed by 4-step open animation
- 20% chance of a double-blink
- Runs in a daemon thread to avoid blocking other operations

### navigation/zigzag.py

Implements the automatic cleaning pattern as a state machine:

1. DRIVE_STRAIGHT - Travel forward for the configured distance (default 1000mm), using PID correction from gyroscope heading error applied as differential motor speed
2. TURN_FIRST - Spin 90 degrees using gyroscope feedback, with speed reduction as the target angle is approached
3. SHIFT_FORWARD - Drive forward by the robot width (default 250mm) to move to the next lane
4. TURN_SECOND - Spin another 90 degrees in the same direction
5. Return to step 1 with alternated turn direction

Obstacle avoidance: When either ToF sensor detects an object within 150mm, the robot stops, reverses briefly, turns away from the obstacle, and resumes the pattern.

### web/server.py

Flask application providing:

- `GET /` - Serves the HTML control panel
- `GET /video_feed` - MJPEG camera stream
- `POST /api/mode` - Switch between "auto" and "manual"
- `POST /api/control` - Manual drive commands (forward, backward, left, right, stop)
- `POST /api/vacuum` - Start, stop, or set vacuum speed
- `POST /api/sweeper` - Start, stop, or toggle sweeper motors
- `GET /api/status` - JSON response with all sensor data, battery status, navigation state

### web/camera.py

Captures frames from the Raspberry Pi Camera V2 using Picamera2, converts them to JPEG, and provides a generator function for MJPEG streaming. Frame capture runs in a dedicated thread. The camera is started when entering manual mode and stopped in automatic mode to conserve CPU resources.

---

## 8. Libraries and Dependencies

### Python Packages (RPi.GPIO version)

| Package | Version | Purpose |
|:--|:--|:--|
| flask | >= 3.0 | Web server framework |
| smbus2 | >= 0.4 | I2C communication |
| luma.oled | >= 3.12 | OLED display driver (SSD1306) |
| luma.core | >= 2.4 | Core display abstractions |
| Pillow | >= 10.0 | Image drawing for OLED |
| pigpio | >= 1.78 | Precise PWM for ESC control |
| RPi.GPIO | >= 0.7 | GPIO input/output and interrupts |
| picamera2 | >= 0.3 | Raspberry Pi camera interface |
| numpy | >= 1.24 | Numerical operations |

### Python Packages (libgpiod version)

Same as above, except `RPi.GPIO` is replaced by:

| Package | Version | Purpose |
|:--|:--|:--|
| gpiod | >= 2.1 | Low-level GPIO character device interface |

### System Packages

| Package | Purpose |
|:--|:--|
| i2c-tools | I2C bus scanning and debugging |
| pigpio | pigpio C library and daemon |
| python3-pigpio | pigpio Python bindings |
| python3-libcamera | Camera stack (required by picamera2) |
| python3-picamera2 | Picamera2 system package |
| libgpiod-dev | libgpiod development headers (libgpiod version only) |

---

## 9. Setup and Installation

### Prerequisites

- Raspberry Pi Zero 2W with Raspberry Pi OS (Bookworm or later)
- All hardware components assembled and wired according to Section 3
- Network connectivity (Wi-Fi configured)
- SSH access enabled

### Step 1: Transfer Files

From your development computer:

```bash
scp -r DUSK/ pi@<RASPBERRY_PI_IP>:~/DUSK/
```

For the libgpiod version:

```bash
scp -r DUSK_libgpiod/ pi@<RASPBERRY_PI_IP>:~/DUSK/
```

### Step 2: Run Setup Script

```bash
ssh pi@<RASPBERRY_PI_IP>
cd ~/DUSK
chmod +x setup.sh
sudo ./setup.sh
```

The setup script performs the following:

1. Updates system packages
2. Installs all system dependencies
3. Enables I2C and Camera interfaces via raspi-config
4. Adds the virtual I2C overlay to /boot/config.txt (GPIO5 SDA, GPIO6 SCL, bus 3)
5. Adds the hardware PWM overlay for GPIO18
6. Enables and starts the pigpiod systemd service
7. Creates a Python virtual environment with all pip packages
8. Adds the current user to the i2c, gpio, and video groups
9. Creates an optional systemd service file for auto-start

### Step 3: Reboot

```bash
sudo reboot
```

A reboot is mandatory for the device tree overlays (virtual I2C and PWM) to take effect.

### Step 4: Verify Hardware

After rebooting:

```bash
# Verify the virtual I2C bus exists
ls /dev/i2c*
# Expected output includes: /dev/i2c-3

# Scan for the TCA9548A multiplexer
sudo i2cdetect -y 3
# Should show address 0x70

# Verify pigpiod is running
systemctl status pigpiod
```

---

## 10. Running the Robot

### Manual Start

```bash
cd ~/DUSK
source venv/bin/activate
sudo python3 main.py
```

The initialization sequence will print the status of each subsystem. Once all systems report OK, the web panel is accessible.

### Systemd Service (Background / Auto-start)

```bash
# Enable auto-start on boot
sudo systemctl enable dusk

# Manual service control
sudo systemctl start dusk
sudo systemctl stop dusk
sudo systemctl restart dusk

# View live logs
sudo journalctl -u dusk -f
```

### Shutdown

Press Ctrl+C or send SIGTERM. The shutdown sequence will:

1. Stop the zig-zag navigation
2. Stop all motors (wheels, sweepers, vacuum)
3. Stop the camera stream
4. Play the OLED eye closing animation
5. Release all GPIO resources
6. Close the I2C bus

---

## 11. Web Control Panel

Access the control panel at:

```
http://<RASPBERRY_PI_IP>:5000
```

### Interface Elements

- **Mode Switch** - Toggle between Manual and Automatic mode
- **Live Camera** - MJPEG video feed (active in manual mode only)
- **D-Pad Controls** - Directional buttons for forward, backward, left, right, and stop
- **Keyboard Support** - Arrow keys or W/A/S/D for driving (manual mode)
- **Battery Display** - Voltage, current, and percentage with visual indicator
- **Vacuum Slider** - Set vacuum motor speed from 0% to 100%
- **Sweeper Toggle** - Enable or disable sweeper motors
- **Sensor Panel** - ToF left/right distances, heading, navigation state, wheel speeds

The status panel refreshes every 500 milliseconds via polling.

---

## 12. Operating Modes

### Automatic Mode

When switched to automatic mode:

1. The sweeper motors start at the default speed (70%)
2. The vacuum motor starts at the default speed (50%)
3. The zig-zag navigation begins
4. The camera stream shuts down to conserve CPU

The robot drives in straight lines, makes 90-degree turns at each end, shifts over by one robot width, and reverses direction. The PID controller uses gyroscope heading error to apply differential motor speed corrections, keeping the robot on a straight path.

If a ToF sensor detects an obstacle within 150mm, the robot stops, reverses 500ms, turns away from the obstacle, and resumes the cleaning pattern.

### Manual Mode

When switched to manual mode:

1. The navigation stops and motors halt
2. The camera stream activates
3. The web D-pad and keyboard controls become active
4. The vacuum and sweeper can be independently controlled via the web panel

Drive commands are sent as POST requests. Pressing a direction button sends the command; releasing it sends a stop command. This provides immediate responsive control.

---

## 13. Calibration

### Gyroscope Calibration

Gyroscope calibration runs automatically at startup. The robot must be stationary for approximately 1 second while 100 gyroscope samples are averaged to determine the bias offset. If the robot is moved during this phase, the heading measurements will be inaccurate.

### ESC Calibration

If the ESC has not been previously calibrated:

```python
from actuators.vacuum import VacuumMotor
motor = VacuumMotor()
motor.calibrate()
```

Follow the interactive prompts to set the throttle endpoints. This only needs to be done once per ESC.

### Encoder Pulses Per Revolution

The default value is 20 pulses per revolution. If your encoder disc has a different number of slots, update `ENCODER_PULSES_PER_REV` in config.py. You can verify by manually rotating a wheel one full revolution and checking the pulse count.

### Wheel Diameter

The default wheel diameter is 65mm (circumference 204.2mm). Measure your actual wheels and update `WHEEL_DIAMETER_MM` and `WHEEL_CIRCUMFERENCE_MM` in config.py for accurate distance calculation.

---

## 14. Troubleshooting

| Symptom | Likely Cause | Solution |
|:--|:--|:--|
| `/dev/i2c-3` does not exist | Virtual I2C overlay not loaded | Check `/boot/config.txt` for `dtoverlay=i2c-gpio,i2c_gpio_sda=5,i2c_gpio_scl=6,bus=3`, reboot |
| `i2cdetect` shows no devices at 0x70 | TCA9548A wiring issue | Verify SDA/SCL connections to GPIO5/6, check 3.3V power, check pull-up resistors |
| MPU6050 WHO_AM_I error | MPU6050 not powered or wrong channel | Verify 3.3V to MPU6050, verify TCA Channel 0 wiring |
| VL53L0X returns 8190mm | Sensor not initialized or out of range | Check 3.3V power, verify TCA Channel 3/4 wiring |
| OLED displays nothing | Wrong driver or address | Verify SSD1306 controller type, try address 0x3D if 0x3C fails |
| Motors do not spin | L298N not powered or ENA/ENB not connected | Verify 12V to L298N, verify ENA/ENB GPIO connections |
| ESC beeps continuously | ESC not armed or not calibrated | Run the arming sequence, or perform full ESC calibration |
| Camera error | libcamera not installed | Run `libcamera-hello` to test, install python3-picamera2 |
| Web panel not accessible | Firewall blocking port 5000 | Run `sudo ufw allow 5000` or disable firewall |
| pigpio connection error | pigpiod not running | Run `sudo pigpiod` or `sudo systemctl start pigpiod` |
| Robot drifts during straight line | Gyroscope not calibrated | Ensure robot is stationary during startup calibration |
| Robot turns more/less than 90 degrees | Turn tolerance too high/low | Adjust `TURN_TOLERANCE` in config.py |

---

## 15. Version Differences

Two versions of the codebase are provided:

### DUSK/ (RPi.GPIO + pigpio)

- Uses RPi.GPIO for digital input/output and interrupt-based encoder counting
- Uses RPi.GPIO PWM for motor enable pins (ENA, ENB)
- Uses pigpio exclusively for ESC PWM (GPIO18)
- Requires `RPi.GPIO` pip package

### DUSK_libgpiod/ (libgpiod + pigpio)

- Uses the Linux kernel's GPIO character device interface via the gpiod Python library
- Encoder pulse counting uses `gpiod.request_lines()` with `Edge.FALLING` detection and `wait_edge_events()` in a dedicated thread
- Motor and sweeper direction pins use `gpiod.request_lines()` with `Direction.OUTPUT`
- Motor PWM (ENA, ENB, sweeper ENA) uses pigpio `set_PWM_dutycycle()` because libgpiod does not support PWM
- ESC PWM still uses pigpio `set_servo_pulsewidth()`
- No `GPIO.setmode()` or `GPIO.cleanup()` calls; gpiod handles resource cleanup via `request.release()`
- Requires `gpiod>=2.1` pip package and `libgpiod-dev` system package
- GPIO chip path configured as `/dev/gpiochip0` in config.py

The libgpiod version is the recommended approach for newer Raspberry Pi OS versions, as RPi.GPIO is deprecated in favor of the character device interface.

### Files Modified in libgpiod Version

| File | Changes |
|:--|:--|
| config.py | Added `GPIO_CHIP = "/dev/gpiochip0"` |
| sensors/encoders.py | Replaced RPi.GPIO interrupts with gpiod edge events |
| actuators/motors.py | Direction pins via gpiod, PWM via pigpio |
| actuators/sweeper.py | Direction pins via gpiod, PWM via pigpio |
| main.py | Removed RPi.GPIO imports and GPIO.cleanup() |
| requirements.txt | Replaced RPi.GPIO with gpiod |
| setup.sh | Added libgpiod-dev and python3-libgpiod packages |

---

## 16. Safety Notes

- Always ensure the brushless motor propeller or vacuum fan is securely attached before running the vacuum motor. Loose parts at high RPM are dangerous.
- Never connect the ESC UBEC 5V output to the Raspberry Pi simultaneously with the LM2596 5.1V supply. This can cause voltage conflicts and damage the Pi.
- The Li-Po battery must be charged and discharged through the BMS. Never bypass the BMS.
- When the system reports a critical battery level (below 9.9V for 3S), the robot will initiate an emergency shutdown. Do not continue operating below this voltage.
- Disconnect the battery before performing any wiring changes.
- The L298N motor drivers and brushless motor can draw significant current. Ensure all power wiring uses adequately rated conductors.
- The 3.3V and 5V rails must come from the LM2596 regulators, not from the Raspberry Pi's own 3.3V/5V pins. The Pi cannot supply enough current for all connected devices.
