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
