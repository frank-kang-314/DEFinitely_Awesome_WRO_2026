from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
from camera import camera_loop, get_latest_pillars
import threading
import time

ui = WebUI()
threading.Thread(target=camera_loop, args=(ui,), daemon=True).start()

WALL_FRONT_CM  = 20
PILLAR_NEAR_CM = 60
BALANCE_DIFF   = 8

last_cmd        = None
last_right_time = 0
RIGHT_DURATION  = 3.0   # seconds to hold right
COOLDOWN        = 4.0   # seconds to stay straight after a right turn

def send_steering(cmd):
    global last_cmd
    if cmd == last_cmd:
        return
    last_cmd = cmd
    try:
        Bridge.call("set_steering", cmd)
    except Exception as e:
        print("[SERVO ERR] " + str(e))

def hardware_loop():
    global last_right_time

    while True:
        try:
            data = Bridge.call("get_data")
            front, left, right = [int(float(x)) for x in data.split(",")]

            pillars = get_latest_pillars()
            closest = None
            if pillars:
                valid = [p for p in pillars if p["distance"] is not None and p["distance"] < PILLAR_NEAR_CM]
                if valid:
                    closest = min(valid, key=lambda p: p["distance"])

            # ── Steering logic ────────────────────────────
            now = time.time()
            in_cooldown = (now - last_right_time) < COOLDOWN

            if in_cooldown:
                cmd = "STRAIGHT"

            elif front < WALL_FRONT_CM or closest is not None or right > left + BALANCE_DIFF:
                # Trigger a right turn
                send_steering("RIGHT")
                print("| SERVO:  RIGHT (turning for " + str(RIGHT_DURATION) + "s)")
                time.sleep(RIGHT_DURATION)
                last_right_time = time.time()
                send_steering("STRAIGHT")
                time.sleep(0.1)
                continue

            else:
                cmd = "STRAIGHT"

            send_steering(cmd)

            # ── Camera print ──────────────────────────────
            if pillars:
                cam_lines = []
                for p in pillars:
                    c = p.get("color", "?")
                    d = p.get("distance", "?")
                    s = p.get("side", "?")
                    cam_lines.append(c + " " + str(d) + "cm " + s)
                cam_str = " | ".join(cam_lines)
            else:
                cam_str = "NONE"

            print("+---------------------------------")
            print("| F:" + str(front) + "cm  L:" + str(left) + "cm  R:" + str(right) + "cm")
            print("| SERVO:  " + str(last_cmd))
            print("| CAMERA: " + cam_str)
            print("+---------------------------------")

        except Exception as e:
            print("[ERR] " + str(e))

        time.sleep(0.1)

threading.Thread(target=hardware_loop, daemon=True).start()
App.run()