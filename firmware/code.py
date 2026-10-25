import board
import busio
import digitalio
import neopixel

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC, make_key
from kmk.scanners import DiodeOrientation
from kmk.modules import Module

from adafruit_mpr121 import MPR121


# --------------------------------------------------
# Configuration
# --------------------------------------------------

NUM_LEDS = 6

COLOURS = [
    (255, 0, 0),       # Red
    (0, 255, 0),       # Green
    (0, 0, 255),       # Blue
    (255, 255, 0),     # Yellow
    (255, 0, 255),     # Magenta
    (0, 255, 255),     # Cyan
    (255, 255, 255),   # White
    (0, 0, 0),         # Off
]

# Use the pin names exposed by your CircuitPython board.
# On builds that expose IO aliases, board.IO2 etc. may
# be used instead of board.GP2.
def pin(n):
    return getattr(board, f"IO{n}", getattr(board, f"GP{n}", None))


# --------------------------------------------------
# LEDs
# --------------------------------------------------

leds = neopixel.NeoPixel(
    pin(1),
    NUM_LEDS,
    brightness=0.15,
    auto_write=True,
)

led_indices = [0] * NUM_LEDS


def cycle_led(index):
    led_indices[index] = (led_indices[index] + 1) % len(COLOURS)
    leds[index] = COLOURS[led_indices[index]]
    print("Matrix key:", index, "LED colour:", COLOURS[led_indices[index]])


# --------------------------------------------------
# I2C and MPR121
# --------------------------------------------------

i2c = busio.I2C(scl=pin(12), sda=pin(11))
mpr = MPR121(i2c)

irq = digitalio.DigitalInOut(pin(13))
irq.direction = digitalio.Direction.INPUT
irq.pull = digitalio.Pull.UP


# --------------------------------------------------
# Individual switches
# --------------------------------------------------

switches = []

for gpio, name in [(44, "RX switch"), (43, "TX switch")]:
    sw = digitalio.DigitalInOut(pin(gpio))
    sw.direction = digitalio.Direction.INPUT
    sw.pull = digitalio.Pull.UP
    switches.append((sw, name))


# --------------------------------------------------
# Rotary encoders
# --------------------------------------------------

# Each encoder is represented as (A, B, name).
encoders = []

for a_gpio, b_gpio, name in [
    (8, 7, "Encoder 1"),
    (10, 9, "Encoder 2"),
]:
    a = digitalio.DigitalInOut(pin(a_gpio))
    b = digitalio.DigitalInOut(pin(b_gpio))

    a.direction = digitalio.Direction.INPUT
    b.direction = digitalio.Direction.INPUT
    a.pull = digitalio.Pull.UP
    b.pull = digitalio.Pull.UP

    encoders.append((a, b, name))


# --------------------------------------------------
# KMK hardware test module
# --------------------------------------------------

class HardwareTest(Module):
    def __init__(self):
        self.switch_states = [True, True]
        self.encoder_states = []
        self.irq_active = False

        for a, b, _ in encoders:
            self.encoder_states.append(
                (a.value << 1) | b.value
            )

    def before_matrix_scan(self, keyboard):
        # Individual switches: active LOW.
        for i, (sw, name) in enumerate(switches):
            pressed = not sw.value

            if pressed and self.switch_states[i]:
                print(name, "pressed")

            self.switch_states[i] = not pressed

        # Simple quadrature encoder decoder.
        # A complete Gray-code cycle indicates one detent.
        transitions = {
            (0, 1): 1,  (1, 3): 1,
            (3, 2): 1,  (2, 0): 1,
            (1, 0): -1, (3, 1): -1,
            (2, 3): -1, (0, 2): -1,
        }

        for i, (a, b, name) in enumerate(encoders):
            current = (a.value << 1) | b.value
            previous = self.encoder_states[i]

            delta = transitions.get((previous, current), 0)

            if delta:
                print(name, "clockwise" if delta > 0 else "anticlockwise")

            self.encoder_states[i] = current

        # MPR121: check the interrupt line, not every
        # electrode's state on every scan.
        #
        # The interrupt is normally active LOW.
        if not irq.value:
            if not self.irq_active:
                touched = []

                for i in range(12):
                    if mpr[i].value:
                        touched.append(i)

                if touched:
                    print("MPR121 touched electrodes:", touched)

                self.irq_active = True
        else:
            self.irq_active = False


# --------------------------------------------------
# KMK keyboard and matrix
# --------------------------------------------------

keyboard = KMKKeyboard()

keyboard.col_pins = (
    pin(2),
    pin(3),
    pin(4),
)

keyboard.row_pins = (
    pin(5),
    pin(6),
)

keyboard.diode_orientation = DiodeOrientation.COL2ROW

# Custom matrix keys: each press advances one LED.
def make_led_key(index):
    return make_key(
        names=(f"LED_TEST_{index}",),
        on_press=lambda key, keyboard: cycle_led(index),
    )


keyboard.keymap = [
    [
        make_led_key(0),
        make_led_key(1),
        make_led_key(2),
        make_led_key(3),
        make_led_key(4),
        make_led_key(5),
    ]
]

keyboard.modules.append(HardwareTest())

print("Hardware test ready.")
keyboard.go()
