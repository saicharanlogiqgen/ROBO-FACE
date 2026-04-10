"""
TTS Robot Face - Text-to-Speech with Lip Sync
Speaks "Hello world my name is AI Nestham" with synchronized lip movements
"""

import pygame
import threading
import time
from robo import RobotFace, WIDTH, HEIGHT, FPS

# Initialize Pygame
pygame.init()

def speak_with_lip_sync(robot, text):
    """Speak text with synchronized lip movements"""
    try:
        import pyttsx3
    except ImportError:
        print("pyttsx3 not installed. Installing...")
        print("Please run: pip install pyttsx3")
        return False
    
    # Enable lip sync
    robot.enable_lip_sync(True)
    
    # Initialize TTS engine
    engine = pyttsx3.init()
    
    # Configure voice properties
    engine.setProperty('rate', 150)  # Speed of speech (words per minute)
    engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
    
    # Try to set a more natural voice (optional)
    voices = engine.getProperty('voices')
    if voices:
        # Prefer female voice if available, otherwise use first available
        for voice in voices:
            if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
    
    # Start TTS in a separate thread
    def tts_thread():
        engine.say(text)
        engine.runAndWait()
        # Give a moment for lip sync to finish
        time.sleep(0.5)
        robot.enable_lip_sync(False)
    
    # Start TTS thread
    tts_thread_obj = threading.Thread(target=tts_thread)
    tts_thread_obj.daemon = True
    tts_thread_obj.start()
    
    # Process text character by character for lip sync
    # This runs in sync with the main loop
    char_index = 0
    last_char_time = time.time()
    # Adjust delay based on speech rate (150 WPM ≈ 2.5 words/sec ≈ 10-12 chars/sec)
    char_delay = 0.08  # Delay between characters (adjust based on speech rate)
    
    return True, char_index, last_char_time, char_delay, text


def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TTS Robot Face - AI Nestham")
    clock = pygame.time.Clock()
    
    robot = RobotFace(screen)
    robot.set_expression("happy")
    
    # Text to speak
    text = "Hello world my name is AI Nestham"
    
    # Start TTS with lip sync
    tts_started, char_index, last_char_time, char_delay, speech_text = speak_with_lip_sync(robot, text)
    
    if not tts_started:
        print("TTS not available. Please install pyttsx3: pip install pyttsx3")
        return
    
    # Variables for character-by-character lip sync
    processing_text = True  # Start processing immediately
    text_start_time = time.time()
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    # Restart speech
                    tts_started, char_index, last_char_time, char_delay, speech_text = speak_with_lip_sync(robot, text)
                    processing_text = True
                    text_start_time = time.time()
                elif event.key == pygame.K_ESCAPE:
                    running = False
        
        # Process text character by character for lip sync
        if tts_started and processing_text:
            current_time = time.time()
            if current_time - last_char_time >= char_delay and char_index < len(speech_text):
                char = speech_text[char_index]
                # Set phoneme for this character
                robot.set_phoneme(char, phoneme_duration=int(char_delay * FPS))
                char_index += 1
                last_char_time = current_time
                
                # Check if we've processed all characters
                if char_index >= len(speech_text):
                    processing_text = False
        
        # Update robot animations
        robot.update()
        
        # Draw everything - full screen face only
        screen.fill((255, 255, 255))
        robot.draw_face()
        
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()


if __name__ == "__main__":
    main()

