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
        self.root_group = None
        self.auto_refresh = False
        self.refreshes = 0
        self.rotations = []

    def refresh(self):
        self.refreshes += 1
        self.rotations.append(self.rotation)


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


def test_ring_is_closed_keyhole():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
    inner = [(2, 2), (8, 2), (8, 8), (2, 8)]
    pts = ceg._ring(outer, inner)
    assert pts[:5] == outer + [outer[0]]
    assert pts[5] == inner[0] and pts[-1] == inner[0]
    assert pts[6:9] == [(2, 8), (8, 8), (8, 2)]


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
    ring, = shapes(d)
    assert isinstance(ring, vectorio.Polygon)
    assert len(ring.points) == 10


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
    assert isinstance(ring, vectorio.Polygon)


def test_draw_line():
    d = draw(lambda: (drawLine(10, 50, 110, 50),
                      drawLine(10, 10, 50, 50, lineWidth=4, fill='blue')))
    flat, diag = shapes(d)
    assert isinstance(flat, vectorio.Rectangle)
    assert (flat.x, flat.y, flat.width, flat.height) == (10, 49, 100, 2)
    assert isinstance(diag, vectorio.Polygon) and len(diag.points) == 4
    with pytest.raises(ValueError, match='arrows'):
        draw(lambda: drawLine(0, 0, 10, 10, arrowEnd=True))


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
    (lambda: drawRect(0, 0, 1, 1, dashes=True), ValueError),
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
