"""
AT8236 dual motor driver - Raspberry Pi 5 version
(converted from the Arduino AT8236 example - drive logic only;
 the serial test loop, LED blink, and auto-reverse demo from the
 original sketch were bench-test scaffolding and are left out)

Wiring (AT8236 -> Pi 5, BCM numbering - change to match your wiring):
    AIN1 -> GPIO 12
    AIN2 -> GPIO 13
    BIN1 -> GPIO 19
    BIN2 -> GPIO 26
    GND  -> Pi GND
    Motor power (the AT8236's VM/battery input) comes from your battery pack,
    NOT from the Pi - the Pi only supplies the logic-level PWM signals.

Optional wheel encoders (only needed if you want speed feedback - not
required for basic driving):
    E1A (left)  -> GPIO 6
    E1B (left)  -> GPIO 16
    E2A (right) -> GPIO 20
    E2B (right) -> GPIO 21

Requires:
    pip install gpiozero lgpio
"""

from gpiozero import PWMOutputDevice, DigitalInputDevice

# ----------------------------- CONFIG ----------------------------------

AIN1_PIN, AIN2_PIN = 12, 13   # Motor A (e.g. left)
BIN1_PIN, BIN2_PIN = 19, 26   # Motor B (e.g. right)

PWM_FREQUENCY = 1000          # Hz - higher = quieter motor whine

# Encoder pins (only used if you create a WheelEncoder)
ENCODER_L_A, ENCODER_L_B = 6, 16
ENCODER_R_A, ENCODER_R_B = 20, 21

# -------------------------------------------------------------------------


class MotorDriver:
    """
    Drives two DC motors through an AT8236 (or any similar dual H-bridge
    with two PWM inputs per motor, e.g. DRV8833/TB6612-style).

    speed values are -1.0 (full reverse) .. 0.0 (stop) .. 1.0 (full forward),
    matching the -1..1 convention used by set_speed() in the main controller.
    """

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

    def set_motor_a(self, speed):
        self._drive(self.ain1, self.ain2, speed)

    def set_motor_b(self, speed):
        self._drive(self.bin1, self.bin2, speed)

    def set_speed(self, speed):
        """Drive both motors together - use this for straight forward/reverse."""
        self.set_motor_a(speed)
        self.set_motor_b(speed)

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


class WheelEncoder:
    """
    Optional wheel speed feedback (quadrature encoder), converted from the
    original interrupt-driven pulse counting.

    Usage:
        enc = WheelEncoder(ENCODER_L_A, ENCODER_L_B)
        ...
        pulses = enc.read_and_reset()   # call this every ~10-50ms
        rpm = (pulses / PULSES_PER_REV) * (1000 / interval_ms) * 60
    """

    def __init__(self, pin_a, pin_b):
        self._count = 0
        self.pin_b = DigitalInputDevice(pin_b)
        self.pin_a = DigitalInputDevice(pin_a)
        self.pin_a.when_activated = self._on_edge
        self.pin_a.when_deactivated = self._on_edge

    def _on_edge(self):
        # direction determined by the other phase, same idea as the
        # original READ_ENCODER_L/R interrupt handlers
        if self.pin_a.value == self.pin_b.value:
            self._count += 1
        else:
            self._count -= 1

    def read_and_reset(self):
        pulses = self._count
        self._count = 0
        return pulses