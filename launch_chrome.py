"""
Chrome Launcher for AI Nestham
Automatically opens the robot face in Chrome (fullscreen/kiosk mode)
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def find_chrome():
    """Find Chrome executable based on OS"""
    chrome_paths = {
        'linux': [
            'google-chrome',
            'chromium-browser',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/google-chrome-stable'
        ],
        'win32': [
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
            os.path.expanduser('~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe')
        ],
        'darwin': [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium'
        ]
    }
    
    platform = sys.platform
    if platform not in chrome_paths:
        platform = 'linux'  # Default to linux paths
    
    for path in chrome_paths[platform]:
        if os.path.exists(path):
            print(f"✓ Found Chrome: {path}")
            return path
        
        # Try to find in PATH
        try:
            result = subprocess.run([path, '--version'], 
                                  capture_output=True, 
                                  timeout=2,
                                  text=True)
            if result.returncode == 0:
                print(f"✓ Found Chrome in PATH: {path}")
                return path
        except:
            continue
    
    return None


def create_html_file():
    """Create the HTML file with robot face"""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Nestham - Robot Face</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            overflow: hidden;
        }
        #container { text-align: center; position: relative; }
        canvas {
            background: white;
            border-radius: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .controls {
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255,255,255,0.95);
            padding: 20px 40px;
            border-radius: 50px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .btn {
            padding: 15px 40px;
            border: none;
            border-radius: 30px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            transition: all 0.3s;
        }
        .btn:hover { transform: scale(1.05); }
        .btn.listening {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
        .info {
            position: absolute;
            top: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255,255,255,0.95);
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: 600;
            color: #555;
        }
    </style>
</head>
<body>
    <div id="container">
        <div class="info">🤖 AI Nestham - Press 'T' or click button to talk</div>
        <canvas id="canvas" width="800" height="480"></canvas>
        <div class="controls">
            <button class="btn" id="talkBtn" onclick="startTalk()">🎤 TALK</button>
        </div>
    </div>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const btn = document.getElementById('talkBtn');
        
        let robot = { pupilX: 0, pupilY: 0, frame: 0, mouthOpen: 0, lipSync: false };
        
        function drawFace() {
            ctx.fillStyle = '#FFDAB9';
            ctx.fillRect(0, 0, 800, 480);
            
            // Face
            ctx.fillStyle = '#FFDAB9';
            ctx.beginPath();
            ctx.roundRect(40, 40, 720, 400, 50);
            ctx.fill();
            ctx.strokeStyle = '#FFB6C1';
            ctx.lineWidth = 4;
            ctx.stroke();
            
            // Eyes
            drawEye(280, 200, 70);
            drawEye(520, 200, 70);
            
            // Cheeks
            ctx.fillStyle = 'rgba(255, 182, 193, 0.6)';
            ctx.beginPath();
            ctx.arc(160, 320, 30, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(640, 320, 30, 0, Math.PI * 2);
            ctx.fill();
            
            // Mouth
            ctx.strokeStyle = '#C89696';
            ctx.lineWidth = 5;
            ctx.beginPath();
            const mouthW = 100 + robot.mouthOpen * 40;
            const mouthH = 40 + robot.mouthOpen * 20;
            ctx.ellipse(400, 340, mouthW, mouthH, 0, 0, Math.PI);
            ctx.stroke();
            
            robot.frame++;
        }
        
        function drawEye(x, y, size) {
            ctx.fillStyle = '#64C8FF';
            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#999';
            ctx.lineWidth = 3;
            ctx.stroke();
            
            const px = x + robot.pupilX;
            const py = y + robot.pupilY;
            
            ctx.fillStyle = '#3296DC';
            ctx.beginPath();
            ctx.arc(px, py, 25, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.fillStyle = '#000';
            ctx.beginPath();
            ctx.arc(px, py, 16, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.fillStyle = '#FFF';
            ctx.beginPath();
            ctx.arc(px - 4, py - 4, 5, 0, Math.PI * 2);
            ctx.fill();
        }
        
        function animate() {
            const angle = robot.frame * 0.02;
            robot.pupilX = Math.cos(angle) * 8;
            robot.pupilY = Math.sin(angle) * 8;
            
            if (robot.lipSync) {
                robot.mouthOpen = 0.5 + Math.sin(robot.frame * 0.3) * 0.5;
            } else {
                robot.mouthOpen = 0;
            }
            
            drawFace();
            requestAnimationFrame(animate);
        }
        
        let recognition;
        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US';
            
            recognition.onstart = () => {
                btn.classList.add('listening');
                btn.textContent = '🎤 LISTENING...';
            };
            
            recognition.onresult = (e) => {
                const text = e.results[0][0].transcript;
                console.log('You said:', text);
                respond(text);
            };
            
            recognition.onend = () => {
                btn.classList.remove('listening');
                btn.textContent = '🎤 TALK';
            };
        }
        
        function startTalk() {
            if (recognition) recognition.start();
        }
        
        function respond(text) {
            robot.lipSync = true;
            const responses = [
                'Hello! I am AI Nestham. How can I help you?',
                'That is interesting! Tell me more!',
                'I understand. What else would you like to know?',
                'Great! Is there anything else I can do for you?'
            ];
            const response = responses[Math.floor(Math.random() * responses.length)];
            
            const utterance = new SpeechSynthesisUtterance(response);
            utterance.rate = 0.9;
            utterance.onend = () => { robot.lipSync = false; };
            window.speechSynthesis.speak(utterance);
        }
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 't' || e.key === 'T') startTalk();
        });
        
        animate();
    </script>
</body>
</html>"""
    
    html_path = Path('ai_nestham.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✓ Created HTML file: {html_path.absolute()}")
    return html_path.absolute()


def launch_in_chrome(html_path, kiosk_mode=True):
    """Launch HTML file in Chrome"""
    chrome_exe = find_chrome()
    
    if not chrome_exe:
        print("✗ Chrome not found. Trying default browser...")
        webbrowser.open(f'file://{html_path}')
        return
    
    # Chrome arguments
    args = [chrome_exe]
    
    if kiosk_mode:
        # Kiosk mode (fullscreen, no UI)
        args.extend([
            '--kiosk',
            '--no-first-run',
            '--disable-infobars',
            '--disable-session-crashed-bubble',
            f'file://{html_path}'
        ])
    else:
        # App mode (no tabs, minimal UI)
        args.extend([
            '--app=' + f'file://{html_path}',
            '--start-fullscreen',
            '--no-first-run'
        ])
    
    print(f"✓ Launching Chrome in {'kiosk' if kiosk_mode else 'app'} mode...")
    print(f"  Press F11 to exit fullscreen")
    print(f"  Press Alt+F4 (Windows/Linux) or Cmd+Q (Mac) to close")
    
    try:
        subprocess.Popen(args)
        print("✓ Chrome launched successfully!")
    except Exception as e:
        print(f"✗ Error launching Chrome: {e}")
        print("  Trying default browser...")
        webbrowser.open(f'file://{html_path}')


def main():
    print("=" * 60)
    print("AI NESTHAM - Chrome Launcher")
    print("=" * 60)
    print()
    
    # Ask user for mode
    print("Choose launch mode:")
    print("1. Kiosk Mode (Fullscreen, no browser UI - for Raspberry Pi)")
    print("2. App Mode (Windowed with minimal UI)")
    print("3. Normal Browser")
    
    choice = input("\nEnter choice (1/2/3) [default: 1]: ").strip() or "1"
    
    kiosk = choice == "1"
    
    print()
    print("Creating HTML file...")
    html_path = create_html_file()
    
    print()
    time.sleep(0.5)
    
    if choice == "3":
        print("Opening in default browser...")
        webbrowser.open(f'file://{html_path}')
    else:
        launch_in_chrome(html_path, kiosk_mode=kiosk)
    
    print()
    print("✓ Done! The robot face should now be displayed in Chrome.")
    print()


if __name__ == "__main__":
    main()