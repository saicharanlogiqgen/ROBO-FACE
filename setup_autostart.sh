#!/bin/bash
# setup_autostart.sh
# Run this script once to configure AI Nestham to start automatically on boot

echo "=========================================="
echo "AI Nestham - Autostart Setup"
echo "=========================================="
echo ""

# Get the current directory (where your project is)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if voice_robot.py exists
if [ ! -f "$PROJECT_DIR/voice_robot.py" ]; then
    echo "❌ Error: voice_robot.py not found in $PROJECT_DIR"
    echo "Please run this script from your AI Nestham project directory"
    exit 1
fi

# Check if GROQ_API_KEY is set in .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  Warning: .env file not found"
    read -p "Enter your GROQ_API_KEY: " GROQ_KEY
    echo "GROQ_API_KEY=$GROQ_KEY" > "$PROJECT_DIR/.env"
    echo "✓ Created .env file with your API key"
else
    echo "✓ Found .env file"
fi

# Create the launcher script
echo "[1/4] Creating launcher script..."
cat > "$PROJECT_DIR/start_robot.sh" << 'EOF'
#!/bin/bash
# AI Nestham Auto-start Launcher

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Log file
LOG_FILE="$DIR/robot_startup.log"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "Starting AI Nestham Robot Face..."

# Wait for X server to be ready (important for GUI)
log_message "Waiting for X server..."
sleep 5

# Set display
export DISPLAY=:0

# Change to project directory
cd "$DIR"

# Load environment variables
if [ -f "$DIR/.env" ]; then
    export $(cat "$DIR/.env" | grep -v '^#' | xargs)
    log_message "Loaded environment variables from .env"
else
    log_message "⚠️  Warning: .env file not found"
fi

# Check if virtual environment exists
if [ -d "$DIR/venv" ]; then
    log_message "Activating virtual environment..."
    source "$DIR/venv/bin/activate"
else
    log_message "⚠️  Warning: Virtual environment not found, using system Python"
fi

# Start the robot face
log_message "Launching voice_robot.py..."
python3 "$DIR/voice_robot.py" 2>&1 | tee -a "$LOG_FILE"

log_message "AI Nestham stopped."
EOF

chmod +x "$PROJECT_DIR/start_robot.sh"
echo "✓ Created launcher script: $PROJECT_DIR/start_robot.sh"

# Create systemd service (Method 1 - Recommended for headless operation)
echo ""
echo "[2/4] Creating systemd service..."
SERVICE_FILE="/etc/systemd/system/ai-nestham.service"

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=AI Nestham Robot Face
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$USER/.Xauthority
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/start_robot.sh
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

echo "✓ Created systemd service: $SERVICE_FILE"

# Create autostart desktop entry (Method 2 - For desktop environment)
echo ""
echo "[3/4] Creating autostart desktop entry..."
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/ai-nestham.desktop" << EOF
[Desktop Entry]
Type=Application
Name=AI Nestham Robot Face
Comment=Start AI Nestham robot face on login
Exec=$PROJECT_DIR/start_robot.sh
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

echo "✓ Created autostart entry: $AUTOSTART_DIR/ai-nestham.desktop"

# Ask user which method to enable
echo ""
echo "[4/4] Choose autostart method:"
echo "=========================================="
echo "1) Systemd Service (Recommended - starts before login)"
echo "2) Desktop Autostart (starts after desktop login)"
echo "3) Both methods"
echo "4) Skip (manual setup later)"
echo "=========================================="
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Enabling systemd service..."
        sudo systemctl daemon-reload
        sudo systemctl enable ai-nestham.service
        echo "✓ Systemd service enabled"
        echo ""
        echo "Service commands:"
        echo "  Start now:    sudo systemctl start ai-nestham"
        echo "  Stop:         sudo systemctl stop ai-nestham"
        echo "  View logs:    sudo journalctl -u ai-nestham -f"
        echo "  Disable:      sudo systemctl disable ai-nestham"
        ;;
    2)
        echo ""
        echo "✓ Desktop autostart enabled"
        echo "The robot will start automatically after you log in to the desktop"
        ;;
    3)
        echo ""
        echo "Enabling both methods..."
        sudo systemctl daemon-reload
        sudo systemctl enable ai-nestham.service
        echo "✓ Both methods enabled"
        echo ""
        echo "Service commands:"
        echo "  Start now:    sudo systemctl start ai-nestham"
        echo "  Stop:         sudo systemctl stop ai-nestham"
        echo "  View logs:    sudo journalctl -u ai-nestham -f"
        echo "  Disable:      sudo systemctl disable ai-nestham"
        ;;
    4)
        echo ""
        echo "⚠️  Skipped autostart setup"
        echo "You can enable it later by running:"
        echo "  sudo systemctl enable ai-nestham"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "✓ Autostart Setup Complete!"
echo "=========================================="
echo ""
echo "Additional Configuration:"
echo ""
echo "1. To test the launcher manually:"
echo "   $PROJECT_DIR/start_robot.sh"
echo ""
echo "2. To disable autostart later:"
echo "   sudo systemctl disable ai-nestham"
echo "   rm $AUTOSTART_DIR/ai-nestham.desktop"
echo ""
echo "3. View startup logs:"
echo "   cat $PROJECT_DIR/robot_startup.log"
echo ""
echo "4. The robot will start automatically on next boot!"
echo ""
echo "Reboot now? (y/n)"
read -p "> " reboot_choice

if [[ "$reboot_choice" =~ ^[Yy]$ ]]; then
    echo "Rebooting in 5 seconds... (Ctrl+C to cancel)"
    sleep 5
    sudo reboot
else
    echo "Please reboot manually to test autostart: sudo reboot"
fi