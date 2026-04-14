"""
classroom_buddy.py
==================
Classroom-friendly activities using your existing building blocks:
  - Head gestures (NOD=YES, SHAKE=NO) as hands-free input
  - AR stickers as rewards (unlock as points increase)

Modes
-----
1) Quick Quiz (gesture answers)
2) Random Student Picker (SHAKE to shuffle, NOD to pick)
3) Sticker Free Play (manual cycle + points)

Run:
  python classroom_buddy.py

Keys:
  1 / 2 / 3 : switch mode
  A / D     : previous / next sticker
  R         : reset points
  Q / ESC   : quit
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass

import cv2

from head_gesture_quiz import HeadGestureDetector
from sticker import STICKER_CATALOG, StickerLoader, alpha_blend


FRAME_W = 640
FRAME_H = 480


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 210, 80)
RED = (0, 60, 220)
YELLOW = (0, 200, 220)
UI_BG = (16, 16, 16)


def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def _draw_scrim(frame, alpha: float = 0.55):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 0), -1)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def _pill(frame, x: int, y: int, text: str, bg=(60, 60, 60), fg=WHITE):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    pad_x, pad_y = 10, 6
    w = tw + 2 * pad_x
    h = th + 2 * pad_y
    r = h // 2
    cv2.circle(frame, (x + r, y + r), r, bg, -1)
    cv2.circle(frame, (x + w - r, y + r), r, bg, -1)
    cv2.rectangle(frame, (x + r, y), (x + w - r, y + h), bg, -1)
    cv2.putText(frame, text, (x + pad_x, y + h - pad_y), font, scale, fg, thickness, cv2.LINE_AA)


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
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


def _load_students(path: str) -> list[str]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            names = [ln.strip() for ln in f.readlines()]
        names = [n for n in names if n and not n.startswith("#")]
        if names:
            return names
    # fallback
    return ["Aarav", "Anaya", "Ishaan", "Meera", "Vihaan", "Zoya"]


def _load_questions(path: str):
    """
    Optional JSON file format:
      [
        {"question": "2+2=4?", "answer": true},
        {"question": "Fish can fly?", "answer": false}
      ]
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = []
        for item in data:
            q = str(item.get("question", "")).strip()
            a = bool(item.get("answer", False))
            if q:
                out.append({"question": q, "answer": a})
        return out or None
    except Exception:
        return None


@dataclass
class QuizState:
    questions: list[dict]
    idx: int = 0
    points: int = 0
    total: int = 0
    feedback: str = ""
    feedback_color: tuple[int, int, int] = WHITE
    feedback_until: float = 0.0
    waiting: bool = True

    def current(self):
        return self.questions[self.idx] if self.questions else None

    def next_q(self):
        if not self.questions:
            return
        self.idx = (self.idx + 1) % len(self.questions)
        self.waiting = True

    def answer(self, gesture: str):
        q = self.current()
        if not q or not self.waiting:
            return
        self.waiting = False
        self.total += 1
        correct = (gesture == "YES") == bool(q["answer"])
        if correct:
            self.points += 1
            self.feedback = "Correct! +1 point"
            self.feedback_color = GREEN
        else:
            expected = "YES" if q["answer"] else "NO"
            self.feedback = f"Oops! Correct was {expected}"
            self.feedback_color = RED
        self.feedback_until = time.time() + 1.6


class ClassroomBuddy:
    def __init__(self):
        self.detector = HeadGestureDetector(frame_width=FRAME_W, frame_height=FRAME_H)

        # Stickers
        self.stickers = []
        sticker_dir = os.path.join(os.path.dirname(__file__), "stickers")
        for entry in STICKER_CATALOG:
            self.stickers.append(StickerLoader.load(os.path.join(sticker_dir, entry["file"])))
        self.sticker_idx = 0

        # Students + questions (optional external files)
        base = os.path.dirname(__file__)
        self.students = _load_students(os.path.join(base, "students.txt"))
        self.picked: list[str] = []
        self.current_pick: str | None = None
        self.pick_until = 0.0

        q = _load_questions(os.path.join(base, "questions.json"))
        if q is None:
            q = [
                {"question": "Is the sky blue?", "answer": True},
                {"question": "Is 2 + 2 equal to 5?", "answer": False},
                {"question": "Do plants need sunlight?", "answer": True},
                {"question": "Does a fish live on a tree?", "answer": False},
                {"question": "Is 10 bigger than 5?", "answer": True},
            ]
        random.shuffle(q)
        self.quiz = QuizState(questions=q)

        # Mode: 1 quiz, 2 picker, 3 free play
        self.mode = 1

    # ─────────────────────────────────────────────
    #  Stickers overlay (face-box anchored)
    # ─────────────────────────────────────────────
    def _apply_current_sticker(self, frame, face_box, points: int):
        if not face_box:
            return frame
        entry = STICKER_CATALOG[self.sticker_idx]
        if entry["unlock"] > points:
            return frame
        sticker = self.stickers[self.sticker_idx]
        if sticker is None:
            return frame

        x, y, w, h = face_box
        target_w = int(w * entry["x_scale"])
        sh, sw = sticker.shape[:2]
        aspect = sh / max(sw, 1)
        target_h = int(target_w * aspect)

        anchor = entry["anchor"]
        if anchor == "head_top":
            px = x + int(w * entry["x_offset"])
            py = y + int(h * entry["y_offset"])
        elif anchor == "eye_line":
            eye_y = y + int(h * 0.35)
            px = x + int(w * entry["x_offset"])
            py = eye_y + int(h * entry["y_offset"])
        else:
            px, py = x, y

        return alpha_blend(frame, sticker, px, py, target_w, target_h)

    # ─────────────────────────────────────────────
    #  UI
    # ─────────────────────────────────────────────
    def _draw_topbar(self, frame, points: int):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 44), UI_BG, -1)
        cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
        mode_name = {1: "Quick Quiz", 2: "Random Picker", 3: "Sticker Free Play"}.get(self.mode, "Classroom")
        cv2.putText(frame, f"ROBO-FACE Classroom Buddy  |  {mode_name}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, WHITE, 1, cv2.LINE_AA)

        sticker_name = STICKER_CATALOG[self.sticker_idx]["name"]
        _pill(frame, w - 310, 10, f"Points: {points}", bg=(40, 80, 40), fg=WHITE)
        _pill(frame, w - 170, 10, sticker_name, bg=(55, 55, 55), fg=WHITE)

    def _draw_footer_hints(self, frame):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 42), (w, h), UI_BG, -1)
        cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
        cv2.putText(frame, "1 Quiz   2 Picker   3 FreePlay   A/D Stickers   R Reset points   Q Quit", (12, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (210, 210, 210), 1, cv2.LINE_AA)

    # ─────────────────────────────────────────────
    #  Modes
    # ─────────────────────────────────────────────
    def _mode_quiz(self, frame, gesture: str | None):
        if gesture and self.quiz.waiting:
            self.quiz.answer(gesture)

        # After feedback delay, auto-advance
        if not self.quiz.waiting and time.time() >= self.quiz.feedback_until:
            self.quiz.next_q()

        q = self.quiz.current()
        if not q:
            return frame

        h, w = frame.shape[:2]
        _draw_scrim(frame, 0.25)

        card_w = min(600, w - 60)
        card_h = 190
        x1 = (w - card_w) // 2
        y1 = h - card_h - 70
        x2 = x1 + card_w
        y2 = y1 + card_h
        cv2.rectangle(frame, (x1, y1), (x2, y2), (28, 28, 28), -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (60, 60, 60), 2)

        cv2.putText(frame, "Answer with head gestures", (x1 + 16, y1 + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1, cv2.LINE_AA)

        lines = _wrap(q["question"], 46)
        yy = y1 + 78
        for line in lines[:3]:
            cv2.putText(frame, line, (x1 + 16, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.85, WHITE, 2, cv2.LINE_AA)
            yy += 34

        if self.quiz.waiting:
            _pill(frame, x1 + 16, y2 - 44, "NOD = YES    SHAKE = NO", bg=(55, 55, 55), fg=WHITE)
        else:
            _pill(frame, x1 + 16, y2 - 44, "Checking...", bg=(50, 50, 80), fg=WHITE)

        if time.time() < self.quiz.feedback_until:
            _pill(frame, x1 + 16, y1 - 44, self.quiz.feedback, bg=(30, 30, 30), fg=self.quiz.feedback_color)

        return frame

    def _mode_picker(self, frame, gesture: str | None):
        # SHAKE -> shuffle order; NOD -> pick a student not picked recently
        if gesture == "NO":
            random.shuffle(self.students)
            self.current_pick = "Shuffled!"
            self.pick_until = time.time() + 1.0
        elif gesture == "YES":
            choices = [s for s in self.students if s not in self.picked] or self.students[:]
            pick = random.choice(choices) if choices else None
            if pick:
                self.picked.append(pick)
                # keep memory bounded
                if len(self.picked) > max(8, len(self.students)):
                    self.picked = self.picked[-max(8, len(self.students)) :]
            self.current_pick = pick or "No students"
            self.pick_until = time.time() + 3.0

        h, w = frame.shape[:2]
        _draw_scrim(frame, 0.30)

        title = "Random Student Picker"
        cv2.putText(frame, title, (22, 86), cv2.FONT_HERSHEY_SIMPLEX, 1.0, YELLOW, 2, cv2.LINE_AA)
        cv2.putText(frame, "SHAKE = shuffle    NOD = pick", (24, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2, cv2.LINE_AA)

        if time.time() < self.pick_until and self.current_pick:
            name = self.current_pick
        else:
            name = "Ready..."

        box_w = min(560, w - 60)
        box_h = 140
        x1 = (w - box_w) // 2
        y1 = (h - box_h) // 2
        x2 = x1 + box_w
        y2 = y1 + box_h
        cv2.rectangle(frame, (x1, y1), (x2, y2), (28, 28, 28), -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (70, 70, 70), 2)

        (tw, th), _ = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 1.6, 3)
        tx = (w - tw) // 2
        ty = y1 + 92
        cv2.putText(frame, name, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 1.6, WHITE, 3, cv2.LINE_AA)

        small = f"Students loaded: {len(self.students)}"
        cv2.putText(frame, small, (24, h - 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, "Tip: create students.txt (one name per line)", (24, h - 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1, cv2.LINE_AA)

        return frame

    def _mode_freeplay(self, frame):
        h, w = frame.shape[:2]
        _draw_scrim(frame, 0.10)
        cv2.putText(frame, "Sticker Free Play", (22, 86), cv2.FONT_HERSHEY_SIMPLEX, 1.0, YELLOW, 2, cv2.LINE_AA)
        cv2.putText(frame, "Use A/D to change stickers. Earn points in Quiz mode to unlock more.", (24, 122), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 220, 220), 2, cv2.LINE_AA)

        # Show unlock requirement for current sticker (if any)
        req = STICKER_CATALOG[self.sticker_idx]["unlock"]
        if req > 0:
            _pill(frame, 24, 140, f"Unlock requirement: {req} points", bg=(70, 50, 20), fg=WHITE)
        return frame

    # ─────────────────────────────────────────────
    #  Run loop
    # ─────────────────────────────────────────────
    def run(self):
        if not self.detector.start():
            print("✗ Could not start camera. Check connection.")
            return

        win = "ROBO-FACE — Classroom Buddy"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, FRAME_W, FRAME_H)

        try:
            while True:
                frame = self.detector.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                gesture = self.detector.get_gesture()
                face_box = self.detector.get_face_box()

                # Points are shared across modes (quiz points unlock stickers).
                points = self.quiz.points

                # AR overlay first, then UI
                frame = self._apply_current_sticker(frame, face_box, points)
                self._draw_topbar(frame, points)
                self._draw_footer_hints(frame)

                if self.mode == 1:
                    frame = self._mode_quiz(frame, gesture)
                elif self.mode == 2:
                    frame = self._mode_picker(frame, gesture)
                else:
                    frame = self._mode_freeplay(frame)

                cv2.imshow(win, frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("1"):
                    self.mode = 1
                elif key == ord("2"):
                    self.mode = 2
                elif key == ord("3"):
                    self.mode = 3
                elif key in (ord("a"), 81):  # OpenCV left arrow often 81
                    self.sticker_idx = (self.sticker_idx - 1) % len(STICKER_CATALOG)
                elif key in (ord("d"), 83):  # OpenCV right arrow often 83
                    self.sticker_idx = (self.sticker_idx + 1) % len(STICKER_CATALOG)
                elif key == ord("r"):
                    self.quiz.points = 0
                    self.quiz.total = 0
                    self.quiz.idx = 0
                    random.shuffle(self.quiz.questions)

        finally:
            self.detector.stop()
            cv2.destroyAllWindows()


def main():
    print("=" * 62)
    print(" ROBO-FACE Classroom Buddy")
    print(" - Mode 1: Quiz (NOD=YES, SHAKE=NO) -> earns points")
    print(" - Mode 2: Random picker (SHAKE shuffle, NOD pick)")
    print(" - Mode 3: Sticker free play")
    print("=" * 62)
    ClassroomBuddy().run()


if __name__ == "__main__":
    main()

