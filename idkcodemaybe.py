"""

WRO Future Engineers Obstacle Challenge behavior, as described:
    - drive the track, turn 90 degrees at corners based on which side
      opens up, stop after 3 laps
    - RED pillar   -> pass it keeping the pillar on the car's LEFT
                      (the car steers/stays to the pillar's right)
    - GREEN pillar -> pass it keeping the pillar on the car's RIGHT
                      (the car steers/stays to the pillar's left)

Priority order each loop, highest first:
    1. Finish an in-progress 90-degree corner turn (don't interrupt it)
    2. Start a new corner turn if the front is blocked and a side opened up
    3. Steer around a pillar if one is close and roughly ahead
    4. Small left/right wall-correction if both side walls are ~even distance
    5. Drive straight


Requires (on the Pi):
    sudo apt install -y python3-picamera2 python3-opencv
    pip install gpiozero lgpio

"""

import time
import math
import threading
from datetime import datetime, UTC

import cv2
import numpy as np
from gpiozero import DistanceSensor, AngularServo, PWMOutputDevice
from picamera2 import Picamera2

# =========================================================================
# CONFIG
# =========================================================================

# --- HC-SR04 pins (BCM numbering) - change to match your wiring ---
FRONT_TRIG, FRONT_ECHO = 23, 24
LEFT_TRIG, LEFT_ECHO = 17, 27
RIGHT_TRIG, RIGHT_ECHO = 22, 5
SENSOR_MAX_DISTANCE_M = 2.0

# --- Steering servo ---
SERVO_PIN = 18
ANGLE_STRAIGHT = 110    # higher angle = more left, lower = more right
ANGLE_MAX_LEFT = 150
ANGLE_MAX_RIGHT = 60

# --- AT8236 motor driver pins (BCM) ---
AIN1_PIN, AIN2_PIN = 12, 13   # Motor A
BIN1_PIN, BIN2_PIN = 19, 26   # Motor B
PWM_FREQUENCY = 1000
DRIVE_SPEED = 0.6              # 0.0-1.0, tune on the actual car

# --- Corner turning ---
FRONT_TURN_TRIGGER = 25        # front obstacle closer than this -> consider turning
SIDE_OPEN_TRIGGER = 80         # a side reading above this counts as "open" (no wall)
TURN_COOLDOWN_S = 1.0          # ignore new turn triggers for this long after a turn starts
TURN_DURATION_S = 0.6          # how long the servo holds the turn angle before returning straight

# --- Wall-hugging correction (both sides ~even, small nudge toward the farther one) ---
CORRECTION_LOW = 40
CORRECTION_HIGH = 60
CORRECTION_DIFF_TRIGGER = 6
CORRECTION_GAIN = 0.4
CORRECTION_MAX_OFFSET = 15

# --- Camera / pillar detection ---
FRAME_SIZE = (640, 480)
MIN_AREA = 1500
BLOCK_REAL_CM = 5.0
FOCAL_LENGTH_PX = 400       # recalibrate for the AI Camera's actual lens (see notes below)
SHOW_PREVIEW = False         # True only with a monitor attached, for debugging
CAMERA_LOOP_DELAY_S = 0.05   # ~20 Hz
ROTATE_180 = True            # False if the camera isn't mounted upside down

COLOR_RANGES = {
    "RED": [
        (np.array([0, 100, 80]), np.array([8, 255, 255])),
        (np.array([172, 100, 80]), np.array([180, 255, 255])),
    ],
    "GREEN": [
        (np.array([38, 60, 50]), np.array([88, 255, 255])),
    ],
}
BOX_COLORS = {"RED": (0, 0, 255), "GREEN": (0, 255, 80)}

# --- Pillar avoidance ---
PILLAR_TRIGGER_DISTANCE_CM = 60
PILLAR_FOV_DEG = 30
PILLAR_AVOID_OFFSET = 25
PILLAR_AVOID_HOLD_S = 1.2
PILLAR_STEER_SIGN = {
    "RED": -1,    # steer toward ANGLE_MAX_RIGHT -> pillar ends up on the car's left
    "GREEN": +1,  # steer toward ANGLE_MAX_LEFT -> pillar ends up on the car's right
}

# --- Laps ---
LAPS_TARGET = 3
TURNS_PER_LAP = 4               # standard 4-corner WRO track; change if your track differs
TOTAL_TURNS_TARGET = LAPS_TARGET * TURNS_PER_LAP

LOOP_HZ = 20

# =========================================================================
# MOTOR DRIVER (AT8236)
# =========================================================================


class MotorDriver:
    def __init__(self):
        self.ain1 = PWMOutputDevice(AIN1_PIN, frequency=PWM_FREQUENCY)
        self.ain2 = PWMOutputDevice(AIN2_PIN, frequency=PWM_FREQUENCY)
        self.bin1 = PWMOutputDevice(BIN1_PIN, frequency=PWM_FREQUENCY)
        self.bin2 = PWMOutputDevice(BIN2_PIN, frequency=PWM_FREQUENCY)

    def _drive(self, pin_forward, pin_reverse, speed):
        speed = max(-1.0, min(1.0, speed))
        if speed > 0:
            pin_forward.value = speed
            pin_reverse.value = 0
        elif speed < 0:
            pin_forward.value = 0
            pin_reverse.value = -speed
        else:
            pin_forward.value = 0
            pin_reverse.value = 0

    def set_speed(self, speed):
        """Drive both motors together."""
        self._drive(self.ain1, self.ain2, speed)
        self._drive(self.bin1, self.bin2, speed)

    def stop(self):
        self.ain1.off()
        self.ain2.off()
        self.bin1.off()
        self.bin2.off()

    def close(self):
        self.stop()
        self.ain1.close()
        self.ain2.close()
        self.bin1.close()
        self.bin2.close()


# =========================================================================
# CAMERA / PILLAR DETECTION (runs in a background thread)
# =========================================================================

_pillar_lock = threading.Lock()
_latest_pillars = []   # list of detection dicts, updated by camera_loop()


def get_latest_pillars():
    with _pillar_lock:
        return list(_latest_pillars)


def get_mask(hsv, color):
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for (lo, hi) in COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, lo, hi)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
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
    cv2.rectangle(frame, (x, y), (x + w, y + h), bgr, 2)
    cs = 12
    for (px, py, sx, sy) in [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]:
        cv2.line(frame, (px, py), (px + cs * sx, py), bgr, 3)
        cv2.line(frame, (px, py), (px, py + cs * sy), bgr, 3)
    dist_str = f" ~{distance_cm}cm" if distance_cm is not None else ""
    angle_str = f" | {angle_deg:+.1f}deg" if angle_deg is not None else ""
    label = f"{color_name}{angle_str} | cx:{x + w // 2} cy:{y + h // 2}{dist_str}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.rectangle(frame, (x, y - th - 8), (x + tw + 4, y), bgr, -1)
    cv2.putText(frame, label, (x + 2, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)


def camera_loop():
    global _latest_pillars

    picam2 = Picamera2()
    # picamera2's "RGB888" format is actually delivered in BGR byte order
    # (a documented historical quirk) - which is exactly what OpenCV
    # expects, so no extra color conversion is needed here.
    config = picam2.create_preview_configuration(main={"size": FRAME_SIZE, "format": "RGB888"})
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

                cx = x + w // 2
                cy = y + h // 2
                angle_deg = estimate_angle_deg(cx, frame_width)
                distance_cm = estimate_distance(w)

                if SHOW_PREVIEW:
                    draw_box(frame, x, y, w, h, color_name, distance_cm, angle_deg)

                detected.append({
                    "color": color_name,
                    "x": cx, "y": cy, "width": w, "height": h,
                    "distance": distance_cm,
                    "angle_deg": angle_deg,   # + = right of center, - = left of center
                    "confidence": 1.0,
                    "timestamp": datetime.now(UTC).isoformat(),
                })

        with _pillar_lock:
            _latest_pillars = detected

        if SHOW_PREVIEW:
            cv2.imshow("Pillar Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        time.sleep(CAMERA_LOOP_DELAY_S)

    picam2.stop()
    if SHOW_PREVIEW:
        cv2.destroyAllWindows()


def start_camera_thread():
    t = threading.Thread(target=camera_loop, daemon=True)
    t.start()
    return t


# =========================================================================
# SENSORS + SERVO
# =========================================================================


def make_sensors():
    front = DistanceSensor(echo=FRONT_ECHO, trigger=FRONT_TRIG, max_distance=SENSOR_MAX_DISTANCE_M)
    left = DistanceSensor(echo=LEFT_ECHO, trigger=LEFT_TRIG, max_distance=SENSOR_MAX_DISTANCE_M)
    right = DistanceSensor(echo=RIGHT_ECHO, trigger=RIGHT_TRIG, max_distance=SENSOR_MAX_DISTANCE_M)
    return front, left, right


def make_servo():
    return AngularServo(
        SERVO_PIN,
        min_angle=0,
        max_angle=180,
        min_pulse_width=0.0005,
        max_pulse_width=0.0025,
    )


def read_cm(sensor):
    return sensor.distance * 100.0


# =========================================================================
# STEERING / LAP DECISION LOGIC
# =========================================================================


def pick_relevant_pillar(pillars):
    """Closest pillar that's near enough and roughly ahead to act on, or None."""
    candidates = [
        p for p in pillars
        if p["distance"] is not None
        and p["distance"] < PILLAR_TRIGGER_DISTANCE_CM
        and abs(p["angle_deg"]) < PILLAR_FOV_DEG
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: p["distance"])


class SteeringState:
    def __init__(self):
        self.turn_count = 0
        self.last_turn_time = 0.0
        self.turning_until = 0.0
        self.turn_angle_active = ANGLE_STRAIGHT
        self.avoiding_until = 0.0
        self.avoid_angle_active = ANGLE_STRAIGHT


def compute_steering(front, left, right, pillars, state):
    """
    Priority: in-progress corner turn > new corner turn > pillar avoidance
    > wall correction > straight. Mutates `state`, returns the angle.
    """
    now = time.monotonic()

    # 1. Finish an in-progress corner turn.
    if now < state.turning_until:
        return state.turn_angle_active

    # 2. Start a new corner turn if due.
    in_turn_cooldown = (now - state.last_turn_time) < TURN_COOLDOWN_S
    if not in_turn_cooldown and front < FRONT_TURN_TRIGGER:
        left_open = left > SIDE_OPEN_TRIGGER
        right_open = right > SIDE_OPEN_TRIGGER

        if left_open and not right_open:
            angle = ANGLE_MAX_LEFT
        elif right_open and not left_open:
            angle = ANGLE_MAX_RIGHT
        elif left_open and right_open:
            angle = ANGLE_MAX_RIGHT  # both clear, no signal which way - default right
        else:
            angle = None  # front blocked but no side open yet - not safe to turn

        if angle is not None:
            state.turn_count += 1
            state.turning_until = now + TURN_DURATION_S
            state.turn_angle_active = angle
            state.last_turn_time = now
            print(f"[TURN] #{state.turn_count} -> angle {angle} "
                  f"(front={front:.1f} left={left:.1f} right={right:.1f})")
            return angle

    # 3. Continue/start pillar avoidance.
    if now < state.avoiding_until:
        return state.avoid_angle_active

    pillar = pick_relevant_pillar(pillars)
    if pillar is not None:
        sign = PILLAR_STEER_SIGN.get(pillar["color"])
        if sign is not None:
            angle = ANGLE_STRAIGHT + sign * PILLAR_AVOID_OFFSET
            state.avoiding_until = now + PILLAR_AVOID_HOLD_S
            state.avoid_angle_active = angle
            print(f"[PILLAR] {pillar['color']} at {pillar['distance']}cm, "
                  f"{pillar['angle_deg']:+.1f}deg -> steering to {angle}")
            return angle

    # 4. Wall-hugging correction.
    both_in_band = (CORRECTION_LOW <= left <= CORRECTION_HIGH) and (CORRECTION_LOW <= right <= CORRECTION_HIGH)
    diff = left - right
    if both_in_band and abs(diff) >= CORRECTION_DIFF_TRIGGER:
        offset = diff * CORRECTION_GAIN
        offset = max(-CORRECTION_MAX_OFFSET, min(CORRECTION_MAX_OFFSET, offset))
        return ANGLE_STRAIGHT + offset

    # 5. Straight.
    return ANGLE_STRAIGHT


# =========================================================================
# MAIN
# =========================================================================


def main():
    front_sensor, left_sensor, right_sensor = make_sensors()
    servo = make_servo()
    servo.angle = ANGLE_STRAIGHT
    motors = MotorDriver()
    state = SteeringState()

    start_camera_thread()
    time.sleep(1.5)  # give the camera a moment to start producing frames

    print(f"Target: {TOTAL_TURNS_TARGET} turns ({LAPS_TARGET} laps x {TURNS_PER_LAP} turns/lap)")

    motors.set_speed(DRIVE_SPEED)

    try:
        while state.turn_count < TOTAL_TURNS_TARGET:
            front = read_cm(front_sensor)
            left = read_cm(left_sensor)
            right = read_cm(right_sensor)
            pillars = get_latest_pillars()

            angle = compute_steering(front, left, right, pillars, state)
            servo.angle = angle

            time.sleep(1.0 / LOOP_HZ)

        print(f"Reached {state.turn_count} turns ({LAPS_TARGET} laps). Stopping.")

    finally:
        motors.stop()
        servo.angle = ANGLE_STRAIGHT


if __name__ == "__main__":
    main()