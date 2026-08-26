"""
OVERALL HIERARCHY OF THE CODE: 

Main class: Car (General controls)
    * Start car
    * Leave parking lot (if applicable)
    * Perform main sequence
    * Park (if applicable)
    * Stop

Four systems: Steering (Actuators), Camera, Ultrasonic (Sensors), Map (Software)

Steering: 
    * Turn
    * Drive forward / backward
    * Stop

Camera: 
    * Read camera data
    * Output the data to other functions / classes
    
Ultrasonic: 
    * Read ultrasonic sensor data
    * Output the data to other functions / classes

Map: 
    * Create walls
    * Record seen obstacles
    * Update car position
    * Send instructions to steering


Processes needed:     

1. Ultrasonic sensor data
2. Camera data
3. Steering instructions & main control

"""

# ---------- IMPORT STATEMENTS ----------

from gpiozero import DistanceSensor, AngularServo

import multiprocessing

from datetime import datetime, UTC
import cv2
import time
import base64
import numpy as np
import threading

# ---------- VARIABLES ----------

rect_types = {
    "no_collide_outer": "NO_COLLIDE_OUTER", #things you can't hit the outside of, like traffic signs
    "no_collide_inner": "NO_COLLIDE_INNER", #things you can't hit the inside of, like the outer walls)
    }

pins = {
    "ULTRASONIC_FRONT_TRIG": 23, 
    "ULTRASONIC_FRONT_ECHO": 24,
    "ULTRASONIC_LEFT_TRIG": 17,
    "ULTRASONIC_LEFT_ECHO": 27,
    "ULTRASONIC_RIGHT_TRIG": 22,
    "ULTRASONIC_RIGHT_ECHO": 5,
    "SERVO":  18
}

ULTRASONIC_MAX_DISTANCE = 4

# ---------- MAIN FUNCTION ----------

def main():
    car = Car()

    # p1 = multiprocessing.Process(target=Car.read_ultrasonics)
    # p2 = multiprocessing.Process(target=Camera.read_camera)
    # p3 = multiprocessing.Process(target=Car.drive)

    car.start()

# ---------- CLASSES ----------

class Rect:
    def __init__(self, *, bottom_left_corner, width, height, type):
        self.bottom_left_corner = bottom_left_corner
        self.width = width
        self.height = height
        self.type = type 
        """
        Types include: 
        no_collide_outer (things you can't hit the outside of, like traffic signs)
        no_collide_inner (things you can't hit the inside of, like walls)

        (SEE rect_types VARIABLE ABOVE)
        
        """
        
class Wall(Rect):
    def __init__(self, **location: str):
        if location == "outer":
            self.bottom_left_corner = (0,0)
            self.width = 300
            self.height = 300
            self.type = rect_types["no_collide_inner"]            

class Block(Rect):
    def __init__(self, color, position):
        self.color = color
        self.position = position
    def update_position(self, **data):
        pass

class ParkingLot(Rect):
    def __init__(self):
        pass

class Motors:
    def __init__(self):
        pass

    def start(self):
        pass

    def move(self, *, direction: str, speed: float):
        pass

    def stop(self):
        pass

class Ultrasonic:
    #Run the read_sensor function to get the latest sensor data. 
    #Takes the latest five values to ensure that a single inaccurate reading doesn't affect the output.
    def __init__(self, *, echo, trig):
        self.sensor = DistanceSensor(echo, trig, max_distance=ULTRASONIC_MAX_DISTANCE)
        self.STOP_SIGNAL = False
        self.readings = []
        self.frequency = 20
        self.outlier_tolerance = 0.25
    def read_sensor(self):
        while True: 
            distance = self.sensor.distance * 100 #in centimeters
            self.readings.append(distance)
            if len(self.readings) >= 5:
                while len(self.readings) > 5: 
                    self.readings.pop(0)
            time.sleep(1 / self.frequency)
            if self.STOP_SIGNAL:
                break
    def get_data(self):
        if not self.is_outlier(self.readings[-1]):
            return self.readings[-1]
        else: 
            for i in range(-1, -11, -1):
                if not self.is_outlier(self.readings[i]):
                    return self.readings[i]
    def stop_sensor(self):
            self.STOP_SIGNAL = True
            
    def is_outlier(self, value):
        others_average = (sum(self.readings) - value) / (len(self.readings) - 1)
        if value > (1 + self.outlier_tolerance) * others_average or (1 - self.outlier_tolerance) * others_average:
            return True
        return False

class Camera:
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

    def __init__(self):
        pass

    def get_mask(self, hsv, color):
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for (lo, hi) in self.COLOR_RANGES[color]:
            mask |= cv2.inRange(hsv, lo, hi)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return mask

    def estimate_distance(self,pixel_width):
        if pixel_width <= 0:
            return None
        return round((self.BLOCK_REAL_CM * self.FOCAL_LENGTH_PX) / pixel_width, 1)

    def draw_box(self,frame, x, y, w, h, color_name, distance_cm=None, side=None):
        bgr = self.BOX_COLORS[color_name]
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
    _lock = threading.Lock()
    _latest_pillars  = []   # list of detection dicts

    def get_latest_pillars():
        with _lock:
            return list(_latest_pillars)

    def read_camera(self):
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
                mask = self.get_mask(hsv, color_name)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area < self.MIN_AREA:
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
                    distance_cm = self.estimate_distance(w)
    
                    self.draw_box(frame, x, y, w, h, color_name, distance_cm, side)
    
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
    def return_data(self):
        pass

class Servo:
    # Servo angles (degrees)
    ANGLE_STRAIGHT = 110
    ANGLE_MAX_LEFT = 150
    ANGLE_MAX_RIGHT = 60

    # Distance thresholds (cm)
    FRONT_TURN_TRIGGER = 25        # front obstacle closer than this -> consider turning
    SIDE_OPEN_TRIGGER = 80         # a side reading above this counts as "open" (no wall)

    CORRECTION_LOW = 40            # "both sides ~50ish" band, lower bound
    CORRECTION_HIGH = 60           # "both sides ~50ish" band, upper bound
    CORRECTION_DIFF_TRIGGER = 6    # if |left - right| >= this, nudge toward the farther side
    CORRECTION_GAIN = 0.4          # degrees of nudge per cm of difference (tune on the track)
    CORRECTION_MAX_OFFSET = 15     # cap how far a "slight correction" can push off straight

    TURN_COOLDOWN_S = 1.0          # ignore new turn triggers for this long after a turn starts
    TURN_DURATION_S = 0.6          # how long the servo holds the turn angle before returning straight

    LAPS_TARGET = 3
    TURNS_PER_LAP = 4              # standard 4-corner WRO track; change if your track differs
    TOTAL_TURNS_TARGET = LAPS_TARGET * TURNS_PER_LAP

    def make_servo():
        return AngularServo(
            pins["SERVO"],
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,   # 500us -> 0 degrees
            max_pulse_width=0.0025,   # 2500us -> 180 degrees
        )

class Car:
    #Insert actual measurements when chassis is complete
    width, height = 20, 30 #in centimeters
    LOOP_HZ = 20 # main loop rate
    def __init__(self):
        pass
    def start(self):
        self.camera = Camera()
        self.front_sensor = Ultrasonic(echo=pins["ULTRASONIC_A_ECHO"],trig=pins["ULTRASONIC_A_TRIG"])
        self.left_sensor = Ultrasonic(echo=pins["ULTRASONIC_B_ECHO"],trig=pins["ULTRASONIC_B_TRIG"])
        self.right_sensor = Ultrasonic(echo=pins["ULTRASONIC_C_ECHO"],trig=pins["ULTRASONIC_C_TRIG"])

    def compute_steering(front, left, right, last_turn_time, turn_count, turning_until, turn_angle_active):
        """
        Decide the servo angle and whether a turn/lap should be counted.
        Returns (angle, new_turn_count, new_turning_until, new_turn_angle_active)
        """
        now = time.monotonic()

        # If we're mid-turn, keep holding the turn angle until TURN_DURATION_S elapses.
        if now < turning_until:
            return turn_angle_active, turn_count, turning_until, turn_angle_active

        # Cooldown: don't evaluate a brand-new turn trigger too soon after the last one.
        in_cooldown = (now - last_turn_time) < Servo.TURN_COOLDOWN_S

        if not in_cooldown and front < Servo.FRONT_TURN_TRIGGER:
            left_open = left > Servo.SIDE_OPEN_TRIGGER
            right_open = right > Servo.SIDE_OPEN_TRIGGER

            if left_open and not right_open:
                # left side is clear -> turn left
                angle = Servo.ANGLE_MAX_LEFT
            elif right_open and not left_open:
                # right side is clear -> turn right
                angle = Servo.ANGLE_MAX_RIGHT
            elif left_open and right_open:
                # both sides clear: no signal for which way, default to right
                angle = Servo.ANGLE_MAX_RIGHT
            else:
                # front blocked but neither side reads "open" - can't safely turn yet,
                # go straight and let the car close in / a side reading update
                return Servo.ANGLE_STRAIGHT, turn_count, turning_until, Servo.ANGLE_STRAIGHT

            turn_count += 1
            turning_until = now + Servo.TURN_DURATION_S
            return angle, turn_count, turning_until, angle

        # Not turning: check the "both sides ~50cm but uneven" correction case
        both_in_band = (Servo.CORRECTION_LOW <= left <= Servo.CORRECTION_HIGH) and (Servo.CORRECTION_LOW <= right <= Servo.CORRECTION_HIGH)
        diff = left - right

        if both_in_band and abs(diff) >= Servo.CORRECTION_DIFF_TRIGGER:
            # nudge toward the side that's farther away (the bigger reading)
            offset = diff * Servo.CORRECTION_GAIN
            offset = max(-Servo.CORRECTION_MAX_OFFSET, min(Servo.CORRECTION_MAX_OFFSET, offset))
            # left is bigger (diff > 0) -> steer left (toward larger angle, since left=150)
            angle = Servo.ANGLE_STRAIGHT + offset
            return angle, turn_count, turning_until, Servo.ANGLE_STRAIGHT

        return Servo.ANGLE_STRAIGHT, turn_count, turning_until, Servo.ANGLE_STRAIGHT

    def drive_open(self):
        self.servo.angle = Servo.ANGLE_STRAIGHT

        turn_count = 0
        last_turn_time = 0.0
        turning_until = 0.0

        turn_angle_active = Servo.ANGLE_STRAIGHT

        print(f"Target: {Servo.TOTAL_TURNS_TARGET} turns ({Servo.LAPS_TARGET} laps x {Servo.TURNS_PER_LAP} turns/lap)")

        Motors.move(direction="forward", speed=0.6)  # start moving forward - tune this value

        try:
            while turn_count < Servo.TOTAL_TURNS_TARGET:
                front = self.front_sensor.read_sensor()
                left = self.left_sensor.read_sensor()
                right = self.right_sensor.read_sensor()

                was_turning = time.monotonic() < turning_until

                angle, turn_count, turning_until, turn_angle_active = self.compute_steering(
                    front, left, right, last_turn_time, turn_count, turning_until, turn_angle_active
                )

                if not was_turning and time.monotonic() < turning_until:
                    # a new turn just started this iteration
                    last_turn_time = time.monotonic()
                    print(f"Turn #{turn_count} -> angle {angle}  (front={front:.1f} left={left:.1f} right={right:.1f})")

                self.servo.angle = angle
                time.sleep(1.0 / Servo.LOOP_HZ)

            print(f"Reached {turn_count} turns ({Servo.LAPS_TARGET} laps). Stopping.")

        finally:
            Motors.stop()
            self.angle = Servo.ANGLE_STRAIGHT


    def drive_obstacle(self):
        self.map = Map()
        self.map.setup()

        parking_lot_detected = None
        if parking_lot_detected:
            self.leave_parking_lot()
        while self.map.laps < 12:
            if something:
                pass
            else: 
                move_straight()
            

        self.park()

    def move_straight():
        
    def leave_parking_lot(self):
        pass
    def park(self):
        pass

class Map:
    laps = 0
    track_width = 300

    #Coordinates range from (0,0) (bottom left) to (300,300) (top right)

    block_positions =((100,40), (100,60), (150,40), (150,60), (200,40), (200,60), (40,100), (60,100), (40,150), (60,150), (40,200), (60,200), (100,240), (100,260), (150,240), (150,260), (200,240), (200,260), (240,100), (260,100), (240,150), (260,150), (240,200), (260,200))

    def __init__(self):
        pass
    def setup(self):
        #This is the list where all future objects on the map will be added
        self.objects = []

        self.objects.append(Wall(location = "outer"))

        #Set challenge type (open/obstacle) and direction (clockwise/counterclockwise)



        #Set current position

        #Start looking for obstacles
        pass
    def add(self):
        #Add new objects as the car discovers more of the track
        pass
        
    def recalibrate(self):
        pass
    def check_laps(self):
        return self.__laps
    def increment_laps(self):
        pass

if __name__ == "__main__":
    main()