"""

Requires:
    pip install gpiozero lgpio
    (lgpio is the GPIO backend gpiozero needs on Pi 5 - RPi.GPIO does not
    work on Pi 5's new GPIO chip)

Run:
    python3 wro_controller.py
"""

import time
from gpiozero import DistanceSensor, AngularServo

# ----------------------------- CONFIG ----------------------------------

FRONT_TRIG, FRONT_ECHO = 23, 24
LEFT_TRIG, LEFT_ECHO = 17, 27
RIGHT_TRIG, RIGHT_ECHO = 22, 5

SENSOR_MAX_DISTANCE_M = 2.0    # gpiozero needs an upper bound; readings beyond
                                # this report as this max. 2m is plenty for indoor track walls.

SERVO_PIN = 18                 # BCM pin driving the steering servo

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

LOOP_HZ = 20                   # main loop rate

# -------------------------------------------------------------------------


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
        min_pulse_width=0.0005,   # 500us -> 0 degrees
        max_pulse_width=0.0025,   # 2500us -> 180 degrees
    )


def set_speed(speed):
    """
    Placeholder for your motor driver.
    speed: -1.0 (full reverse) .. 0.0 (stop) .. 1.0 (full forward)
    Fill in with your actual motor driver GPIO pins / PWM calls.
    """
    pass


def read_cm(sensor):
    """gpiozero DistanceSensor.distance is in meters -> convert to cm."""
    return sensor.distance * 100.0


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
    in_cooldown = (now - last_turn_time) < TURN_COOLDOWN_S

    if not in_cooldown and front < FRONT_TURN_TRIGGER:
        left_open = left > SIDE_OPEN_TRIGGER
        right_open = right > SIDE_OPEN_TRIGGER

        if left_open and not right_open:
            # left side is clear -> turn left
            angle = ANGLE_MAX_LEFT
        elif right_open and not left_open:
            # right side is clear -> turn right
            angle = ANGLE_MAX_RIGHT
        elif left_open and right_open:
            # both sides clear: no signal for which way, default to right
            angle = ANGLE_MAX_RIGHT
        else:
            # front blocked but neither side reads "open" - can't safely turn yet,
            # go straight and let the car close in / a side reading update
            return ANGLE_STRAIGHT, turn_count, turning_until, ANGLE_STRAIGHT

        turn_count += 1
        turning_until = now + TURN_DURATION_S
        return angle, turn_count, turning_until, angle

    # Not turning: check the "both sides ~50cm but uneven" correction case
    both_in_band = (CORRECTION_LOW <= left <= CORRECTION_HIGH) and (CORRECTION_LOW <= right <= CORRECTION_HIGH)
    diff = left - right

    if both_in_band and abs(diff) >= CORRECTION_DIFF_TRIGGER:
        # nudge toward the side that's farther away (the bigger reading)
        offset = diff * CORRECTION_GAIN
        offset = max(-CORRECTION_MAX_OFFSET, min(CORRECTION_MAX_OFFSET, offset))
        # left is bigger (diff > 0) -> steer left (toward larger angle, since left=150)
        angle = ANGLE_STRAIGHT + offset
        return angle, turn_count, turning_until, ANGLE_STRAIGHT

    return ANGLE_STRAIGHT, turn_count, turning_until, ANGLE_STRAIGHT


def main():
    front_sensor, left_sensor, right_sensor = make_sensors()
    servo = make_servo()
    servo.angle = ANGLE_STRAIGHT

    turn_count = 0
    last_turn_time = 0.0
    turning_until = 0.0
    turn_angle_active = ANGLE_STRAIGHT

    print(f"Target: {TOTAL_TURNS_TARGET} turns ({LAPS_TARGET} laps x {TURNS_PER_LAP} turns/lap)")

    set_speed(0.6)  # start moving forward - tune this value

    try:
        while turn_count < TOTAL_TURNS_TARGET:
            front = read_cm(front_sensor)
            left = read_cm(left_sensor)
            right = read_cm(right_sensor)

            was_turning = time.monotonic() < turning_until

            angle, turn_count, turning_until, turn_angle_active = compute_steering(
                front, left, right, last_turn_time, turn_count, turning_until, turn_angle_active
            )

            if not was_turning and time.monotonic() < turning_until:
                # a new turn just started this iteration
                last_turn_time = time.monotonic()
                print(f"Turn #{turn_count} -> angle {angle}  (front={front:.1f} left={left:.1f} right={right:.1f})")

            servo.angle = angle
            time.sleep(1.0 / LOOP_HZ)

        print(f"Reached {turn_count} turns ({LAPS_TARGET} laps). Stopping.")

    finally:
        set_speed(0.0)
        servo.angle = ANGLE_STRAIGHT


if __name__ == "__main__":
    main()