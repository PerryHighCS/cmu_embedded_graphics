# Desktop unit tests for cmu_embedded_graphics, run with fakes for the
# CircuitPython modules:   pytest desktop   (or python -m pytest in desktop/)

import types

import pytest

import supervisor
import vectorio
import cmu_embedded_graphics as ceg
from cmu_embedded_graphics import (MVCError, drawCircle, drawLabel, drawLine,
                                   drawRect, rgb)


class FakeDisplay:
    def __init__(self):
        self.rotation = 180
        self.brightness = 1.0
        self.brightnesses = []
        self.root_group = None
        self.auto_refresh = False
        self.refreshes = 0
        self.rotations = []

    def refresh(self):
        self.refreshes += 1
        self.rotations.append(self.rotation)
        self.brightnesses.append(self.brightness)


class FakeKeys:
    def __init__(self, batches=()):
        self.batches = list(batches)

    def poll(self):
        if self.batches:
            return [(k, True) for k in self.batches.pop(0)]
        return ()


def run(display=None, inputs=(), **callbacks):
    display = display or FakeDisplay()
    ns = types.SimpleNamespace(**callbacks)
    ceg._run(ns, display, [FakeKeys(inputs)] if inputs is not None else [])
    return display


def stopAfter(steps):
    def onStep(app):
        app.n = getattr(app, 'n', 0) + 1
        if app.n >= steps:
            app.stop()
    return onStep


def shapes(display):
    # Visible shapes after the background, in draw order.
    return [s for s in display.root_group.items[1:] if not s.hidden]


# ---------------------------------------------------------------- Colors

def test_named_colors():
    assert ceg._toColor('red') == 0xFF0000
    assert ceg._toColor('Red') == 0xFF0000
    assert ceg._toColor('aliceblue') == 0xF0F8FF
    assert ceg._toColor('yellowgreen') == 0x9ACD32
    assert ceg._toColor('tan') == 0xD2B48C
    assert ceg._toColor(None) is None


@pytest.mark.parametrize('bad', ['', 'ff0000', '00ffff', 'red ff0000',
                                 'chartreuse2', 'notacolor', ' red'])
def test_unknown_colors(bad):
    with pytest.raises(ValueError):
        ceg._toColor(bad)


def test_rgb():
    assert ceg._toColor(rgb(1, 2, 3)) == 0x010203
    assert rgb(1, 2, 3) == rgb(1, 2, 3)
    assert repr(rgb(255, 0, 10)) == 'rgb(255, 0, 10)'
    for bad in ((256, 0, 0), (-1, 0, 0), (1.5, 0, 0), (True, 0, 0)):
        with pytest.raises(ValueError):
            rgb(*bad)
    with pytest.raises(ValueError):
        ceg._toColor((255, 0, 0))


def test_blend():
    assert ceg._blend(0xFF0000, 0xFFFFFF, 100) == 0xFF0000
    assert ceg._blend(0xFF0000, 0xFFFFFF, 0) == 0xFFFFFF
    assert ceg._blend(0x000000, 0xFFFFFF, 50) == 0x808080


# ------------------------------------------------------- Geometry helpers

def test_align():
    assert ceg._alignOffset('left-top', 10, 20) == (0, 0)
    assert ceg._alignOffset('center', 10, 20) == (5, 10)
    assert ceg._alignOffset('right-bottom', 10, 20) == (10, 20)
    with pytest.raises(ValueError):
        ceg._alignOffset('middle', 10, 20)


def test_ticks_diff_wraps():
    assert ceg._ticksDiff(5, 0x1FFFFFFF - 4) == 10
    assert ceg._ticksDiff(0x1FFFFFFF - 4, 5) == -10


def test_rotate_clockwise():
    (x, y), = ceg._rotate([(10, 0)], 0, 0, 90)
    assert (round(x), round(y)) == (0, 10)   # y down: clockwise


def test_ring_pieces_overlap_and_wrap():
    outer = [(i * 10, 0) for i in range(8)]
    inner = [(i * 10, 5) for i in range(8)]
    pieces = ceg._ringPieces(outer, inner, 4)
    assert len(pieces) == 2
    # Piece 0: outer 0..4, inner 4..0. Piece 1 wraps around to point 0.
    assert pieces[0] == outer[0:5] + inner[4::-1]
    assert pieces[1] == outer[4:8] + [outer[0]] + [inner[0]] + inner[7:3:-1]


def _cost(poly):
    # vectorio work for one polygon: pixels in its box * number of edges.
    xs = [x for x, y in poly.points]
    ys = [y for x, y in poly.points]
    return (max(xs) - min(xs)) * (max(ys) - min(ys)) * len(poly.points)


def test_hollow_circle_is_cheap_to_draw():
    d = draw(lambda: drawCircle(120, 120, 110, fill=None, border='white'))
    group, = shapes(d)
    polys = [p for p in group.items if not p.hidden]
    assert len(polys) == 16
    # One keyhole polygon was ~220*220*131 = 6.3 million edge tests.
    assert sum(_cost(p) for p in polys) < 250_000


# ----------------------------------------------------------- App rules

def test_callbacks_and_redraw_count():
    log = []

    def onAppStart(app):
        log.append('start')
        app.stepsPerSecond = 1000

    def redrawAll(app):
        log.append('draw')

    d = run(onAppStart=onAppStart, onStep=stopAfter(3), redrawAll=redrawAll)
    assert log == ['start', 'draw', 'draw', 'draw', 'draw']
    assert d.refreshes == 4
    assert d.auto_refresh is True       # handed back to the console


def test_no_redraw_without_events():
    supervisor.autoAdvance = 1
    count = [0]

    def onAppStart(app):
        app.stepsPerSecond = 0           # no steps at all
        app.t = 0

    def onKeyPress(app, key):
        app.stop()

    def redrawAll(app):
        count[0] += 1

    run(onAppStart=onAppStart, onKeyPress=onKeyPress, redrawAll=redrawAll,
        inputs=[[], [], [], ['q']])
    assert count[0] == 2                 # start + after the key


def test_steps_follow_clock_and_skip_backlog():
    supervisor.autoAdvance = 1
    times = []

    def onAppStart(app):
        app.stepsPerSecond = 10          # every 100 ms

    def onStep(app):
        times.append(supervisor.now)
        if len(times) == 2:
            supervisor.autoAdvance = 1000   # fall far behind once
        else:
            supervisor.autoAdvance = 1
        if len(times) == 4:
            app.stop()

    try:
        run(onAppStart=onAppStart, onStep=onStep)
    finally:
        supervisor.autoAdvance = 1
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert 95 <= gaps[0] <= 105
    # After the stall the next step runs once, not ten times in a row.
    assert gaps[2] >= 95


def test_paused_skips_steps():
    def onAppStart(app):
        app.stepsPerSecond = 1000
        app.paused = True

    def onKeyPress(app, key):
        app.stop()

    calls = []
    run(onAppStart=onAppStart, onStep=lambda app: calls.append(1),
        onKeyPress=onKeyPress, inputs=[[]] * 50 + [['x']])
    assert calls == []


def test_key_names_passed():
    keys = []

    def onKeyPress(app, key):
        keys.append(key)
        if key == 'q':
            app.stop()

    run(onKeyPress=onKeyPress, inputs=[['up', 'space'], ['q']])
    assert keys == ['up', 'space', 'q']


def test_app_defaults_and_read_only():
    seen = {}

    def onAppStart(app):
        seen.update(sps=app.stepsPerSecond, w=app.width, h=app.height,
                    rot=app.rotation, paused=app.paused, bg=app.background)
        for name in ('width', 'height', 'elapsedTime'):
            with pytest.raises(AttributeError):
                setattr(app, name, 1)
        with pytest.raises(AttributeError, match='onAppStart'):
            app.missing
        app.stop()

    run(onAppStart=onAppStart)
    assert seen == dict(sps=30, w=240, h=240, rot=0, paused=False, bg=None)


@pytest.mark.parametrize('name,value,exc', [
    ('stepsPerSecond', -1, ValueError),
    ('stepsPerSecond', 'fast', TypeError),
    ('stepsPerSecond', True, TypeError),
    ('rotation', 45, ValueError),
    ('rotation', 90.0, TypeError),
    ('rotation', '90', TypeError),
    ('background', 'notacolor', ValueError),
    ('brightness', 101, ValueError),
    ('brightness', -1, ValueError),
    ('brightness', 'dim', TypeError),
    ('brightness', True, TypeError),
])
def test_app_setter_errors(name, value, exc):
    def onAppStart(app):
        setattr(app, name, value)
    with pytest.raises(exc):
        run(onAppStart=onAppStart)


def test_set_app_in_redraw_is_mvc_error():
    def redrawAll(app):
        app.score = 1
    with pytest.raises(MVCError, match='redrawAll cannot set app.score'):
        run(redrawAll=redrawAll)


def test_draw_outside_redraw_is_mvc_error():
    def onAppStart(app):
        drawRect(0, 0, 10, 10)
    with pytest.raises(MVCError, match='drawRect: use in redrawAll only'):
        run(onAppStart=onAppStart)
    with pytest.raises(MVCError):
        drawCircle(1, 1, 1)


def test_callback_must_be_callable():
    with pytest.raises(TypeError, match='onStep must be a function'):
        run(onStep=5)


def test_mouse_callback_rejected():
    with pytest.raises(MVCError, match='no mouse'):
        run(onMousePress=lambda app, x, y: None)


def test_dpad_callback_warns(capsys):
    run(onAppStart=lambda app: app.stop(), onKeyRelease=lambda a, k: None)
    assert 'onKeyRelease needs the d-pad' in capsys.readouterr().out


def test_run_app_size_and_reentry():
    with pytest.raises(ValueError):
        ceg.runApp(width=400, height=400)

    def onAppStart(app):
        with pytest.raises(RuntimeError):
            ceg._run(types.SimpleNamespace(), FakeDisplay(), [])
        app.stop()
    run(onAppStart=onAppStart)
    assert ceg._runtime is None


def test_student_error_preserved_and_shown():
    def onStep(app):
        app.score += missingVariable  # noqa: F821

    def onAppStart(app):
        app.score = 0

    d = FakeDisplay()
    with pytest.raises(NameError):
        run(d, onAppStart=onAppStart, onStep=onStep)
    # Error screen: black background and labels with the message.
    assert d.root_group.items[0].pixel_shader[0] == ceg.BLACK
    labels = shapes(d)
    assert all(isinstance(s, ceg.displayio.Group) for s in labels)
    assert ceg._runtime is None


# ------------------------------------------------------------- Rotation

def test_rotation_applied_relative_to_panel():
    def onAppStart(app):
        app.rotation = 90
        app.stepsPerSecond = 1000

    def onStep(app):
        app.rotation = 270
        app.stop()

    d = run(onAppStart=onAppStart, onStep=onStep)
    assert d.rotations == [270, 90]       # (180 + 90), (180 + 270) % 360


# -------------------------------------------------------------- Drawing

def draw(fn, background=None):
    def onAppStart(app):
        app.background = background
        app.stop()
    return run(onAppStart=onAppStart, redrawAll=lambda app: fn())


def test_background_default_white_and_set():
    d = draw(lambda: None)
    assert d.root_group.items[0].pixel_shader[0] == 0xFFFFFF
    d = draw(lambda: None, background='navy')
    assert d.root_group.items[0].pixel_shader[0] == 0x000080


def test_draw_rect_plain_and_aligned():
    d = draw(lambda: (drawRect(10, 20, 30, 40, fill='red'),
                      drawRect(100, 100, 20, 10, align='center')))
    a, b = shapes(d)
    assert isinstance(a, vectorio.Rectangle)
    assert (a.x, a.y, a.width, a.height, a.color) == (10, 20, 30, 40, 0xFF0000)
    assert (b.x, b.y, b.width, b.height, b.color) == (90, 95, 20, 10, 0)


def test_draw_rect_border_and_hollow():
    d = draw(lambda: drawRect(10, 10, 20, 20, fill='red', border='blue',
                              borderWidth=4))
    outer, inner = shapes(d)
    assert (outer.x, outer.y, outer.width, outer.color) == (8, 8, 24, 0xFF)
    assert (inner.x, inner.y, inner.width, inner.color) == (12, 12, 16,
                                                            0xFF0000)
    d = draw(lambda: drawRect(10, 10, 20, 20, fill=None, border='blue'))
    outline, = shapes(d)
    strips = outline.items
    assert [len(p.points) for p in strips] == [4, 4, 4, 4]
    xs = [x for p in strips for x, y in p.points]
    ys = [y for p in strips for x, y in p.points]
    assert (min(xs), max(xs), min(ys), max(ys)) == (9, 31, 9, 31)


def test_draw_rect_rotated_is_polygon():
    d = draw(lambda: drawRect(0, 0, 20, 10, rotateAngle=90))
    poly, = shapes(d)
    assert isinstance(poly, vectorio.Polygon)
    xs = sorted(x for x, y in poly.points)
    ys = sorted(y for x, y in poly.points)
    assert (xs[0], xs[-1], ys[0], ys[-1]) == (5, 15, -5, 15)


def test_draw_rect_zero_size_draws_nothing_and_negative_errors():
    d = draw(lambda: drawRect(0, 0, 0, 10))
    assert shapes(d) == []
    with pytest.raises(ValueError):
        draw(lambda: drawRect(0, 0, -1, 10))


def test_draw_circle_variants():
    d = draw(lambda: (drawCircle(120, 120, 50, fill='green'),
                      drawCircle(0, 0, 10, align='left-top'),
                      drawCircle(50, 50, 20, fill='red', border='black',
                                 borderWidth=4)))
    a, b, outer, inner = shapes(d)
    assert (a.x, a.y, a.radius, a.color) == (120, 120, 50, 0x008000)
    assert (b.x, b.y, b.radius) == (10, 10, 10)
    assert (outer.radius, inner.radius) == (22, 18)
    d = draw(lambda: drawCircle(50, 50, 20, fill=None, border='red'))
    ring, = shapes(d)
    assert isinstance(ring, ceg.displayio.Group)
    assert all(isinstance(p, vectorio.Polygon) for p in ring.items)
    assert all(p.pixel_shader[0] == 0xFF0000 for p in ring.items)


def test_draw_line():
    d = draw(lambda: (drawLine(10, 50, 110, 50),
                      drawLine(10, 10, 50, 50, lineWidth=4, fill='blue')))
    flat, diag = shapes(d)
    assert isinstance(flat, vectorio.Rectangle)
    assert (flat.x, flat.y, flat.width, flat.height) == (10, 49, 100, 2)
    assert isinstance(diag, vectorio.Polygon) and len(diag.points) == 4
    d = draw(lambda: drawLine(10, 50, 110, 50, arrowEnd=True,
                              arrowStart=True, lineWidth=4))
    body, end, start = shapes(d)
    assert isinstance(body, vectorio.Rectangle)
    assert end.points[0] == (110, 50) and start.points[0] == (10, 50)
    # Desktop size: length min(50, 10*sqrt(lineWidth)) = 20, half-width 20/3.
    assert sorted(end.points) == [(90, 43), (90, 57), (110, 50)]


def test_draw_label():
    d = draw(lambda: drawLabel('Hi!', 120, 120, size=24, fill='red'))
    group, = shapes(d)
    tiles = group[0]
    assert group.scale == 2
    # 3 chars * 6 px * 2 = 36 wide, 12 * 2 = 24 tall, centered.
    assert (group.x, group.y) == (102, 108)
    assert tiles.tiles[:3] == [ord('H') - 32, ord('i') - 32, ord('!') - 32]
    assert set(tiles.tiles[3:]) == {0}          # padded with spaces
    assert tiles.pixel_shader[1] == 0xFF0000
    assert 0 in tiles.pixel_shader.transparent


def test_label_unknown_char_and_number_value():
    d = draw(lambda: drawLabel(3.5, 0, 0, align='left-top'))
    group, = shapes(d)
    assert group[0].tiles[:3] == [ord(c) - 32 for c in '3.5']
    d = draw(lambda: drawLabel('é', 0, 0))
    assert shapes(d)[0][0].tiles[0] == ord('?') - 32


def test_opacity_blends_with_background():
    d = draw(lambda: drawRect(0, 0, 10, 10, fill='black', opacity=50),
             background='white')
    r, = shapes(d)
    assert r.color == 0x808080


@pytest.mark.parametrize('call,exc', [
    (lambda: drawRect('a', 0, 1, 1), TypeError),
    (lambda: drawRect(0, 0, 1, 1, fill='nope'), ValueError),
    (lambda: drawRect(0, 0, 1, 1, align='middle'), ValueError),
    (lambda: drawRect(0, 0, 1, 1, opacity=150), ValueError),
    (lambda: drawRect(0, 0, 1, 1, dashes='yes'), TypeError),
    (lambda: drawRect(0, 0, 1, 1, dashes=[]), TypeError),
    (lambda: drawRect(0, 0, 1, 1, dashes=[4, -1]), ValueError),
    (lambda: drawRect(0, 0, 1, 1, dashes=[0, 0]), ValueError),
    (lambda: drawLine(0, 0, 9, 9, dashes=[True, 2]), ValueError),
    (lambda: drawRect(0, 0, 1, 1, borderWidth=-1), ValueError),
    (lambda: drawCircle(0, 0, -5), ValueError),
    (lambda: drawLabel('x', 0, 0, size=0), ValueError),
    (lambda: drawLabel('x', 0, 0, rotateAngle=45), ValueError),
])
def test_draw_argument_errors(call, exc):
    with pytest.raises(exc):
        draw(call)


def test_invisible_draws_nothing():
    d = draw(lambda: (drawRect(0, 0, 5, 5, visible=False),
                      drawCircle(5, 5, 5, visible=False),
                      drawLabel('x', 5, 5, visible=False)))
    assert shapes(d) == []


# ----------------------------------------------------------- Shape pool

def test_pool_reuses_hides_and_replaces():
    frames = [
        lambda: (drawRect(0, 0, 10, 10), drawCircle(50, 50, 5)),
        lambda: (drawRect(5, 0, 10, 10),),
        lambda: (drawCircle(1, 1, 1), drawCircle(50, 50, 5)),
    ]

    def onAppStart(app):
        app.frame = 0
        app.stepsPerSecond = 1000

    def onStep(app):
        app.frame += 1
        if app.frame == 2:
            app.stop()

    seen = []

    def redrawAll(app):
        frames[app.frame]()

    def snapshot(display):
        items = display.root_group.items[1:]
        seen.append([(type(s).__name__, s.hidden) for s in items])

    class D(FakeDisplay):
        def refresh(self):
            super().refresh()
            snapshot(self)

    d = D()
    first = []

    def redrawAll2(app):
        redrawAll(app)
        first.append(ceg._runtime.renderer.slots[0].shape)

    run(d, onAppStart=onAppStart, onStep=onStep, redrawAll=redrawAll2)
    assert seen == [
        [('Rectangle', False), ('Circle', False)],
        [('Rectangle', False), ('Circle', True)],
        [('Circle', False), ('Circle', False)],
    ]
    assert first[0] is first[1]        # rect reused in place
    assert first[2] is not first[1]    # replaced by a circle


def test_pool_skips_unchanged_updates():
    def onAppStart(app):
        app.stepsPerSecond = 1000
        app.n = 0

    def onStep(app):
        app.n += 1
        if app.n == 3:
            app.stop()

    d = run(onAppStart=onAppStart, onStep=onStep,
            redrawAll=lambda app: (drawRect(1, 2, 3, 4, fill='red'),
                                   drawLabel('same', 50, 50)))
    rect = ceg.displayio.Group.__getitem__(d.root_group, 1)
    assert rect.writes == 4            # x, y, width, height on frame 1 only
    assert rect.pixel_shader.writes == 1


def test_too_many_shapes():
    def redrawAll(app):
        for i in range(ceg.MAX_SHAPES + 1):
            drawCircle(i, i, 2)
    with pytest.raises(RuntimeError, match='too many shapes'):
        run(redrawAll=redrawAll)


# ---------------------------------------------------------- Serial keys

def feed(text):
    keys = ceg.SerialKeys()
    keys._read = lambda: None
    keys.pending = text
    return keys


def test_serial_key_names():
    events = feed('a \r\n\t\x7f\x1b[A\x1b[B\x1b[C\x1b[D\x1b[3~Z\n').poll()
    assert [k for k, _ in events] == [
        'a', 'space', 'enter', 'tab', 'backspace', 'up', 'down', 'right',
        'left', 'delete', 'Z', 'enter']
    assert all(p for _, p in events)


def test_serial_split_escape_sequence_waits():
    keys = feed('x\x1b[')
    assert keys.poll() == [('x', True)]
    assert keys.pending == '\x1b['
    keys.pending += 'A'
    assert keys.poll() == [('up', True)]


def test_lone_escape():
    assert feed('\x1b').poll() == [('escape', True)]


# ------------------------------------------------------------ Demo app

def test_demo_code_py_runs():
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'code.py')
    source = open(path).read()
    display = FakeDisplay()
    keys = [['left', 'up', 'c'], ['space'], ['space', 'r']] + [[]] * 400

    def fakeRunApp():
        ns = types.SimpleNamespace(**g)
        steps = [0]
        onStep = ns.onStep

        def countingStep(app):
            onStep(app)
            steps[0] += 1
            if steps[0] == 300:
                app.stop()
        ns.onStep = countingStep
        ceg._run(ns, display, [FakeKeys(keys)])

    g = {'__name__': 'demo'}
    exec(compile(source.replace('runApp()', ''), path, 'exec'), g)
    g['runApp'] = fakeRunApp
    exec('runApp()', g)
    assert display.refreshes > 300
    assert display.rotations[-1] == 270      # 180 + one 'r' press


def test_pieces_reuse_and_hide_extra_polygons():
    def onAppStart(app):
        app.stepsPerSecond = 1000
        app.r = 60

    def onStep(app):
        app.r = 12 if app.r == 60 else 60
        app.n = getattr(app, 'n', 0) + 1
        if app.n == 2:
            app.stop()

    groups = []

    class D(FakeDisplay):
        def refresh(self):
            super().refresh()
            g = self.root_group.items[1]
            groups.append((g, sum(1 for p in g.items if not p.hidden),
                           len(g.items)))

    run(D(), onAppStart=onAppStart, onStep=onStep,
        redrawAll=lambda app: drawCircle(120, 120, app.r, fill=None,
                                         border='red'))
    (g0, vis0, n0), (g1, vis1, n1), (g2, vis2, n2) = groups
    assert g0 is g1 is g2                  # same group reused
    assert (vis0, vis1, vis2) == (15, 3, 15)
    assert n1 == n0                        # small ring hides, not deletes


# --------------------------------------------------------------- Images

import struct

from cmu_embedded_graphics import drawImage, getImageSize


def writeBmp(path, width, height, bpp=8, rows=None, palette=None):
    # Bottom-up palette BMP. rows: list of rows (top first) of indices.
    colors = 1 << bpp
    palette = palette or [(i, i, i) for i in range(colors)]
    rows = rows or [[(x + y) % colors for x in range(width)]
                    for y in range(height)]
    stride = ((width * bpp + 31) // 32) * 4
    data = b''
    for row in reversed(rows):
        bits = 0
        line = bytearray(stride)
        for x, v in enumerate(row):
            bit = x * bpp
            line[bit // 8] |= v << (8 - bpp - bit % 8)
        data += bytes(line)
    pal = b''.join(bytes((b, g, r, 0)) for r, g, b in palette)
    offset = 54 + len(pal)
    header = (b'BM' + struct.pack('<IHHI', offset + len(data), 0, 0, offset)
              + struct.pack('<IiiHHIIiiII', 40, width, height, 1, bpp, 0,
                            len(data), 2835, 2835, len(palette), 0))
    with open(path, 'wb') as f:
        f.write(header + pal + data)
    return str(path)


@pytest.fixture(autouse=True)
def resetMemory():
    ceg.displayio.Bitmap.budget = None
    ceg.displayio.Bitmap.allocated = 0
    yield
    ceg.displayio.Bitmap.budget = None


def test_image_loads_pixels_and_palette(tmp_path):
    path = writeBmp(tmp_path / 'a.bmp', 3, 2, rows=[[1, 2, 3], [4, 5, 6]],
                    palette=[(10, 20, 30)] * 1 + [(255, 0, 0)] * 255)
    d = draw(lambda: drawImage(path, 100, 50))
    group, = shapes(d)
    tiles = group[0]
    bitmap = tiles.bitmap
    assert (bitmap.width, bitmap.height) == (3, 2)
    assert [bitmap[x, 0] for x in range(3)] == [1, 2, 3]   # top row first
    assert [bitmap[x, 1] for x in range(3)] == [4, 5, 6]
    assert tiles.pixel_shader[0] == 0x0A141E
    assert tiles.pixel_shader[1] == 0xFF0000
    assert (group.x, group.y, group.scale) == (100, 50, 1)


def test_image_4bit_and_align_and_scale(tmp_path):
    path = writeBmp(tmp_path / 'b.bmp', 5, 4, bpp=4)
    d = draw(lambda: drawImage(path, 120, 120, align='center', width=10))
    group, = shapes(d)
    assert group.scale == 2
    assert (group.x, group.y) == (115, 116)
    assert group[0].bitmap[4, 0] == 4


def test_image_size_and_errors(tmp_path):
    path = writeBmp(tmp_path / 'c.bmp', 7, 3)
    assert getImageSize(path) == (7, 3)
    for kwargs in (dict(width=10), dict(width=14, height=3),
                   dict(width=3.5), dict(opacity=50), dict(rotateAngle=90)):
        with pytest.raises(ValueError):
            draw(lambda: drawImage(path, 0, 0, **kwargs))
    with pytest.raises(ValueError, match='not found'):
        draw(lambda: drawImage(str(tmp_path / 'missing.bmp'), 0, 0))
    bad = tmp_path / 'x.png'
    bad.write_bytes(b'\x89PNG' + bytes(60))
    with pytest.raises(ValueError, match='only BMP'):
        draw(lambda: drawImage(str(bad), 0, 0))
    with pytest.raises(MVCError):
        drawImage(path, 0, 0)


def test_image_loaded_once_and_reused(tmp_path, monkeypatch):
    path = writeBmp(tmp_path / 'd.bmp', 4, 4)
    loads = []
    real = ceg._loadImage
    monkeypatch.setattr(ceg, '_loadImage',
                        lambda p, ram: loads.append(p) or real(p, ram))

    def onAppStart(app):
        app.stepsPerSecond = 1000
        app.n = 0

    def onStep(app):
        app.n += 1
        if app.n == 5:
            app.stop()

    tiles = []

    class D(FakeDisplay):
        def refresh(self):
            super().refresh()
            tiles.append(self.root_group.items[1][0])

    run(D(), onAppStart=onAppStart, onStep=onStep,
        redrawAll=lambda app: drawImage(path, app.n, 0))
    assert loads == [path]
    assert all(t is tiles[0] for t in tiles)


def test_image_swap_frees_unused_when_memory_is_short(tmp_path):
    a = writeBmp(tmp_path / 'a.bmp', 10, 10)
    b = writeBmp(tmp_path / 'b.bmp', 10, 10)
    ceg.displayio.Bitmap.budget = 150        # room for one 10x10 image

    def onAppStart(app):
        app.stepsPerSecond = 1000
        app.n = 0

    def onStep(app):
        app.n += 1
        if app.n == 3:
            app.stop()

    kinds = []

    def redrawAll(app):
        drawImage(a if app.n % 2 == 0 else b, 0, 0)
        img = ceg._runtime.renderer.slots[0].text
        kinds.append(type(img.bitmap).__name__)
        cached.append(sorted(ceg._runtime.images))

    cached = []
    run(onAppStart=onAppStart, onStep=onStep, redrawAll=redrawAll)
    # Each swap dropped the other image and loaded this one into RAM.
    assert kinds == ['Bitmap'] * 4
    assert cached == [[a], [b], [a], [b]]


def test_image_falls_back_to_disk_when_too_big(tmp_path, capsys):
    path = writeBmp(tmp_path / 'big.bmp', 20, 20)
    ceg.displayio.Bitmap.budget = 100
    d = draw(lambda: drawImage(path, 0, 0))
    assert 'not enough memory' in capsys.readouterr().out
    group, = shapes(d)
    assert isinstance(group[0].bitmap, ceg.displayio.OnDiskBitmap)
    assert isinstance(group[0].pixel_shader, ceg.displayio.ColorConverter)


def test_24bit_image_reads_from_disk(tmp_path):
    path = tmp_path / 'rgb.bmp'
    data = bytes(2 * 4 * 2)     # 2x2, 24-bit, rows padded to 8 bytes
    header = (b'BM' + struct.pack('<IHHI', 54 + len(data), 0, 0, 54)
              + struct.pack('<IiiHHIIiiII', 40, 2, 2, 1, 24, 0, len(data),
                            0, 0, 0, 0))
    path.write_bytes(header + data)
    d = draw(lambda: drawImage(str(path), 0, 0))
    assert isinstance(shapes(d)[0][0].bitmap, ceg.displayio.OnDiskBitmap)


def test_transparent_color_hides_matching_palette_entries(tmp_path):
    palette = [(0, 0, 0)] * 256
    palette[3] = (45, 255, 0)
    palette[7] = (45, 255, 0)
    palette[9] = (45, 255, 1)
    path = writeBmp(tmp_path / 'k.bmp', 4, 4, palette=palette)
    shaders = []

    def onAppStart(app):
        app.stepsPerSecond = 1000
        app.n = 0

    def onStep(app):
        app.n += 1
        if app.n == 3:
            app.stop()

    def redrawAll(app):
        key = rgb(45, 255, 0) if app.n % 2 == 0 else None
        drawImage(path, 0, 0, transparentColor=key)
        shaders.append(ceg._runtime.renderer.slots[0].tiles.pixel_shader)

    run(onAppStart=onAppStart, onStep=onStep, redrawAll=redrawAll)
    keyed, plain = shaders[0], shaders[1]
    assert keyed.transparent == {3, 7}
    assert plain.transparent == set()
    assert shaders[2] is keyed               # reused, not rebuilt
    with pytest.raises(ValueError):
        draw(lambda: drawImage(path, 0, 0, transparentColor='nope'))


def test_transparent_color_on_24bit_uses_converter(tmp_path):
    path = tmp_path / 'rgb.bmp'
    data = bytes(2 * 4 * 2)
    header = (b'BM' + struct.pack('<IHHI', 54 + len(data), 0, 0, 54)
              + struct.pack('<IiiHHIIiiII', 40, 2, 2, 1, 24, 0, len(data),
                            0, 0, 0, 0))
    path.write_bytes(header + data)
    d = draw(lambda: drawImage(str(path), 0, 0, transparentColor='lime'))
    shader = shapes(d)[0][0].pixel_shader
    assert shader.transparent == {0x00FF00}


def test_eye_example_blinks_with_both_images_in_memory(monkeypatch, capsys):
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.chdir(os.path.join(root, 'examples', 'eye'))
    ceg.displayio.Bitmap.budget = 240 * 240 + 260 * 165
    source = open('code.py').read().replace('runApp()', '')
    g = {'__name__': 'eye'}
    exec(compile(source, 'code.py', 'exec'), g)
    frames = []

    def redrawAll(app):
        g['redrawAll'](app)
        r = ceg._runtime.renderer
        frames.append(tuple((os.path.basename(s.text.path),
                             type(s.text.bitmap).__name__,
                             s.shape.x, s.shape.y,
                             sorted(s.tiles.pixel_shader.transparent))
                            for s in r.slots[:r.count]))

    def onStep(app):
        g['onStep'](app)
        if app.elapsedTime > 4:
            app.stop()

    supervisor.autoAdvance = 1
    ns = types.SimpleNamespace(onAppStart=g['onAppStart'], onStep=onStep,
                               onKeyPress=g['onKeyPress'],
                               redrawAll=redrawAll)
    ceg._run(ns, FakeDisplay(), [FakeKeys([['space']])])
    opened = ('open.bmp', 'Bitmap', 0, 0, [])
    shut = ('closedsm.bmp', 'Bitmap', -10, 38, [254])
    assert frames[0] == (opened,)
    assert (opened, shut) in frames            # blinked, overlay keyed
    assert all(f in ((opened,), (opened, shut)) for f in frames)
    assert 'not enough memory' not in capsys.readouterr().out



# ------------------------------------------------------ Phase 2 shapes

from cmu_embedded_graphics import (drawArc, drawOval, drawPolygon,
                                   drawRegularPolygon, drawStar, gradient,
                                   runAppWithScreens, setActiveScreen)


def raster(points):
    # Pixels vectorio fills for a polygon: its winding-number test
    # (shared-module/vectorio/Polygon.c), over the polygon's box.
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    out = set()
    n = len(points)
    for y in range(min(ys), max(ys) + 1):
        for x in range(min(xs), max(xs) + 1):
            w = 0
            for i in range(n):
                x1, y1 = points[i]
                x2, y2 = points[(i + 1) % n]
                side = (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1)
                if y1 <= y:
                    if y2 > y and side > 0:
                        w += 1
                elif y2 <= y and side < 0:
                    w -= 1
            if w:
                out.add((x, y))
    return out


def polygons(item):
    if isinstance(item, vectorio.Polygon):
        return [item] if not item.hidden else []
    return [p for p in item.items if not p.hidden]


@pytest.mark.parametrize('pts', [
    [(20, 20), (220, 40), (200, 220), (30, 180)],             # convex
    [(120, 10), (150, 110), (230, 120), (150, 130), (120, 230),
     (90, 130), (10, 120), (90, 110)],                        # concave star
])
def test_band_split_fill_matches_one_polygon(pts):
    pieces = ceg._fillPieces(pts)
    assert len(pieces) > 1
    whole = raster(ceg._intPoints(pts))
    union = set()
    for piece in pieces:
        cover = raster(piece)
        assert not (cover & union)          # no pixel drawn twice
        union |= cover
    # Rounding where strips cut a slanted edge can move that edge by under
    # a pixel, so differences may only sit on the outline: no holes.
    for x, y in union ^ whole:
        near = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        assert any(p in whole for p in near)
        assert any(p not in whole for p in near)
    assert len(union ^ whole) < 0.02 * len(whole)


def test_small_fill_is_one_polygon():
    assert len(ceg._fillPieces([(0, 0), (20, 0), (10, 20)])) == 1


def test_draw_oval():
    d = draw(lambda: drawOval(120, 120, 60, 60, fill='red'))
    circle, = shapes(d)
    assert isinstance(circle, vectorio.Circle) and circle.radius == 30
    d = draw(lambda: drawOval(120, 120, 200, 100, fill='red'))
    oval, = shapes(d)
    cover = set()
    for p in polygons(oval):
        cover |= raster(p.points)
    xs = [x for x, y in cover]
    ys = [y for x, y in cover]
    assert (min(xs), max(xs), min(ys), max(ys)) == (20, 219, 70, 169)
    d = draw(lambda: drawOval(0, 0, 40, 20, fill='red', align='left-top'))
    oval, = shapes(d)
    xs = [x for p in polygons(oval) for x, y in p.points]
    assert min(xs) == 0 and max(xs) == 40


def test_draw_oval_rotated_and_outlined():
    d = draw(lambda: drawOval(120, 120, 100, 40, fill=None, border='blue',
                              borderWidth=4, rotateAngle=90))
    ring, = shapes(d)
    pts = [pt for p in polygons(ring) for pt in p.points]
    xs = [x for x, y in pts]
    ys = [y for x, y in pts]
    assert (min(xs), max(xs)) == (98, 142) and (min(ys), max(ys)) == (68, 172)
    # Every piece is small: no big boxes for vectorio to test.
    for p in polygons(ring):
        px = [x for x, y in p.points]
        py = [y for x, y in p.points]
        assert (max(px) - min(px)) * (max(py) - min(py)) * len(p.points) \
            <= ceg.FILL_BUDGET


def test_draw_arc_angles_counterclockwise_from_east():
    d = draw(lambda: drawArc(100, 100, 80, 40, 0, 90, fill='red'))
    wedge, = shapes(d)
    pts = wedge.points
    assert pts[0] == (100, 100)            # pie slice from the center
    assert pts[1] == (140, 100)            # 0 degrees: 3 o'clock
    assert pts[-1] == (100, 80)            # 90 degrees: 12 o'clock
    with pytest.raises(ValueError):
        draw(lambda: drawArc(100, 100, 80, 40, 0, 400))
    assert shapes(draw(lambda: drawArc(100, 100, 80, 40, 0, 0))) == []


def test_draw_polygon():
    d = draw(lambda: drawPolygon(10, 10, 50, 10, 30, 40, fill='green'))
    tri, = shapes(d)
    assert tri.points == [(10, 10), (50, 10), (30, 40)]
    assert tri.color == 0x008000
    with pytest.raises(ValueError):
        draw(lambda: drawPolygon(10, 10, 50))
    with pytest.raises(TypeError):
        draw(lambda: drawPolygon(10, 10, 50, 'x', 30, 40))
    with pytest.raises(TypeError):
        draw(lambda: drawPolygon(10, 10, 50, 10, 30, 40, align='center'))
    # Rotated about its centroid (30, 20): a 180 degree turn flips it.
    d = draw(lambda: drawPolygon(10, 10, 50, 10, 30, 40, rotateAngle=180))
    tri, = shapes(d)
    assert sorted(tri.points) == sorted([(50, 30), (10, 30), (30, 0)])


def test_draw_regular_polygon_and_star():
    d = draw(lambda: drawRegularPolygon(100, 100, 30, 4, fill='red'))
    sq, = shapes(d)
    assert sq.points == [(100, 70), (130, 100), (100, 130), (70, 100)]
    d = draw(lambda: drawStar(100, 100, 25, 5, fill='gold'))
    star, = shapes(d)
    pts = star.points
    assert len(pts) == 10 and pts[0] == (100, 75)
    inner = ceg.distance(100, 100, *pts[1])
    assert abs(inner - 25 * 0.38196601125) < 1
    d = draw(lambda: drawStar(100, 100, 20, 6, roundness=80, fill='gold'))
    star, = shapes(d)
    assert abs(ceg.distance(100, 100, *star.points[1]) - 16) < 1
    for bad in (dict(points=2), dict(points=2.5)):
        with pytest.raises((ValueError, TypeError)):
            draw(lambda: drawStar(100, 100, 50, **bad))
    with pytest.raises(ValueError):
        draw(lambda: drawStar(100, 100, 50, 5, roundness=150))


def test_star_border_mitered_and_capped():
    d = draw(lambda: drawStar(120, 120, 60, 5, fill=None, border='red',
                              borderWidth=6))
    ring, = shapes(d)
    pts = [pt for p in polygons(ring) for pt in p.points]
    far = max(ceg.distance(120, 120, x, y) for x, y in pts)
    # Tip miter, capped at 4 border widths past the tip.
    assert 60 < far <= 60 + 4 * 6 + 1


def test_rotated_rect_align_uses_box_after_rotation():
    d = draw(lambda: drawRect(0, 0, 40, 40, rotateAngle=45))
    poly, = shapes(d)
    xs = [x for x, y in poly.points]
    assert (min(xs), max(xs)) == (-8, 48)      # turned about its center
    d = draw(lambda: drawRect(0, 0, 40, 40, rotateAngle=45,
                              align='left-top'))
    poly, = shapes(d)
    xs = [x for x, y in poly.points]
    ys = [y for x, y in poly.points]
    assert (min(xs), min(ys)) == (0, 0)


def test_gradient_draws_first_color():
    g = gradient('red', 'blue', start='left')
    assert ceg._toColor(g) == 0xFF0000
    d = draw(lambda: drawRect(0, 0, 10, 10, fill=gradient('lime', 'navy')))
    assert shapes(d)[0].color == 0x00FF00
    for args in (('red',), ('red', None), ('red', 'blue', 'x')):
        with pytest.raises(ValueError):
            gradient(*args[:2]) if len(args) < 3 else gradient(
                'red', 'blue', start='middle')


def test_math_helpers_match_desktop():
    assert ceg.angleTo(0, 0, 10, 0) == 90
    assert ceg.angleTo(0, 0, 0, 10) == 180
    x, y = ceg.getPointInDir(0, 0, 90, 10)
    assert (pythonRound(x, 6), pythonRound(y, 6)) == (10, 0)
    assert ceg.rounded(2.5) == 3 and ceg.rounded(-2.5) == -3
    assert ceg.pythonRound(2.5) == 2
    with pytest.raises(Exception, match='rounded'):
        ceg.round(2.5)
    assert ceg.distance(0, 0, 3, 4) == 5
    assert ceg.makeList(2, 3, 0) == [[0, 0, 0], [0, 0, 0]]
    assert ceg.almostEqual(0.1 + 0.2, 0.3)
    assert abs(ceg.dsin(30) - 0.5) < 1e-9
    assert abs(ceg.fromPythonAngle(ceg.toPythonAngle(30)) - 30) < 1e-9
    for name in ('choice', 'random', 'randrange', 'seed'):
        assert name in ceg.__all__


pythonRound = ceg.pythonRound


def test_app_quit_stops():
    run(onAppStart=lambda app: app.quit())


# -------------------------------------------------------------- Screens

def runScreens(initial, inputs=(), **callbacks):
    ns = types.SimpleNamespace(**callbacks)
    ceg._run(ns, FakeDisplay(), [FakeKeys(inputs)], screen=initial)


def test_screens_switch_and_activate():
    log = []

    def onAppStart(app):
        app.stepsPerSecond = 0
        log.append('start')

    def title_onScreenActivate(app):
        log.append('title active')

    def title_redrawAll(app):
        log.append('title draw')

    def title_onKeyPress(app, key):
        setActiveScreen('game')

    def game_onScreenActivate(app):
        log.append('game active')

    def game_redrawAll(app):
        log.append('game draw')

    def game_onKeyPress(app, key):
        app.stop()

    runScreens('title', [['x'], ['y']], onAppStart=onAppStart,
               title_onScreenActivate=title_onScreenActivate,
               title_redrawAll=title_redrawAll,
               title_onKeyPress=title_onKeyPress,
               game_onScreenActivate=game_onScreenActivate,
               game_redrawAll=game_redrawAll,
               game_onKeyPress=game_onKeyPress)
    assert log == ['start', 'title active', 'title draw', 'game active',
                   'game draw', 'game draw']


def test_screen_errors():
    with pytest.raises(MVCError, match='Do not define onStep'):
        runScreens('a', a_redrawAll=lambda app: None, onStep=lambda app: 0)
    with pytest.raises(ValueError, match="requires 'b_redrawAll"):
        runScreens('b', a_redrawAll=lambda app: None)
    with pytest.raises(MVCError, match='event functions only'):
        runScreens('a', a_redrawAll=lambda app: setActiveScreen('a'))
    with pytest.raises(MVCError, match='no mouse'):
        runScreens('a', a_redrawAll=lambda app: None,
                   a_onMousePress=lambda app, x, y: None)
    with pytest.raises(MVCError):
        setActiveScreen('a')


def test_on_device_shapes_test_runs_both_screens():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'tests', 'test_shapes.py')
    source = open(path).read().replace("runAppWithScreens('basic')", '')
    g = {'__name__': 'shapes'}
    exec(compile(source, path, 'exec'), g)
    drawn = []
    calls = []

    def basic_onKeyPress(app, key):
        g['basic_onKeyPress'](app, key)
        calls.append(key)
        if len(calls) == 3:
            app.stop()

    def wrap(name):
        def redrawAll(app):
            g[name](app)
            drawn.append((name, ceg._runtime.renderer.count))
        return redrawAll

    ns = types.SimpleNamespace(
        onAppStart=g['onAppStart'], basic_onKeyPress=basic_onKeyPress,
        more_onKeyPress=g['more_onKeyPress'],
        dashes_onKeyPress=g['dashes_onKeyPress'],
        basic_redrawAll=wrap('basic_redrawAll'),
        more_redrawAll=wrap('more_redrawAll'),
        dashes_redrawAll=wrap('dashes_redrawAll'))
    d = FakeDisplay()
    keys = [['r'], ['space'], ['space'], ['space'], ['x']]
    ceg._run(ns, d, [FakeKeys(keys)], screen='basic')
    names = [n for n, _ in drawn]
    assert names == ['basic_redrawAll', 'basic_redrawAll', 'more_redrawAll',
                     'dashes_redrawAll', 'basic_redrawAll',
                     'basic_redrawAll']
    assert d.rotations[-1] == 270             # 180 + one 'r'
    assert max(count for _, count in drawn) < ceg.MAX_SHAPES


def test_brightness_sets_backlight():
    def onAppStart(app):
        assert app.brightness == 100
        app.brightness = 25
        app.stepsPerSecond = 1000

    def onStep(app):
        app.brightness = 0
        app.stop()

    d = run(onAppStart=onAppStart, onStep=onStep)
    assert d.brightnesses == [0.25, 0.0]



# --------------------------------------------------------------- Dashes

def test_dash_patterns_and_intervals():
    assert ceg._dashPattern(True) == [5, 5]
    assert ceg._dashPattern(False) is None
    assert ceg._dashPattern([4]) == [4, 4]
    assert ceg._dashPattern((6, 2, 1)) == [6, 2, 1, 6, 2, 1]
    assert ceg._dashIntervals(30, [5, 5]) == [(0, 5), (10, 15), (20, 25)]
    assert ceg._dashIntervals(12, [5, 5]) == [(0, 5), (10, 12)]
    assert ceg._dashIntervals(10, [0, 3]) == []


def test_dashed_line():
    d = draw(lambda: drawLine(0, 10, 30, 10, lineWidth=4, dashes=True))
    group, = shapes(d)
    boxes = []
    for p in polygons(group):
        xs = [x for x, y in p.points]
        ys = [y for x, y in p.points]
        boxes.append((min(xs), max(xs), min(ys), max(ys)))
    assert boxes == [(0, 5, 8, 12), (10, 15, 8, 12), (20, 25, 8, 12)]
    # Arrowheads stay solid, as on desktop.
    d = draw(lambda: drawLine(0, 10, 60, 10, dashes=True, arrowEnd=True))
    dashes, arrow = shapes(d)
    assert isinstance(arrow, vectorio.Polygon) and arrow.points[0] == (60, 10)


def test_dashed_rect_border_keeps_corners():
    d = draw(lambda: drawRect(20, 20, 40, 30, fill='red', border='blue',
                              borderWidth=4, dashes=[50, 10]))
    body, group = shapes(d)
    assert (body.x, body.y, body.width, body.height) == (20, 20, 40, 30)
    pieces = polygons(group)
    # Perimeter 140, 50 on / 10 off: dashes 0-50, 60-110, 120-140.
    assert len(pieces) == 3
    # The first dash runs along the top (40) and turns the top-right
    # corner: its outer corner is mitered at (62, 18).
    assert (62, 18) in pieces[0].points
    assert len(pieces[0].points) == 6
    # The second starts on the right edge (at 60 of 40..70) and turns the
    # bottom-right corner (62, 52).
    assert (62, 52) in pieces[1].points
    ring = set()
    for p in polygons(shapes(draw(lambda: drawRect(
            20, 20, 40, 30, fill=None, border='blue', borderWidth=4)))[0]):
        ring |= raster(p.points)
    dashed = set()
    for p in pieces:
        dashed |= raster(p.points)
    assert dashed <= ring and 0.7 < len(dashed) / len(ring) < 0.95


def test_dashed_circle_and_shapes():
    d = draw(lambda: drawCircle(120, 120, 50, fill=None, border='white',
                                dashes=True))
    group, = shapes(d)
    # Perimeter ~314 in 10 px steps.
    assert 30 <= len(polygons(group)) <= 33
    d = draw(lambda: drawCircle(120, 120, 50, fill='red', border='white',
                                dashes=True))
    disk, group = shapes(d)
    assert isinstance(disk, vectorio.Circle) and disk.radius == 50
    for fn in (lambda: drawOval(120, 120, 100, 60, dashes=True,
                                border='red'),
               lambda: drawStar(120, 120, 40, 5, border='red', dashes=[3]),
               lambda: drawArc(120, 120, 80, 80, 0, 270, border='red',
                               dashes=True),
               lambda: drawPolygon(10, 10, 90, 20, 50, 80, border='red',
                                   fill=None, dashes=True),
               lambda: drawRect(60, 60, 50, 30, rotateAngle=30,
                                border='red', dashes=True)):
        d = draw(fn)
        assert isinstance(shapes(d)[-1], ceg.displayio.Group)
    # Labels accept dashes and ignore them, like font and bold.
    assert len(shapes(draw(lambda: drawLabel('hi', 50, 50,
                                             dashes=True)))) == 1


def test_dash_starting_on_a_corner_follows_the_next_edge():
    d = draw(lambda: drawRect(20, 20, 40, 30, fill=None, border='blue',
                              borderWidth=4, dashes=[30, 10]))
    group, = shapes(d)
    second = polygons(group)[1]          # 40-70: exactly the right edge
    assert sorted(second.points) == [(58, 20), (58, 50), (62, 20), (62, 50)]
