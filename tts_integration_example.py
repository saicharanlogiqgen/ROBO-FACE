"""
Example integration of RobotFace with Text-to-Speech

This file shows how to integrate lip sync with various TTS libraries.
Choose the example that matches your TTS library.
"""

import pygame
from robo import RobotFace, Viseme, WIDTH, HEIGHT, FPS

# Initialize Pygame
pygame.init()

# ============================================================================
# EXAMPLE 1: Simple character-based lip sync (works with any TTS)
# ============================================================================
def example_simple_character_based():
    """Simple approach: process text character by character"""
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    robot = RobotFace(screen)
    robot.set_expression("happy")
    
    text = "Hello, I am a cute robot!"
    
    # Enable lip sync
    robot.enable_lip_sync(True)
    
    # Process each character
    for char in text:
        robot.set_phoneme(char, phoneme_duration=4)
        # In a real implementation, you would sync this with TTS timing
        # For now, we'll just animate through the characters
    
    # Your TTS call would go here:
    # tts_engine.say(text)
    # tts_engine.runAndWait()
    
    # After TTS completes:
    # robot.enable_lip_sync(False)


# ============================================================================
# EXAMPLE 2: Using pyttsx3 (offline TTS)
# ============================================================================
def example_pyttsx3():
    """Integration with pyttsx3 library"""
    try:
        import pyttsx3
    except ImportError:
        print("pyttsx3 not installed. Install with: pip install pyttsx3")
        return
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    robot = RobotFace(screen)
    robot.set_expression("happy")
    
    text = "Hello, I am a cute robot!"
    
    # Enable lip sync
    robot.enable_lip_sync(True)
    
    # Process text for lip sync
    robot.speak_text(text, phoneme_duration=5)
    
    # Initialize TTS engine
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Speed of speech
    
    # Speak the text
    engine.say(text)
    
    # Run in a separate thread or use callbacks for better sync
    # For now, simple approach:
    engine.runAndWait()
    
    # Disable lip sync after speaking
    robot.enable_lip_sync(False)


# ============================================================================
# EXAMPLE 3: Using Windows SAPI (Windows only)
# ============================================================================
def example_windows_sapi():
    """Integration with Windows SAPI"""
    try:
        import win32com.client
    except ImportError:
        print("pywin32 not installed. Install with: pip install pywin32")
        return
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    robot = RobotFace(screen)
    robot.set_expression("happy")
    
    text = "Hello, I am a cute robot!"
    
    # Enable lip sync
    robot.enable_lip_sync(True)
    
    # Create SAPI object
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    
    # Process text for lip sync
    robot.speak_text(text, phoneme_duration=5)
    
    # Speak
    speaker.Speak(text)
    
    # Disable lip sync
    robot.enable_lip_sync(False)


# ============================================================================
# EXAMPLE 4: Manual phoneme timing (most accurate)
# ============================================================================
def example_manual_phoneme_timing():
    """Manual phoneme timing - most accurate but requires phoneme data"""
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    robot = RobotFace(screen)
    robot.set_expression("happy")
    
    # Phoneme list: (phoneme, duration_ms)
    # This would come from your TTS library's phoneme analysis
    phonemes = [
        ('h', 50),   # "H" sound
        ('e', 100),  # "E" sound
        ('l', 80),   # "L" sound
        ('l', 80),   # "L" sound
        ('o', 150),  # "O" sound
        (' ', 50),   # Pause
        ('i', 80),   # "I" sound
        (' ', 50),   # Pause
        ('a', 100),  # "A" sound
        ('m', 80),   # "M" sound
        (' ', 50),   # Pause
        ('a', 100),  # "A" sound
        (' ', 50),   # Pause
        ('c', 80),   # "C" sound (K)
        ('u', 120),  # "U" sound
        ('t', 80),   # "T" sound
        ('e', 100),  # "E" sound
    ]
    
    robot.enable_lip_sync(True)
    
    # Set each phoneme with its duration
    for phoneme, duration_ms in phonemes:
        duration_frames = int((duration_ms / 1000.0) * FPS)
        robot.set_phoneme(phoneme, max(1, duration_frames))
        # In real implementation, you would wait for duration_ms
        # or sync with audio playback
    
    robot.enable_lip_sync(False)


# ============================================================================
# EXAMPLE 5: Real-time with threading (recommended for smooth animation)
# ============================================================================
def example_realtime_with_threading():
    """Real-time lip sync using threading"""
    import threading
    import time
    
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    robot = RobotFace(screen)
    robot.set_expression("happy")
    
    text = "Hello, I am a cute robot!"
    
    def speak_thread():
        """Thread for TTS"""
        robot.enable_lip_sync(True)
        
        # Process text
        for char in text:
            robot.set_phoneme(char, phoneme_duration=4)
            time.sleep(0.1)  # Adjust timing based on your TTS speed
        
        # Your TTS call here
        # tts_engine.say(text)
        # tts_engine.runAndWait()
        
        time.sleep(1)  # Wait for speech to complete
        robot.enable_lip_sync(False)
    
    # Start TTS in separate thread
    tts_thread = threading.Thread(target=speak_thread)
    tts_thread.daemon = True
    tts_thread.start()
    
    # Main loop
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        robot.update()
        
        screen.fill((255, 255, 255))
        robot.draw_face()
        pygame.display.flip()
        clock.tick(FPS)


# ============================================================================
# MAIN: Choose which example to run
# ============================================================================
if __name__ == "__main__":
    print("TTS Integration Examples")
    print("=" * 50)
    print("1. Simple character-based")
    print("2. pyttsx3 integration")
    print("3. Windows SAPI integration")
    print("4. Manual phoneme timing")
    print("5. Real-time with threading")
    print()
    
    choice = input("Choose example (1-5): ").strip()
    
    if choice == "1":
        example_simple_character_based()
    elif choice == "2":
        example_pyttsx3()
    elif choice == "3":
        example_windows_sapi()
    elif choice == "4":
        example_manual_phoneme_timing()
    elif choice == "5":
        example_realtime_with_threading()
    else:
        print("Invalid choice")

