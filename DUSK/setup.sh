#!/bin/bash
# ============================================================
# DUSK - Setup Script for Raspberry Pi Zero 2W
# Run this script once before first use.
# Usage: chmod +x setup.sh && sudo ./setup.sh
# ============================================================

set -e

echo "============================================================"
echo "  DUSK - Setup Script"
echo "  Dust Unification & Sweeping Keeper"
echo "============================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Please run as root: sudo ./setup.sh"
    exit 1
fi

# ----- System Update -----
echo "[1/8] Updating system packages..."
apt-get update -y
apt-get upgrade -y

# ----- Install System Dependencies -----
echo "[2/8] Installing system dependencies..."
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-smbus \
    python3-pil \
    python3-numpy \
    python3-libcamera \
    python3-picamera2 \
    i2c-tools \
    pigpio \
    python3-pigpio \
    libopenjp2-7 \
    libtiff5 \
    libfreetype6-dev \
    git

# ----- Enable Interfaces -----
echo "[3/8] Enabling I2C and Camera interfaces..."

# Enable I2C
raspi-config nonint do_i2c 0

# Enable Camera
raspi-config nonint do_camera 0

# ----- Configure Virtual I2C -----
echo "[4/8] Configuring Virtual I2C on GPIO5(SDA) / GPIO6(SCL)..."

CONFIG_FILE="/boot/config.txt"
# Check if newer path exists
if [ -f "/boot/firmware/config.txt" ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
fi

# Add virtual I2C overlay if not already present
if ! grep -q "dtoverlay=i2c-gpio,i2c_gpio_sda=5,i2c_gpio_scl=6" "$CONFIG_FILE"; then
    echo "" >> "$CONFIG_FILE"
    echo "# DUSK: Virtual I2C on GPIO5(SDA) / GPIO6(SCL)" >> "$CONFIG_FILE"
    echo "dtoverlay=i2c-gpio,i2c_gpio_sda=5,i2c_gpio_scl=6,bus=3" >> "$CONFIG_FILE"
    echo "  Added i2c-gpio overlay to $CONFIG_FILE"
else
    echo "  i2c-gpio overlay already configured"
fi

# Enable hardware PWM for ESC on GPIO18
if ! grep -q "dtoverlay=pwm" "$CONFIG_FILE"; then
    echo "" >> "$CONFIG_FILE"
    echo "# DUSK: Hardware PWM for ESC" >> "$CONFIG_FILE"
    echo "dtoverlay=pwm,pin=18,func=2" >> "$CONFIG_FILE"
    echo "  Added PWM overlay to $CONFIG_FILE"
else
    echo "  PWM overlay already configured"
fi

# ----- Enable pigpiod Service -----
echo "[5/8] Enabling pigpio daemon..."
systemctl enable pigpiod
systemctl start pigpiod || true

# ----- Create Python Virtual Environment -----
echo "[6/8] Setting up Python virtual environment..."

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create venv with system packages (for picamera2, etc.)
python3 -m venv --system-site-packages "$SCRIPT_DIR/venv"

# Activate and install packages
source "$SCRIPT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"
deactivate

echo "  Virtual environment created at: $SCRIPT_DIR/venv"

# ----- Add User to Required Groups -----
echo "[7/8] Adding user to required groups..."
ACTUAL_USER="${SUDO_USER:-$USER}"
usermod -aG i2c "$ACTUAL_USER" 2>/dev/null || true
usermod -aG gpio "$ACTUAL_USER" 2>/dev/null || true
usermod -aG video "$ACTUAL_USER" 2>/dev/null || true

# ----- Create Systemd Service (optional) -----
echo "[8/8] Creating systemd service..."

cat > /etc/systemd/system/dusk.service << EOF
[Unit]
Description=DUSK Smart Vacuum Cleaner
After=network.target pigpiod.service
Wants=pigpiod.service

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python3 $SCRIPT_DIR/main.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "  Service created: dusk.service"
echo "  To enable auto-start: sudo systemctl enable dusk"

# ----- Done -----
echo ""
echo "============================================================"
echo "  Setup Complete!"
echo "============================================================"
echo ""
echo "  IMPORTANT: A reboot is required for:"
echo "    - Virtual I2C (GPIO5/GPIO6) to be activated"
echo "    - Camera interface to be enabled"
echo "    - PWM overlay to be loaded"
echo ""
echo "  After reboot, verify I2C with:"
echo "    sudo i2cdetect -y 3"
echo ""
echo "  To run DUSK:"
echo "    cd $SCRIPT_DIR"
echo "    source venv/bin/activate"
echo "    sudo python3 main.py"
echo ""
echo "  Or use the systemd service:"
echo "    sudo systemctl start dusk"
echo "    sudo journalctl -u dusk -f"
echo ""
echo "  Reboot now? (y/n)"
read -r REBOOT_ANSWER
if [ "$REBOOT_ANSWER" = "y" ] || [ "$REBOOT_ANSWER" = "Y" ]; then
    reboot
fi
