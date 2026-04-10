"""
Face Recognition and Emotion Detection Module for Raspberry Pi
- Detects faces using OpenCV
- Recognizes emotions using FER (Facial Expression Recognition)
- Stores recognized faces for future recognition
- Optimized for Raspberry Pi performance
"""

import cv2
import numpy as np
import pickle
import os
import threading
import time
from collections import deque

try:
    from fer import FER
    FER_AVAILABLE = True
except ImportError:
    FER_AVAILABLE = False
    print("FER library not available. Install with: pip install fer")


class FaceRecognitionEmotion:
    def __init__(self, camera_index=0, face_db_path="faces_db.pkl"):
        """
        Initialize face recognition and emotion detection
        
        Args:
            camera_index: Camera index (0 for default camera)
            face_db_path: Path to store recognized faces database
        """
        self.camera_index = camera_index
        self.face_db_path = face_db_path
        self.cap = None
        self.face_cascade = None
        self.emotion_detector = None
        self.known_faces = {}  # Dictionary: {face_id: {"name": str, "encoding": np.array}}
        self.next_face_id = 1
        
        # Current detection state
        self.current_face_detected = False
        self.current_emotion = None
        self.current_face_id = None
        self.current_face_name = None
        self.last_detection_time = 0
        self.detection_confidence = 0.0
        
        # Threading
        self.detection_thread = None
        self.is_running = False
        self.lock = threading.Lock()
        
        # Emotion history for smoother detection
        self.emotion_history = deque(maxlen=10)
        
        # Load face database
        self.load_face_database()
        
        # Initialize OpenCV face detector
        self._init_face_detector()
        
        # Initialize emotion detector
        if FER_AVAILABLE:
            self._init_emotion_detector()
        else:
            print("⚠ FER not available. Emotion detection will be disabled.")
    
    def _init_face_detector(self):
        """Initialize OpenCV face detector"""
        try:
            # Try to load Haar cascade (lightweight, works well on Pi)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty():
                raise Exception("Could not load face cascade")
            print("✓ Face detector initialized")
        except Exception as e:
            print(f"✗ Error initializing face detector: {e}")
            self.face_cascade = None
    
    def _init_emotion_detector(self):
        """Initialize FER emotion detector"""
        try:
            # FER uses a lightweight model optimized for edge devices
            self.emotion_detector = FER(mtcnn=False)  # mtcnn=False for better Pi performance
            print("✓ Emotion detector initialized")
        except Exception as e:
            print(f"✗ Error initializing emotion detector: {e}")
            self.emotion_detector = None
    
    def load_face_database(self):
        """Load recognized faces from database"""
        if os.path.exists(self.face_db_path):
            try:
                with open(self.face_db_path, 'rb') as f:
                    data = pickle.load(f)
                    self.known_faces = data.get('faces', {})
                    self.next_face_id = data.get('next_id', 1)
                print(f"✓ Loaded {len(self.known_faces)} recognized faces")
            except Exception as e:
                print(f"✗ Error loading face database: {e}")
                self.known_faces = {}
                self.next_face_id = 1
        else:
            print("No face database found. Starting fresh.")
    
    def save_face_database(self):
        """Save recognized faces to database"""
        try:
            with open(self.face_db_path, 'wb') as f:
                pickle.dump({
                    'faces': self.known_faces,
                    'next_id': self.next_face_id
                }, f)
            print(f"✓ Saved {len(self.known_faces)} faces to database")
        except Exception as e:
            print(f"✗ Error saving face database: {e}")
    
    def register_face(self, name, face_image):
        """
        Register a new face
        
        Args:
            name: Name to associate with the face
            face_image: Cropped face image (numpy array)
        """
        if face_image is None or face_image.size == 0:
            return False
        
        try:
            # Create a simple encoding (resize and flatten for simplicity)
            # For production, you might want to use face_recognition library
            face_resized = cv2.resize(face_image, (128, 128))
            face_encoding = face_resized.flatten()
            
            face_id = self.next_face_id
            self.known_faces[face_id] = {
                'name': name,
                'encoding': face_encoding,
                'image': face_resized
            }
            self.next_face_id += 1
            
            self.save_face_database()
            print(f"✓ Registered face: {name} (ID: {face_id})")
            return True
        except Exception as e:
            print(f"✗ Error registering face: {e}")
            return False
    
    def recognize_face(self, face_image):
        """
        Recognize a face from the database
        
        Args:
            face_image: Cropped face image (numpy array)
            
        Returns:
            (face_id, name, confidence) or (None, None, 0.0)
        """
        if face_image is None or face_image.size == 0 or len(self.known_faces) == 0:
            return None, None, 0.0
        
        try:
            # Resize face for comparison
            face_resized = cv2.resize(face_image, (128, 128))
            face_encoding = face_resized.flatten()
            
            best_match_id = None
            best_confidence = 0.0
            
            # Simple distance-based matching
            for face_id, face_data in self.known_faces.items():
                stored_encoding = face_data['encoding']
                
                # Calculate cosine similarity (normalized)
                dot_product = np.dot(face_encoding, stored_encoding)
                norm_a = np.linalg.norm(face_encoding)
                norm_b = np.linalg.norm(stored_encoding)
                
                if norm_a > 0 and norm_b > 0:
                    similarity = dot_product / (norm_a * norm_b)
                    if similarity > best_confidence:
                        best_confidence = similarity
                        best_match_id = face_id
            
            # Threshold for recognition (adjust as needed)
            if best_confidence > 0.7:  # 70% similarity threshold
                name = self.known_faces[best_match_id]['name']
                return best_match_id, name, best_confidence
            
            return None, None, 0.0
        except Exception as e:
            print(f"✗ Error recognizing face: {e}")
            return None, None, 0.0
    
    def detect_emotion(self, face_image):
        """
        Detect emotion from face image
        
        Args:
            face_image: Cropped face image (numpy array)
            
        Returns:
            Dictionary with emotion probabilities or None
        """
        if self.emotion_detector is None or face_image is None:
            return None
        
        try:
            # FER expects RGB image
            if len(face_image.shape) == 2:
                face_rgb = cv2.cvtColor(face_image, cv2.COLOR_GRAY2RGB)
            else:
                face_rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            
            # Detect emotions
            emotions = self.emotion_detector.detect_emotions(face_rgb)
            
            if emotions and len(emotions) > 0:
                # Get the first face's emotions
                emotion_data = emotions[0]['emotions']
                
                # Get dominant emotion
                dominant_emotion = max(emotion_data.items(), key=lambda x: x[1])
                
                return {
                    'emotions': emotion_data,
                    'dominant': dominant_emotion[0],
                    'confidence': dominant_emotion[1]
                }
            
            return None
        except Exception as e:
            # Silently handle errors to avoid spam
            return None
    
    def start_detection(self):
        """Start continuous face and emotion detection"""
        if self.is_running:
            return
        
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                print(f"✗ Could not open camera {self.camera_index}")
                return False
            
            # Set camera properties for better performance on Pi
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 15)  # Lower FPS for Pi
            
            self.is_running = True
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()
            print("✓ Face detection started")
            return True
        except Exception as e:
            print(f"✗ Error starting detection: {e}")
            return False
    
    def stop_detection(self):
        """Stop face and emotion detection"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        if self.detection_thread:
            self.detection_thread.join(timeout=2.0)
        print("✓ Face detection stopped")
    
    def _detection_loop(self):
        """Main detection loop (runs in separate thread)"""
        frame_skip = 2  # Process every Nth frame for better performance
        frame_count = 0
        
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                if frame_count % frame_skip != 0:
                    continue  # Skip frames for performance
                
                # Convert to grayscale for face detection (faster)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(50, 50)
                )
                
                with self.lock:
                    if len(faces) > 0:
                        # Use the largest face
                        largest_face = max(faces, key=lambda x: x[2] * x[3])
                        x, y, w, h = largest_face
                        
                        # Extract face region
                        face_roi = gray[y:y+h, x:x+w]
                        
                        # Recognize face
                        face_id, face_name, confidence = self.recognize_face(face_roi)
                        
                        # Detect emotion (use color frame for better accuracy)
                        face_color = frame[y:y+h, x:x+w]
                        emotion_data = self.detect_emotion(face_color)
                        
                        # Update state
                        self.current_face_detected = True
                        self.current_face_id = face_id
                        self.current_face_name = face_name if face_name else "Unknown"
                        self.detection_confidence = confidence
                        self.last_detection_time = time.time()
                        
                        if emotion_data:
                            self.current_emotion = emotion_data['dominant']
                            self.emotion_history.append(emotion_data)
                        else:
                            self.current_emotion = None
                    else:
                        self.current_face_detected = False
                        self.current_emotion = None
                        self.current_face_id = None
                        self.current_face_name = None
                
                time.sleep(0.05)  # Small delay to prevent CPU overload
                
            except Exception as e:
                print(f"✗ Error in detection loop: {e}")
                time.sleep(0.1)
    
    def get_current_detection(self):
        """
        Get current face and emotion detection results
        
        Returns:
            Dictionary with detection results
        """
        with self.lock:
            # Get most common emotion from history
            dominant_emotion = None
            if self.emotion_history:
                emotion_counts = {}
                for emo_data in self.emotion_history:
                    dom = emo_data.get('dominant')
                    if dom:
                        emotion_counts[dom] = emotion_counts.get(dom, 0) + 1
                if emotion_counts:
                    dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0]
            
            return {
                'face_detected': self.current_face_detected,
                'face_id': self.current_face_id,
                'face_name': self.current_face_name,
                'emotion': dominant_emotion or self.current_emotion,
                'confidence': self.detection_confidence,
                'last_detection': self.last_detection_time
            }
    
    def get_smoothed_emotion(self):
        """Get smoothed emotion from history"""
        if not self.emotion_history:
            return None
        
        emotion_counts = {}
        for emo_data in self.emotion_history:
            dom = emo_data.get('dominant')
            conf = emo_data.get('confidence', 0)
            if dom:
                if dom not in emotion_counts:
                    emotion_counts[dom] = []
                emotion_counts[dom].append(conf)
        
        if not emotion_counts:
            return None
        
        # Get emotion with highest average confidence
        best_emotion = None
        best_avg_conf = 0
        
        for emotion, confidences in emotion_counts.items():
            avg_conf = sum(confidences) / len(confidences)
            if avg_conf > best_avg_conf:
                best_avg_conf = avg_conf
                best_emotion = emotion
        
        return best_emotion if best_avg_conf > 0.3 else None  # Minimum confidence threshold
    
    def capture_current_face(self):
        """
        Capture the current detected face for registration
        
        Returns:
            Face image (numpy array) or None
        """
        if not self.cap or not self.is_running:
            return None
        
        try:
            ret, frame = self.cap.read()
            if not ret:
                return None
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50)
            )
            
            if len(faces) > 0:
                # Get the largest face
                largest_face = max(faces, key=lambda x: x[2] * x[3])
                x, y, w, h = largest_face
                
                # Extract face region
                face_roi = gray[y:y+h, x:x+w]
                return face_roi
            
            return None
        except Exception as e:
            print(f"✗ Error capturing face: {e}")
            return None


def generate_cute_comment(emotion, face_name=None):
    """
    Generate cute comments based on detected emotion
    
    Args:
        emotion: Detected emotion (happy, sad, angry, surprise, fear, neutral, disgust)
        face_name: Name of the detected person (optional)
    
    Returns:
        Cute comment string
    """
    name_prefix = f"Hey {face_name}, " if face_name else ""
    
    comments = {
        'happy': [
            f"{name_prefix}You have such a beautiful smile! It makes me happy too!",
            f"{name_prefix}Your smile is so bright and cheerful!",
            f"{name_prefix}You look so happy! That's wonderful!",
            f"{name_prefix}I love seeing you smile like that!",
            f"{name_prefix}Your happy face is absolutely adorable!",
        ],
        'sad': [
            f"{name_prefix}Oh no, you look a bit sad. Would you like to talk?",
            f"{name_prefix}I'm here for you! Let's do something fun together!",
            f"{name_prefix}Don't worry, everything will be okay!",
            f"{name_prefix}Would you like a hug? I'm here to help!",
            f"{name_prefix}Let's turn that frown upside down together!",
        ],
        'angry': [
            f"{name_prefix}I see you're feeling upset. Let's take a deep breath together!",
            f"{name_prefix}It's okay to feel angry sometimes. Want to talk about it?",
            f"{name_prefix}Let's calm down together. I'm here to help!",
            f"{name_prefix}Take your time. I'm here whenever you're ready!",
        ],
        'surprise': [
            f"{name_prefix}Wow! You look surprised! Did something exciting happen?",
            f"{name_prefix}Your surprised expression is so cute!",
            f"{name_prefix}Something amazing must have happened!",
            f"{name_prefix}You have such an expressive face!",
        ],
        'fear': [
            f"{name_prefix}Don't worry, you're safe here with me!",
            f"{name_prefix}Everything is okay! I'm here to protect you!",
            f"{name_prefix}There's nothing to be afraid of!",
            f"{name_prefix}Let's be brave together!",
        ],
        'neutral': [
            f"{name_prefix}You look thoughtful today!",
            f"{name_prefix}Hello there! Nice to see you!",
            f"{name_prefix}You have such a calm and peaceful expression!",
            f"{name_prefix}Hi! How are you doing today?",
        ],
        'disgust': [
            f"{name_prefix}Oh, something doesn't seem right. Are you okay?",
            f"{name_prefix}Let's find something better to focus on!",
        ]
    }
    
    import random
    emotion_comments = comments.get(emotion, comments['neutral'])
    return random.choice(emotion_comments)

