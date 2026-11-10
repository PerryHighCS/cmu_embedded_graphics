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

__all__ = ('runApp', 'drawRect', 'drawCircle', 'drawLine', 'drawLabel',
           'drawImage', 'getImageSize', 'rgb', 'MVCError')

CALLBACK_NAMES = ('onAppStart', 'redrawAll', 'onStep', 'onKeyPress')
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


def _toColor(color):
    # Color name, rgb(...) or None -> 0xRRGGBB int, or None for no color.
    if color is None:
        return None
    if isinstance(color, RGB):
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
    raise ValueError('use a color name, rgb(...) or None: ' + repr(color))


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
    return [(cx + radius * math.cos(i * step), cy + radius * math.sin(i * step))
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

    def image(self, image, x, y, scale):
        slot = self.claim(IMAGE, None)
        group = slot.shape
        if slot.text is not image:
            tiles = displayio.TileGrid(image.bitmap,
                                       pixel_shader=image.shader)
            if slot.tiles is None:
                group.append(tiles)
            else:
                group[0] = tiles
            slot.tiles = tiles
            slot.text = image
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


# -------------------------------------------------------------- Runtime

class Runtime:
    def __init__(self, namespace, display=None, inputs=None):
        self.phase = INTERNAL
        self.stepsChanged = True
        self.lastTick = supervisor.ticks_ms()
        self.elapsedMs = 0

        for name in NO_MOUSE:
            if hasattr(namespace, name):
                raise MVCError(name + ': the EyePi has no mouse')
        for name in NEEDS_DPAD:
            if hasattr(namespace, name):
                print('Warning: %s needs the d-pad; it is not called yet'
                      % name)
        for name in CALLBACK_NAMES:
            callback = getattr(namespace, name, None)
            if callback is not None and not callable(callback):
                raise TypeError(name + ' must be a function')
            setattr(self, name, callback)

        self.app = App()
        if display is None:
            display, self.baseRotation = _getDisplay()
        else:
            self.baseRotation = display.rotation
        self.display = display
        self.rotation = None
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

def runApp(width=WIDTH, height=HEIGHT):
    if width != WIDTH or height != HEIGHT:
        raise ValueError('the EyePi screen is %dx%d' % (WIDTH, HEIGHT))
    import __main__
    _run(__main__)


def _run(namespace, display=None, inputs=None):
    # runApp without the size check; tests pass a fake display and inputs.
    global _runtime
    if _runtime is not None:
        raise RuntimeError('runApp already running')
    _runtime = Runtime(namespace, display, inputs)
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
    _number(opacity, 'opacity')
    if not 0 <= opacity <= 100:
        raise ValueError('opacity must be 0 to 100: ' + repr(opacity))
    if dashes:
        raise ValueError('dashes are not supported on the EyePi yet')


def _checkBorderWidth(borderWidth):
    _number(borderWidth, 'borderWidth')
    if borderWidth < 0:
        raise ValueError('borderWidth must be >= 0')


def drawRect(left, top, width, height, fill='black', border=None,
             borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
             align='left-top', visible=True):
    runtime = _checkView('drawRect')
    for value, name in ((left, 'left'), (top, 'top'), (width, 'width'),
                        (height, 'height'), (rotateAngle, 'rotateAngle')):
        _number(value, name)
    if width < 0 or height < 0:
        raise ValueError('drawRect width and height must be >= 0')
    _checkBorderWidth(borderWidth)
    _checkCommon(opacity, dashes)
    background = runtime.background
    fill = _fillColor(fill, opacity, background)
    border = _fillColor(border, opacity, background)
    if not visible:
        return
    if borderWidth == 0:
        border = None
    dx, dy = _alignOffset(align, width, height)
    left -= dx
    top -= dy
    renderer = runtime.renderer
    half = borderWidth / 2 if border is not None else 0
    rotated = rotateAngle % 360 != 0

    if not rotated:
        if border is not None and fill is not None:
            _rect(renderer, left - half, top - half, width + 2 * half,
                  height + 2 * half, border)
            _rect(renderer, left + half, top + half, width - 2 * half,
                  height - 2 * half, fill)
            return
        if fill is not None:
            _rect(renderer, left, top, width, height, fill)
            return
        if border is None:
            return

    cx = left + width / 2
    cy = top + height / 2
    if border is None:
        pts = _rotate(_rectPoints(left, top, width, height), cx, cy,
                      rotateAngle)
        renderer.polygon(_intPoints(pts), fill)
        return
    outer = _rotate(_rectPoints(left - half, top - half, width + 2 * half,
                                height + 2 * half), cx, cy, rotateAngle)
    innerW = width - 2 * half
    innerH = height - 2 * half
    if fill is None:
        if innerW <= 0 or innerH <= 0:
            renderer.polygon(_intPoints(outer), border)
        else:
            renderer.pieces(_rectOutline(left, top, width, height, half,
                                         cx, cy, rotateAngle), border)
        return
    renderer.polygon(_intPoints(outer), border)
    if innerW > 0 and innerH > 0:
        inner = _rotate(_rectPoints(left + half, top + half, innerW, innerH),
                        cx, cy, rotateAngle)
        renderer.polygon(_intPoints(inner), fill)


def _rect(renderer, left, top, width, height, color):
    # Round the edges, not the size, so neighboring rects line up.
    x = _round(left)
    y = _round(top)
    renderer.rect(x, y, _round(left + width) - x, _round(top + height) - y,
                  color)


def drawCircle(centerX, centerY, radius, fill='black', border=None,
               borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
               align='center', visible=True):
    runtime = _checkView('drawCircle')
    for value, name in ((centerX, 'centerX'), (centerY, 'centerY'),
                        (radius, 'radius'), (rotateAngle, 'rotateAngle')):
        _number(value, name)
    if radius < 0:
        raise ValueError('drawCircle radius must be >= 0')
    _checkBorderWidth(borderWidth)
    _checkCommon(opacity, dashes)
    background = runtime.background
    fill = _fillColor(fill, opacity, background)
    border = _fillColor(border, opacity, background)
    if not visible:
        return
    dx, dy = _alignOffset(align, 2 * radius, 2 * radius)
    cx = _round(centerX - dx + radius)
    cy = _round(centerY - dy + radius)
    renderer = runtime.renderer
    if border is None or borderWidth <= 0:
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
    _checkCommon(opacity, dashes)
    if arrowStart or arrowEnd:
        raise ValueError('arrows are not supported on the EyePi yet')
    color = _fillColor(fill, opacity, runtime.background)
    if not visible or color is None or lineWidth <= 0:
        return
    renderer = runtime.renderer
    half = lineWidth / 2
    if rotateAngle % 360 == 0:
        if y1 == y2:
            _rect(renderer, min(x1, x2), y1 - half, abs(x2 - x1), lineWidth,
                  color)
            return
        if x1 == x2:
            _rect(renderer, x1 - half, min(y1, y2), lineWidth, abs(y2 - y1),
                  color)
            return
    length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if length == 0:
        return
    nx = -(y2 - y1) / length * half
    ny = (x2 - x1) / length * half
    pts = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
           (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
    pts = _rotate(pts, (x1 + x2) / 2, (y1 + y2) / 2, rotateAngle)
    renderer.polygon(_intPoints(pts), color)


def drawLabel(value, centerX, centerY, fill='black', border=None,
              borderWidth=2, opacity=100, rotateAngle=0, dashes=False,
              align='center', visible=True, size=12, font='arial',
              bold=False, italic=False):
    # font, bold, italic and border are accepted for desktop compatibility;
    # the EyePi has one built-in font.
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
              width=None, height=None, visible=True):
    # url is a BMP file on CIRCUITPY, e.g. 'images/cat.bmp'.
    runtime = _checkView('drawImage')
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
    runtime.renderer.image(image, _round(left - dx), _round(top - dy), scale)


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
