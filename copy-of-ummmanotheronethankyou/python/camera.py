# SPDX-FileCopyrightText: Copyright (C) ARDUINO SRL (http://www.arduino.cc)
# SPDX-License-Identifier: MPL-2.0

from arduino.app_bricks.web_ui import WebUI
from datetime import datetime, UTC
import cv2
import numpy as np
import threading
import time
import base64

# ─── CONFIG ───────────────────────────────────────────────
MIN_AREA        = 1500
BLOCK_REAL_CM   = 5.0
FOCAL_LENGTH_PX = 400
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

def draw_box(frame, x, y, w, h, color_name, distance_cm=None, side=None):
    bgr = BOX_COLORS[color_name]
    cv2.rectangle(frame, (x, y), (x+w, y+h), bgr, 2)
    cs = 12
    for (px, py, sx, sy) in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
        cv2.line(frame, (px, py), (px + cs*sx, py), bgr, 3)
        cv2.line(frame, (px, py), (px, py + cs*sy), bgr, 3)
    dist_str = f" ~{distance_cm}cm" if distance_cm else ""
    side_str = f" | {side}" if side else ""
    label = f"{color_name}{side_str} | cx:{x+w//2} cy:{y+h//2}{dist_str}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.rectangle(frame, (x, y - th - 8), (x + tw + 4, y), bgr, -1)
    cv2.putText(frame, label, (x + 2, y - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)


# Shared detection state — written by camera thread, read by main loop
_lock            = threading.Lock()
_latest_pillars  = []   # list of detection dicts

def get_latest_pillars():
    with _lock:
        return list(_latest_pillars)


def camera_loop(ui: WebUI):
    global _latest_pillars

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera.")
        return
    print("[SYS] Camera active.")

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

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
                side        = "LEFT" if cx < frame_width // 2 else "RIGHT"
                distance_cm = estimate_distance(w)

                draw_box(frame, x, y, w, h, color_name, distance_cm, side)

                det = {
                    "color":      color_name,
                    "content":    color_name,
                    "x":          cx,
                    "y":          cy,
                    "width":      w,
                    "height":     h,
                    "distance":   distance_cm,
                    "side":       side,
                    "confidence": 1.0,
                    "timestamp":  datetime.now(UTC).isoformat()
                }
                detected.append(det)
                ui.send_message("detection", message=det)
                print(f"DETECT {color_name} | {side} | dist:{distance_cm}cm")

        # Update shared state
        with _lock:
            _latest_pillars = detected

        # Stream frame
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
        ui.send_message("frame", message={"data": b64})

        time.sleep(0.05)