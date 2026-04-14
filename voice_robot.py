"""
AI Nestham – Telugu + English (Language-to-Language)
Raspberry Pi SAFE + ALSA SAFE + GROQ + PYTTSX3 SAFE
FINAL FIX: WAV -> PCM16 for pygame compatibility
"""

import os, sys, time, threading, pygame, re, tempfile, wave, io
import numpy as np
import sounddevice as sd
import cv2
import random
from openai import OpenAI
from dotenv import load_dotenv
import asyncio
import edge_tts

from robo import RobotFace, WIDTH, HEIGHT, FPS
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# ================= API CONFIG =================

# ---- LOGGING ----
# Set DEBUG=1 to enable diagnostic prints.
DEBUG = os.getenv("DEBUG", "0").strip() in {"1", "true", "True", "yes", "YES"}


def dprint(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


# ---- GROQ ----
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "api_key")
GROQ_STT_MODEL = "whisper-large-v3-turbo"
GROQ_CHAT_MODEL = "llama-3.1-8b-instant"

# Validate API key
if GROQ_API_KEY == "key" or not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not set!")
    print("   Please set it in one of the following ways:")
    print("   1. Create a .env file with: GROQ_API_KEY=your_key_here")
    print("   2. Set environment variable: export GROQ_API_KEY=your_key_here")
    print("   3. Or edit voice_robot.py and set GROQ_API_KEY directly")

# =============================================

# ---------------- INIT ----------------
pygame.init()
# Stereo + larger buffer — helps MP3 playback on Raspberry Pi
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)


def _pygame_supports_mp3_bytesio():
    """pygame.mixer.music.load(BytesIO, 'mp3') needs pygame 2.1.3+."""
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", str(getattr(pygame.version, "ver", "")))
    if not m:
        return False
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) >= (2, 1, 3)

# ---------------- AUDIO CONFIG ----------------
MAX_RECORDING = 4.5  # hard ceiling (seconds)
CHUNK_TIME = 0.1  # smaller chunks = faster reaction (was 0.2)
SILENCE_TIME = 0.25  # cut off sooner after speech ends (was 0.4)
VAD_THRESHOLD = 0.06  # fallback — adaptive floor replaces it in practice

# ---- Smarter VAD config ----
VAD_CALIBRATION_CHUNKS = 8  # first 0.8s used to measure room noise floor
VAD_SNR_RATIO = 4.0  # speech must be 4× louder than noise floor to count
VAD_MIN_SPEECH_CHUNKS = 3  # ignore blips shorter than 3 chunks (0.3s)
VAD_HANGOVER_CHUNKS = 3  # stay "active" for 3 chunks after energy drops (0.3s)

# ---------------- MIC SAFE CONFIG ----------------
def get_safe_input_config():
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            try:
                sd.check_input_settings(
                    device=i,
                    samplerate=int(d["default_samplerate"]),
                    channels=1
                )
                dprint(f"✓ Selected Mic {i}: {d['name']} @ {int(d['default_samplerate'])} Hz")
                return i, int(d["default_samplerate"])
            except Exception:
                continue
    raise RuntimeError("No valid microphone found")

MIC_DEVICE, MIC_SR = get_safe_input_config()

# ---------------- ROBOT ----------------
class VoiceRobot:
    def __init__(self, screen):
        self.screen = screen
        self.robot = RobotFace(screen)
        self.robot.set_expression("happy")
        self.tts_voice = "en-US-AriaNeural"

        self.busy = False
        self.speaking = False
        self._prefetched_audio = None

        self.groq = Groq(api_key=GROQ_API_KEY)
        
        # ---- GROQ STT CLIENT (OpenAI-compatible) ----
        self.stt_client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )

        
        # ---- FACE DETECTION INIT ----
        self.face_cascade = None
        self.camera = None
        self._init_face_detector()

    # ---------------- RECORD AUDIO (smart VAD) ----------------
    def record_audio(self):
        """
        Smarter VAD with:
          - RMS energy instead of peak amplitude (noise-resistant)
          - Adaptive noise floor (auto-calibrates to the room)
          - Hangover logic (short silences mid-word don't cut off early)
          - Dynamic silence timeout (short responses cut off faster)
          - Minimum speech gate (ignores sub-0.3s noise bursts)
        """
        return self._record_with_smart_vad(prefetch=False)

    def _record_with_smart_vad(self, prefetch=False):
        """Shared smart VAD for normal recording and pipeline prefetch."""
        if not prefetch:
            self.robot.set_expression("thinking")
        else:
            time.sleep(0.2)

        audio_chunks = []
        elapsed = 0.0
        speech_active = False
        speech_started = False
        silence_time = 0.0
        noise_floor = VAD_THRESHOLD
        hangover = 0
        speech_chunk_count = 0
        peak_energy = 0.0

        calibration_frames = []
        for _ in range(VAD_CALIBRATION_CHUNKS):
            if prefetch and not pygame.mixer.music.get_busy() and elapsed > 0.5:
                break
            chunk = sd.rec(
                int(CHUNK_TIME * MIC_SR),
                samplerate=MIC_SR,
                channels=1,
                device=MIC_DEVICE,
                dtype="float32",
                blocking=True
            ).flatten()
            calibration_frames.append(chunk)
            audio_chunks.append(chunk)
            elapsed += CHUNK_TIME

        if not calibration_frames:
            if not prefetch:
                self.robot.set_expression("happy")
            return None

        cal_audio = np.concatenate(calibration_frames)
        noise_floor = max(
            float(np.sqrt(np.mean(cal_audio ** 2))) * VAD_SNR_RATIO,
            VAD_THRESHOLD,
        )
        if not prefetch:
            dprint(
                f"🎙️  Noise floor: {noise_floor:.4f}  (threshold × {VAD_SNR_RATIO})"
            )

        while elapsed < MAX_RECORDING:
            if prefetch and not pygame.mixer.music.get_busy() and elapsed > 0.5:
                break

            chunk = sd.rec(
                int(CHUNK_TIME * MIC_SR),
                samplerate=MIC_SR,
                channels=1,
                device=MIC_DEVICE,
                dtype="float32",
                blocking=True
            ).flatten()

            audio_chunks.append(chunk)
            elapsed += CHUNK_TIME

            rms = float(np.sqrt(np.mean(chunk ** 2)))
            is_speech = rms > noise_floor

            if is_speech:
                peak_energy = max(peak_energy, rms)
                if not speech_started:
                    speech_started = True
                    speech_active = True
                    if not prefetch:
                        dprint("🗣️  Speech detected")
                hangover = VAD_HANGOVER_CHUNKS
                silence_time = 0.0
                speech_chunk_count += 1

            else:
                if speech_started:
                    if hangover > 0:
                        hangover -= 1
                        speech_chunk_count += 1
                    else:
                        speech_active = False
                        silence_time += CHUNK_TIME

            if speech_started and not speech_active:
                dynamic_silence = SILENCE_TIME
                if speech_chunk_count > 15:
                    dynamic_silence = 0.35
                if silence_time >= dynamic_silence:
                    if not prefetch:
                        dprint(
                            f"✂️  Cut off after {silence_time:.2f}s silence  "
                            f"({speech_chunk_count} speech chunks)"
                        )
                    break

        if not prefetch:
            self.robot.set_expression("happy")

        if not speech_started or speech_chunk_count < VAD_MIN_SPEECH_CHUNKS:
            if not prefetch:
                dprint("🔇 Too short / no speech detected — ignoring")
            return None

        return np.concatenate(audio_chunks)

    # ---------------- STT ----------------
    def speech_to_text(self, audio):
        audio16 = (audio * 32767).astype(np.int16)

        # Build WAV in memory — no tempfile, no disk write
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(MIC_SR)
            wf.writeframes(audio16.tobytes())
        buf.seek(0)

        # Groq's OpenAI-compatible client needs a file-like object with a .name
        buf.name = "audio.wav"

        transcription = self.stt_client.audio.transcriptions.create(
            file=buf,
            model=GROQ_STT_MODEL
        )
        return transcription.text.strip()

    # ---------------- LLM ----------------
    def reply(self, text):
        system = "You are AI Nestham, a friendly and cheerful robot assistant for kids aged 8 to 13. Always reply in English only. Keep every response under 40 words. Use simple, fun, and age-appropriate language. Never use technical jargon, adult topics, or complex words. Be encouraging, positive, and engaging like a best friend."
        
        r = self.groq.chat.completions.create(
            model=GROQ_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text}
            ],
            max_tokens=140
        )

        return r.choices[0].message.content

    # ---------------- PYTTSX3 + LIP SYNC ----------------
    def _text_for_tts(self, text):
        """Remove markdown/symbols so TTS doesn't read 'asterisk' or 'star' aloud."""
        if not text or not isinstance(text, str):
            return ""
        # Remove **bold** and *italic* and _underline_ (keep inner text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)
        # Remove remaining formatting symbols (read as "asterisk", "hash", etc.)
        text = re.sub(r"[*_#]+", " ", text)
        # Collapse multiple spaces and strip
        return re.sub(r"\s+", " ", text).strip()


    def speak(self, text):
        text_clean = self._text_for_tts(text)
        if not text_clean:
            return

        self.speaking = True

        def run():
            async def _stream():
                communicate = edge_tts.Communicate(
                    text_clean,
                    voice=self.tts_voice,
                    rate="+0%",
                    volume="+0%"
                )

                mp3_buf = io.BytesIO()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        mp3_buf.write(chunk["data"])

                if mp3_buf.tell() == 0:
                    self.speaking = False
                    return

                # Lip sync duration: edge_tts ~24 kbps CBR MP3 (good enough for phoneme timing)
                mp3_bytes = mp3_buf.tell()
                mp3_buf.seek(0)
                estimated_duration = (mp3_bytes * 8) / 24_000
                estimated_duration = max(1.0, estimated_duration)

                text_length = len(text_clean)
                frames_per_char = max(
                    4, min(12, int((estimated_duration / text_length) * FPS))
                ) if text_length > 0 else 6

                self.robot.speak_text(text_clean, phoneme_duration=frames_per_char)
                self.robot.viseme_timer = 999
                self.robot.viseme_duration = 0
                self.robot.phoneme_queue_index = 0
                self.robot.enable_lip_sync(True)

                try:
                    if _pygame_supports_mp3_bytesio():
                        pygame.mixer.music.load(mp3_buf, "mp3")
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy():
                            await asyncio.sleep(0.01)
                    else:
                        mp3_path = tempfile.mktemp(".mp3")
                        try:
                            with open(mp3_path, "wb") as f:
                                f.write(mp3_buf.read())
                            pygame.mixer.music.load(mp3_path)
                            pygame.mixer.music.play()
                            while pygame.mixer.music.get_busy():
                                await asyncio.sleep(0.01)
                        finally:
                            try:
                                os.unlink(mp3_path)
                            except OSError:
                                pass
                finally:
                    self.robot.enable_lip_sync(False)
                    self.speaking = False

            asyncio.run(_stream())

        threading.Thread(target=run, daemon=True).start()

    # ---------------- FACE DETECTION ----------------
    def _init_face_detector(self):
        """Initialize Haar Cascade face detector"""
        try:
            # Try local file first (if user has it in project directory)
            local_cascade = "haarcascade_frontalface_default.xml"
            if os.path.exists(local_cascade):
                cascade_path = local_cascade
                dprint(f"Using local cascade file: {cascade_path}")
            else:
                # Use OpenCV's built-in cascade
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                dprint(f"Using OpenCV cascade: {cascade_path}")
            
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty():
                raise Exception(f"Could not load face cascade from {cascade_path}")
            dprint("✓ Face detector initialized")
        except Exception as e:
            dprint(f"✗ Error initializing face detector: {e}")
            dprint("   Make sure OpenCV is properly installed or haarcascade file exists")
            self.face_cascade = None
    
    def detect_face(self):
        """Detect faces from camera and return funny comment"""
        if self.face_cascade is None:
            return "Sorry, I can't see you! My face detector isn't working."
        
        try:
            # Open camera if not already open
            if self.camera is None:
                dprint("Opening camera...")
                # On Windows, use DirectShow backend so camera doesn't hang with pygame window
                if sys.platform == "win32":
                    self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                else:
                    self.camera = cv2.VideoCapture(0)
                # Give camera time to initialize
                time.sleep(0.5)

                if not self.camera.isOpened():
                    # Try alternative camera indices (same backend on Windows)
                    for i in range(1, 3):
                        dprint(f"Trying camera {i}...")
                        if sys.platform == "win32":
                            self.camera = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                        else:
                            self.camera = cv2.VideoCapture(i)
                        time.sleep(0.3)
                        if self.camera.isOpened():
                            break

                    if not self.camera.isOpened():
                        return "Oops! I can't access the camera. Check if it's connected!"

                # Set lower resolution for faster processing
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                # Reduce buffer so we get fresh frames; helps on Windows with GUI
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Warm up: read a few frames (some webcams need this)
                for _ in range(5):
                    self.camera.read()

            # Flush old frames to get latest
            for _ in range(2):
                self.camera.read()
            
            # Capture frame
            ret, frame = self.camera.read()
            if not ret or frame is None:
                return "Hmm, I can't see anything. Are you there?"
            
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50)
            )
            
            if len(faces) == 0:
                return self._get_no_face_comment()
            elif len(faces) == 1:
                x, y, w, h = faces[0]
                # Analyze face size and position for funny comments
                face_size = w * h
                face_center_x = x + w // 2
                frame_center_x = frame.shape[1] // 2
                offset = abs(face_center_x - frame_center_x)
                
                return self._get_face_comment(face_size, offset, w, h)
            else:
                return self._get_multiple_faces_comment(len(faces))
                
        except cv2.error as e:
            dprint(f"OpenCV error: {e}")
            return "Camera error! Make sure your camera is working properly."
        except Exception as e:
            dprint(f"Face detection error: {e}")
            import traceback
            traceback.print_exc()
            return "Whoops! Something went wrong with my vision. Try again!"
    
    def _get_no_face_comment(self):
        """Generate funny comment when no face is detected"""
        comments = [
            "Hey! Where did you go? I'm looking but I can't see anyone!",
            "Are you hiding? Come closer so I can see your beautiful face!",
            "Hmm, I don't see anyone. Are you a ghost? 👻",
            "Hello? Is anyone there? I'm looking but I see nothing!",
            "Come on, show me your face! I promise I won't judge... much! 😄",
            "I'm scanning... scanning... nope, no faces detected. Are you invisible?",
            "Hey! Get in front of the camera! I want to see who I'm talking to!",
            "No face detected! Are you wearing an invisibility cloak?",
        ]
        return random.choice(comments)
    
    def _get_face_comment(self, face_size, offset, width, height):
        """Generate funny comment based on face characteristics"""
        comments = []
        
        # Size-based comments
        if face_size > 50000:  # Very large face (close)
            comments.extend([
                "Wow! You're really close! I can see every detail of your face!",
                "Whoa! You're so close I can count your eyelashes! Back up a bit! 😄",
                "Hey there, close-up! I can see you're excited to meet me!",
            ])
        elif face_size < 15000:  # Small face (far)
            comments.extend([
                "Hey! You're so far away! Come closer so I can see you better!",
                "Are you trying to hide? Come closer, I won't bite! 😊",
                "I can barely see you! Step closer, friend!",
            ])
        else:  # Normal size
            comments.extend([
                "Perfect! I can see you clearly! Nice to meet you!",
                "Hello there! I see a friendly face! 👋",
                "Great! I found you! You look nice today!",
            ])
        
        # Position-based comments
        if offset > 150:  # Off-center
            comments.extend([
                "Hey! You're a bit off-center. Are you trying to avoid me? 😄",
                "I see you! But you're not in the middle. That's okay, I still see you!",
            ])
        
        # Aspect ratio comments
        aspect_ratio = width / height if height > 0 else 1
        if aspect_ratio > 1.2:  # Wide face
            comments.extend([
                "I see a wide smile! You must be happy! 😊",
            ])
        elif aspect_ratio < 0.8:  # Tall face
            comments.extend([
                "You have a nice face shape! Looking good!",
            ])
        
        # Generic positive comments
        comments.extend([
            "Hello beautiful human! I'm glad to see you!",
            "Nice to meet you! You have a lovely face!",
            "Hey there! I see you and you look great!",
            "Perfect! I found you! Ready to chat?",
            "Hello friend! I can see you clearly now!",
        ])
        
        return random.choice(comments)
    
    def _get_multiple_faces_comment(self, count):
        """Generate funny comment when multiple faces detected"""
        comments = [
            f"Wow! I see {count} faces! Are you having a party?",
            f"Hey! There are {count} people here! Say hello to everyone!",
            f"Whoa! {count} faces detected! I'm popular today! 😄",
            f"Amazing! I can see {count} people! This is exciting!",
            f"Hello to all {count} of you! I'm happy to see so many faces!",
        ]
        return random.choice(comments)
    
    def face_detection_with_comment(self):
        """Face detection wrapper that runs in thread"""
        try:
            self.busy = True
            print("🔍 Detecting face...")
            comment = self.detect_face()
            print(f"🤖 Face Detection: {comment}")
            self.speak(comment)
        except Exception as e:
            dprint(f"Face detection error: {e}")
            error_msg = "Oops! Something went wrong with face detection. Try again!"
            self.speak(error_msg)
        finally:
            self.busy = False
    
    def close_camera(self):
        """Close camera when done"""
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    # ---------------- TALK FLOW ----------------
    def talk(self):
        """Entry point: press T to start a turn. Non-blocking."""
        if self.busy:
            return
        threading.Thread(target=self._pipeline_run, daemon=True).start()

    def _pipeline_run(self):
        """
        Pipelined turn:
          1. Record audio (blocking mic capture)
          2. STT then LLM (each in executor; LLM starts immediately after STT)
          3. Speak reply
          4. While speaking: pre-record the NEXT utterance in a background thread
          5. If pre-recorded audio exists, next talk() skips mic wait
        """
        asyncio.run(self._async_pipeline())

    async def _async_pipeline(self):
        loop = asyncio.get_event_loop()

        audio = getattr(self, "_prefetched_audio", None)
        self._prefetched_audio = None

        try:
            self.busy = True

            if audio is None:
                self.robot.set_expression("thinking")
                audio = await loop.run_in_executor(None, self.record_audio)

            if audio is None:
                dprint("No speech detected.")
                return

            dprint("🎤 Transcribing...")
            text = await loop.run_in_executor(None, self.speech_to_text, audio)
            if not text:
                dprint("Empty transcription, skipping.")
                return
            print(f"You: {text}")

            dprint("🤖 Thinking...")
            self.robot.set_expression("thinking")
            reply = await loop.run_in_executor(None, self.reply, text)
            if not reply:
                return
            print(f"AI: {reply}")

            self.speak(reply)

            await asyncio.sleep(0.3)

            dprint("👂 Pre-recording next turn while speaking...")
            prefetched = await loop.run_in_executor(None, self._prefetch_audio)
            self._prefetched_audio = prefetched

            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)

        except Exception as e:
            dprint(f"Pipeline error: {e}")
        finally:
            self.busy = False

    def _prefetch_audio(self):
        """
        Record audio during the robot's speech window.
        Returns numpy audio array or None (same contract as record_audio).
        Stops early if speech ends.
        """
        time.sleep(0.2)

        audio, silence, started, elapsed = [], 0, False, 0

        while elapsed < MAX_RECORDING:
            if not pygame.mixer.music.get_busy() and elapsed > 0.5:
                break

            chunk = sd.rec(
                int(CHUNK_TIME * MIC_SR),
                samplerate=MIC_SR,
                channels=1,
                device=MIC_DEVICE,
                dtype="float32",
                blocking=True
            ).flatten()

            amp = np.max(np.abs(chunk))
            audio.append(chunk)
            elapsed += CHUNK_TIME

            if amp > VAD_THRESHOLD:
                started, silence = True, 0
            elif started:
                silence += CHUNK_TIME

            if started and silence >= SILENCE_TIME:
                break

        if started and len(audio) > 0:
            dprint("✓ Pre-recorded speech ready.")
            return np.concatenate(audio)
        return None

# ---------------- MAIN ----------------
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("AI Nestham – Telugu + English")

    vr = VoiceRobot(screen)
    clock = pygame.time.Clock()

    print("Press T to Talk | F for Face Detection | ESC to Exit")

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_t:
                    vr.talk()
                elif e.key == pygame.K_f:
                    # Face detection with funny comment (run in thread to avoid blocking)
                    if not vr.busy:
                        print("🔍 Starting face detection...")
                        vr.robot.set_expression("excited")
                        threading.Thread(target=vr.face_detection_with_comment, daemon=True).start()
                    else:
                        print("⏳ Please wait, I'm busy right now!")
                elif e.key == pygame.K_ESCAPE:
                    running = False

        vr.robot.update()
        
        screen.fill((255, 255, 255))
        vr.robot.draw_face()
        pygame.display.flip()
        clock.tick(FPS)

    vr.close_camera()
    pygame.quit()

if __name__ == "__main__":
    main()
