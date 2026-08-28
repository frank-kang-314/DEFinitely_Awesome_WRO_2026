"""
Pillar (red/green block) detection - Raspberry Pi 5 + Raspberry Pi AI Camera (IMX500).

Changes from the Arduino App Lab version:
  - Removed arduino.app_bricks.web_ui (Arduino-specific) - streaming/detection
    now runs as plain OpenCV processing on frames pulled from Picamera2.
  - Camera capture uses picamera2 (the CSI/libcamera stack), not
    cv2.VideoCapture - the AI Camera is not a USB device so cv2.VideoCapture
    won't see it.
  - Replaced LEFT/RIGHT "side" with the actual angle (in degrees) of the
    block from the center of the camera's view, computed with the same
    pinhole-camera model already used for distance:
        angle_deg = atan2(cx - frame_center_x, FOCAL_LENGTH_PX)
    Positive angle = block is to the right of center, negative = left,
    0 = dead center.
  - Optional live preview window (cv2.imshow) if you have a monitor hooked
    up to the Pi for debugging - disable it for headless competition runs.

Note on the AI Camera's on-chip AI features: the IMX500 can run neural
network inference directly on the sensor, but that's a separate capability
(needs a compiled model + the picamera2 IMX500 helper classes). This script
just uses it as a regular camera and does the red/green detection in
software with OpenCV, same approach as before - simplest path to get this
working with your existing color-detection logic.

Usage from your main robot script:
    from pillar_detection import start_camera_thread, get_latest_pillars

    start_camera_thread()
    ...
    pillars = get_latest_pillars()   # list of detection dicts, updated ~20x/sec
    for p in pillars:
        print(p["color"], p["angle_deg"], p["distance"])

Requires (install via apt, not pip - picamera2 needs system libcamera bindings):
    sudo apt install -y python3-picamera2 python3-opencv
"""

import cv2
import numpy as np
import threading
import time
import math
from datetime import datetime, UTC
from picamera2 import Picamera2

# ─── CONFIG ───────────────────────────────────────────────
FRAME_SIZE      = (640, 480)   # lower = faster processing; AI Camera supports much higher
MIN_AREA        = 1500
BLOCK_REAL_CM   = 5.0
FOCAL_LENGTH_PX = 400       # will very likely need recalibrating for the AI Camera's lens
                            # (different focal length/FOV than whatever camera you used before)
SHOW_PREVIEW    = False     # set True only when a monitor is attached for debugging
LOOP_DELAY_S    = 0.05      # ~20 Hz
ROTATE_180      = True      # set False if the camera isn't mounted upside down
# ──────────────────────────────────────────────────────────

COLOR_RANGES = {
    "RED": [
        (np.array([0,   100, 80]),  np.array([8,   255, 255])),
        (np.array([172, 100, 80]),  np.array([180, 255, 255])),
    ],
    "GREEN": [
        (np.array([38,  60,  50]),  np.array([88,  255, 255])),
    ],
}
BOX_COLORS = {
    "RED":   (0,   0,   255),
    "GREEN": (0,   255, 80),
}


def get_mask(hsv, color):
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for (lo, hi) in COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, lo, hi)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def estimate_distance(pixel_width):
    if pixel_width <= 0:
        return None
    return round((BLOCK_REAL_CM * FOCAL_LENGTH_PX) / pixel_width, 1)


def estimate_angle_deg(cx, frame_width):
    """Angle of the block from the center of the frame, in degrees.
    Positive = right of center, negative = left of center."""
    offset_px = cx - (frame_width / 2)
    angle_rad = math.atan2(offset_px, FOCAL_LENGTH_PX)
    return round(math.degrees(angle_rad), 1)


def draw_box(frame, x, y, w, h, color_name, distance_cm=None, angle_deg=None):
    bgr = BOX_COLORS[color_name]
    cv2.rectangle(frame, (x, y), (x+w, y+h), bgr, 2)
    cs = 12
    for (px, py, sx, sy) in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
        cv2.line(frame, (px, py), (px + cs*sx, py), bgr, 3)
        cv2.line(frame, (px, py), (px, py + cs*sy), bgr, 3)
    dist_str  = f" ~{distance_cm}cm" if distance_cm is not None else ""
    angle_str = f" | {angle_deg:+.1f}deg" if angle_deg is not None else ""
    label = f"{color_name}{angle_str} | cx:{x+w//2} cy:{y+h//2}{dist_str}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.rectangle(frame, (x, y - th - 8), (x + tw + 4, y), bgr, -1)
    cv2.putText(frame, label, (x + 2, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)


# Shared detection state - written by camera thread, read by main loop
_lock           = threading.Lock()
_latest_pillars = []   # list of detection dicts


def get_latest_pillars():
    with _lock:
        return list(_latest_pillars)


def camera_loop():
    global _latest_pillars

    picam2 = Picamera2()
    # Note: picamera2's "RGB888" format is actually delivered in BGR byte
    # order (a documented historical quirk) - which is exactly what OpenCV
    # expects, so no extra color conversion is needed here.
    config = picam2.create_preview_configuration(
        main={"size": FRAME_SIZE, "format": "RGB888"}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)  # let auto-exposure/white-balance settle
    print("[SYS] Camera active.")

    while True:
        frame = picam2.capture_array()

        if ROTATE_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        frame_width = frame.shape[1]

        detected = []

        for color_name in ["RED", "GREEN"]:
            mask = get_mask(hsv, color_name)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_AREA:
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                if area / (w * h) < 0.40:
                    continue
                aspect = w / h if h > 0 else 0
                if aspect < 0.25 or aspect > 4.0:
                    continue

                cx          = x + w // 2
                cy          = y + h // 2
                angle_deg   = estimate_angle_deg(cx, frame_width)
                distance_cm = estimate_distance(w)

                if SHOW_PREVIEW:
                    draw_box(frame, x, y, w, h, color_name, distance_cm, angle_deg)

                det = {
                    "color":      color_name,
                    "x":          cx,
                    "y":          cy,
                    "width":      w,
                    "height":     h,
                    "distance":   distance_cm,
                    "angle_deg":  angle_deg,   # + = right of center, - = left of center
                    "confidence": 1.0,
                    "timestamp":  datetime.now(UTC).isoformat()
                }
                detected.append(det)
                print(f"DETECT {color_name} | angle:{angle_deg:+.1f}deg | dist:{distance_cm}cm")

        # Update shared state
        with _lock:
            _latest_pillars = detected

        if SHOW_PREVIEW:
            cv2.imshow("Pillar Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        time.sleep(LOOP_DELAY_S)

    picam2.stop()
    if SHOW_PREVIEW:
        cv2.destroyAllWindows()


def start_camera_thread():
    """Starts the camera loop in a background thread and returns immediately."""
    t = threading.Thread(target=camera_loop, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # Standalone test: run the camera loop directly in the main thread
    camera_loop()