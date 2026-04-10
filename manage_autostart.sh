#!/bin/bash
# manage_autostart.sh
# Script to easily manage AI Nestham autostart

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_menu() {
    clear
    echo "=========================================="
    echo "    AI Nestham - Autostart Manager"
    echo "=========================================="
    echo ""
    echo "1) Start Robot Now"
    echo "2) Stop Robot"
    echo "3) Restart Robot"
    echo "4) Enable Autostart"
    echo "5) Disable Autostart"
    echo "6) Check Status"
    echo "7) View Live Logs"
    echo "8) View Startup Log"
    echo "9) Test Launcher Script"
    echo "0) Exit"
    echo ""
    echo "=========================================="
}

while true; do
    show_menu
    read -p "Enter your choice: " choice
    
    case $choice in
        1)
            echo ""
            echo "Starting AI Nestham..."
            sudo systemctl start ai-nestham
            echo "✓ Started. Check status with option 6"
            read -p "Press Enter to continue..."
            ;;
        2)
            echo ""
            echo "Stopping AI Nestham..."
            sudo systemctl stop ai-nestham
            echo "✓ Stopped"
            read -p "Press Enter to continue..."
            ;;
        3)
            echo ""
            echo "Restarting AI Nestham..."
            sudo systemctl restart ai-nestham
            echo "✓ Restarted"
            read -p "Press Enter to continue..."
            ;;
        4)
            echo ""
            echo "Enabling autostart..."
            sudo systemctl enable ai-nestham
            echo "✓ Autostart enabled - will start on next boot"
            read -p "Press Enter to continue..."
            ;;
        5)
            echo ""
            echo "Disabling autostart..."
            sudo systemctl disable ai-nestham
            sudo systemctl stop ai-nestham
            rm -f "$HOME/.config/autostart/ai-nestham.desktop"
            echo "✓ Autostart disabled"
            read -p "Press Enter to continue..."
            ;;
        6)
            echo ""
            echo "Current Status:"
            echo "=========================================="
            sudo systemctl status ai-nestham --no-pager
            echo ""
            echo "Autostart Status:"
            systemctl is-enabled ai-nestham 2>/dev/null && echo "✓ Autostart ENABLED" || echo "✗ Autostart DISABLED"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        7)
            echo ""
            echo "Live logs (Press Ctrl+C to exit):"
            echo "=========================================="
            sudo journalctl -u ai-nestham -f
            ;;
        8)
            echo ""
            echo "Startup Log:"
            echo "=========================================="
            if [ -f "$PROJECT_DIR/robot_startup.log" ]; then
                tail -50 "$PROJECT_DIR/robot_startup.log"
            else
                echo "No startup log found"
            fi
            echo ""
            read -p "Press Enter to continue..."
            ;;
        9)
            echo ""
            echo "Testing launcher script..."
            echo "=========================================="
            "$PROJECT_DIR/start_robot.sh"
            ;;
        0)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo ""
            echo "❌ Invalid choice"
            sleep 2
            ;;
    esac
done