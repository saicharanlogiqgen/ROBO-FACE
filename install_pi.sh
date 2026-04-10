#!/bin/bash
# Raspberry Pi Installation Script for Voice Robot Face

echo "=========================================="
echo "Voice Robot Face - Raspberry Pi Setup"
echo "=========================================="

# Check if running on Pi
if [ ! -f /proc/cpuinfo ] || ! grep -q "Raspberry Pi\|BCM" /proc/cpuinfo; then
    echo "Warning: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "[1/7] Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install system dependencies
echo "[2/7] Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv \
    portaudio19-dev python3-pyaudio libasound2-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    build-essential git

# Create virtual environment
echo "[3/7] Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
echo "[4/7] Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "[5/7] Upgrading pip..."
pip install --upgrade pip

# Install sounddevice (recommended for Pi)
echo "[6/7] Installing sounddevice (recommended for Pi)..."
pip install sounddevice

# Install Python dependencies
echo "[7/7] Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Set your GROQ_API_KEY in .env file or as environment variable"
echo "2. Activate virtual environment: source venv/bin/activate"
echo "3. Run the application: python3 voice_robot.py"
echo ""
echo "For detailed setup instructions, see RASPBERRY_PI_SETUP.md"
echo ""

