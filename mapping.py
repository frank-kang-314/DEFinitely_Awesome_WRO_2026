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

import multiprocessing

from datetime import datetime, UTC
import cv2
import time
import base64
import numpy as np
import threading

rect_types = {
    "no_collide_outer": "NO_COLLIDE_OUTER", #things you can't hit the outside of, like traffic signs
    "no_collide_inner": "NO_COLLIDE_INNER", #things you can't hit the inside of, like the outer walls)
    }

def main():
    car = Car()

    p1 = multiprocessing.Process(target=Ultrasonic.read_ultrasonic)
    p2 = multiprocessing.Process(target=Camera.read_camera)
    p3 = multiprocessing.Process(target=Car.drive)

    car.start()

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

class Map:
    __laps = 0 #Private variable
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

class Steering:
    def __init__(self):
        pass

    def start(self):
        pass

    def turn(self, angle: int):
        #Straight: 110
        #Left: 150
        #Right: 60
        pass

    def move(self, *, direction: str, speed: float):
        pass

    def brake(self):
        pass

class Ultrasonic:
    def __init__(self):
        pass

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
    _lock            = threading.Lock()
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

class Car:
    #Insert actual measurements when chassis is complete
    width, height = 20, 30 #in centimeters
    def __init__(self):
        pass
    def start(self):
        steering = Steering()

        camera = Camera()

        map = Map()
        map.setup()
    def drive(self, challenge_type):
        self.leave_parking_lot()

            #blahblahblah insert driving stuff here blahblahblah

        self.park()

    def leave_parking_lot(self):
        pass
    def park(self):
        pass

if __name__ == "__main__":
    main()