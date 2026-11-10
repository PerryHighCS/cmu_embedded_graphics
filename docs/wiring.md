# EyePi hardware and display bring-up

## Board facts

| Item | Value |
|---|---|
| MCU | RP2040 |
| Flash | Winbond W25Q32JVUUIQ, 4 MB |
| Display | GC9A01, 240×240 round, 4-wire SPI |
| Expansion connector | A0, A1, 5 V, 3.3 V, GND |

## Display pins

| Display signal | RP2040 pin |
|---|---|
| SCK | GP18 |
| MOSI | GP19 |
| CS | GP17 |
| DC | GP16 |
| RST | GP20 |
| Backlight | GP21 |

Working settings: SPI 62.5 MHz, rotation 180.

To use different pins (for example a Pico on a breadboard), put overrides in
`CIRCUITPY/settings.toml`:

```toml
CMU_TFT_SCK = "GP10"
CMU_TFT_MOSI = "GP11"
CMU_TFT_CS = "GP9"
CMU_TFT_DC = "GP8"
CMU_TFT_RST = "GP12"
CMU_TFT_BL = "GP13"
CMU_TFT_ROTATION = 180
CMU_SPI_HZ = 62500000
```

## Bring-up test (milestone 1)

### Step 1: on the current EyePi firmware

1. Back up everything on `CIRCUITPY`.
2. Copy `tests/bringup_display.py` to `CIRCUITPY/code.py`.
3. Open the serial console and check the screen against the checklist
   below.

### Step 2: on CircuitPython 10

There's no EyePi firmware for CircuitPython 10 yet, so use the stock
Raspberry Pi Pico firmware. It sees only 2 MB of the 4 MB flash, so
`CIRCUITPY` will be about 1 MB. That's fine for testing.

1. Back up `CIRCUITPY` (flashing new firmware can erase it).
2. Download the CircuitPython 10.x UF2 for **Raspberry Pi Pico** from
   <https://circuitpython.org/board/raspberry_pi_pico/>.
3. Hold BOOTSEL while plugging in the EyePi, then copy the UF2 to the
   `RPI-RP2` drive.
4. Copy `tests/bringup_display.py` to `CIRCUITPY/code.py`.

To go back, flash `firmware/Firmware-eyePi-CircuitPython.uf2` from the
EyePi repo the same way.

### Checklist

On the screen:

- [ ] A thin white ring just inside the edge of the glass, evenly spaced all
      around. If it's off-center or clipped, the panel offset is wrong.
- [ ] A small yellow square at the top (12 o'clock). If it's somewhere else,
      change `CMU_TFT_ROTATION`.
- [ ] Three bars, left to right: **red, green, blue**. If red and blue are
      swapped, the BGR bit in the init sequence (`0x36` command) is wrong.
      If the colors look like negatives, flip inversion (`0x21` ↔ `0x20`).
- [ ] An orange triangle near the bottom.
- [ ] A white ball bouncing left and right, with no tearing or leftover
      trail.

In the serial console, record:

- [ ] `firmware` and `display` lines (which API was used)
- [ ] `board.A0 is board.GP26` and `board.A1 is board.GP27` (should both be
      `True`; the A0/A1 connector depends on it)
- [ ] `CIRCUITPY` size
- [ ] `free RAM` at startup
- [ ] `fps` and `free RAM` lines once the ball is moving

### Results

| Check | EyePi 9.0.0-alpha firmware | EyePi CircuitPython 10.3.1 (our build) |
|---|---|---|
| Ring centered | | |
| Rotation (square at top) | | |
| Colors red/green/blue | | |
| Display API used | old `displayio.FourWire/Display` | `fourwire`/`busdisplay` |
| USB VID/PID | 2E8A / 1003 | 2E8A / 1003 |
| A0 = GP26, A1 = GP27 | yes / yes | yes / yes |
| `CIRCUITPY` size | 2.98 MB | 2.98 MB (files kept after flashing) |
| Free RAM at start | 177,024 bytes | 151,088 bytes |
| Free RAM while running | 175,920 bytes (steady, no leak) | 150,000 bytes (steady, no leak) |
| FPS (one moving ball) | ~450 | ~382 |

On 10.3.1 the new `TFT_*`, `SDA` and `SCL` pin names all map to the right
GPIOs. The first 10.3.1 build was missing `board.I2C()`; fixed in the next
build.

FPS here is high because only the ball's small area changes each frame
(displayio sends only changed regions). A full-screen redraw will be much
slower; measure that when the renderer exists.

USB identity, confirmed in Windows Device Manager: `VID_2E8A&PID_1003`,
serial port shows as "USB Serial Device". Board ID `eyepi`, UID
`DE624823DF7F4A2B` (this unit).
