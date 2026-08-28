"""
Motor test - single file, no other files needed.

Drives both motors forward for 5s, stops for 3s, reverses for 5s.
Use this to confirm your AT8236 wiring/direction before running anything else.

Wiring (AT8236 -> Pi 5, BCM numbering - change these 4 pins to match your wiring):
    AIN1 -> GPIO 12
    AIN2 -> GPIO 13
    BIN1 -> GPIO 19
    BIN2 -> GPIO 26
    GND  -> Pi GND
    Motor power comes from your battery pack into the AT8236 - NOT from the Pi.

Requires:
    pip install gpiozero lgpio

Run:
    python3 motor_test.py
"""

import time
from gpiozero import PWMOutputDevice

# ----------------------------- CONFIG ----------------------------------

AIN1_PIN, AIN2_PIN = 12, 13   # Motor A
BIN1_PIN, BIN2_PIN = 19, 26   # Motor B

PWM_FREQUENCY = 1000           # Hz - higher = quieter motor whine
SPEED = 0.6                    # 0.0 - 1.0, lower if it's too fast/jerky on the bench

# -------------------------------------------------------------------------


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


def main():
    motors = MotorDriver()
    try:
        print("Forward...")
        motors.set_speed(SPEED)
        time.sleep(5)

        print("Stop...")
        motors.stop()
        time.sleep(3)

        print("Reverse...")
        motors.set_speed(-SPEED)
        time.sleep(5)

        print("Stop.")
        motors.stop()

    finally:
        motors.close()


if __name__ == "__main__":
    main()