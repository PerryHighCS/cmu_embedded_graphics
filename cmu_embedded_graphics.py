# cmu_embedded_graphics.py - CMU Graphics (CS3 mode) for the EyePi
#
# Students write callbacks in code.py and call runApp(). The runtime owns
# the App, reads serial keys, dispatches events, and draws the view.
#
#   Controllers (onAppStart, onStep, onKeyPress) change the model.
#   redrawAll(app) reads the model and draws shapes.
#
# The screen is a 240x240 round GC9A01. Drawing uses displayio + vectorio
# with a pool of reusable shapes: each draw call in redrawAll claims the
# next slot, so nothing is allocated per frame once the pool has grown.

import gc
import math
import os
import struct
import sys

import bitmaptools
import board
import displayio
import supervisor
import terminalio
import vectorio
from random import choice, random, randrange, seed

__all__ = (
    # running the app
    'runApp', 'runAppWithScreens', 'setActiveScreen', 'MVCError',
    # drawing
    'drawRect', 'drawCircle', 'drawOval', 'drawArc', 'drawLine',
    'drawPolygon', 'drawRegularPolygon', 'drawStar', 'drawLabel',
    'drawImage', 'getImageSize', 'rgb', 'gradient',
    # helpers, as in desktop CMU Graphics
    'distance', 'angleTo', 'getPointInDir', 'fromPythonAngle',
    'toPythonAngle', 'rounded', 'pythonRound', 'round', 'almostEqual',
    'makeList', 'dsin', 'dcos', 'choice', 'random', 'randrange', 'seed')

CALLBACK_NAMES = ('onAppStart', 'redrawAll', 'onStep', 'onKeyPress')
SCREEN_NAMES = ('redrawAll', 'onStep', 'onKeyPress')   # per-screen versions
NEEDS_DPAD = ('onKeyRelease', 'onKeyHold')
NO_MOUSE = ('onMousePress', 'onMouseRelease', 'onMouseDrag', 'onMouseMove')

WIDTH = HEIGHT = 240
MAX_SHAPES = 200
WHITE = 0xFFFFFF
BLACK = 0x000000

# Execution phases
INTERNAL = 0
CONTROLLER = 1
VIEW = 2

_runtime = None


class MVCError(Exception):
    pass


# supervisor.ticks_ms() wraps every 2**29 ms, so compare ticks with this.
def _ticksDiff(a, b):
    return ((a - b + 0x10000000) & 0x1FFFFFFF) - 0x10000000


def _round(x):
    return int(math.floor(x + 0.5))


def _isNumber(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _number(value, name):
    if not _isNumber(value):
        raise TypeError(name + ' must be a number: ' + repr(value))
    return value


# --------------------------------------------------------------- Colors

# CSS named colors, as used by CMU Graphics. One string instead of a dict
# keeps ~140 entries cheap on the RP2040: ' name rrggbb' per color.
_COLOR_TABLE = (
    ' aliceblue f0f8ff antiquewhite faebd7 aqua 00ffff aquamarine 7fffd4'
    ' azure f0ffff beige f5f5dc bisque ffe4c4 black 000000'
    ' blanchedalmond ffebcd blue 0000ff blueviolet 8a2be2 brown a52a2a'
    ' burlywood deb887 cadetblue 5f9ea0 chartreuse 7fff00'
    ' chocolate d2691e coral ff7f50 cornflowerblue 6495ed'
    ' cornsilk fff8dc crimson dc143c cyan 00ffff darkblue 00008b'
    ' darkcyan 008b8b darkgoldenrod b8860b darkgray a9a9a9'
    ' darkgreen 006400 darkgrey a9a9a9 darkkhaki bdb76b'
    ' darkmagenta 8b008b darkolivegreen 556b2f darkorange ff8c00'
    ' darkorchid 9932cc darkred 8b0000 darksalmon e9967a'
    ' darkseagreen 8fbc8f darkslateblue 483d8b darkslategray 2f4f4f'
    ' darkslategrey 2f4f4f darkturquoise 00ced1 darkviolet 9400d3'
    ' deeppink ff1493 deepskyblue 00bfff dimgray 696969 dimgrey 696969'
    ' dodgerblue 1e90ff firebrick b22222 floralwhite fffaf0'
    ' forestgreen 228b22 fuchsia ff00ff gainsboro dcdcdc'
    ' ghostwhite f8f8ff gold ffd700 goldenrod daa520 gray 808080'
    ' green 008000 greenyellow adff2f grey 808080 honeydew f0fff0'
    ' hotpink ff69b4 indianred cd5c5c indigo 4b0082 ivory fffff0'
    ' khaki f0e68c lavender e6e6fa lavenderblush fff0f5'
    ' lawngreen 7cfc00 lemonchiffon fffacd lightblue add8e6'
    ' lightcoral f08080 lightcyan e0ffff lightgoldenrodyellow fafad2'
    ' lightgray d3d3d3 lightgreen 90ee90 lightgrey d3d3d3'
    ' lightpink ffb6c1 lightsalmon ffa07a lightseagreen 20b2aa'
    ' lightskyblue 87cefa lightslategray 778899 lightslategrey 778899'
    ' lightsteelblue b0c4de lightyellow ffffe0 lime 00ff00'
    ' limegreen 32cd32 linen faf0e6 magenta ff00ff maroon 800000'
    ' mediumaquamarine 66cdaa mediumblue 0000cd mediumorchid ba55d3'
    ' mediumpurple 9370db mediumseagreen 3cb371 mediumslateblue 7b68ee'
    ' mediumspringgreen 00fa9a mediumturquoise 48d1cc'
    ' mediumvioletred c71585 midnightblue 191970 mintcream f5fffa'
    ' mistyrose ffe4e1 moccasin ffe4b5 navajowhite ffdead navy 000080'
    ' oldlace fdf5e6 olive 808000 olivedrab 6b8e23 orange ffa500'
    ' orangered ff4500 orchid da70d6 palegoldenrod eee8aa'
    ' palegreen 98fb98 paleturquoise afeeee palevioletred db7093'
    ' papayawhip ffefd5 peachpuff ffdab9 peru cd853f pink ffc0cb'
    ' plum dda0dd powderblue b0e0e6 purple 800080 rebeccapurple 663399'
    ' red ff0000 rosybrown bc8f8f royalblue 4169e1 saddlebrown 8b4513'
    ' salmon fa8072 sandybrown f4a460 seagreen 2e8b57 seashell fff5ee'
    ' sienna a0522d silver c0c0c0 skyblue 87ceeb slateblue 6a5acd'
    ' slategray 708090 slategrey 708090 snow fffafa springgreen 00ff7f'
    ' steelblue 4682b4 tan d2b48c teal 008080 thistle d8bfd8'
    ' tomato ff6347 turquoise 40e0d0 violet ee82ee wheat f5deb3'
    ' white ffffff whitesmoke f5f5f5 yellow ffff00 yellowgreen 9acd32 ')

_colorCache = {}


class RGB:
    # What rgb() returns. Holds the color as a 0xRRGGBB int.
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, RGB) and other.value == self.value

    def __repr__(self):
        v = self.value
        return 'rgb(%d, %d, %d)' % (v >> 16, (v >> 8) & 0xFF, v & 0xFF)


def rgb(red, green, blue):
    for c in (red, green, blue):
        if not isinstance(c, int) or isinstance(c, bool) or not 0 <= c <= 255:
            raise ValueError('rgb needs whole numbers 0-255: rgb(%r, %r, %r)'
                             % (red, green, blue))
    return RGB((red << 16) | (green << 8) | blue)


class Gradient:
    # What gradient() returns. The screen can't draw gradients yet, so a
    # gradient fill is drawn in its first color.
    def __init__(self, colors, start):
        self.colors = colors
        self.start = start
        self.value = _toColor(colors[0])

    def __repr__(self):
        return 'gradient(%s, start=%r)' % (
            ', '.join(repr(c) for c in self.colors), self.start)


def gradient(*colors, start='center'):
    if len(colors) < 2:
        raise ValueError('gradient needs at least 2 colors; you gave %d'
                         % len(colors))
    for color in colors:
        if color is None or isinstance(color, Gradient):
            raise ValueError('gradient colors must be names or rgb(...): '
                             + repr(color))
        _toColor(color)
    if start not in _ALIGN:
        raise ValueError('unknown gradient start ' + repr(start))
    return Gradient(colors, start)


def _toColor(color):
    # Color name, rgb(...), gradient(...) or None -> 0xRRGGBB int, or None
    # for no color.
    if color is None:
        return None
    if isinstance(color, RGB):
        return color.value
    if isinstance(color, Gradient):
        return color.value
    if isinstance(color, str):
        value = _colorCache.get(color)
        if value is None:
            name = color.lower()
            i = _COLOR_TABLE.find(' ' + name + ' ')
            j = i + len(name) + 2
            try:
                # Must land on a name, not on one of the hex values.
                if i < 0 or ' ' in name or _COLOR_TABLE[j + 6] != ' ':
                    raise ValueError
                value = int(_COLOR_TABLE[j:j + 6], 16)
            except (ValueError, IndexError):
                raise ValueError('unknown color ' + repr(color))
            if len(_colorCache) < 32:
                _colorCache[color] = value
        return value
    raise ValueError('use a color name, rgb(...), gradient(...) or None: '
                     + repr(color))


def _blend(color, background, opacity):
    # No real transparency on the screen: mix with the background instead.
    if opacity >= 100:
        return color
    if opacity <= 0:
        return background
    out = 0
    for shift in (16, 8, 0):
        c = (color >> shift) & 0xFF
        b = (background >> shift) & 0xFF
        out |= (b + _round((c - b) * opacity / 100)) << shift
    return out


# ------------------------------------------------- Student math helpers
# The same helpers desktop CMU Graphics gives students. Angles are in
# degrees, clockwise from 12 o'clock, like the rest of CMU Graphics.

pythonRound = round      # Python's own, before ours replaces it below


def round(*args):
    raise Exception("Use our rounded(n) instead of Python 3's round(n)\n"
                    "  Python 3's round(n) does not work as one might "
                    "expect!\n  If you still want Python 3's round, use "
                    "pythonRound")


def rounded(d):
    # Round half away from zero: rounded(2.5) == 3, rounded(-2.5) == -3.
    sign = 1 if d >= 0 else -1
    d = abs(d)
    n = int(d)
    if d - n >= 0.5:
        n += 1
    return sign * n


def almostEqual(x, y, epsilon=10e-7):
    return abs(x - y) <= epsilon


def makeList(rows, cols, value=None):
    if rows < 0 or cols < 0:
        raise ValueError('Both rows and cols must be >= 0')
    return [[value for _ in range(cols)] for _ in range(rows)]


def dsin(angle):
    return math.sin(math.radians(angle))


def dcos(angle):
    return math.cos(math.radians(angle))


def distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def fromPythonAngle(radians):
    return (90 - math.degrees(radians)) % 360


def toPythonAngle(degrees):
    return math.radians(90 - degrees) % (2 * math.pi)


def angleTo(x1, y1, x2, y2):
    return fromPythonAngle(math.atan2(y1 - y2, x2 - x1))


def getPointInDir(x1, y1, degrees, d):
    a = toPythonAngle(degrees)
    return [x1 + d * math.cos(a), y1 - d * math.sin(a)]


# ------------------------------------------------------ Geometry helpers

# align -> (fraction of width, fraction of height) at the given point
_ALIGN = {
    'center': (0.5, 0.5), 'left': (0, 0.5), 'right': (1, 0.5),
    'top': (0.5, 0), 'bottom': (0.5, 1),
    'left-top': (0, 0), 'right-top': (1, 0),
    'left-bottom': (0, 1), 'right-bottom': (1, 1),
}


def _alignOffset(align, width, height):
    try:
        fx, fy = _ALIGN[align]
    except (KeyError, TypeError):
        raise ValueError('unknown align ' + repr(align))
    return width * fx, height * fy


def _rotate(points, cx, cy, degrees):
    # Rotate (x, y) float pairs clockwise (y points down) about (cx, cy).
    if not degrees:
        return points
    a = math.radians(degrees)
    c = math.cos(a)
    s = math.sin(a)
    out = []
    for x, y in points:
        dx = x - cx
        dy = y - cy
        out.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return out


def _rectPoints(left, top, width, height):
    right = left + width
    bottom = top + height
    return [(left, top), (right, top), (right, bottom), (left, bottom)]


def _circlePoints(cx, cy, radius, n):
    step = 2 * math.pi / n
    return [(cx + radius * math.cos(i * step),
             cy + radius * math.sin(i * step))
            for i in range(n)]


def _ringPieces(outer, inner, per):
    # A hollow outline as several small polygons, `per` segments each.
    # vectorio tests every pixel in a polygon's bounding box against every
    # edge, so one big ring polygon is very slow; small pieces are not.
    # Each piece reaches one segment into the next: a pixel exactly on a
    # shared edge belongs to neither polygon, which would leave a gap.
    n = len(outer)
    pieces = []
    for a in range(0, n, per):
        b = min(a + per, n) + 1
        pts = [outer[i % n] for i in range(a, b)]
        for i in range(b - 1, a - 1, -1):
            pts.append(inner[i % n])
        pieces.append(_intPoints(pts))
    return pieces


def _rectOutline(left, top, width, height, half, cx, cy, degrees):
    # Four border strips. Top and bottom span the full outer width, left
    # and right the full outer height, so the corners overlap (no gaps).
    l0 = left - half
    t0 = top - half
    w0 = width + 2 * half
    h0 = height + 2 * half
    b = 2 * half
    strips = (_rectPoints(l0, t0, w0, b), _rectPoints(l0, t0 + h0 - b, w0, b),
              _rectPoints(l0, t0, b, h0), _rectPoints(l0 + w0 - b, t0, b, h0))
    return [_intPoints(_rotate(pts, cx, cy, degrees)) for pts in strips]


def _intPoints(points):
    return [(_round(x), _round(y)) for x, y in points]


# ------------------------------------------------------------- Display

def _pin(key, default):
    name = os.getenv(key) or default
    try:
        return getattr(board, name)
    except AttributeError:
        raise ValueError('settings.toml %s: no pin board.%s' % (key, name))


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

_display = None


def _getDisplay():
    # Returns (display, baseRotation). Uses board.DISPLAY when the firmware
    # sets the screen up; otherwise builds it from the EyePi pins, which
    # settings.toml can override (CMU_TFT_*, CMU_SPI_HZ).
    global _display
    if _display is None:
        display = getattr(board, 'DISPLAY', None)
        if display is not None:
            _display = (display, display.rotation)
        else:
            import busio
            try:
                from fourwire import FourWire
                from busdisplay import BusDisplay
            except ImportError:     # CircuitPython 8 and older
                FourWire = displayio.FourWire
                BusDisplay = displayio.Display
            rotation = int(os.getenv('CMU_TFT_ROTATION') or 180)
            displayio.release_displays()
            spi = busio.SPI(clock=_pin('CMU_TFT_SCK', 'GP18'),
                            MOSI=_pin('CMU_TFT_MOSI', 'GP19'))
            bus = FourWire(spi, command=_pin('CMU_TFT_DC', 'GP16'),
                           chip_select=_pin('CMU_TFT_CS', 'GP17'),
                           reset=_pin('CMU_TFT_RST', 'GP20'),
                           baudrate=int(os.getenv('CMU_SPI_HZ')
                                        or 62_500_000))
            display = BusDisplay(bus, _INIT_SEQUENCE, width=WIDTH,
                                 height=HEIGHT, rotation=rotation,
                                 backlight_pin=_pin('CMU_TFT_BL', 'GP21'),
                                 brightness=1.0, auto_refresh=False)
            _display = (display, rotation)
    return _display


# ------------------------------------------------------------ Renderer

RECT = 0
CIRCLE = 1
POLYGON = 2
LABEL = 3
PIECES = 4      # a Group of polygons in one color (hollow outlines)
IMAGE = 5       # a Group holding a TileGrid of an image


class _Slot:
    def __init__(self, kind, shape, palette, tiles=None):
        self.kind = kind
        self.shape = shape      # what sits in the root group
        self.palette = palette
        self.tiles = tiles      # LABEL, IMAGE: the TileGrid inside shape
        self.color = None
        self.geometry = None    # last geometry, to skip unchanged updates
        self.text = None        # LABEL: text shown; IMAGE: _Image shown
        self.hidden = False


class Renderer:
    # Keeps a displayio.Group of reusable shapes. Each frame, draw calls
    # claim slots in order; a slot of the right kind is updated in place
    # (only what changed, so displayio redraws only what moved), a slot of
    # the wrong kind is replaced, and leftover slots are hidden.

    def __init__(self):
        self.root = displayio.Group()
        self.bgPalette = displayio.Palette(1)
        self.bgPalette[0] = WHITE
        self.bgColor = WHITE
        self.root.append(vectorio.Rectangle(pixel_shader=self.bgPalette,
                                            width=WIDTH, height=HEIGHT,
                                            x=0, y=0))
        self.slots = []
        self.count = 0
        font = terminalio.FONT
        self.font = font
        self.glyphW, self.glyphH = font.get_bounding_box()[:2]
        self.space = self._tileIndex(' ')
        self.unknown = self._tileIndex('?')

    def _tileIndex(self, ch):
        glyph = self.font.get_glyph(ord(ch))
        if glyph is None:
            return None
        return glyph.tile_index

    def begin(self, background):
        if background != self.bgColor:
            self.bgPalette[0] = background
            self.bgColor = background
        self.count = 0

    def end(self):
        slots = self.slots
        for i in range(self.count, len(slots)):
            slot = slots[i]
            if not slot.hidden:
                slot.shape.hidden = True
                slot.hidden = True

    def _make(self, kind):
        palette = displayio.Palette(2 if kind == LABEL else 1)
        if kind == RECT:
            shape = vectorio.Rectangle(pixel_shader=palette, width=1,
                                       height=1, x=0, y=0)
        elif kind == CIRCLE:
            shape = vectorio.Circle(pixel_shader=palette, radius=1, x=0, y=0)
        elif kind == POLYGON:
            shape = vectorio.Polygon(pixel_shader=palette,
                                     points=[(0, 0), (1, 0), (0, 1)],
                                     x=0, y=0)
        elif kind == PIECES or kind == IMAGE:
            shape = displayio.Group()
        else:
            palette.make_transparent(0)
            shape = displayio.Group()
        return _Slot(kind, shape, palette)

    def claim(self, kind, color):
        i = self.count
        if i >= MAX_SHAPES:
            raise RuntimeError('too many shapes in one frame (max %d)'
                               % MAX_SHAPES)
        self.count = i + 1
        slots = self.slots
        if i < len(slots):
            slot = slots[i]
            if slot.kind != kind:
                slot = self._make(kind)
                self.root[i + 1] = slot.shape
                slots[i] = slot
            elif slot.hidden:
                slot.shape.hidden = False
                slot.hidden = False
        else:
            slot = self._make(kind)
            self.root.append(slot.shape)
            slots.append(slot)
        if slot.color != color and color is not None:
            slot.palette[1 if kind == LABEL else 0] = color
            slot.color = color
        return slot

    # -- primitives (integer pixel coordinates)

    def rect(self, x, y, width, height, color):
        if width < 1 or height < 1:
            return
        slot = self.claim(RECT, color)
        shape = slot.shape
        old = slot.geometry
        if old is None or old[0] != x or old[1] != y:
            shape.x = x
            shape.y = y
        if old is None or old[2] != width or old[3] != height:
            shape.width = width
            shape.height = height
        slot.geometry = (x, y, width, height)

    def circle(self, x, y, radius, color):
        if radius < 1:
            return
        slot = self.claim(CIRCLE, color)
        shape = slot.shape
        old = slot.geometry
        if old is None or old[0] != x or old[1] != y:
            shape.x = x
            shape.y = y
        if old is None or old[2] != radius:
            shape.radius = radius
        slot.geometry = (x, y, radius)

    def polygon(self, points, color):
        # points: list of (int, int); placed with x = y = 0.
        if len(points) < 3:
            return
        slot = self.claim(POLYGON, color)
        if slot.geometry != points:
            slot.shape.points = points
            slot.geometry = points

    def pieces(self, pieces, color):
        # pieces: list of point lists, drawn as one shape. Counts as one
        # shape toward MAX_SHAPES.
        slot = self.claim(PIECES, color)
        old = slot.geometry
        if old == pieces:
            return
        group = slot.shape
        have = len(group)
        for i in range(len(pieces)):
            points = pieces[i]
            if i < have:
                child = group[i]
                if old is None or i >= len(old) or old[i] != points:
                    child.points = points
                if child.hidden:
                    child.hidden = False
            else:
                group.append(vectorio.Polygon(pixel_shader=slot.palette,
                                              points=points, x=0, y=0))
        for i in range(len(pieces), have):
            child = group[i]
            if not child.hidden:
                child.hidden = True
        slot.geometry = pieces

    def image(self, image, shader, x, y, scale):
        slot = self.claim(IMAGE, None)
        group = slot.shape
        if slot.text is not image:
            tiles = displayio.TileGrid(image.bitmap, pixel_shader=shader)
            if slot.tiles is None:
                group.append(tiles)
            else:
                group[0] = tiles
            slot.tiles = tiles
            slot.text = image
            slot.palette = shader
        elif slot.palette is not shader:
            slot.tiles.pixel_shader = shader
            slot.palette = shader
        if slot.geometry != (x, y, scale):
            group.x = x
            group.y = y
            group.scale = scale
            slot.geometry = (x, y, scale)

    def dropImages(self, keep):
        # Let go of images not drawn this frame so their memory can be freed.
        for slot in self.slots:
            if slot.kind == IMAGE and slot.tiles is not None \
                    and slot.text.path not in keep:
                slot.shape.pop()
                slot.tiles = None
                slot.text = None

    def label(self, text, x, y, scale, color):
        slot = self.claim(LABEL, color)
        group = slot.shape
        n = len(text)
        if slot.text != text:
            tiles = slot.tiles
            if tiles is None or tiles.width < n:
                capacity = (n + 7) & ~7
                tiles = displayio.TileGrid(
                    self.font.bitmap, pixel_shader=slot.palette,
                    width=capacity, height=1, tile_width=self.glyphW,
                    tile_height=self.glyphH, default_tile=self.space)
                if slot.tiles is None:
                    group.append(tiles)
                else:
                    group[0] = tiles
                slot.tiles = tiles
            for i in range(tiles.width):
                index = self.space
                if i < n:
                    index = self._tileIndex(text[i])
                    if index is None:
                        index = self.unknown
                tiles[i] = index
            slot.text = text
        old = slot.geometry
        if old is None or old != (x, y, scale):
            group.x = x
            group.y = y
            group.scale = scale
            slot.geometry = (x, y, scale)


# -------------------------------------------------------------- Images

class _Image:
    def __init__(self, path, bitmap, shader, width, height):
        self.path = path
        self.bitmap = bitmap
        self.shader = shader
        self.width = width
        self.height = height
        self.keyed = {}     # transparent color -> shader with it hidden

    def shaderFor(self, transparent):
        # The image's colors, with `transparent` (0xRRGGBB) see-through.
        if transparent is None:
            return self.shader
        shader = self.keyed.get(transparent)
        if shader is None:
            source = self.shader
            if isinstance(source, displayio.Palette):
                shader = displayio.Palette(len(source))
                for i in range(len(source)):
                    color = source[i]
                    shader[i] = color
                    if color == transparent:
                        shader.make_transparent(i)
            else:
                # 16/24-bit file: pixels are converted to 0xRRGGBB.
                shader = displayio.ColorConverter()
                shader.make_transparent(transparent)
            self.keyed[transparent] = shader
        return shader


def _readBmpHeader(f, path):
    # Returns (width, height, bitsPerPixel, compression, dataOffset,
    # paletteOffset, colors). height < 0 means rows are stored top-down.
    header = f.read(54)
    if len(header) < 54 or header[0:2] != b'BM':
        raise ValueError(path + ': only BMP images are supported')
    (dataOffset, headerSize, width, height, planes, bpp,
     compression) = struct.unpack_from('<IIiiHHI', header, 10)
    colors = struct.unpack_from('<I', header, 46)[0]
    return (width, height, bpp, compression, dataOffset, 14 + headerSize,
            colors)


def _openImage(path):
    if not isinstance(path, str):
        raise TypeError('image must be a file name: ' + repr(path))
    try:
        return open(path, 'rb')
    except OSError:
        raise ValueError('image not found: ' + repr(path))


def _loadImage(path, inRam):
    # 1-, 4- and 8-bit palette BMPs load into RAM (fast to draw). Others,
    # or when inRam is False, are read from the file as they are drawn
    # (no RAM, but slower).
    f = _openImage(path)
    try:
        width, height, bpp, compression, dataOffset, paletteOffset, colors = \
            _readBmpHeader(f, path)
        rows = abs(height)
        if not inRam or bpp not in (1, 4, 8) or compression != 0:
            f.close()
            f = None
            bitmap = displayio.OnDiskBitmap(path)
            return _Image(path, bitmap, bitmap.pixel_shader, bitmap.width,
                          bitmap.height)
        count = 1 << bpp
        colors = min(colors or count, count)
        f.seek(paletteOffset)
        table = f.read(4 * colors)
        palette = displayio.Palette(count)
        for i in range(colors):
            j = 4 * i
            palette[i] = (table[j + 2] << 16) | (table[j + 1] << 8) | table[j]
        bitmap = displayio.Bitmap(width, rows, count)
        f.seek(dataOffset)
        bitmaptools.readinto(bitmap, f, bits_per_pixel=bpp, element_size=4,
                             reverse_pixels_in_element=True,
                             reverse_rows=height > 0)
        return _Image(path, bitmap, palette, width, rows)
    finally:
        if f is not None:
            f.close()


# ------------------------------------------------------------- Inputs

class SerialKeys:
    # Keys typed in the USB serial console. Serial has no key-up, so this
    # only reports presses: poll() returns a list of (key, True).

    def __init__(self):
        self.pending = ''

    def _read(self):
        n = supervisor.runtime.serial_bytes_available
        if n:
            self.pending += sys.stdin.read(n)

    def poll(self):
        self._read()
        if not self.pending:
            return ()
        events = []
        text = self.pending
        i = 0
        while i < len(text):
            ch = text[i]
            i += 1
            if ch == '\x1b':
                if i >= len(text):
                    events.append(('escape', True))
                elif text[i] in '[O':
                    # Arrow keys: ESC [ A ... ; wait if not all here yet.
                    if i + 1 >= len(text):
                        i -= 1
                        break
                    code = text[i + 1]
                    i += 2
                    key = _ESCAPE_KEYS.get(code)
                    if code == '3' and i < len(text) and text[i] == '~':
                        i += 1
                        key = 'delete'
                    if key is not None:
                        events.append((key, True))
                else:
                    events.append(('escape', True))
            elif ch == '\r':
                events.append(('enter', True))
                if i < len(text) and text[i] == '\n':
                    i += 1
            else:
                events.append((_KEY_NAMES.get(ch, ch), True))
        self.pending = text[i:]
        return events


_ESCAPE_KEYS = {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}
_KEY_NAMES = {' ': 'space', '\n': 'enter', '\t': 'tab',
              '\x7f': 'backspace', '\x08': 'backspace'}


# ---------------------------------------------------------------- Model

class App:
    def __init__(self):
        set = object.__setattr__
        set(self, 'stepsPerSecond', 30)
        set(self, 'running', True)
        set(self, 'paused', False)
        set(self, 'background', None)
        set(self, 'rotation', 0)
        set(self, 'brightness', 100)    # EyePi extra: backlight, 0-100

    def __setattr__(self, name, value):
        if _runtime is not None and _runtime.phase == VIEW:
            raise MVCError('redrawAll cannot set app.' + name)
        if name in ('elapsedTime', 'width', 'height'):
            raise AttributeError('app.' + name + ' is read only')
        if name == 'stepsPerSecond':
            if not _isNumber(value):
                raise TypeError('stepsPerSecond must be a number')
            if value < 0:
                raise ValueError('stepsPerSecond must be >= 0')
            if _runtime is not None:
                _runtime.stepsChanged = True
        elif name == 'background':
            _toColor(value)
        elif name == 'rotation':
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError('app.rotation must be 0, 90, 180 or 270')
            if value not in (0, 90, 180, 270):
                raise ValueError('app.rotation must be 0, 90, 180 or 270')
        elif name == 'brightness':
            if not _isNumber(value):
                raise TypeError('app.brightness must be a number 0 to 100')
            if not 0 <= value <= 100:
                raise ValueError('app.brightness must be 0 to 100')
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        # Only called for attributes that were never set.
        if name == 'elapsedTime':
            return _runtime.elapsedSeconds() if _runtime else 0
        if name == 'width':
            return WIDTH
        if name == 'height':
            return HEIGHT
        raise AttributeError('set app.' + name + ' in onAppStart first')

    def stop(self):
        self.running = False

    def quit(self):
        self.running = False


# -------------------------------------------------------------- Runtime

def _callback(namespace, name):
    callback = getattr(namespace, name, None)
    if callback is not None and not callable(callback):
        raise TypeError(name + ' must be a function')
    return callback


class Runtime:
    def __init__(self, namespace, display=None, inputs=None, screen=None):
        self.phase = INTERNAL
        self.stepsChanged = True
        self.lastTick = supervisor.ticks_ms()
        self.elapsedMs = 0

        self.namespace = namespace
        self.screen = None
        self.initialScreen = screen
        for attr in dir(namespace):
            for name in NO_MOUSE:
                if attr == name or attr.endswith('_' + name):
                    raise MVCError(attr + ': the EyePi has no mouse')
            for name in NEEDS_DPAD:
                if attr == name or attr.endswith('_' + name):
                    print('Warning: %s needs the d-pad; it is not called yet'
                          % attr)
        if screen is not None:
            for name in SCREEN_NAMES:
                if hasattr(namespace, name):
                    raise MVCError('Do not define %s when using screens'
                                   % name)
        for name in CALLBACK_NAMES:
            setattr(self, name, _callback(namespace, name))

        self.app = App()
        if display is None:
            display, self.baseRotation = _getDisplay()
        else:
            self.baseRotation = display.rotation
        self.display = display
        self.rotation = None
        self.brightness = None
        self.renderer = Renderer()
        self.inputs = [SerialKeys()] if inputs is None else inputs
        self.background = WHITE
        self.images = {}            # path -> _Image, loaded on first draw
        self.imagesUsed = set()     # paths drawn in the current frame

    # -- timing

    def tick(self):
        now = supervisor.ticks_ms()
        self.elapsedMs += _ticksDiff(now, self.lastTick)
        self.lastTick = now
        return self.elapsedMs

    def elapsedSeconds(self):
        now = supervisor.ticks_ms()
        return (self.elapsedMs + _ticksDiff(now, self.lastTick)) / 1000

    # -- screens

    def setScreen(self, screen):
        # Use screen_redrawAll, screen_onStep, ... from now on, then call
        # screen_onScreenActivate if it exists. Runs inside an event.
        if not isinstance(screen, str) or not screen:
            raise ValueError(repr(screen) + ' is not a valid screen')
        namespace = self.namespace
        if not hasattr(namespace, screen + '_redrawAll'):
            raise ValueError("Screen '%s' requires '%s_redrawAll()'"
                             % (screen, screen))
        self.screen = screen
        for name in SCREEN_NAMES:
            setattr(self, name, _callback(namespace, screen + '_' + name))
        activate = _callback(namespace, screen + '_onScreenActivate')
        if activate is not None:
            activate(self.app)

    # -- dispatch

    def callController(self, callback, *args):
        self.phase = CONTROLLER
        try:
            callback(self.app, *args)
        finally:
            self.phase = INTERNAL

    def view(self):
        app = self.app
        display = self.display
        if app.rotation != self.rotation:
            display.rotation = (self.baseRotation + app.rotation) % 360
            self.rotation = app.rotation
        if app.brightness != self.brightness:
            display.brightness = app.brightness / 100
            self.brightness = app.brightness
        background = _toColor(app.background)
        if background is None:
            background = WHITE
        self.background = background
        renderer = self.renderer
        renderer.begin(background)
        self.imagesUsed.clear()
        if self.redrawAll is not None:
            self.phase = VIEW
            try:
                self.redrawAll(app)
            finally:
                self.phase = INTERNAL
        renderer.end()
        if display.root_group is not renderer.root:
            display.root_group = renderer.root
        display.refresh()

    def getImage(self, path):
        image = self.images.get(path)
        if image is None:
            try:
                image = _loadImage(path, True)
            except MemoryError:
                # Free images not drawn this frame, then try again; if it
                # still does not fit, draw it straight from the file.
                self.freeImages()
                try:
                    image = _loadImage(path, True)
                except MemoryError:
                    gc.collect()
                    print('drawImage: not enough memory for %r; drawing it '
                          'from the file instead (slower)' % path)
                    image = _loadImage(path, False)
            self.images[path] = image
        self.imagesUsed.add(path)
        return image

    def freeImages(self):
        keep = self.imagesUsed
        self.renderer.dropImages(keep)
        for path in list(self.images):
            if path not in keep:
                del self.images[path]
        gc.collect()

    def pollInputs(self):
        changed = False
        onKeyPress = self.onKeyPress
        for source in self.inputs:
            for key, pressed in source.poll():
                if pressed and onKeyPress is not None:
                    self.callController(onKeyPress, key)
                    changed = True
                    if not self.app.running:
                        return changed
        return changed

    def showError(self, error):
        # Red message on the screen for students without a serial console.
        renderer = self.renderer
        renderer.begin(BLACK)
        name = type(error).__name__
        message = str(error)
        lines = [name]
        while message and len(lines) < 7:
            lines.append(message[:26])
            message = message[26:]
        top = 120 - (len(lines) * 14 + 30) // 2
        _labelAt(renderer, 'Error', 120, top, 2, 0xFF4040, 'top')
        for i, line in enumerate(lines):
            _labelAt(renderer, line, 120, top + 30 + 14 * i, 1, 0xFF8080,
                     'top')
        renderer.end()
        display = self.display
        display.root_group = renderer.root
        display.refresh()

    # -- main loop

    def run(self):
        app = self.app
        try:
            if self.onAppStart is not None:
                self.callController(self.onAppStart)
            if self.initialScreen is not None and self.screen is None:
                self.callController(lambda app: self.setScreen(
                    self.initialScreen))
            self.view()

            interval = 0
            nextStep = 0
            while app.running:
                elapsed = self.tick()
                changed = self.pollInputs()

                if self.stepsChanged:
                    self.stepsChanged = False
                    sps = app.stepsPerSecond
                    interval = int(1000 / sps) if sps > 0 else 0
                    nextStep = elapsed + interval

                if (interval > 0 and self.onStep is not None
                        and app.running and not app.paused
                        and elapsed >= nextStep):
                    self.callController(self.onStep)
                    changed = True
                    nextStep += interval
                    if nextStep <= elapsed:
                        # Fell behind: skip missed steps, no backlog.
                        nextStep = elapsed + interval

                if changed:
                    self.view()
        except Exception as error:
            self.phase = INTERNAL
            try:
                self.showError(error)
            except Exception:
                pass
            raise
        finally:
            self.phase = INTERNAL
            # Let CircuitPython show its console (and any traceback) after.
            self.display.auto_refresh = True


# ------------------------------------------------------------ Public API

def _checkSize(width, height):
    if width != WIDTH or height != HEIGHT:
        raise ValueError('the EyePi screen is %dx%d' % (WIDTH, HEIGHT))


def runApp(width=WIDTH, height=HEIGHT):
    _checkSize(width, height)
    import __main__
    _run(__main__)


def runAppWithScreens(initialScreen, width=WIDTH, height=HEIGHT):
    # Callbacks are named screen_redrawAll, screen_onStep, screen_onKeyPress
    # and screen_onScreenActivate; onAppStart is shared by all screens.
    _checkSize(width, height)
    import __main__
    _run(__main__, screen=initialScreen)


def setActiveScreen(screen):
    if _runtime is None:
        raise MVCError('setActiveScreen: app not running')
    if _runtime.phase != CONTROLLER:
        raise MVCError('setActiveScreen: use in event functions only')
    _runtime.setScreen(screen)


def _run(namespace, display=None, inputs=None, screen=None):
    # runApp without the size check; tests pass a fake display and inputs.
    global _runtime
    if _runtime is not None:
        raise RuntimeError('runApp already running')
    _runtime = Runtime(namespace, display, inputs, screen)
    try:
        _runtime.run()
    finally:
        _runtime = None


def _checkView(name):
    if _runtime is None or _runtime.phase != VIEW:
        raise MVCError(name + ': use in redrawAll only')
    return _runtime


def _fillColor(fill, opacity, background):
    color = _toColor(fill)
    if color is None:
        return None
    return _blend(color, background, opacity)


def _checkCommon(opacity, dashes):
    # Returns the dash pattern (list of on/off lengths) or None.
    _number(opacity, 'opacity')
    if not 0 <= opacity <= 100:
        raise ValueError('opacity must be 0 to 100: ' + repr(opacity))
    return _dashPattern(dashes)


def _dashPattern(dashes):
    # Like desktop CMU: True is 5 on, 5 off; a list gives on, off, on, ...
    # lengths, and an odd-length list repeats so on/off keeps alternating.
    if dashes is None or dashes is False:
        return None
    if dashes is True:
        return [5, 5]
    if not isinstance(dashes, (list, tuple)) or not dashes:
        raise TypeError('dashes must be True, False or a list of lengths: '
                        + repr(dashes))
    for d in dashes:
        if not _isNumber(d) or d < 0:
            raise ValueError('dash lengths must be numbers >= 0: '
                             + repr(dashes))
    if sum(dashes) <= 0:
        raise ValueError('dash lengths cannot all be 0: ' + repr(dashes))
    pattern = list(dashes)
    if len(pattern) % 2:
        pattern = pattern + pattern
    return pattern


def _checkBorderWidth(borderWidth):
    _number(borderWidth, 'borderWidth')
    if borderWidth < 0:
        raise ValueError('borderWidth must be >= 0')


# ------------------------------------------------------ Polygon drawing

BAND = 16             # height of the strips a big fill is cut into
FILL_BUDGET = 30000   # box pixels * edges above which a fill is cut up
MITER_LIMIT = 4       # longest border corner, in border widths


def _dedupe(points):
    out = []
    for p in points:
        if not out or p != out[-1]:
            out.append(p)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _clipY(points, y, below):
    # The part of the polygon with y >= limit (below) or y <= limit.
    out = []
    for i in range(len(points)):
        p = points[i - 1]
        q = points[i]
        pIn = p[1] >= y if below else p[1] <= y
        qIn = q[1] >= y if below else q[1] <= y
        if pIn != qIn:
            # Same endpoint order either way, so neighbors agree exactly.
            a, b = (p, q) if p < q else (q, p)
            out.append((a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]),
                        y))
        if qIn:
            out.append(q)
    return out


def _fillPieces(points):
    # A filled polygon as a list of int point lists. vectorio tests every
    # pixel in a polygon's box against every edge, so a big polygon is cut
    # into horizontal strips with small boxes. Strips meet on whole pixel
    # rows, so there are no gaps or overlaps. Works for concave shapes too.
    points = _dedupe(_intPoints(points))
    if len(points) < 3:
        return []
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    top = min(ys)
    bottom = max(ys)
    if (max(xs) - min(xs)) * (bottom - top) * len(points) <= FILL_BUDGET:
        return [points]
    pieces = []
    for y0 in range(top, bottom, BAND):
        band = _clipY(_clipY(points, y0, True), min(y0 + BAND, bottom),
                      False)
        band = _dedupe(_intPoints(band))
        if len(band) >= 3:
            pieces.append(band)
    return pieces


def _fill(renderer, points, color):
    pieces = _fillPieces(points)
    if len(pieces) == 1:
        renderer.polygon(pieces[0], color)
    elif pieces:
        renderer.pieces(pieces, color)


def _area2(points):
    # Twice the signed area; > 0 means clockwise on the screen (y down).
    total = 0
    for i in range(len(points)):
        x1, y1 = points[i - 1]
        x2, y2 = points[i]
        total += x1 * y2 - x2 * y1
    return total


def _normals(points, closed):
    # Unit normal of each edge, pointing out of a closed shape.
    sign = 1 if not closed or _area2(points) >= 0 else -1
    n = len(points)
    normals = []
    for i in range(n if closed else n - 1):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        normals.append((sign * dy / length, -sign * dx / length))
    return normals


def _offsets(points, half, normals=None, closed=True):
    # The outline grown and shrunk by `half`, with mitered corners (capped
    # at MITER_LIMIT border widths for sharp points like star tips). For an
    # open path the two ends are cut square.
    if normals is None:
        normals = _normals(points, closed)
    n = len(points)
    limit = MITER_LIMIT * 2 * half
    outer = []
    inner = []
    for i in range(n):
        if closed:
            ax, ay = normals[i - 1]
            bx, by = normals[i]
        else:
            ax, ay = normals[max(i - 1, 0)]
            bx, by = normals[min(i, n - 2)]
        denom = 1 + ax * bx + ay * by
        if denom < 1e-6:            # the outline doubles back on itself
            ox = ax * half
            oy = ay * half
        else:
            ox = (ax + bx) * half / denom
            oy = (ay + by) * half / denom
        length = math.sqrt(ox * ox + oy * oy)
        if length > limit:
            ox *= limit / length
            oy *= limit / length
        x, y = points[i]
        outer.append((x + ox, y + oy))
        inner.append((x - ox, y - oy))
    return outer, inner


def _border(renderer, points, borderWidth, color, dashes=None):
    # The border is centered on the outline, like desktop CMU: a ring of
    # small pieces, each cut into strips if it is still big.
    points = _dedupe(points)
    if len(points) < 3 or borderWidth <= 0:
        return
    if dashes is not None:
        _stroke(renderer, points, True, borderWidth, color, dashes)
        return
    outer, inner = _offsets(points, borderWidth / 2)
    pieces = []
    for piece in _ringPieces(outer, inner, 1 if len(points) <= 16 else 4):
        pieces.extend(_fillPieces(piece))
    if pieces:
        renderer.pieces(pieces, color)


def _dashIntervals(length, pattern):
    # (start, end) distances along a path of `length` that are drawn.
    out = []
    pos = 0
    i = 0
    while pos < length:
        on = pattern[i % len(pattern)]
        off = pattern[(i + 1) % len(pattern)]
        if on > 0:
            out.append((pos, min(pos + on, length)))
        pos += on + off
        i += 2
    return out


def _stroke(renderer, points, closed, width, color, dashes):
    # A dashed stroke along points (a closed outline or an open line).
    # Each dash is the piece of the mitered outline between two distances,
    # so dashes keep proper corners; dash ends are cut square.
    path = list(points)
    if closed:
        path.append(points[0])
    normals = _normals(points, closed)
    outer, inner = _offsets(points, width / 2, normals, closed)
    n = len(points)
    cum = [0]
    for i in range(len(path) - 1):
        (x1, y1), (x2, y2) = path[i], path[i + 1]
        cum.append(cum[-1] + math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))
    half = width / 2

    def at(d, side, after):
        # Point at distance d along the path, pushed to one side. At a
        # corner, a dash start uses the edge after it, a dash end the one
        # before.
        i = 0
        while i < len(cum) - 2 and (cum[i + 1] <= d if after
                                    else cum[i + 1] < d):
            i += 1
        span = cum[i + 1] - cum[i]
        t = (d - cum[i]) / span if span else 0
        (x1, y1), (x2, y2) = path[i], path[i + 1]
        nx, ny = normals[i % len(normals)]
        return (x1 + (x2 - x1) * t + side * nx * half,
                y1 + (y2 - y1) * t + side * ny * half)

    pieces = []
    for start, end in _dashIntervals(cum[-1], dashes):
        if end <= start:
            continue
        top = [at(start, 1, True)]
        bottom = [at(start, -1, True)]
        for k in range(1, len(path) - 1):
            if start < cum[k] < end:
                top.append(outer[k % n])
                bottom.append(inner[k % n])
        top.append(at(end, 1, False))
        bottom.append(at(end, -1, False))
        bottom.reverse()
        pieces.extend(_fillPieces(top + bottom))
    if pieces:
        renderer.pieces(pieces, color)


def _polygonShape(renderer, points, fill, border, borderWidth, dashes=None):
    if fill is not None:
        _fill(renderer, points, fill)
    if border is not None:
        _border(renderer, points, borderWidth, border, dashes)


def _place(points, align, x, y, cx, cy):
    # Desktop CMU moves a shape only when align is given: the named side
    # of its box after rotation ('left', 'right', 'top', 'bottom'), else
    # its center, goes to (x, y).
    if align is None:
        return points
    _alignOffset(align, 0, 0)       # checks the name
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if 'left' in align:
        dx = x - min(xs)
    elif 'right' in align:
        dx = x - max(xs)
    else:
        dx = x - cx
    if 'top' in align:
        dy = y - min(ys)
    elif 'bottom' in align:
        dy = y - max(ys)
    else:
        dy = y - cy
    return [(px + dx, py + dy) for px, py in points]


def _boxCenter(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _centroid(points):
    # Area centroid, as desktop CMU rotates polygons about it.
    a = _area2(points)
    if a == 0:
        n = len(points)
        return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)
    cx = cy = 0
    for i in range(len(points)):
        x1, y1 = points[i - 1]
        x2, y2 = points[i]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    return cx / (3 * a), cy / (3 * a)


def _ovalSegments(a, b):
    # About one segment per 5 pixels of edge, a multiple of 4.
    n = int(math.pi * (a + b) / 5)
    return max(12, min(96, n)) & ~3


def _ovalPoints(cx, cy, a, b, n):
    step = 2 * math.pi / n
    return [(cx + a * math.cos(i * step), cy + b * math.sin(i * step))
            for i in range(n)]


# --------------------------------------------------------- Draw functions

def _checkShape(runtime, values, borderWidth, opacity, dashes):
    # Checks the arguments; returns the dash pattern or None.
    for value, name in values:
        _number(value, name)
    _checkBorderWidth(borderWidth)
    return _checkCommon(opacity, dashes)


def _colors(runtime, fill, border, borderWidth, opacity):
    background = runtime.background
    fill = _fillColor(fill, opacity, background)
    border = _fillColor(border, opacity, background)
    if borderWidth == 0:
        border = None
    return fill, border


def drawRect(left, top, width, height, fill='black', border=None,
             borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
             align=None, visible=True):
    runtime = _checkView('drawRect')
    dashes = _checkShape(
        runtime, ((left, 'left'), (top, 'top'), (width, 'width'),
                  (height, 'height'), (rotateAngle, 'rotateAngle')),
        borderWidth, opacity, dashes)
    if width < 0 or height < 0:
        raise ValueError('drawRect width and height must be >= 0')
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible:
        return
    renderer = runtime.renderer
    if rotateAngle % 360 != 0:
        cx = left + width / 2
        cy = top + height / 2
        pts = _rotate(_rectPoints(left, top, width, height), cx, cy,
                      rotateAngle)
        pts = _place(pts, align, left, top, cx, cy)
        _polygonShape(renderer, pts, fill, border, borderWidth, dashes)
        return
    # Not rotated: Rectangles are the cheapest thing to draw.
    if align is not None:
        dx, dy = _alignOffset(align, width, height)
        left -= dx
        top -= dy
    half = borderWidth / 2
    if border is not None and dashes is not None:
        if fill is not None:
            _rect(renderer, left, top, width, height, fill)
        _border(renderer, _rectPoints(left, top, width, height),
                borderWidth, border, dashes)
    elif border is None:
        if fill is not None:
            _rect(renderer, left, top, width, height, fill)
    elif fill is not None:
        _rect(renderer, left - half, top - half, width + 2 * half,
              height + 2 * half, border)
        _rect(renderer, left + half, top + half, width - 2 * half,
              height - 2 * half, fill)
    elif width - 2 * half <= 0 or height - 2 * half <= 0:
        _rect(renderer, left - half, top - half, width + 2 * half,
              height + 2 * half, border)
    else:
        renderer.pieces(_rectOutline(left, top, width, height, half,
                                     0, 0, 0), border)


def _rect(renderer, left, top, width, height, color):
    # Round the edges, not the size, so neighboring rects line up.
    x = _round(left)
    y = _round(top)
    renderer.rect(x, y, _round(left + width) - x, _round(top + height) - y,
                  color)


def _circleShape(renderer, cx, cy, radius, fill, border, borderWidth,
                 dashes=None):
    cx = _round(cx)
    cy = _round(cy)
    if border is not None and dashes is not None:
        if fill is not None:
            renderer.circle(cx, cy, _round(radius), fill)
        _border(renderer, _circlePoints(cx, cy, radius,
                                        _ovalSegments(radius, radius)),
                borderWidth, border, dashes)
        return
    if border is None:
        if fill is not None:
            renderer.circle(cx, cy, _round(radius), fill)
        return
    half = borderWidth / 2
    outer = _round(radius + half)
    inner = _round(radius - half)
    if fill is not None:
        renderer.circle(cx, cy, outer, border)
        renderer.circle(cx, cy, inner, fill)
    elif inner < 1:
        renderer.circle(cx, cy, outer, border)
    else:
        # Enough segments to look round at this size, 4 per piece.
        n = max(12, min(64, outer)) & ~3
        renderer.pieces(_ringPieces(_circlePoints(cx, cy, outer, n),
                                    _circlePoints(cx, cy, inner, n), 4),
                        border)


def drawCircle(centerX, centerY, radius, fill='black', border=None,
               borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
               align=None, visible=True):
    runtime = _checkView('drawCircle')
    dashes = _checkShape(
        runtime, ((centerX, 'centerX'), (centerY, 'centerY'),
                  (radius, 'radius'), (rotateAngle, 'rotateAngle')),
        borderWidth, opacity, dashes)
    if radius < 0:
        raise ValueError('drawCircle radius must be >= 0')
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible:
        return
    dx, dy = _alignOffset(align or 'center', 2 * radius, 2 * radius)
    _circleShape(runtime.renderer, centerX - dx + radius,
                 centerY - dy + radius, radius, fill, border, borderWidth,
                 dashes)


def drawOval(centerX, centerY, width, height, fill='black', border=None,
             borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
             align=None, visible=True):
    runtime = _checkView('drawOval')
    dashes = _checkShape(runtime, ((centerX, 'centerX'), (centerY, 'centerY'),
                                   (width, 'width'), (height, 'height'),
                                   (rotateAngle, 'rotateAngle')),
                         borderWidth, opacity, dashes)
    if width < 0 or height < 0:
        raise ValueError('drawOval width and height must be >= 0')
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible or width == 0 or height == 0:
        return
    renderer = runtime.renderer
    a = width / 2
    b = height / 2
    if width == height or rotateAngle % 360 == 0:
        dx, dy = _alignOffset(align or 'center', width, height)
        centerX += a - dx
        centerY += b - dy
        if width == height:
            _circleShape(renderer, centerX, centerY, a, fill, border,
                         borderWidth, dashes)
            return
        rotateAngle = 0
        align = None
    pts = _ovalPoints(centerX, centerY, a, b, _ovalSegments(a, b))
    pts = _rotate(pts, centerX, centerY, rotateAngle)
    pts = _place(pts, align, centerX, centerY, centerX, centerY)
    _polygonShape(renderer, pts, fill, border, borderWidth, dashes)


def drawArc(centerX, centerY, width, height, startAngle, sweepAngle,
            fill='black', border=None, borderWidth=2, opacity=100,
            rotateAngle=0, dashes=False, align=None, visible=True):
    # A pie slice of an oval. As in desktop CMU's CS3 mode, angles are in
    # degrees, starting at 3 o'clock and going counterclockwise.
    runtime = _checkView('drawArc')
    dashes = _checkShape(runtime, ((centerX, 'centerX'), (centerY, 'centerY'),
                                   (width, 'width'), (height, 'height'),
                                   (startAngle, 'startAngle'),
                                   (sweepAngle, 'sweepAngle'),
                                   (rotateAngle, 'rotateAngle')),
                         borderWidth, opacity, dashes)
    if width < 0 or height < 0:
        raise ValueError('drawArc width and height must be >= 0')
    if not 0 <= sweepAngle <= 360:
        raise ValueError('sweepAngle must be 0 to 360: ' + repr(sweepAngle))
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible or width == 0 or height == 0 or sweepAngle == 0:
        return
    a = width / 2
    b = height / 2
    n = max(3, int(_ovalSegments(a, b) * sweepAngle / 360) + 1)
    start = math.radians(startAngle)
    sweep = math.radians(sweepAngle)
    pts = [(centerX, centerY)]
    for i in range(n):
        theta = start + sweep * i / (n - 1)
        pts.append((centerX + a * math.cos(theta),
                    centerY - b * math.sin(theta)))
    pts = _rotate(pts, centerX, centerY, rotateAngle)
    pts = _place(pts, align, centerX, centerY, centerX, centerY)
    _polygonShape(runtime.renderer, pts, fill, border, borderWidth,
                  dashes)


def drawPolygon(*coords, fill='black', border=None, borderWidth=2,
                opacity=100, rotateAngle=0, dashes=False, visible=True):
    # drawPolygon(x1, y1, x2, y2, x3, y3, ...)
    runtime = _checkView('drawPolygon')
    if len(coords) % 2:
        raise ValueError('drawPolygon needs pairs of numbers: x1, y1, ...')
    for i in range(len(coords)):
        _number(coords[i], 'polygon point')
    dashes = _checkShape(runtime, ((rotateAngle, 'rotateAngle'),), borderWidth,
                         opacity, dashes)
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible or len(coords) < 6:
        return
    pts = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
    if rotateAngle % 360 != 0:
        cx, cy = _centroid(pts)
        pts = _rotate(pts, cx, cy, rotateAngle)
    _polygonShape(runtime.renderer, pts, fill, border, borderWidth,
                  dashes)


def _checkPoints(points):
    if not isinstance(points, int) or isinstance(points, bool):
        raise TypeError('points must be a whole number: ' + repr(points))
    if points < 3:
        raise ValueError('points must be 3 or more: ' + repr(points))


def _inDir(cx, cy, degrees, d):
    # getPointInDir as a tuple: degrees clockwise from 12 o'clock.
    a = math.radians(degrees)
    return (cx + d * math.sin(a), cy - d * math.cos(a))


def drawRegularPolygon(centerX, centerY, radius, points, fill='black',
                       border=None, borderWidth=2, opacity=100,
                       rotateAngle=0, dashes=False, align=None,
                       visible=True):
    runtime = _checkView('drawRegularPolygon')
    dashes = _checkShape(
        runtime, ((centerX, 'centerX'), (centerY, 'centerY'),
                  (radius, 'radius'), (rotateAngle, 'rotateAngle')),
        borderWidth, opacity, dashes)
    _checkPoints(points)
    if radius < 0:
        raise ValueError('drawRegularPolygon radius must be >= 0')
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible or radius == 0:
        return
    pts = [_inDir(centerX, centerY, i * 360 / points, radius)
           for i in range(points)]
    pts = _rotate(pts, centerX, centerY, rotateAngle)
    pts = _place(pts, align, centerX, centerY, centerX, centerY)
    _polygonShape(runtime.renderer, pts, fill, border, borderWidth,
                  dashes)


def drawStar(centerX, centerY, radius, points, fill='black', border=None,
             borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
             align=None, visible=True, roundness=None):
    # roundness (0-100) is the inner radius as a percent of radius.
    runtime = _checkView('drawStar')
    dashes = _checkShape(
        runtime, ((centerX, 'centerX'), (centerY, 'centerY'),
                  (radius, 'radius'), (rotateAngle, 'rotateAngle')),
        borderWidth, opacity, dashes)
    _checkPoints(points)
    if radius < 0:
        raise ValueError('drawStar radius must be >= 0')
    if roundness is None:
        roundness = 38.196601125 if points < 6 else 57.735026919
    _number(roundness, 'roundness')
    if not 0 <= roundness <= 100:
        raise ValueError('roundness must be 0 to 100: ' + repr(roundness))
    fill, border = _colors(runtime, fill, border, borderWidth, opacity)
    if not visible or radius == 0:
        return
    inner = radius * max(5, roundness) / 100
    step = 360 / points
    pts = []
    for i in range(points):
        pts.append(_inDir(centerX, centerY, i * step, radius))
        pts.append(_inDir(centerX, centerY, i * step + step / 2, inner))
    pts = _rotate(pts, centerX, centerY, rotateAngle)
    pts = _place(pts, align, centerX, centerY, centerX, centerY)
    _polygonShape(runtime.renderer, pts, fill, border, borderWidth,
                  dashes)


def drawLine(x1, y1, x2, y2, fill='black', lineWidth=2, opacity=100,
             rotateAngle=0, dashes=False, arrowStart=False, arrowEnd=False,
             visible=True):
    runtime = _checkView('drawLine')
    for value, name in ((x1, 'x1'), (y1, 'y1'), (x2, 'x2'), (y2, 'y2'),
                        (lineWidth, 'lineWidth'),
                        (rotateAngle, 'rotateAngle')):
        _number(value, name)
    if lineWidth < 0:
        raise ValueError('lineWidth must be >= 0')
    dashes = _checkCommon(opacity, dashes)
    color = _fillColor(fill, opacity, runtime.background)
    if not visible or color is None or lineWidth <= 0:
        return
    renderer = runtime.renderer
    half = lineWidth / 2
    rotated = rotateAngle % 360 != 0
    if dashes is not None:
        if (x1, y1) != (x2, y2):
            ends = _rotate([(x1, y1), (x2, y2)], (x1 + x2) / 2,
                           (y1 + y2) / 2, rotateAngle)
            _stroke(renderer, ends, False, lineWidth, color, dashes)
    elif not rotated and y1 == y2:
        _rect(renderer, min(x1, x2), y1 - half, abs(x2 - x1), lineWidth,
              color)
    elif not rotated and x1 == x2:
        _rect(renderer, x1 - half, min(y1, y2), lineWidth, abs(y2 - y1),
              color)
    length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if length == 0:
        return
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    if dashes is None and (rotated or (y1 != y2 and x1 != x2)):
        nx = -dy * half
        ny = dx * half
        pts = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
               (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
        _fill(renderer, _rotate(pts, cx, cy, rotateAngle), color)
    # Arrowheads: the same size as desktop CMU's.
    arrowLength = min(50, 10 * math.sqrt(lineWidth))
    arrowWidth = arrowLength / 3
    for on, x, y, way in ((arrowEnd, x2, y2, -1), (arrowStart, x1, y1, 1)):
        if on:
            bx = x + way * arrowLength * dx
            by = y + way * arrowLength * dy
            pts = [(x, y), (bx + arrowWidth * dy, by - arrowWidth * dx),
                   (bx - arrowWidth * dy, by + arrowWidth * dx)]
            _fill(renderer, _rotate(pts, cx, cy, rotateAngle), color)


def drawLabel(value, centerX, centerY, fill='black', border=None,
              borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
              align='center', visible=True, size=12, font='arial',
              bold=False, italic=False):
    # font, bold, italic, border and dashes are accepted for desktop
    # compatibility; the EyePi has one built-in font and no text outlines.
    runtime = _checkView('drawLabel')
    for v, name in ((centerX, 'centerX'), (centerY, 'centerY'),
                    (size, 'size'), (rotateAngle, 'rotateAngle')):
        _number(v, name)
    if size <= 0:
        raise ValueError('label size must be > 0')
    if rotateAngle % 360 != 0:
        raise ValueError('labels cannot be rotated on the EyePi yet')
    _checkCommon(opacity, dashes)
    color = _fillColor(fill, opacity, runtime.background)
    if not visible or color is None:
        return
    renderer = runtime.renderer
    scale = max(1, _round(size / renderer.glyphH))
    _labelAt(renderer, str(value), centerX, centerY, scale, color, align)


def _labelAt(renderer, text, x, y, scale, color, align):
    width = len(text) * renderer.glyphW * scale
    height = renderer.glyphH * scale
    dx, dy = _alignOffset(align, width, height)
    if text:
        renderer.label(text, _round(x - dx), _round(y - dy), scale, color)


def getImageSize(url):
    # (width, height) of a BMP file. Works anywhere, not just in redrawAll.
    if _runtime is not None:
        image = _runtime.images.get(url)
        if image is not None:
            return (image.width, image.height)
    f = _openImage(url)
    try:
        width, height = _readBmpHeader(f, url)[:2]
    finally:
        f.close()
    return (width, abs(height))


def drawImage(url, left, top, opacity=100, rotateAngle=0, align='left-top',
              width=None, height=None, visible=True, transparentColor=None):
    # url is a BMP file on CIRCUITPY, e.g. 'images/cat.bmp'.
    # transparentColor is EyePi-only (desktop CMU has no such option):
    # pixels of exactly that color are not drawn, so what is under the
    # image shows through. Exact matches work best with palette BMPs.
    runtime = _checkView('drawImage')
    transparent = _toColor(transparentColor)
    for value, name in ((left, 'left'), (top, 'top'),
                        (rotateAngle, 'rotateAngle')):
        _number(value, name)
    _checkCommon(opacity, False)
    if opacity != 100:
        raise ValueError('image opacity is not supported on the EyePi yet')
    if rotateAngle % 360 != 0:
        raise ValueError('images cannot be rotated on the EyePi yet')
    for value, name in ((width, 'width'), (height, 'height')):
        if value is not None:
            _number(value, name)
            if value <= 0:
                raise ValueError('drawImage %s must be > 0' % name)
    if not visible:
        return
    image = runtime.getImage(url)
    scale = _imageScale(image, width, height)
    w = image.width * scale
    h = image.height * scale
    dx, dy = _alignOffset(align, w, h)
    runtime.renderer.image(image, image.shaderFor(transparent),
                           _round(left - dx), _round(top - dy), scale)


def _imageScale(image, width, height):
    # The screen can only enlarge images by whole numbers (2x, 3x, ...).
    if width is None and height is None:
        return 1
    sx = width / image.width if width is not None else None
    sy = height / image.height if height is not None else None
    scale = sx if sx is not None else sy
    if (sx is not None and sy is not None and sx != sy) or scale < 1 \
            or scale != int(scale):
        raise ValueError('on the EyePi, images can only be drawn at their '
                         'own size or 2x, 3x, ... (%dx%d)'
                         % (image.width, image.height))
    return int(scale)
