"""
AR Sticker Overlay — Kids Face Filter
======================================
Raspberry Pi 4B optimised | Only needs: opencv-python, numpy
No dlib, no landmarks — pure Haar cascade bounding box

Sticker placement uses smart anchor points derived from the face box:
  HEAD_TOP   → crown, wizard hat, santa hat, birthday hat, cat ears
  EYE_LINE   → sunglasses, superhero mask, rainbow band

Features:
  - 8 stickers loaded from ./stickers/*.png (RGBA)
  - Fallback stickers generated with numpy if PNG missing
  - Smooth alpha blending with boundary clamping (safe at edges)
  - Box smoothing over N frames to reduce jitter
  - Keyboard switching: LEFT / RIGHT arrows cycle stickers
  - Reward unlock system — stickers unlock after N correct answers
  - Standalone demo mode OR importable class for voice_robot.py

Controls (standalone):
  ← →   cycle stickers
  + / - unlock points (demo)
  S     screenshot
  H     toggle HUD
  Q/ESC quit
"""

from __future__ import annotations

import os
import sys
import time
import threading
from collections import deque

import cv2
import numpy as np


# ─────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0
FRAME_W = 640
FRAME_H = 480
TARGET_FPS = 20
FRAME_SKIP = 2  # detect face every N frames
SMOOTH_FRAMES = 6  # box smoothing window (reduces jitter)

STICKER_DIR = os.path.join(os.path.dirname(__file__), "stickers")

# Sticker catalogue ─────────────────────────────────────────────
#  anchor:  "head_top" | "eye_line" | "chin"
#  x_scale: sticker width = face_w * x_scale
#  y_offset: vertical shift as fraction of face_h (negative = upward)
#  x_offset: horizontal shift as fraction of face_w
STICKER_CATALOG = [
    {
        "name": "Crown",
        "file": "crown.png",
        "anchor": "head_top",
        "x_scale": 1.3,
        "y_offset": -0.52,
        "x_offset": -0.15,
        "unlock": 0,
    },
    {
        "name": "Wizard Hat",
        "file": "wizard_hat.png",
        "anchor": "head_top",
        "x_scale": 0.85,
        "y_offset": -1.15,
        "x_offset": 0.075,
        "unlock": 0,
    },
    {
        "name": "Sunglasses",
        "file": "sunglasses.png",
        "anchor": "eye_line",
        "x_scale": 1.10,
        "y_offset": -0.08,
        "x_offset": -0.05,
        "unlock": 0,
    },
    {
        "name": "Rainbow Band",
        "file": "rainbow_band.png",
        "anchor": "head_top",
        "x_scale": 1.05,
        "y_offset": -0.18,
        "x_offset": -0.025,
        "unlock": 0,
    },
    {
        "name": "Cat Ears",
        "file": "cat_ears.png",
        "anchor": "head_top",
        "x_scale": 1.1,
        "y_offset": -0.42,
        "x_offset": -0.05,
        "unlock": 0,
    },
    {
        "name": "Superhero Mask",
        "file": "superhero_mask.png",
        "anchor": "eye_line",
        "x_scale": 1.15,
        "y_offset": -0.10,
        "x_offset": -0.075,
        "unlock": 3,
    },
    {
        "name": "Santa Hat",
        "file": "santa_hat.png",
        "anchor": "head_top",
        "x_scale": 0.80,
        "y_offset": -1.05,
        "x_offset": 0.10,
        "unlock": 5,
    },
    {
        "name": "Birthday Hat",
        "file": "birthday_hat.png",
        "anchor": "head_top",
        "x_scale": 0.70,
        "y_offset": -0.95,
        "x_offset": 0.15,
        "unlock": 8,
    },
]


# ══════════════════════════════════════════════════════════════════
#  STICKER LOADER
# ══════════════════════════════════════════════════════════════════
class StickerLoader:
    """Loads PNG stickers (RGBA). Falls back to a generated sticker."""

    @staticmethod
    def load(filepath: str) -> np.ndarray | None:
        if os.path.exists(filepath):
            img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
            if img is not None:
                if img.ndim == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
                elif img.shape[2] == 3:
                    alpha = np.full((*img.shape[:2], 1), 255, dtype=np.uint8)
                    img = np.concatenate([img, alpha], axis=2)
                return img

        print(f"  ⚠ Missing sticker: {filepath} — using fallback")
        return StickerLoader._fallback(os.path.splitext(os.path.basename(filepath))[0])

    @staticmethod
    def _fallback(name: str) -> np.ndarray:
        h, w = 120, 240
        img = np.zeros((h, w, 4), dtype=np.uint8)
        img[:, :, 0] = 80
        img[:, :, 1] = 180
        img[:, :, 2] = 255
        img[:, :, 3] = 200
        cv2.rectangle(img, (4, 4), (w - 5, h - 5), (255, 255, 255, 200), 2)
        cv2.putText(img, name[:12], (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0, 255), 2, cv2.LINE_AA)
        return img


# ══════════════════════════════════════════════════════════════════
#  ALPHA BLEND HELPER
# ══════════════════════════════════════════════════════════════════
def alpha_blend(frame: np.ndarray, sticker: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """Alpha-blend a resized sticker onto frame at (x, y) with size (w, h). Safe at edges."""
    if w <= 0 or h <= 0:
        return frame

    fh, fw = frame.shape[:2]

    try:
        st = cv2.resize(sticker, (w, h), interpolation=cv2.INTER_LINEAR)
    except Exception:
        return frame

    sx1, sy1, sx2, sy2 = 0, 0, w, h
    dx1, dy1, dx2, dy2 = x, y, x + w, y + h

    if dx1 < 0:
        sx1 -= dx1
        dx1 = 0
    if dy1 < 0:
        sy1 -= dy1
        dy1 = 0
    if dx2 > fw:
        sx2 -= (dx2 - fw)
        dx2 = fw
    if dy2 > fh:
        sy2 -= (dy2 - fh)
        dy2 = fh

    if dx2 <= dx1 or dy2 <= dy1:
        return frame

    roi = frame[dy1:dy2, dx1:dx2].astype(np.float32)
    stk_roi = st[sy1:sy2, sx1:sx2]

    if roi.shape[:2] != stk_roi.shape[:2]:
        return frame

    if stk_roi.shape[2] == 4:
        alpha = stk_roi[:, :, 3:4].astype(np.float32) / 255.0
        bgr = stk_roi[:, :, :3].astype(np.float32)
    else:
        alpha = np.ones((*stk_roi.shape[:2], 1), dtype=np.float32)
        bgr = stk_roi[:, :, :3].astype(np.float32)

    blended = bgr * alpha + roi * (1.0 - alpha)
    frame[dy1:dy2, dx1:dx2] = np.clip(blended, 0, 255).astype(np.uint8)
    return frame


# ══════════════════════════════════════════════════════════════════
#  AR STICKER ENGINE  (reusable class)
# ══════════════════════════════════════════════════════════════════
class ARStickerEngine:
    """Detects faces and overlays AR stickers in a background thread."""

    def __init__(self, camera_index: int = CAMERA_INDEX):
        self.camera_index = camera_index
        self.cap: cv2.VideoCapture | None = None
        self.cascade: cv2.CascadeClassifier | None = None

        self._stickers: list[np.ndarray | None] = []
        self._current_idx = 0
        self._score = 0

        self._box_x = deque(maxlen=SMOOTH_FRAMES)
        self._box_y = deque(maxlen=SMOOTH_FRAMES)
        self._box_w = deque(maxlen=SMOOTH_FRAMES)
        self._box_h = deque(maxlen=SMOOTH_FRAMES)

        self._face_box = None  # (x, y, w, h) smoothed
        self._frame_out: np.ndarray | None = None
        self._frame_raw: np.ndarray | None = None
        self._frame_cnt = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self._load_stickers()

    # ── public API ──────────────────────────────────────────────

    def start(self) -> bool:
        if self._running:
            return True
        if not self._init_camera():
            return False
        self._init_cascade()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("✓ ARStickerEngine started")
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        self.cap = None
        print("✓ ARStickerEngine stopped")

    def get_frame(self) -> np.ndarray | None:
        return self._frame_out

    def get_raw_frame(self) -> np.ndarray | None:
        return self._frame_raw

    def set_sticker(self, index: int) -> None:
        n = len(STICKER_CATALOG)
        with self._lock:
            self._current_idx = index % n

    def next_sticker(self) -> None:
        with self._lock:
            self._current_idx = (self._current_idx + 1) % len(STICKER_CATALOG)

    def prev_sticker(self) -> None:
        with self._lock:
            self._current_idx = (self._current_idx - 1) % len(STICKER_CATALOG)

    def get_sticker_name(self) -> str:
        return STICKER_CATALOG[self.get_sticker_index()]["name"]

    def get_sticker_index(self) -> int:
        with self._lock:
            return self._current_idx

    def unlock_sticker(self, score: int) -> None:
        with self._lock:
            self._score = score

    def get_unlocked_count(self) -> int:
        with self._lock:
            sc = self._score
        return sum(1 for s in STICKER_CATALOG if s["unlock"] <= sc)

    def is_face_detected(self) -> bool:
        return self._face_box is not None

    # ── internal ────────────────────────────────────────────────

    def _load_stickers(self) -> None:
        print("Loading stickers...")
        for entry in STICKER_CATALOG:
            path = os.path.join(STICKER_DIR, entry["file"])
            img = StickerLoader.load(path)
            self._stickers.append(img)
            status = "✓" if img is not None else "✗"
            print(f"  {status} {entry['name']}")
        print(f"  {len(self._stickers)} stickers ready")

    def _init_camera(self) -> bool:
        if sys.platform == "win32":
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            print(f"✗ Cannot open camera {self.camera_index}")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        self.cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        try:
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
        except Exception:
            pass

        print(f"✓ Camera {self.camera_index} opened  {FRAME_W}×{FRAME_H}@{TARGET_FPS}fps")
        return True

    def _init_cascade(self) -> None:
        # Prefer local cascade shipped in repo (same as your other scripts).
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
        while self._running and self.cap:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.03)
                continue

            self._frame_raw = frame.copy()
            self._frame_cnt += 1

            # Face detection every N frames (on downscaled frame for speed).
            if self._frame_cnt % FRAME_SKIP == 0 and self.cascade is not None:
                small = cv2.resize(frame, (320, 240))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = self.cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))

                if len(faces) > 0:
                    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                    sx = FRAME_W / 320
                    sy = FRAME_H / 240
                    self._box_x.append(int(fx * sx))
                    self._box_y.append(int(fy * sy))
                    self._box_w.append(int(fw * sx))
                    self._box_h.append(int(fh * sy))
                else:
                    self._box_x.clear()
                    self._box_y.clear()
                    self._box_w.clear()
                    self._box_h.clear()
                    self._face_box = None

            # Smoothed box.
            if self._box_x:
                self._face_box = (int(np.mean(self._box_x)), int(np.mean(self._box_y)), int(np.mean(self._box_w)), int(np.mean(self._box_h)))

            output = frame.copy()
            if self._face_box:
                output = self._apply_sticker(output, self._face_box)

            self._frame_out = output

    def _apply_sticker(self, frame: np.ndarray, face_box: tuple[int, int, int, int]) -> np.ndarray:
        idx = self.get_sticker_index()
        entry = STICKER_CATALOG[idx]

        with self._lock:
            score = self._score

        if entry["unlock"] > score:
            x, y, w, _h = face_box
            cv2.putText(
                frame,
                f"[Locked — need {entry['unlock']} pts]",
                (x, max(20, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 120, 255),
                1,
                cv2.LINE_AA,
            )
            return frame

        sticker = self._stickers[idx]
        if sticker is None:
            return frame

        x, y, w, h = face_box

        target_w = int(w * entry["x_scale"])
        sh_orig, sw_orig = sticker.shape[:2]
        aspect = sh_orig / max(sw_orig, 1)
        target_h = int(target_w * aspect)

        anchor = entry["anchor"]
        if anchor == "head_top":
            paste_x = x + int(w * entry["x_offset"])
            paste_y = y + int(h * entry["y_offset"])
        elif anchor == "eye_line":
            eye_y = y + int(h * 0.35)
            paste_x = x + int(w * entry["x_offset"])
            paste_y = eye_y + int(h * entry["y_offset"])
        elif anchor == "chin":
            paste_x = x + int(w * entry["x_offset"])
            paste_y = y + h + int(h * entry["y_offset"])
        else:
            paste_x, paste_y = x, y

        return alpha_blend(frame, sticker, paste_x, paste_y, target_w, target_h)


# ══════════════════════════════════════════════════════════════════
#  HUD
# ══════════════════════════════════════════════════════════════════
def draw_hud(frame: np.ndarray, engine: ARStickerEngine, score: int = 0, show_hud: bool = True) -> np.ndarray:
    if not show_hud:
        return frame

    fh, fw = frame.shape[:2]
    cur = engine.get_sticker_index()
    n = len(STICKER_CATALOG)

    # Bottom strip
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, fh - 70), (fw, fh), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    dot_spacing = fw // (n + 1)
    for i, s in enumerate(STICKER_CATALOG):
        cx = dot_spacing * (i + 1)
        cy = fh - 35
        locked = s["unlock"] > score
        if i == cur:
            col = (0, 220, 255)
            cv2.circle(frame, (cx, cy), 14, col, -1)
            cv2.circle(frame, (cx, cy), 16, col, 2)
            label = s["name"]
            lw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)[0][0]
            cv2.putText(frame, label, (cx - lw // 2, fh - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1, cv2.LINE_AA)
        elif locked:
            cv2.circle(frame, (cx, cy), 9, (80, 80, 80), -1)
            cv2.putText(frame, str(s["unlock"]), (cx - 5, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (160, 160, 160), 1, cv2.LINE_AA)
        else:
            cv2.circle(frame, (cx, cy), 9, (160, 160, 160), -1)

    # Top bar
    overlay2 = frame.copy()
    cv2.rectangle(overlay2, (0, 0), (fw, 38), (20, 20, 20), -1)
    cv2.addWeighted(overlay2, 0.6, frame, 0.4, 0, frame)

    cv2.putText(frame, f"AI BUDDY  |  {engine.get_sticker_name()}", (12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

    score_txt = f"Score: {score}  Unlocked: {engine.get_unlocked_count()}/{n}"
    sw = cv2.getTextSize(score_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0]
    cv2.putText(frame, score_txt, (fw - sw - 12, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 220, 255), 1, cv2.LINE_AA)

    hint = "Face detected" if engine.is_face_detected() else "No face — position yourself in frame"
    hcol = (0, 220, 80) if engine.is_face_detected() else (0, 140, 255)
    cv2.putText(frame, hint, (12, fh - 78), cv2.FONT_HERSHEY_SIMPLEX, 0.45, hcol, 1, cv2.LINE_AA)

    return frame


def main():
    print("=" * 55)
    print("  AR Sticker Overlay — AI BUDDY Kids Filter")
    print("  ← → arrows : cycle stickers")
    print("  + / -      : add/remove score points (unlock demo)")
    print("  S          : screenshot")
    print("  H          : toggle HUD")
    print("  Q/ESC      : quit")
    print("=" * 55)

    engine = ARStickerEngine(camera_index=CAMERA_INDEX)
    if not engine.start():
        print("✗ Failed to start. Check camera connection.")
        return

    win = "AI BUDDY — AR Stickers"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, FRAME_W, FRAME_H)

    score = 0
    show_hud = True
    shot_n = 0

    try:
        while True:
            frame = engine.get_frame()
            if frame is None:
                time.sleep(0.02)
                continue

            engine.unlock_sticker(score)
            display = draw_hud(frame.copy(), engine, score, show_hud)
            cv2.imshow(win, display)

            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                break
            # Arrow keys (OpenCV codes), plus A/D fallback.
            if key in (81, ord("a")):
                engine.prev_sticker()
            elif key in (83, ord("d")):
                engine.next_sticker()
            elif key in (ord("+"), ord("=")):
                score += 1
                print(f"Score: {score}  Unlocked: {engine.get_unlocked_count()}")
            elif key == ord("-"):
                score = max(0, score - 1)
                print(f"Score: {score}")
            elif key == ord("s"):
                fname = f"ar_shot_{shot_n:03d}.jpg"
                cv2.imwrite(fname, display)
                shot_n += 1
                print(f"✓ Screenshot saved: {fname}")
            elif key == ord("h"):
                show_hud = not show_hud

    finally:
        engine.stop()
        cv2.destroyAllWindows()
        print("Done.")


if __name__ == "__main__":
    main()

