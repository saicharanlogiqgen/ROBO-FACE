"""
Head Nod / Shake Detector — Kids Quiz Game
==========================================
Raspberry Pi 4B optimised | Only needs: opencv-python + numpy

No dlib, no landmarks, no ML model — pure centroid tracking

How it works:
  - Tracks face bounding box center (cx, cy) across frames
  - Rolling window of last N positions detects patterns
  - Horizontal oscillation  → HEAD SHAKE  → Answer: NO
  - Vertical oscillation    → HEAD NOD    → Answer: YES

Standalone:
  python3 head_gesture_quiz.py

Integration:
  from head_gesture_quiz import HeadGestureDetector
  detector = HeadGestureDetector()
  detector.start()
  gesture = detector.get_gesture()  # "YES" / "NO" / None
  detector.stop()
"""

from __future__ import annotations

import os
import sys
import time
import threading
from collections import deque

import cv2
import numpy as np


# ─────────────────────────────────────────
#  TUNING CONSTANTS  (adjust if needed)
# ─────────────────────────────────────────
CAMERA_INDEX = 0  # 0 = default Pi camera / USB cam

FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Camera capture target (best-effort). Processing is capped separately.
CAMERA_TARGET_FPS = 30

# Processing throttle (major CPU saver on Pi).
PROCESS_TARGET_FPS = 20

WINDOW_SIZE = 18  # frames in rolling history
MIN_OSCILLATIONS = 2  # direction reversals needed to confirm gesture
NOD_THRESHOLD = 28  # px vertical travel to count as a nod move
SHAKE_THRESHOLD = 38  # px horizontal travel to count as a shake move
GESTURE_COOLDOWN = 1.8  # seconds between accepted gestures
CONFIRM_HOLD = 0.4  # seconds gesture must persist before accepting

FACE_SCALE = 1.2  # detectMultiScale scaleFactor
FACE_NEIGHBORS = 5  # minNeighbors (higher = fewer false positives)
FRAME_SKIP = 2  # process every Nth frame (1 = every frame)

# Visual overlays (set to False for clean camera view)
DRAW_TRAIL = False  # the "tracking line" you mentioned

# Extra Pi saver: after first detection, search in an expanded ROI box.
# If ROI search fails, fall back to full-frame detection.
USE_ROI_TRACKING = True
ROI_EXPAND = 0.35  # expand last face box by this fraction each side


# ─────────────────────────────────────────
#  QUIZ DATA  (extend as needed)
# ─────────────────────────────────────────
QUIZ_QUESTIONS = [
    {"question": "Is the sky blue?", "answer": True},
    {"question": "Does a fish live on a tree?", "answer": False},
    {"question": "Do cats say MEOW?", "answer": True},
    {"question": "Is 2 + 2 equal to 5?", "answer": False},
    {"question": "Does the sun rise in the east?", "answer": True},
    {"question": "Do birds have wings?", "answer": True},
    {"question": "Is ice hot?", "answer": False},
    {"question": "Does a cow give milk?", "answer": True},
    {"question": "Do elephants fly?", "answer": False},
    {"question": "Is the moon a star?", "answer": False},
    {"question": "Do plants need sunlight?", "answer": True},
    {"question": "Is 10 bigger than 5?", "answer": True},
]

# ─────────────────────────────────────────
#  COLOURS  (BGR)
# ─────────────────────────────────────────
GREEN = (0, 210, 80)
RED = (0, 60, 220)
BLUE = (220, 120, 0)
YELLOW = (0, 200, 220)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (180, 180, 180)
ORANGE = (0, 140, 255)

UI_BG_DARK = (18, 18, 18)
UI_PANEL = (28, 28, 28)
UI_SHADOW = (0, 0, 0)
UI_ACCENT = (255, 170, 0)

# UI sizing (reduce "thick" look)
UI_TEXT_THICK = 2
UI_TEXT_THICK_BOLD = 2


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def _expand_box(x: int, y: int, w: int, h: int, frac: float, img_w: int, img_h: int):
    dx = int(w * frac)
    dy = int(h * frac)
    x2 = _clamp(x - dx, 0, img_w - 1)
    y2 = _clamp(y - dy, 0, img_h - 1)
    w2 = _clamp(w + 2 * dx, 1, img_w - x2)
    h2 = _clamp(h + 2 * dy, 1, img_h - y2)
    return x2, y2, w2, h2


def _draw_panel(frame, x1: int, y1: int, x2: int, y2: int, *, fill, shadow: bool = True, shadow_offset: int = 6):
    """Fast 'card' panel with a simple drop shadow (rectangles only for speed)."""
    if shadow:
        cv2.rectangle(frame, (x1 + shadow_offset, y1 + shadow_offset), (x2 + shadow_offset, y2 + shadow_offset), UI_SHADOW, -1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), fill, -1)


def _draw_pill(frame, x: int, y: int, text: str, *, bg, fg=WHITE):
    """Simple status pill (rounded-ish using 2 circles + rect)."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    pad_x, pad_y = 9, 6
    w = tw + pad_x * 2
    h = th + pad_y * 2
    r = h // 2
    # left/right caps
    cv2.circle(frame, (x + r, y + r), r, bg, -1)
    cv2.circle(frame, (x + w - r, y + r), r, bg, -1)
    cv2.rectangle(frame, (x + r, y), (x + w - r, y + h), bg, -1)
    cv2.putText(frame, text, (x + pad_x, y + h - pad_y), font, scale, fg, thickness, cv2.LINE_AA)
    return w, h


# ══════════════════════════════════════════
#  HEAD GESTURE DETECTOR  (reusable class)
# ══════════════════════════════════════════
class HeadGestureDetector:
    """
    Detects YES (nod) and NO (shake) from face centroid movement.
    """

    def __init__(
        self,
        camera_index: int = CAMERA_INDEX,
        *,
        frame_width: int = FRAME_WIDTH,
        frame_height: int = FRAME_HEIGHT,
    ):
        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height

        self.cap: cv2.VideoCapture | None = None
        self.cascade: cv2.CascadeClassifier | None = None

        # State
        self.cx_history = deque(maxlen=WINDOW_SIZE)
        self.cy_history = deque(maxlen=WINDOW_SIZE)
        self.ts_history = deque(maxlen=WINDOW_SIZE)  # timestamps

        self._gesture = None  # latest confirmed gesture
        self._pending_gesture = None  # gesture being held / confirmed
        self._pending_since = 0.0
        self._last_accepted = 0.0
        self._face_box = None  # (x, y, w, h) latest face box in FULL frame coords
        self._frame_count = 0
        self._lock = threading.Lock()

        # Running state
        self._running = False
        self._thread: threading.Thread | None = None
        self._frame_out = None  # latest frame for display

    # ── public API ────────────────────────

    def start(self) -> bool:
        """Start background detection thread."""
        if self._running:
            return True
        if not self._init_camera():
            return False
        self._init_cascade()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("✓ HeadGestureDetector started")
        return True

    def stop(self) -> None:
        """Stop detection and release camera."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        self.cap = None
        print("✓ HeadGestureDetector stopped")

    def get_gesture(self, consume: bool = True):
        """
        Returns the latest confirmed gesture ("YES" / "NO" / None).
        If consume=True (default), clears the gesture after reading.
        """
        with self._lock:
            g = self._gesture
            if consume:
                self._gesture = None
            return g

    def get_frame(self):
        """Returns the latest annotated frame (for display)."""
        return self._frame_out

    def get_face_box(self):
        """Returns (x, y, w, h) of latest detected face or None."""
        return self._face_box

    # ── internal ──────────────────────────

    def _init_camera(self) -> bool:
        # On Windows, DirectShow avoids some webcam stalls with GUI windows.
        if sys.platform == "win32":
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"✗ Cannot open camera {self.camera_index}")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.cap.set(cv2.CAP_PROP_FPS, CAMERA_TARGET_FPS)

        # Helps reduce latency on some backends.
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        # Disable autofocus for stable frame rate on Pi (best-effort).
        try:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        except Exception:
            pass

        return True

    def _init_cascade(self) -> None:
        # Prefer local cascade if present (your repo already has it).
        local = "haarcascade_frontalface_default.xml"
        if os.path.exists(local):
            path = local
        else:
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

        self.cascade = cv2.CascadeClassifier(path)
        if self.cascade.empty():
            raise RuntimeError(f"Cannot load cascade: {path}")
        print(f"✓ Haar cascade loaded ({path})")

    def _loop(self) -> None:
        """Main detection loop — runs in background thread."""
        last_proc = 0.0
        proc_period = 1.0 / max(PROCESS_TARGET_FPS, 1)

        while self._running and self.cap:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.02)
                continue

            now = time.time()

            # Throttle processing to reduce CPU.
            if now - last_proc < proc_period:
                # Still update annotated output to keep UI smooth-ish.
                self._frame_out = self._annotate(frame.copy())
                continue
            last_proc = now

            self._frame_count += 1

            # ── Detect face every Nth processed frame ──
            if self._frame_count % FRAME_SKIP == 0:
                self._detect_and_update(frame, now)

            self._frame_out = self._annotate(frame.copy())

    def _detect_and_update(self, frame, now: float) -> None:
        if self.cascade is None:
            return

        fh, fw = frame.shape[:2]

        # ROI search first (cheaper) when we have a recent face box.
        roi = None
        roi_offset = (0, 0)
        if USE_ROI_TRACKING and self._face_box is not None:
            x, y, w, h = self._face_box
            rx, ry, rw, rh = _expand_box(x, y, w, h, ROI_EXPAND, fw, fh)
            roi = frame[ry : ry + rh, rx : rx + rw]
            roi_offset = (rx, ry)

        faces = []
        if roi is not None and roi.size:
            faces = self._detect_faces_in_image(roi)
            # Convert ROI coords back to full coords
            if faces:
                ox, oy = roi_offset
                faces = [(x + ox, y + oy, w, h) for (x, y, w, h) in faces]

        # Fallback to full frame if ROI failed.
        if not faces:
            faces = self._detect_faces_in_image(frame)

        if not faces:
            return

        # Use largest face.
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]

        cx = x + w // 2
        cy = y + h // 2

        self.cx_history.append(cx)
        self.cy_history.append(cy)
        self.ts_history.append(now)
        self._face_box = (x, y, w, h)

        gesture = self._analyse_gesture()
        self._update_gesture(gesture)

    def _detect_faces_in_image(self, img):
        """
        Detect faces in an image using downscaled grayscale to save CPU.
        Returns list of (x, y, w, h) in ORIGINAL img coordinates.
        """
        ih, iw = img.shape[:2]

        # Downscale to ~320x240 for speed (keep aspect).
        target_w = 320
        scale = target_w / float(iw) if iw > target_w else 1.0
        small = cv2.resize(img, (int(iw * scale), int(ih * scale))) if scale != 1.0 else img

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        faces = self.cascade.detectMultiScale(
            gray,
            scaleFactor=FACE_SCALE,
            minNeighbors=FACE_NEIGHBORS,
            minSize=(40, 40),
        )

        if len(faces) == 0:
            return []

        # Scale coords back to original img space.
        if scale != 1.0:
            inv = 1.0 / scale
            out = []
            for (x, y, w, h) in faces:
                out.append((int(x * inv), int(y * inv), int(w * inv), int(h * inv)))
            return out

        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def _analyse_gesture(self):
        """
        Counts direction reversals in cx (shake) and cy (nod) histories.
        Returns "YES", "NO", or None.
        """
        if len(self.cx_history) < max(3, WINDOW_SIZE // 2):
            return None

        cx_list = list(self.cx_history)
        cy_list = list(self.cy_history)

        h_osc = self._count_oscillations(cx_list, SHAKE_THRESHOLD)
        v_osc = self._count_oscillations(cy_list, NOD_THRESHOLD)

        if h_osc >= MIN_OSCILLATIONS and h_osc > v_osc:
            return "NO"
        if v_osc >= MIN_OSCILLATIONS and v_osc > h_osc:
            return "YES"
        return None

    @staticmethod
    def _count_oscillations(values, threshold: int) -> int:
        """
        Count how many times the signal reverses direction by >= threshold px.
        e.g. [300, 340, 290, 345, 295]  →  3 reversals  (solid head shake)
        """
        if len(values) < 3:
            return 0

        direction = 0  # +1 = moving right/down, -1 = moving left/up
        reversals = 0
        last_turn = values[0]

        for v in values[1:]:
            delta = v - last_turn
            if abs(delta) < threshold:
                continue
            new_dir = 1 if delta > 0 else -1
            if direction != 0 and new_dir != direction:
                reversals += 1
            direction = new_dir
            last_turn = v

        return reversals

    def _update_gesture(self, gesture) -> None:
        """
        Requires a gesture to persist for CONFIRM_HOLD seconds before accepting.
        Enforces GESTURE_COOLDOWN between gestures.
        """
        now = time.time()

        if gesture is None:
            self._pending_gesture = None
            self._pending_since = 0.0
            return

        # New pending gesture.
        if gesture != self._pending_gesture:
            self._pending_gesture = gesture
            self._pending_since = now
            return

        # Gesture persisted long enough?
        if (now - self._pending_since) >= CONFIRM_HOLD:
            # Cooldown elapsed?
            if (now - self._last_accepted) >= GESTURE_COOLDOWN:
                with self._lock:
                    self._gesture = gesture
                self._last_accepted = now
                self._pending_gesture = None
                # Clear history to avoid re-triggering.
                self.cx_history.clear()
                self.cy_history.clear()
                self.ts_history.clear()

    def _annotate(self, frame):
        """Draw face box, centroid trail, and gesture label onto frame."""
        h, w = frame.shape[:2]

        # Face box.
        if self._face_box:
            x, y, bw, bh = self._face_box
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), BLUE, 2)

            # Centroid dot.
            if self.cx_history:
                cx = self.cx_history[-1]
                cy = self.cy_history[-1]
                cv2.circle(frame, (cx, cy), 5, YELLOW, -1)

        # Centroid trail (last 10 points).
        if DRAW_TRAIL:
            pts_cx = list(self.cx_history)[-10:]
            pts_cy = list(self.cy_history)[-10:]
            for i in range(1, len(pts_cx)):
                alpha = i / max(len(pts_cx), 1)
                c = (int(220 * alpha), int(180 * alpha), 0)
                cv2.line(frame, (pts_cx[i - 1], pts_cy[i - 1]), (pts_cx[i], pts_cy[i]), c, 2)

        # Pending gesture indicator.
        if self._pending_gesture:
            elapsed = time.time() - self._pending_since
            progress = min(elapsed / CONFIRM_HOLD, 1.0)
            bar_w = int(200 * progress)
            color = GREEN if self._pending_gesture == "YES" else RED
            cv2.rectangle(frame, (20, h - 30), (20 + bar_w, h - 10), color, -1)
            cv2.putText(
                frame,
                f"Detecting: {self._pending_gesture}",
                (20, h - 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        return frame


# ══════════════════════════════════════════
#  QUIZ GAME  (standalone runner)
# ══════════════════════════════════════════
class QuizGame:
    """Simple yes/no quiz driven entirely by head gestures."""

    def __init__(self):
        self.detector = HeadGestureDetector()
        self.questions = QUIZ_QUESTIONS.copy()
        self.q_index = 0
        self.score = 0
        self.total = 0
        self.feedback = ""
        self.feedback_color = WHITE
        self.feedback_until = 0.0
        self.waiting = True  # waiting for gesture
        self._shuffle_questions()

    def _shuffle_questions(self):
        import random

        random.shuffle(self.questions)

    def current_question(self):
        if self.q_index < len(self.questions):
            return self.questions[self.q_index]
        return None

    def answer(self, gesture: str) -> None:
        """Process a YES/NO gesture answer."""
        q = self.current_question()
        if q is None or not self.waiting:
            return

        self.waiting = False
        self.total += 1
        correct = (gesture == "YES") == q["answer"]

        if correct:
            self.score += 1
            self.feedback = "CORRECT!  Well done!"
            self.feedback_color = GREEN
        else:
            expected = "YES" if q["answer"] else "NO"
            self.feedback = f"Oops! Answer was {expected}"
            self.feedback_color = RED

        self.feedback_until = time.time() + 2.2
        threading.Timer(2.2, self._next_question).start()

    def _next_question(self) -> None:
        self.q_index += 1
        if self.q_index >= len(self.questions):
            self.q_index = 0
            self._shuffle_questions()
        self.waiting = True

    def draw(self, frame):
        """Overlay all quiz UI onto frame."""
        h, w = frame.shape[:2]

        # Header (decorated).
        header_h = 78
        cv2.rectangle(frame, (0, 0), (w, header_h), UI_BG_DARK, -1)
        cv2.line(frame, (0, header_h - 1), (w, header_h - 1), (45, 45, 45), 2)

        # Title + subtitle.
        cv2.putText(frame, "AI BUDDY", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.92, UI_ACCENT, UI_TEXT_THICK_BOLD, cv2.LINE_AA)
        cv2.putText(frame, "Head Gesture Quiz", (16, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.62, WHITE, UI_TEXT_THICK, cv2.LINE_AA)

        # Score block (right).
        score_panel_w = 270
        sx1, sy1 = w - score_panel_w - 16, 12
        sx2, sy2 = w - 16, header_h - 12
        _draw_panel(frame, sx1, sy1, sx2, sy2, fill=UI_PANEL, shadow=False)

        score_txt = f"{self.score} / {self.total}"
        cv2.putText(frame, "SCORE", (sx1 + 14, sy1 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GRAY, 1, cv2.LINE_AA)
        cv2.putText(frame, score_txt, (sx1 + 14, sy1 + 56), cv2.FONT_HERSHEY_SIMPLEX, 0.92, YELLOW, UI_TEXT_THICK_BOLD, cv2.LINE_AA)

        pct = int(100 * self.score / self.total) if self.total else 0
        _draw_pill(frame, sx2 - 92, sy1 + 14, f"{pct}%", bg=(60, 60, 60), fg=WHITE)

        # Progress bar under header.
        bar_x1, bar_x2 = 16, w - 16
        bar_y1, bar_y2 = header_h + 8, header_h + 18
        cv2.rectangle(frame, (bar_x1, bar_y1), (bar_x2, bar_y2), (40, 40, 40), -1)
        prog = (self.total and (self.score / max(self.total, 1))) or 0.0
        fill_w = int((bar_x2 - bar_x1) * prog)
        if fill_w > 0:
            cv2.rectangle(frame, (bar_x1, bar_y1), (bar_x1 + fill_w, bar_y2), GREEN, -1)

        # Question box.
        q = self.current_question()
        if q:
            # Question "card"
            card_x1, card_x2 = 16, w - 16
            card_y2 = h - 18
            card_y1 = h - 178
            _draw_panel(frame, card_x1, card_y1, card_x2, card_y2, fill=UI_PANEL, shadow=True, shadow_offset=7)

            # Question number (based on shuffled list)
            qno = (self.q_index + 1)
            cv2.putText(frame, f"QUESTION {qno}", (card_x1 + 18, card_y1 + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, GRAY, 1, cv2.LINE_AA)

            q_text = q["question"]
            lines = self._wrap_text(q_text, 44)
            y0 = card_y1 + 70
            for line in lines[:3]:
                cv2.putText(frame, line, (card_x1 + 18, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.78, WHITE, UI_TEXT_THICK, cv2.LINE_AA)
                y0 += 32

            # Status pill + hint.
            if self.waiting:
                _draw_pill(frame, card_x1 + 18, card_y2 - 48, "Waiting: NOD = YES, SHAKE = NO", bg=(55, 55, 55), fg=WHITE)
            else:
                _draw_pill(frame, card_x1 + 18, card_y2 - 48, "Checking your answer...", bg=(50, 50, 80), fg=WHITE)

        # Feedback overlay.
        if time.time() < self.feedback_until:
            overlay = frame.copy()
            # Dim background + draw centered banner "card"
            cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

            banner_w = min(560, w - 60)
            banner_h = 104
            bx1 = (w - banner_w) // 2
            by1 = (h - banner_h) // 2
            bx2 = bx1 + banner_w
            by2 = by1 + banner_h
            _draw_panel(frame, bx1, by1, bx2, by2, fill=(25, 25, 25), shadow=True, shadow_offset=8)

            txt_size = cv2.getTextSize(self.feedback, cv2.FONT_HERSHEY_SIMPLEX, 0.95, UI_TEXT_THICK_BOLD)[0]
            tx = (w - txt_size[0]) // 2
            cv2.putText(
                frame,
                self.feedback,
                (tx, by1 + 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.95,
                self.feedback_color,
                UI_TEXT_THICK_BOLD,
                cv2.LINE_AA,
            )

        # Gesture hint icons.
        # Keep hints, but move them to the left side and make them smaller.
        self._draw_arrow(frame, (90, header_h + 110), "down", GREEN, "YES = NOD")
        self._draw_arrow(frame, (90, header_h + 190), "side", RED, "NO = SHAKE")

        return frame

    # ── helpers ───────────────────────────

    @staticmethod
    def _wrap_text(text: str, max_chars: int):
        words = text.split()
        lines = []
        line = ""
        for word in words:
            if len(line) + len(word) + (1 if line else 0) <= max_chars:
                line += ("" if not line else " ") + word
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    @staticmethod
    def _draw_arrow(frame, pos, direction: str, color, label: str):
        x, y = pos
        if direction == "down":
            pts = np.array(
                [[x, y - 20], [x + 12, y], [x + 5, y], [x + 5, y + 20], [x - 5, y + 20], [x - 5, y], [x - 12, y]],
                np.int32,
            )
            cv2.fillPoly(frame, [pts], color)
            cv2.putText(frame, label, (x - 45, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            return

        # side (left + right)
        pts_l = np.array(
            [[x - 25, y], [x - 10, y - 10], [x - 10, y - 4], [x + 10, y - 4], [x + 10, y + 4], [x - 10, y + 4], [x - 10, y + 10]],
            np.int32,
        )
        pts_r = np.array(
            [[x + 30, y], [x + 15, y - 10], [x + 15, y - 4], [x - 5, y - 4], [x - 5, y + 4], [x + 15, y + 4], [x + 15, y + 10]],
            np.int32,
        )
        cv2.fillPoly(frame, [pts_l], color)
        cv2.fillPoly(frame, [pts_r], color)
        cv2.putText(frame, label, (x - 45, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def main():
    print("=" * 55)
    print("  Head Gesture Quiz — Raspberry Pi")
    print("  NOD your head = YES   |   SHAKE = NO")
    print("  Q = quit  |  N = next question  |  R = reset")
    print("=" * 55)

    game = QuizGame()
    if not game.detector.start():
        print("✗ Could not start camera. Check connection.")
        return

    win = "AI BUDDY — Quiz"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, FRAME_WIDTH, FRAME_HEIGHT)

    try:
        while True:
            frame = game.detector.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            gesture = game.detector.get_gesture()
            if gesture and game.waiting:
                game.answer(gesture)

            frame = game.draw(frame)
            cv2.imshow(win, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("n"):
                game._next_question()
            if key == ord("r"):
                game.score = 0
                game.total = 0
                game.q_index = 0
                game._shuffle_questions()

    finally:
        game.detector.stop()
        cv2.destroyAllWindows()
        print(f"\nFinal Score: {game.score} / {game.total}")


if __name__ == "__main__":
    main()

