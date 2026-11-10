# bringup_display.py - Milestone 1 hardware check for the EyePi display.
#
# Copy to the board as CIRCUITPY/code.py. No libraries needed: it uses only
# modules built into CircuitPython (displayio, vectorio, busio, ...).
#
# Works on CircuitPython 10 (stock Raspberry Pi Pico firmware) and on the
# original EyePi 9.0.0-alpha firmware, which still uses the older displayio
# class names.
#
# What to look for on the screen (see docs/wiring.md for the checklist):
#   - a thin white ring just inside the edge of the round glass
#   - a small yellow square at 12 o'clock (top), which checks rotation
#   - three bars, left to right: RED, GREEN, BLUE (checks color order)
#   - a white ball bouncing across the middle
# The serial console prints board facts, then frame rate and free memory.

import gc
import os
import time

import board
import busio
import displayio
import microcontroller
import vectorio

# ----------------------------------------------------------- Settings
# EyePi wiring (from github.com/mrbdahlem/EyePi eye.py). These are used even
# on stock Pico firmware, which reports the board as a Pico. Override any of
# them in CIRCUITPY/settings.toml, e.g.  CMU_TFT_SCK = "GP10"


def _pin(key, default):
    name = os.getenv(key) or default
    return getattr(board, name)


TFT_SCK = _pin('CMU_TFT_SCK', 'GP18')
TFT_MOSI = _pin('CMU_TFT_MOSI', 'GP19')
TFT_CS = _pin('CMU_TFT_CS', 'GP17')
TFT_DC = _pin('CMU_TFT_DC', 'GP16')
TFT_RST = _pin('CMU_TFT_RST', 'GP20')
TFT_BL = _pin('CMU_TFT_BL', 'GP21')
ROTATION = int(os.getenv('CMU_TFT_ROTATION') or 180)
SPI_HZ = int(os.getenv('CMU_SPI_HZ') or 62_500_000)

WIDTH = HEIGHT = 240

# GC9A01 init sequence, from EyePi's gc9a01.py
# (Tyler Crumpton, CircuitPython_GC9A01, MIT license).
# Format: command, (length | 0x80 if a delay byte follows), data..., [delay ms]
_INIT_SEQUENCE = bytes(
    b"\xFE\x00"
    b"\xEF\x00"
    b"\xB6\x02\x00\x00"
    b"\x36\x01\x48"              # MADCTL: column order + BGR
    b"\x3a\x01\x05"              # 16 bits per pixel
    b"\xC3\x01\x13"
    b"\xC4\x01\x13"
    b"\xC9\x01\x22"
    b"\xF0\x06\x45\x09\x08\x08\x26\x2a"
    b"\xF1\x06\x43\x70\x72\x36\x37\x6f"
    b"\xF2\x06\x45\x09\x08\x08\x26\x2a"
    b"\xF3\x06\x43\x70\x72\x36\x37\x6f"
    b"\x66\x0a\x3c\x00\xcd\x67\x45\x45\x10\x00\x00\x00"
    b"\x67\x0a\x00\x3c\x00\x00\x00\x01\x54\x10\x32\x98"
    b"\x74\x07\x10\x85\x80\x00\x00\x4e\x00"
    b"\x98\x02\x3e\x07"
    b"\x35\x00"                  # tearing effect line on
    b"\x21\x00"                  # display inversion on
    b"\x11\x80\x78"              # sleep out, wait 120 ms
    b"\x29\x80\x14"              # display on, wait 20 ms
    b"\x2a\x04\x00\x00\x00\xef"  # columns 0-239
    b"\x2b\x04\x00\x00\x00\xef"  # rows 0-239
)

# CircuitPython 9+ moved these classes out of displayio.
try:
    from fourwire import FourWire
    from busdisplay import BusDisplay
    API = 'fourwire/busdisplay (CircuitPython 9+)'
except ImportError:
    FourWire = displayio.FourWire
    BusDisplay = displayio.Display
    API = 'displayio.FourWire/Display (old API)'


# ------------------------------------------------------- Board facts

def report():
    print()
    print('=== EyePi display bring-up ===')
    print('firmware :', os.uname().version)
    print('machine  :', os.uname().machine)
    print('board_id :', getattr(board, 'board_id', '?'))
    print('cpu MHz  :', microcontroller.cpu.frequency // 1_000_000)
    fs = os.statvfs('/')
    print('CIRCUITPY: %.2f MB' % (fs[0] * fs[2] / 1_048_576))
    print('display  :', API)
    for name, gp in (('A0', 'GP26'), ('A1', 'GP27')):
        if hasattr(board, name) and hasattr(board, gp):
            same = getattr(board, name) is getattr(board, gp)
            print('board.%s is board.%s: %s' % (name, gp, same))
        else:
            print('board.%s or board.%s missing' % (name, gp))
    print('builtin DISPLAY:', hasattr(board, 'DISPLAY'))
    gc.collect()
    print('free RAM :', gc.mem_free())


# ------------------------------------------------------------ Display

def make_display():
    displayio.release_displays()
    spi = busio.SPI(clock=TFT_SCK, MOSI=TFT_MOSI)
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS,
                   reset=TFT_RST, baudrate=SPI_HZ)
    return BusDisplay(bus, _INIT_SEQUENCE, width=WIDTH, height=HEIGHT,
                      rotation=ROTATION, backlight_pin=TFT_BL,
                      brightness=1.0, auto_refresh=False)


def solid(color):
    palette = displayio.Palette(1)
    palette[0] = color
    return palette


def build_scene(root):
    # Visible-area ring: white circle with a black one just inside it.
    root.append(vectorio.Circle(pixel_shader=solid(0xFFFFFF), radius=119,
                                x=120, y=120))
    root.append(vectorio.Circle(pixel_shader=solid(0x000000), radius=116,
                                x=120, y=120))
    # Rotation marker at 12 o'clock.
    root.append(vectorio.Rectangle(pixel_shader=solid(0xFFFF00), width=12,
                                   height=12, x=114, y=8))
    # Color order bars: red, green, blue from left to right.
    for i, color in enumerate((0xFF0000, 0x00FF00, 0x0000FF)):
        root.append(vectorio.Rectangle(pixel_shader=solid(color), width=40,
                                       height=50, x=60 + 40 * i, y=40))
    # A filled triangle, to check vectorio.Polygon.
    root.append(vectorio.Polygon(pixel_shader=solid(0xFF8000),
                                 points=[(0, 40), (40, 40), (20, 0)],
                                 x=100, y=170))
    ball = vectorio.Circle(pixel_shader=solid(0xFFFFFF), radius=10,
                           x=40, y=130)
    root.append(ball)
    return ball


def main():
    report()
    display = make_display()
    root = displayio.Group()
    display.root_group = root
    ball = build_scene(root)
    display.refresh()
    print('Scene drawn. Check the screen against docs/wiring.md.')

    dx = 3
    frames = 0
    start = time.monotonic_ns()
    while True:
        ball.x += dx
        if ball.x < 40 or ball.x > 200:
            dx = -dx
        display.refresh()
        frames += 1
        if frames == 200:
            seconds = (time.monotonic_ns() - start) / 1e9
            gc.collect()
            print('fps: %.1f  free RAM: %d' % (frames / seconds,
                                               gc.mem_free()))
            frames = 0
            start = time.monotonic_ns()


main()
