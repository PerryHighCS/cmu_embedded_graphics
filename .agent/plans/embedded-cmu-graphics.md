# Plan: Embedded CMU Graphics for RP2040 + GC9A01 round display

Status: draft · Created 2026-11-10

## 1. Goal

Build a CircuitPython library, `cmu_embedded_graphics`, that lets students
write CMU-Graphics-style programs (`onAppStart`, `redrawAll`, `onStep`,
`onKeyPress`, `drawRect`, `drawCircle`, `drawLabel`, ...) and run them on
the **EyePi** board: an RP2040 wired to a 1.28" 240×240 round GC9A01 TFT
over 4-wire SPI (see [mrbdahlem/EyePi](https://github.com/mrbdahlem/EyePi)).

Follow the pattern of [perryhighcs/cmu_playground.py](https://github.com/perryhighcs/cmu_playground.py):

- One student file, `code.py`, that starts with
  `from cmu_embedded_graphics import *` and ends with `runApp()`.
- The framework owns the event loop, finds callbacks by name, and enforces
  MVC rules with clear errors (`MVCError`).
- A Windows `build.cmd` / `deploy.cmd` workflow that compiles the `.mpy` and
  copies it to `CIRCUITPY`.
- A GitHub Actions workflow and `tools/build_frozen.sh` that freeze the
  library into a custom CircuitPython UF2.
- A student-facing `README.md` API reference in the same plain style.

Stretch goal: a student program that uses only the supported subset should
also run in desktop `cmu_graphics` (CS3 / 15-112 mode) by changing only the
import line, apart from the smaller 240×240 canvas.

## 2. What we reuse from cmu_playground

| cmu_playground | This project |
|---|---|
| `App` with `__setattr__` guard, read-only `elapsedTime`, `stepsPerSecond`, `running` | Same, plus `width`, `height`, `paused`, `background` |
| Phases `INTERNAL` / `CONTROLLER` / `VIEW` | Same; draw functions only allowed in `VIEW` (`redrawAll`) |
| `updateAll(app)` view function | `redrawAll(app)` (CMU name) |
| `Hardware` class wraps pins | `Display` (GC9A01 + displayio) and `Inputs` classes |
| `Runtime.run()` tick loop, skips missed steps, `_ticksDiff` wraparound | Same loop; redraw only after an event changed state |
| `build.cmd`, `deploy.cmd`, `tools/build_frozen.sh`, `frozen-firmware.yml` | Same structure, retargeted to `ports/raspberrypi` |
| `tests/test_playground_*.py` on-device scripts | Same idea, plus a desktop test harness |

## 3. Hardware

Target board: **EyePi** (RP2040 + GC9A01). Facts below come from the EyePi
repo's `eye.py`, `gc9a01.py`, and the strings in its UF2 firmware.

- **MCU:** RP2040 (264 KB SRAM).
- **Flash:** Winbond **W25Q32JVUUIQ**: 32 Mbit = **4 MB**, QSPI, USON
  package. `CIRCUITPY` shows 2.97 MB (4 MB minus about 1 MB for firmware).
  In `mpconfigboard.mk`, use `EXTERNAL_FLASH_DEVICES = "W25Q32JVxQ"` (the
  package letters don't matter; check the name exists in the pinned
  CircuitPython's external flash device list).
- **Existing firmware:** custom CircuitPython build; `os.uname().machine` is
  `"EyePi with rp2040"`, version string
  `9.0.0-alpha.1-31-g54fe3b023 on 2023-09-07`. That commit is upstream
  `adafruit/circuitpython` main. **The `EyePi` board definition
  (`ports/raspberrypi/boards/eyepi/`) isn't published** (not upstream, not
  in `mrbdahlem/circuitpython`); it only exists in the UF2 and possibly on
  a local machine.
- **USB identity in the firmware** (read from the UF2): manufacturer
  `"Brian Dahlem"`, product `"EyePi"`, VID **0x2E8A** (Raspberry Pi),
  PID **0x1003**. Confirmed on hardware 2026-11-10 (Windows shows
  `USB\VID_2E8A&PID_1003`).
- **Confirmed on hardware (2026-11-10, EyePi firmware):** `board.A0` is
  GP26 and `board.A1` is GP27; free RAM ~177 KB at start; the display test
  runs with the EyePi pins. See `docs/wiring.md` for results.
- **Board pin names in the firmware:** `GP0`–`GP28`, `A0`–`A3`, `LED`,
  `VOLTAGE_MONITOR`, `MISO`, `MOSI`: a Pico-style pin map. On the RP2040,
  `A0`/`A1` are normally `GP26`/`GP27` (ADC0/ADC1). Verify on hardware with
  `board.A0 is board.GP26`.
- **Display:** GC9A01, 240×240, RGB565, round visible area (corners outside
  a 120 px radius circle aren't visible). SPI write-only, no MISO.
- **Display wiring (from `eye.py`, EyePi branch):**

| Display signal | RP2040 pin | Notes |
|---|---|---|
| SCK | GP18 | SPI0 SCK |
| MOSI | GP19 | SPI0 TX |
| CS | GP17 | |
| DC | GP16 | |
| RST | GP20 | |
| BL | GP21 | Backlight; PWM-capable for brightness |

- **Display settings that work:** `baudrate=62_500_000`, `rotation=180`,
  `width=height=240`. The init sequence is in EyePi's `gc9a01.py` (Tyler
  Crumpton's driver, MIT), including `0x21` display inversion ON. Check
  that `adafruit_gc9a01a` gives the same colors; if not, use the EyePi
  sequence.
- **Expansion connector:** `A0`, `A1`, 5 V, 3.3 V, GND. The planned
  **I²C** d-pad connects here. On the RP2040, GP26 = I2C1 SDA and GP27 =
  I2C1 SCL, so if `A0`/`A1` are GP26/GP27 the connector is I²C-capable
  (`busio.I2C(scl=board.A1, sda=board.A0)`). Pull-ups must go to 3.3 V,
  not 5 V (RP2040 pins aren't 5 V tolerant).
- **Display confirmed on hardware (2026-11-10, our 10.3.1 build):**
  centered ring, correct rotation, red/green/blue in order, smooth
  animation with the EyePi pins, init sequence, 62.5 MHz and rotation 180.
- Defaults are the EyePi pins **regardless of firmware name**. On stock
  Pico firmware the EyePi reports itself as a Pico, so EyePi's own
  detect-by-name logic would pick the wrong pins. Allow overrides with `os.getenv()` from
  `settings.toml` (`CMU_TFT_SCK`, `CMU_TFT_MOSI`, `CMU_TFT_CS`,
  `CMU_TFT_DC`, `CMU_TFT_RST`, `CMU_TFT_BL`, `CMU_TFT_ROTATION`,
  `CMU_SPI_HZ`) so a plain Pico on a breadboard also works. EyePi's code
  already lists a Pico wiring (GP10/11/12/8/9/13) we can use as the
  documented alternative.

### API changes since the EyePi code

EyePi targets CircuitPython 8/early-9 APIs. In current CircuitPython (9+):
`displayio.FourWire` → `fourwire.FourWire`, `displayio.Display` →
`busdisplay.BusDisplay`, and `display.show(group)` →
`display.root_group = group`. The new library uses the current names.

## 4. Key design decisions

### 4.1 API style: CS3 immediate mode first

CMU graphics has two styles:

1. **CS3 / 15-112 mode:** `onAppStart(app)`, `redrawAll(app)`,
   `drawRect(...)`. Same MVC shape as cmu_playground.
2. **CS Academy CS1 retained mode:** `Rect(...)` objects that persist,
   `onKeyPress(key)` with no `app`.

Decided: **this version is CS3 mode only.** CS1 retained mode is a future
option (phase 5). Keep the shape-to-primitive code separate from the
CS3 draw functions so retained mode can reuse it later.

### 4.2 Module name

Decided: **`cmu_embedded_graphics`** (`cmu_embedded_graphics.py`,
`from cmu_embedded_graphics import *`). It's clearly different from the
desktop `cmu_graphics` package, and moving a program to the desktop only
means changing the import line.

### 4.2a Display set up in firmware (board.DISPLAY)

Since we're building custom EyePi firmware anyway, the board definition's
`board.c` can initialize the GC9A01 at boot and expose `board.DISPLAY`, as
Adafruit boards with built-in screens do. Benefits: the serial console and
error tracebacks show on the round screen with no student code, no Python
driver needs freezing, and less RAM is used. The library uses
`board.DISPLAY` when it exists and otherwise builds the display itself
(stock firmware / plain Pico).

### 4.3 Renderer: displayio + vectorio with a shape pool

- Use CircuitPython's built-in `displayio`, `fourwire`, `vectorio`,
  `bitmaptools`, and the `adafruit_gc9a01a` driver (init sequence only).
- `displayio` only pushes dirty regions over SPI, so we don't keep a
  115 KB RGB565 framebuffer in Python RAM.
- `display.auto_refresh = False`; the runtime calls `display.refresh()` once
  after each `redrawAll`.
- **Shape pool:** `redrawAll` runs from scratch every frame, but creating
  new `vectorio` objects each frame would churn the heap. Instead, each draw
  call claims the next slot in a pool kept in a `displayio.Group`:
  - Same kind as last frame → update its properties in place (x, y, radius,
    points, palette color).
  - Different kind → replace the object at that group index.
  - Unused slots at the end of a frame → `hidden = True`.
  - Z-order = draw order, as in CMU.
- Mapping CMU shapes to primitives:

| CMU call | Primitive |
|---|---|
| `drawRect` (no rotation) | `vectorio.Rectangle` |
| `drawRect` (rotated), `drawPolygon`, `drawRegularPolygon`, `drawStar` | `vectorio.Polygon` with computed points |
| `drawCircle` | `vectorio.Circle` |
| `drawOval`, `drawArc` | `vectorio.Polygon` approximation (segment count scales with size) |
| `drawLine` (with `lineWidth`) | `vectorio.Polygon` quad; arrowheads as triangles |
| `border` / `borderWidth` | Second shape drawn under the fill (outer) or polygon ring |
| `drawLabel` | `adafruit_display_text.bitmap_label` with `terminalio.FONT`, integer `scale` from `size` |
| `app.background` | Full-screen rectangle at slot 0 |

- **Limits to document:** `opacity` approximated by blending with
  `app.background` (no true alpha in vectorio); one built-in font, sizes
  rounded to multiples of the base font; gradients mapped to their first
  color in v1; `drawImage` deferred (BMP via `displayio.OnDiskBitmap` later).
- Hard cap on shapes per frame (e.g. 200) with a clear error instead of a
  `MemoryError`.

Considered and rejected: MicroPython + a C GC9A01 driver (faster raw
drawing, but loses the `CIRCUITPY` drive workflow and the reference
project's tooling); full-frame `bitmaptools` drawing (no filled polygons,
and slower full-frame SPI pushes).

### 4.4 Canvas and coordinates

- `runApp(width=240, height=240)`: `app.width == app.height == 240`.
  Other sizes raise `ValueError` (no scaling in v1).
- CMU coordinates (origin top-left, y down) map 1:1 to pixels.
- **Screen rotation (user request 2026-11-10):** an easy way to turn the
  picture in 90° steps, for however the EyePi is mounted.
  - Set in `CIRCUITPY/settings.toml`: `CMU_SCREEN_ROTATION = 90` (0, 90,
    180, or 270, clockwise). 0 means upright as the EyePi is normally
    held. The library adds it to the panel's base rotation (180 on the
    EyePi, from `CMU_TFT_ROTATION`), so students never deal with the
    panel's own numbers.
  - Any other value stops the program at startup with a clear
    `ValueError`.
  - The screen is square, so `app.width`/`app.height` stay 240 and student
    code doesn't change. `displayio` rotates in hardware, so it costs
    nothing per frame.
  - A settings file fits a physical setting: it stays with the board, and
    student code still runs unchanged on desktop CMU. If changing it from
    code turns out to be useful too, add a small extra function later
    (e.g. `setScreenRotation(90)` in `onAppStart`), documented as
    EyePi-only.
- Helper constants or a note: the visible area is the circle centered at
  (120, 120) with radius 120. Consider `app.centerX`/`app.centerY`
  conveniences only if desktop CMU has them (don't add non-CMU API casually).

### 4.5 Input

**Decided: the MVP has screen output plus serial-console input only (no
d-pad).** Defining `onKeyRelease` or `onKeyHold` in the MVP prints a clear
warning that they need the d-pad, rather than failing silently. The d-pad
below is post-MVP and is kept so the runtime leaves room for it.

The EyePi has no input hardware yet. A d-pad is planned that plugs into the
**A0/A1 connector**. Later, design the input layer so new sources plug in
without changing the runtime:

```text
InputSource.poll() -> list of (keyName, pressed) events
  SerialKeys   (MVP)
  I2CPadKeys   (post-MVP: the A0/A1 d-pad)
```

The runtime turns those events into `onKeyPress`, `onKeyRelease` and
`onKeyHold(app, keys)`, as in desktop CMU.

1. **Serial keyboard (MVP):** keystrokes typed in the USB serial console
   become `onKeyPress(app, key)` (read with
   `supervisor.runtime.serial_bytes_available`). Map arrow-key escape
   sequences to `'up'`, `'down'`, `'left'`, `'right'`; also `'space'`,
   `'enter'`, letters, digits. Serial input has no release events, so
   `onKeyRelease`/`onKeyHold` do nothing until the d-pad exists (README
   says so).
2. **I²C d-pad on A0/A1 (later; decided: I²C):** `I2CPadKeys` polls the
   button state over I²C each tick and reports changes. Any number of
   buttons can be held at once, so `onKeyHold(app, keys)` and diagonals
   work.
   - The chip on the d-pad is still to be chosen: e.g. a PCF8574/MCP23008
     GPIO expander, or an Adafruit seesaw board (the Mini I²C Gamepad
     already has a d-pad and buttons). Keep the register read in one small
     function so changing chips doesn't affect the runtime.
   - At startup, scan the bus. If no d-pad answers, carry on with serial
     input only (no error), so programs run with or without it.
   - Poll at a fixed rate (e.g. every 10–20 ms) so I²C reads don't slow
     drawing; a missing or unplugged pad shouldn't crash the app.
   - Key names should match desktop CMU (`'up'`, `'down'`, `'left'`,
     `'right'`, `'space'`, `'enter'`) so the same student code works on
     both. Action buttons map to keys in a small table (e.g. A →
     `'space'`, B → `'enter'`).
3. Mouse events (`onMousePress`, ...) aren't supported; if a student
   defines one, they get a clear error.

### 4.6 Errors

Uncaught errors stop the app, print the traceback to serial, and draw a
short red error message centered on the round screen (so students without
a serial console still see something).

## 5. API scope

### Phase 1 (MVP)

- `runApp()`, `app.stepsPerSecond`, `app.elapsedTime`, `app.running`,
  `app.width`, `app.height`, `app.background`, `app.paused`.
- Callbacks: `onAppStart`, `redrawAll`, `onStep`, `onKeyPress` (from the
  serial console).
- Draw: `drawRect`, `drawCircle`, `drawLine`, `drawLabel`.
- Common args: `fill`, `border`, `borderWidth`, `align`, `visible`.
- Colors: CMU named colors (subset that fits; full list stored as a compact
  `bytes` table, not a dict of tuples), `rgb(r, g, b)`, `None` for no fill.
- `MVCError` rules: draw outside `redrawAll`; change `app` in `redrawAll`.

### Phase 2

- `drawOval`, `drawPolygon`, `drawRegularPolygon`, `drawStar`, `drawArc`.
- `rotateAngle`, `opacity` (approximate), `lineWidth`, `arrowStart`,
  `arrowEnd`, `dashes` (if cheap).
- `app.stop()`.
- I²C d-pad with `onKeyRelease`/`onKeyHold` (only when the user decides
  to add it).
- Utilities: `distance`, `angleTo`, `getPointInDir`, `fromPythonAngle`,
  `rounded`, `pythonRound`.

### Phase 3

- Screens: `setActiveScreen('name')` with `name_redrawAll`, `name_onStep`,
  etc.
- `gradient(...)` (first color or simple approximation), `drawImage` with BMP.
- Backlight brightness setting.

### Phase 5 (optional): CS1 retained mode

- `Rect`, `Circle`, `Oval`, `Line`, `Polygon`, `Label`, `Group` objects with
  property setters, `app.group`, `onStep()`, `onKeyPress(key)`.
- Reuses the same shape-to-primitive code; objects own their vectorio
  primitive instead of a pool slot.

## 6. Repository layout

```text
embeddedCMU/
  .agent/plans/            plans like this one
  cmu_embedded_graphics.py the framework (single file, like the reference)
  code.py                  demo student program
  settings.toml.example    pin/rotation config template
  boards/eyepi/            CircuitPython board definition (recreated, see §7)
  build.cmd                mpy-cross compile (version pinned to firmware)
  deploy.cmd               copy .mpy + code.py (+ driver libs) to CIRCUITPY
  README.md                student API reference
  docs/wiring.md           wiring table and photo
  tests/
    test_basic.py          on-device: loop timing, draw, MVC errors
    test_shapes.py         on-device: every shape, visual check
    test_memory.py         on-device: gc.mem_free() before/after import, per frame
  desktop/                 optional desktop harness (see §8)
  tools/
    build_frozen.sh        freeze into CircuitPython for raspberrypi port
    serial.ps1             serial console helper
  .github/workflows/
    frozen-firmware.yml    manual (workflow_dispatch) UF2 build
```

## 7. Build and freeze

- **Decided: CircuitPython 10.** Pin an exact 10.x release (start with
  10.3.1, same as the reference, unless a newer 10.x patch is current). The
  `mpy-cross` version must match.
- The current EyePi firmware is a 2023 9.0.0 alpha. Move to a current
  stable release; the library won't support the alpha.
- **Unfrozen workflow:** `build.cmd` downloads `mpy-cross` to
  `%LOCALAPPDATA%` (it can't run from OneDrive, as the reference notes),
  compiles `cmu_embedded_graphics.mpy`; `deploy.cmd` copies it plus
  `adafruit_display_text/` (and a GC9A01 driver when the firmware has no
  `board.DISPLAY`) into `CIRCUITPY/lib`.
- **The EyePi's USB VID/PID (0x2E8A / 0x1003) must be kept.** So
  CircuitPython 10 testing uses our own EyePi build, never stock Pico
  firmware.
- **Where it builds:** GitHub Actions only (`eyepi-firmware.yml`). The dev
  PC has no WSL, Docker, or ARM toolchain, and the user isn't allowed to
  install Docker.
- **EyePi board definition (done 2026-11-10, in `boards/eyepi/`):** the
  live board's `dir(board)` matched upstream `raspberry_pi_pico` exactly,
  so the original was a renamed Pico. Recreated from the 10.3.1 Pico files
  with these changes:
  - Board name, USB VID/PID/strings, `W25Q32JVxQ` flash.
  - Added `TFT_SCK`/`TFT_MOSI`/`TFT_CS`/`TFT_DC`/`TFT_RESET`/
    `TFT_BACKLIGHT` and `SDA` (GP26) / `SCL` (GP27).
  - **Changed:** `board.I2C()`/`STEMMA_I2C` now use the A0/A1 connector
    (GP27 SCL, GP26 SDA) instead of the Pico's GP5/GP4.
  - Dropped the Pico's `CIRCUITPY__EVE` and `CIRCUITPY_PICODVI` (not
    needed).
  - No `board.DISPLAY` yet: upstream's Waveshare RP2040-LCD-1.28 (same
    display) has no C display setup to copy either. The library sets up the
    display in Python for now; §4.2a is a later improvement.
- Original plan notes for the board definition:
  - `mpconfigboard.h` / `.mk`: `MICROPY_HW_BOARD_NAME "EyePi"`,
    `USB_VID = 0x2E8A`, `USB_PID = 0x1003`,
    `USB_MANUFACTURER = "Brian Dahlem"`, `USB_PRODUCT = "EyePi"` (same as
    the existing firmware), `EXTERNAL_FLASH_DEVICES = "W25Q32JVxQ"` (4 MB).
    0x2E8A is Raspberry Pi's vendor ID; their PIDs from 0x1000 up are
    assigned to other makers' products. Before publishing to perryhighcs,
    check whether 0x1003 was actually assigned to the EyePi. If it wasn't,
    request a PID (Raspberry Pi or pid.codes) to avoid clashing with
    someone else's device.
  - `pins.c`: the same names as the existing firmware (`GP0`–`GP28`,
    `A0`–`A3`, `LED`, `VOLTAGE_MONITOR`), plus `TFT_SCK`, `TFT_MOSI`,
    `TFT_CS`, `TFT_DC`, `TFT_RESET`, `TFT_BACKLIGHT`, `DISPLAY`, and
    `SDA` (A0) / `SCL` (A1) with `board.I2C()` for the connector.
  - `board.c`: GC9A01 init at boot with the EyePi init sequence,
    rotation 180, 62.5 MHz, backlight on GP21 (§4.2a).
  - If the original board folder turns up on a local machine, start from
    that instead.
- **Frozen firmware:** `tools/build_frozen.sh` adapted to:
  - `ports/raspberrypi`, copy `boards/eyepi/` into the checkout, build with
    `BOARD=eyepi`. Keep a `BOARD=raspberry_pi_pico` option for breadboard
    builds.
  - Use the raspberrypi port's board-level submodule fetch (pico-sdk is
    large; check the smallest fetch target).
  - Freeze `cmu_embedded_graphics.py` and `adafruit_display_text` (as a
    submodule or copied directory) via `FROZEN_MPY_DIRS` in a
    `user_post_mpconfigport.mk`. No Python display driver needed when
    `board.c` sets up the display.
  - Make sure `vectorio`, `bitmaptools`, `displayio`, `busdisplay`,
    `fourwire`, `busio`, `terminalio` are enabled (default on RP2040;
    verify). Freeze the d-pad chip's driver too (e.g. `adafruit_seesaw`)
    once it's chosen.
  - Output `firmware/cmu-embedded-graphics-eyepi-<version>.uf2`.
- GitHub Actions workflow mirrors the reference: checkout, ARM GCC, venv
  with `requirements-dev.txt`, run the script, upload the UF2 artifact.
- Install: hold BOOTSEL, plug in, copy UF2 to `RPI-RP2`. Remove any
  `cmu_embedded_graphics.py`/`.mpy` from `CIRCUITPY` so they don't shadow
  the frozen module.

RP2040 has much more RAM than the reference's SAMD21, so the source `.py`
may even import directly. Freezing is still worth it: bytecode stays in
flash, leaving more heap for vectorio objects and labels. Measure with the
same `gc.mem_free()` snippet the reference README uses.

## 8. Testing

1. **Desktop harness (fast loop, no hardware):** run
   `cmu_embedded_graphics.py` under CPython with `adafruit-blinka-displayio` + its pygame display
   backend, so draw logic, MVC errors and callbacks can be tested on a PC.
   Fake `supervisor`/`keypad` shims live in `desktop/`. If vectorio isn't
   available in Blinka, keep the renderer behind a small interface so a
   pygame renderer can stand in.
2. **Unit tests (CPython, pytest):** color parsing, alignment math,
   polygon/oval/arc point generation, `App` guard rules, step timing logic
   with a fake clock.
3. **On-device tests** (`tests/*.py` deployed as `code.py`): frame rate with
   N shapes, memory per frame (no leak across 1000 frames), every error in
   the README error table.
4. **Desktop CMU parity check:** run the demo programs in real desktop
   `cmu_graphics` and compare screenshots by eye.

## 9. Milestones

1. **Bring-up:** on the existing EyePi firmware, a filled circle via
   `displayio` + `vectorio` using the EyePi pins. Then do the same on
   current stable CircuitPython (Pico firmware + Python driver) to confirm
   the new API names. Confirm `board.A0`/`A1` are GP26/GP27 (I²C-capable).
   Write `docs/wiring.md`.
2. **Runtime skeleton:** port `App`, phases, `Runtime.run()` from
   cmu_playground; `onAppStart`/`onStep`/`redrawAll`; serial `onKeyPress`.
3. **Renderer MVP:** shape pool, `drawRect`/`drawCircle`/`drawLine`/
   `drawLabel`, colors, borders, alignment. Demo `code.py` (bouncing ball).
4. **build/deploy scripts + README v1.** Measure FPS and RAM.
5. **EyePi board definition + frozen firmware** script + GitHub Action;
   `board.DISPLAY` at boot; verify on hardware.
6. **Phase 2 API**, utilities. More demos.
7. **D-pad (post-MVP, when the user is ready):** the I²C d-pad on A0/A1
   (`I2CPadKeys`, `onKeyRelease`/`onKeyHold`).
8. **Phase 3 API** (screens, images, gradients).
9. **Optional:** CS1 retained mode.

## 10. Risks

- **Frame rate:** many polygons with rotation recomputed in Python every
  frame may be slow. Mitigate: cache points when args are unchanged; skip
  updating a pool slot whose args match last frame (cheap tuple compare),
  so displayio sees no dirty region.
- **Heap fragmentation** from labels whose text changes each frame. Use
  `bitmap_label` and reuse instances.
- **Driver availability:** confirm `adafruit_gc9a01a` works with the
  pinned CircuitPython; fallback is an inline init sequence in
  `cmu_graphics.py` (it's only ~30 commands).
- **Round screen:** content in corners is invisible; demos and README must
  say so.
- **Opacity/gradients:** vectorio has no alpha, so these are approximations;
  document clearly.

## 11. Open questions

Resolved:
- Board = EyePi; module = `cmu_embedded_graphics`.
- API = CS3 mode for this version; CS1 retained mode is a future option.
- MVP = screen output + serial-console `onKeyPress`, no d-pad. Later: an
  I²C d-pad on the A0/A1 connector.
- CircuitPython 10 (exact 10.x release pinned in build scripts).
- Connector = A0, A1, 5 V, 3.3 V, GND.
- Flash = W25Q32JVUUIQ (4 MB); `CIRCUITPY` = 2.97 MB.

Still open:
1. Original EyePi board definition folder: **user is looking for it**
   (2026-11-10). If found, copy it into `boards/eyepi/` and update it for
   current CircuitPython; if not, recreate it from the Pico board (§7).
2. (Post-MVP) Which I²C chip the d-pad will use.

Also resolved: the repo will live in the `perryhighcs` GitHub org, next to
cmu_playground, once it's ready to publish.
