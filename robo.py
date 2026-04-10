import math
import random
from enum import Enum
import pygame

pygame.init()

WIDTH, HEIGHT = 800, 480
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BG_COLOR = (255, 252, 238)          # #FFFCEE Ivory
FACE_BG = (255, 252, 238)           # Same as bg — no separate panel
CYAN = (0, 200, 240)
LIGHT_CYAN = (120, 225, 255)
DARK_CYAN = (0, 150, 200)
EYE_RING = (80, 210, 255)        # Cyan iris ring
EYE_RING_INNER = (50, 190, 240)
EYE_BLACK = (25, 25, 30)         # Pupil black
EYE_SOCKET = (60, 65, 75)        # Dark ring around eye
MOUTH_BLACK = (30, 25, 35)       # Mouth fill
MOUTH_INSIDE = (80, 50, 70)      # Dark purple inside mouth
PINK = (255, 182, 193)
DEEP_PINK = (255, 105, 180)
ROSE_PINK = (255, 192, 203)
YELLOW = (255, 255, 100)
ORANGE = (255, 165, 0)
LIGHT_GRAY = (240, 240, 240)
BLUE = (100, 200, 255)


class EyeState(Enum):
    NORMAL = "normal"
    CLOSED = "closed"
    SMALL = "small"
    RAISED = "raised"
    OVAL = "oval"
    FAR = "far"
    WINK_LEFT = "wink_left"
    WINK_RIGHT = "wink_right"
    HEART = "heart"
    STAR = "star"


class Viseme(Enum):
    SILENCE = "silence"
    A = "a"
    E = "e"
    I = "i"
    O = "o"
    U = "u"
    MBP = "mbp"
    FV = "fv"
    TH = "th"
    TD = "td"
    KG = "kg"
    NNG = "nng"
    L = "l"
    R = "r"
    WQ = "wq"
    SZ = "sz"
    CHSH = "chsh"
    OPEN = "open"


class RobotFace:
    def __init__(self, screen):
        self.screen = screen
        self.width = WIDTH
        self.height = HEIGHT

        # Feature toggles
        self.has_blue_eyes = True
        self.has_cheeks = False
        self.has_ears = False
        self.has_eyebrows = False
        self.has_eyelids = False
        self.has_hair = False
        self.has_iris = True
        self.has_mouth = True
        self.has_pupils = True
        self.has_nose = False
        self.white_face = True
        self.has_glow = True

        # Eye state
        self.eye_state = EyeState.NORMAL
        self.blink_timer = 0
        self.blink_duration = 8
        self.auto_blink = True

        # Animation
        self.eye_offset_x = 0
        self.eye_offset_y = 0
        self.pupil_x = 0
        self.pupil_y = 0
        self.face_scale = 1.0
        self.expression_timer = 0
        self.glow_phase = 0.0
        self.iris_rotation = 0.0  # Rotating iris lines

        # Expression
        self.current_expression = "happy"
        self.mouth_type = "smile"
        self.eyebrow_type = "normal"

        # Listening animation
        self.listening = False
        self.listen_blink_rate = 0.03  # Faster blinks when listening
        self.listen_pupil_phase = 0.0

        # Lip sync
        self.current_viseme = Viseme.SILENCE
        self.viseme_timer = 0
        self.viseme_duration = 0
        self.lip_sync_enabled = False
        self.phoneme_map = self._create_phoneme_map()
        self.phoneme_queue = []
        self.phoneme_queue_index = 0

    def set_expression(self, expression):
        self.current_expression = expression
        self.expression_timer = 0

        # Reset defaults
        self.has_blue_eyes = True
        self.has_cheeks = False
        self.has_ears = False
        self.has_eyebrows = False
        self.has_eyelids = False
        self.has_hair = False
        self.has_iris = True
        self.has_mouth = True
        self.has_pupils = True
        self.has_nose = False
        self.has_glow = True
        self.eye_offset_x = 0
        self.eye_offset_y = 0
        self.mouth_type = "smile"
        self.eyebrow_type = "normal"

        if expression == "baseline":
            self.has_iris = False
            self.eye_state = EyeState.NORMAL
        elif expression == "happy":
            self.eye_state = EyeState.NORMAL
            self.mouth_type = "big_smile"
        elif expression == "cute":
            self.has_cheeks = True
            self.eye_state = EyeState.SMALL
            self.mouth_type = "smile"
        elif expression == "surprised":
            self.has_eyebrows = True
            self.eye_state = EyeState.RAISED
            self.mouth_type = "surprised"
            self.eyebrow_type = "raised"
        elif expression == "sleepy":
            self.has_eyelids = True
            self.eye_state = EyeState.SMALL
            self.mouth_type = "smile"
        elif expression == "thinking":
            self.has_eyebrows = True
            self.eye_offset_x = 25
            self.mouth_type = "pout"
        elif expression == "sad":
            self.has_eyebrows = True
            self.eye_state = EyeState.SMALL
            self.eye_offset_y = 10
            self.mouth_type = "sad"
            self.eyebrow_type = "sad"
        elif expression == "excited":
            self.has_cheeks = True
            self.has_eyebrows = True
            self.eye_state = EyeState.RAISED
            self.mouth_type = "big_smile"
            self.eyebrow_type = "raised"
        elif expression == "shy":
            self.has_cheeks = True
            self.eye_state = EyeState.SMALL
            self.eye_offset_y = 8
            self.mouth_type = "smile"
        elif expression == "angry":
            self.has_eyebrows = True
            self.eye_state = EyeState.SMALL
            self.mouth_type = "pout"
            self.eyebrow_type = "angry"
        elif expression == "love":
            self.has_cheeks = True
            self.eye_state = EyeState.HEART
            self.mouth_type = "smile"
        elif expression == "wink":
            self.has_cheeks = True
            self.eye_state = EyeState.WINK_RIGHT
            self.mouth_type = "smile"
        elif expression == "confused":
            self.has_eyebrows = True
            self.eye_offset_x = -20
            self.mouth_type = "pout"
        elif expression == "star_eyes":
            self.has_cheeks = True
            self.eye_state = EyeState.STAR
            self.mouth_type = "big_smile"
        elif expression == "listening":
            self.listening = True
            self.has_eyebrows = True
            self.eye_state = EyeState.NORMAL
            self.mouth_type = "listening"
            self.eyebrow_type = "raised"

    def set_listening(self, enabled=True):
        """Toggle listening mode"""
        self.listening = enabled
        if enabled:
            self.set_expression("listening")
        else:
            self.set_expression("happy")

    def _create_phoneme_map(self):
        return {
            'a': Viseme.A, 'A': Viseme.A,
            'e': Viseme.E, 'E': Viseme.E,
            'i': Viseme.I, 'I': Viseme.I,
            'o': Viseme.O, 'O': Viseme.O,
            'u': Viseme.U, 'U': Viseme.U,
            'm': Viseme.MBP, 'M': Viseme.MBP,
            'b': Viseme.MBP, 'B': Viseme.MBP,
            'p': Viseme.MBP, 'P': Viseme.MBP,
            'f': Viseme.FV, 'F': Viseme.FV,
            'v': Viseme.FV, 'V': Viseme.FV,
            't': Viseme.TD, 'T': Viseme.TD,
            'd': Viseme.TD, 'D': Viseme.TD,
            'k': Viseme.KG, 'K': Viseme.KG,
            'g': Viseme.KG, 'G': Viseme.KG,
            'n': Viseme.NNG, 'N': Viseme.NNG,
            'l': Viseme.L, 'L': Viseme.L,
            'r': Viseme.R, 'R': Viseme.R,
            'w': Viseme.WQ, 'W': Viseme.WQ,
            'q': Viseme.WQ, 'Q': Viseme.WQ,
            's': Viseme.SZ, 'S': Viseme.SZ,
            'z': Viseme.SZ, 'Z': Viseme.SZ,
            'c': Viseme.CHSH, 'C': Viseme.CHSH,
            'h': Viseme.CHSH, 'H': Viseme.CHSH,
            ' ': Viseme.SILENCE,
            '.': Viseme.SILENCE,
            ',': Viseme.SILENCE,
            '!': Viseme.OPEN,
            '?': Viseme.OPEN,
        }

    def set_phoneme(self, phoneme, duration_frames=5):
        if phoneme in self.phoneme_map:
            self.current_viseme = self.phoneme_map[phoneme]
        else:
            self.current_viseme = Viseme.SILENCE
        self.viseme_duration = duration_frames
        self.viseme_timer = 0

    def speak_text(self, text, phoneme_duration=5):
        self.phoneme_queue = [(char, phoneme_duration) for char in text]
        self.phoneme_queue_index = 0
        self.lip_sync_enabled = True

    def update(self):
        self.expression_timer += 1
        self.glow_phase += 0.04
        self.iris_rotation += 0.5

        # Blink logic
        blink_rate = self.listen_blink_rate if self.listening else 0.01
        if self.auto_blink and self.blink_timer == 0 and random.random() < blink_rate:
            self.blink()

        if self.blink_timer > 0:
            self.blink_timer -= 1
            if self.blink_timer == 0:
                if self.current_expression == "love":
                    self.eye_state = EyeState.HEART
                elif self.listening:
                    self.eye_state = EyeState.NORMAL
                else:
                    self.eye_state = EyeState.NORMAL

        # Listening: gentle pupil movement
        if self.listening:
            self.listen_pupil_phase += 0.03
            self.pupil_x = math.sin(self.listen_pupil_phase) * 6
            self.pupil_y = math.cos(self.listen_pupil_phase * 0.7) * 4

        # Lip sync queue processing
        if self.lip_sync_enabled and self.phoneme_queue:
            # Check if current viseme timer has expired
            if self.viseme_timer >= self.viseme_duration:
                # Move to next phoneme in queue
                if self.phoneme_queue_index < len(self.phoneme_queue):
                    ph, dur = self.phoneme_queue[self.phoneme_queue_index]
                    self.set_phoneme(ph, dur)
                    self.phoneme_queue_index += 1
                else:
                    # Queue is finished
                    self.current_viseme = Viseme.SILENCE
                    self.lip_sync_enabled = False
                    self.phoneme_queue = []
                    self.phoneme_queue_index = 0
            else:
                # Increment timer for current viseme
                self.viseme_timer += 1
        elif self.lip_sync_enabled and not self.phoneme_queue:
            # Queue is empty but lip sync is enabled - disable it
            self.current_viseme = Viseme.SILENCE
            self.lip_sync_enabled = False

    def blink(self):
        self.blink_timer = self.blink_duration

    # ── Rounded rect helper ──

    def _rounded_rect(self, surface, color, rect, radius):
        x, y, w, h = rect
        r = min(radius, w // 2, h // 2)
        pygame.draw.rect(surface, color, (x + r, y, w - 2 * r, h))
        pygame.draw.rect(surface, color, (x, y + r, w, h - 2 * r))
        pygame.draw.circle(surface, color, (x + r, y + r), r)
        pygame.draw.circle(surface, color, (x + w - r, y + r), r)
        pygame.draw.circle(surface, color, (x + r, y + h - r), r)
        pygame.draw.circle(surface, color, (x + w - r, y + h - r), r)

    # ── Main draw ──

    def draw_face(self):
        cx = self.width // 2
        cy = self.height // 2

        # Fill entire screen with bg color
        self.screen.fill(BG_COLOR)

        # ── Eyes ──
        eye_cy = cy - 30
        self.draw_eyes(cx, eye_cy)

        if self.has_eyebrows:
            self.draw_eyebrows(cx, eye_cy)

        if self.has_eyelids:
            self.draw_eyelids(cx, eye_cy)

        # ── Mouth ──
        if self.has_mouth:
            mouth_cy = cy + 85
            self.draw_mouth(cx, mouth_cy)

        if self.has_cheeks:
            self.draw_cheeks(cx, cy + 40)

    # ── Eyes (reference style: cyan ring + black pupil + highlight) ──

    def draw_eyes(self, center_x, center_y):
        spacing = 130
        lx = center_x - spacing + self.eye_offset_x
        rx = center_x + spacing + self.eye_offset_x
        ey = center_y + self.eye_offset_y

        if self.eye_state == EyeState.HEART:
            self.draw_heart_eye(lx, ey, 55)
            self.draw_heart_eye(rx, ey, 55)
            return
        if self.eye_state == EyeState.STAR:
            self.draw_star_eye(lx, ey, 55)
            self.draw_star_eye(rx, ey, 55)
            return

        radius = 58
        if self.eye_state == EyeState.SMALL:
            radius = 45
        elif self.eye_state == EyeState.RAISED:
            ey -= 12
            radius = 62

        if self.eye_state != EyeState.WINK_LEFT:
            self._draw_eye(lx, ey, radius)
        else:
            self._draw_wink(lx, ey, radius)

        if self.eye_state != EyeState.WINK_RIGHT:
            self._draw_eye(rx, ey, radius)
        else:
            self._draw_wink(rx, ey, radius)

    def _draw_eye(self, x, y, r):
        """Draw eye matching the reference: dark socket, cyan iris ring, black pupil, highlight."""
        ix, iy = int(x), int(y)

        # Blinking
        if self.blink_timer > 0:
            # Closed eye: curved line
            pygame.draw.arc(self.screen, EYE_SOCKET,
                            (ix - r, iy - 6, r * 2, 12),
                            0, math.pi, 6)
            return

        # Outer dark socket ring
        pygame.draw.circle(self.screen, EYE_SOCKET, (ix, iy), r + 4)

        # Cyan iris ring (glowing)
        pulse = 0.85 + 0.15 * math.sin(self.glow_phase * 1.5)
        ring_col = tuple(max(0, min(255, int(c * pulse))) for c in EYE_RING)

        # Glow behind iris
        glow = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for i in range(6):
            a = max(0, 30 - i * 5)
            pygame.draw.circle(glow, (*CYAN[:3], a), (ix, iy), r + 8 + i * 2)
        self.screen.blit(glow, (0, 0))

        # Iris ring
        pygame.draw.circle(self.screen, ring_col, (ix, iy), r)

        # Iris line details (radial lines like the reference)
        iris_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        num_lines = 36
        inner_r = r * 0.55
        for i in range(num_lines):
            ang = (i * 2 * math.pi / num_lines) + math.radians(self.iris_rotation)
            x1 = ix + inner_r * math.cos(ang)
            y1 = iy + inner_r * math.sin(ang)
            x2 = ix + (r - 3) * math.cos(ang)
            y2 = iy + (r - 3) * math.sin(ang)
            line_a = 40 + int(20 * math.sin(ang * 3 + self.glow_phase))
            pygame.draw.line(iris_surf, (*LIGHT_CYAN[:3], line_a),
                             (int(x1), int(y1)), (int(x2), int(y2)), 2)
        self.screen.blit(iris_surf, (0, 0))

        # Black pupil
        pupil_r = int(r * 0.5)
        px = ix + int(self.pupil_x)
        py = iy + int(self.pupil_y)
        pygame.draw.circle(self.screen, EYE_BLACK, (px, py), pupil_r)

        # White highlight dot (top-right of pupil)
        hl_r = max(5, pupil_r // 3)
        pygame.draw.circle(self.screen, WHITE,
                           (px + pupil_r // 3, py - pupil_r // 3), hl_r)
        # Smaller secondary highlight
        pygame.draw.circle(self.screen, WHITE,
                           (px - pupil_r // 4, py + pupil_r // 4), max(2, hl_r // 2))

    def _draw_wink(self, x, y, r):
        """Draw a winking closed eye."""
        ix, iy = int(x), int(y)
        pygame.draw.arc(self.screen, EYE_SOCKET,
                        (ix - r, iy - 8, r * 2, 16),
                        0, math.pi, 5)

    def draw_eyelids(self, center_x, center_y):
        """Draw half-closed eyelids for sleepy expression."""
        spacing = 130
        r = 58
        for ex in [center_x - spacing, center_x + spacing]:
            lid = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.rect(lid, (*BG_COLOR, 220),
                             (int(ex - r - 5), int(center_y - r - 10 + self.eye_offset_y),
                              r * 2 + 10, int(r * 0.9)))
            self.screen.blit(lid, (0, 0))

    # ── Eyebrows ──

    def draw_eyebrows(self, center_x, center_y):
        spacing = 130
        eby = center_y - 80
        col = EYE_SOCKET  # Dark gray to match eye sockets
        thick = 5

        if self.eyebrow_type == "normal":
            # Gentle arcs above each eye
            pygame.draw.arc(self.screen, col,
                            (center_x - spacing - 50, eby - 10, 100, 25),
                            0.2, math.pi - 0.2, thick)
            pygame.draw.arc(self.screen, col,
                            (center_x + spacing - 50, eby - 10, 100, 25),
                            0.2, math.pi - 0.2, thick)

        elif self.eyebrow_type == "raised":
            eby -= 18
            pygame.draw.arc(self.screen, col,
                            (center_x - spacing - 50, eby - 15, 100, 35),
                            0.2, math.pi - 0.2, thick)
            pygame.draw.arc(self.screen, col,
                            (center_x + spacing - 50, eby - 15, 100, 35),
                            0.2, math.pi - 0.2, thick)

        elif self.eyebrow_type == "sad":
            # Inner side raised
            pygame.draw.line(self.screen, col,
                             (center_x - spacing - 45, eby + 5),
                             (center_x - spacing + 45, eby - 10), thick)
            pygame.draw.line(self.screen, col,
                             (center_x + spacing - 45, eby - 10),
                             (center_x + spacing + 45, eby + 5), thick)

        elif self.eyebrow_type == "angry":
            pygame.draw.line(self.screen, col,
                             (center_x - spacing - 45, eby - 5),
                             (center_x - spacing + 45, eby + 10), thick)
            pygame.draw.line(self.screen, col,
                             (center_x + spacing - 45, eby + 10),
                             (center_x + spacing + 45, eby - 5), thick)

    # ── Mouth ──

    def draw_mouth(self, center_x, center_y):
        if self.lip_sync_enabled:
            self.draw_mouth_viseme(center_x, center_y)
        else:
            self.draw_mouth_expression(center_x, center_y)

    def draw_mouth_expression(self, center_x, center_y):
        """Draw mouth matching reference: filled black smile shapes."""
        cx, cy = center_x, center_y

        if self.mouth_type == "smile":
            # D-shaped smile like the reference
            w, h = 80, 45
            rect = (cx - w, cy - h // 2, w * 2, h)
            # Filled black arc (bottom half of ellipse)
            mouth_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.ellipse(mouth_surf, (*MOUTH_BLACK, 255), rect)
            # Cut top half to make D-shape
            pygame.draw.rect(mouth_surf, (0, 0, 0, 0),
                             (cx - w - 1, cy - h // 2 - 1, w * 2 + 2, h // 2 + 1))
            self.screen.blit(mouth_surf, (0, 0))
            # Inside color (dark purple)
            inner_rect = (cx - w + 8, cy, w * 2 - 16, h // 2 - 6)
            pygame.draw.ellipse(self.screen, MOUTH_INSIDE, inner_rect)

        elif self.mouth_type == "big_smile":
            w, h = 100, 60
            rect = (cx - w, cy - h // 2, w * 2, h)
            mouth_surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.ellipse(mouth_surf, (*MOUTH_BLACK, 255), rect)
            pygame.draw.rect(mouth_surf, (0, 0, 0, 0),
                             (cx - w - 1, cy - h // 2 - 1, w * 2 + 2, h // 2 + 1))
            self.screen.blit(mouth_surf, (0, 0))
            inner_rect = (cx - w + 10, cy + 2, w * 2 - 20, h // 2 - 8)
            pygame.draw.ellipse(self.screen, MOUTH_INSIDE, inner_rect)
            # Small cheek dots beside mouth
            pygame.draw.circle(self.screen, ROSE_PINK, (cx - w - 8, cy + 5), 6)
            pygame.draw.circle(self.screen, ROSE_PINK, (cx + w + 8, cy + 5), 6)

        elif self.mouth_type == "sad":
            pygame.draw.arc(self.screen, MOUTH_BLACK,
                            (cx - 60, cy, 120, 50),
                            0.2, math.pi - 0.2, 6)

        elif self.mouth_type == "surprised":
            # Open O mouth
            pygame.draw.circle(self.screen, MOUTH_BLACK, (cx, cy), 30)
            pygame.draw.circle(self.screen, MOUTH_INSIDE, (cx, cy), 25)

        elif self.mouth_type == "pout":
            pygame.draw.ellipse(self.screen, MOUTH_BLACK,
                                (cx - 22, cy - 8, 44, 18))

        elif self.mouth_type == "listening":
            # Slightly open, gentle O shape — robot is listening
            ow = 30 + int(8 * math.sin(self.glow_phase * 2))
            oh = 18 + int(5 * math.sin(self.glow_phase * 2.5))
            pygame.draw.ellipse(self.screen, MOUTH_BLACK,
                                (cx - ow, cy - oh // 2, ow * 2, oh))
            pygame.draw.ellipse(self.screen, MOUTH_INSIDE,
                                (cx - ow + 4, cy - oh // 2 + 3, ow * 2 - 8, oh - 6))

        elif self.mouth_type == "heart":
            pts = [
                (cx, cy + 18),
                (cx - 18, cy - 3),
                (cx, cy - 8),
                (cx + 18, cy - 3),
            ]
            pygame.draw.polygon(self.screen, DEEP_PINK, pts)

    def draw_mouth_viseme(self, center_x, center_y):
        """Lip sync mouth shapes — filled black style."""
        cx, cy = center_x, center_y
        col = MOUTH_BLACK
        inner = MOUTH_INSIDE

        if self.current_viseme == Viseme.SILENCE:
            pygame.draw.line(self.screen, col, (cx - 40, cy), (cx + 40, cy), 4)

        elif self.current_viseme == Viseme.A:
            # Wide open
            pygame.draw.ellipse(self.screen, col, (cx - 50, cy - 20, 100, 45))
            pygame.draw.ellipse(self.screen, inner, (cx - 44, cy - 15, 88, 35))

        elif self.current_viseme == Viseme.E:
            pygame.draw.ellipse(self.screen, col, (cx - 55, cy - 10, 110, 24))
            pygame.draw.ellipse(self.screen, inner, (cx - 49, cy - 6, 98, 16))

        elif self.current_viseme == Viseme.I:
            pygame.draw.ellipse(self.screen, col, (cx - 50, cy - 6, 100, 14))

        elif self.current_viseme == Viseme.O:
            pygame.draw.circle(self.screen, col, (cx, cy), 25)
            pygame.draw.circle(self.screen, inner, (cx, cy), 20)

        elif self.current_viseme == Viseme.U:
            pygame.draw.circle(self.screen, col, (cx, cy), 16)
            pygame.draw.circle(self.screen, inner, (cx, cy), 12)

        elif self.current_viseme == Viseme.MBP:
            pygame.draw.ellipse(self.screen, col, (cx - 35, cy - 5, 70, 12))

        elif self.current_viseme == Viseme.FV:
            pygame.draw.line(self.screen, col, (cx - 40, cy - 4), (cx + 40, cy - 4), 4)
            pygame.draw.arc(self.screen, col, (cx - 35, cy - 4, 70, 18),
                            math.pi, 2 * math.pi, 3)

        elif self.current_viseme == Viseme.WQ:
            pygame.draw.circle(self.screen, col, (cx, cy), 12)
            pygame.draw.circle(self.screen, inner, (cx, cy), 8)

        elif self.current_viseme == Viseme.OPEN:
            pygame.draw.ellipse(self.screen, col, (cx - 55, cy - 25, 110, 55))
            pygame.draw.ellipse(self.screen, inner, (cx - 48, cy - 19, 96, 43))

        else:
            pygame.draw.ellipse(self.screen, col, (cx - 35, cy - 10, 70, 22))
            pygame.draw.ellipse(self.screen, inner, (cx - 29, cy - 6, 58, 14))

    # ── Cheeks ──

    def draw_cheeks(self, center_x, center_y):
        offset = 160
        glow = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for i in range(5):
            a = max(0, 35 - i * 7)
            pygame.draw.circle(glow, (*PINK[:3], a),
                               (center_x - offset, center_y), 25 - i * 3)
            pygame.draw.circle(glow, (*PINK[:3], a),
                               (center_x + offset, center_y), 25 - i * 3)
        self.screen.blit(glow, (0, 0))

    # ── Special eyes ──

    def draw_heart_eye(self, cx, cy, size):
        s = size * 0.7
        col = DEEP_PINK
        pygame.draw.circle(self.screen, col, (int(cx - s * 0.25), int(cy - s * 0.15)), int(s * 0.38))
        pygame.draw.circle(self.screen, col, (int(cx + s * 0.25), int(cy - s * 0.15)), int(s * 0.38))
        pts = [(int(cx), int(cy + s * 0.55)),
               (int(cx - s * 0.6), int(cy + s * 0.1)),
               (int(cx + s * 0.6), int(cy + s * 0.1))]
        pygame.draw.polygon(self.screen, col, pts)
        pygame.draw.circle(self.screen, WHITE, (int(cx - s * 0.1), int(cy - s * 0.1)), max(3, int(s * 0.1)))

    def draw_star_eye(self, cx, cy, size):
        pts = []
        for i in range(10):
            ang = i * math.pi / 5 - math.pi / 2
            r = size * 0.55 if i % 2 == 0 else size * 0.25
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        pygame.draw.polygon(self.screen, YELLOW, pts)
        pygame.draw.polygon(self.screen, ORANGE, pts, 2)
        pygame.draw.circle(self.screen, WHITE, (int(cx), int(cy)), max(4, int(size * 0.12)))

    # ── Utility (unchanged API) ──

    def move_pupils(self, x, y):
        mx = 12
        self.pupil_x = max(-mx, min(mx, x))
        self.pupil_y = max(-mx, min(mx, y))

    def enable_lip_sync(self, enabled=True):
        self.lip_sync_enabled = enabled
        if not enabled:
            self.current_viseme = Viseme.SILENCE

    def update_lipsync(self):
        pass

    def process_phoneme_timing(self, phoneme, start_time, end_time, current_time):
        if start_time <= current_time < end_time:
            duration = int((end_time - start_time) * FPS)
            self.set_phoneme(phoneme, max(1, duration))


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Robot Face")
    clock = pygame.time.Clock()

    robot = RobotFace(screen)
    robot.set_expression("happy")

    pupil_angle = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    robot.set_expression("baseline")
                elif event.key == pygame.K_2:
                    robot.set_expression("happy")
                elif event.key == pygame.K_3:
                    robot.set_expression("cute")
                elif event.key == pygame.K_4:
                    robot.set_expression("surprised")
                elif event.key == pygame.K_5:
                    robot.set_expression("sleepy")
                elif event.key == pygame.K_6:
                    robot.set_expression("thinking")
                elif event.key == pygame.K_7:
                    robot.set_expression("sad")
                elif event.key == pygame.K_8:
                    robot.set_expression("excited")
                elif event.key == pygame.K_9:
                    robot.set_expression("shy")
                elif event.key == pygame.K_0:
                    robot.set_expression("angry")
                elif event.key == pygame.K_l:
                    robot.set_expression("love")
                elif event.key == pygame.K_k:
                    robot.set_expression("wink")
                elif event.key == pygame.K_u:
                    robot.set_expression("confused")
                elif event.key == pygame.K_s:
                    robot.set_expression("star_eyes")
                elif event.key == pygame.K_r:
                    # Toggle listening mode
                    robot.set_listening(not robot.listening)
                elif event.key == pygame.K_b:
                    robot.blink()
                elif event.key == pygame.K_c:
                    robot.has_cheeks = not robot.has_cheeks
                elif event.key == pygame.K_e:
                    robot.has_ears = not robot.has_ears
                elif event.key == pygame.K_h:
                    robot.has_hair = not robot.has_hair
                elif event.key == pygame.K_n:
                    robot.has_nose = not robot.has_nose
                elif event.key == pygame.K_SPACE:
                    robot.auto_blink = not robot.auto_blink
                elif event.key == pygame.K_t:
                    robot.enable_lip_sync(True)
                    robot.speak_text("Hello, I am a cute robot!", phoneme_duration=4)
                elif event.key == pygame.K_x:
                    robot.enable_lip_sync(False)

        # Gentle pupil movement (skip if listening mode handles it)
        if not robot.listening:
            pupil_angle += 0.02
            robot.move_pupils(math.cos(pupil_angle) * 6, math.sin(pupil_angle) * 4)

        robot.update()
        robot.draw_face()
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
