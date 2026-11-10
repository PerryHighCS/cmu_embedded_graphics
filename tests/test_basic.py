# test_basic.py - on-device checks for cmu_embedded_graphics.
# Deploy as code.py ("deploy test") and watch the serial console.
#
#   T1  callbacks, timing: steps per second over 2 s
#   T2  every error in the README error table
#   T3  frame rate: full-screen change every frame, 0/20/60 shapes
#   T4  memory: free RAM stays flat across 1000 frames

import gc
gc.collect(); f0 = gc.mem_free()
from cmu_embedded_graphics import *
import cmu_embedded_graphics
gc.collect(); print('free after import', gc.mem_free(), 'cost', f0 - gc.mem_free())
import supervisor

# ------------------------------------------------------------------ T1
log = []
def onAppStart(app):
    app.stepsPerSecond = 10
    app.steps = 0
    app.draws = 0
def onStep(app):
    app.steps += 1
    if app.elapsedTime >= 2:
        app.stop()
def redrawAll(app):
    drawCircle(120, 120, 20 + app.steps * 5, fill='orange')
    drawLabel('T1 steps: %d' % app.steps, 120, 120)
    log.append(app.steps)
runApp()
print('T1 steps in 2 s @10 sps:', log[-1], '(expect ~20) draws:', len(log))

# ------------------------------------------------------------------ T2
def expect(label, exc):
    try:
        runApp()
        print(label, 'FAIL: no error')
    except exc as e:
        print(label, 'ok:', type(e).__name__, e)
    except Exception as e:
        print(label, 'FAIL other:', type(e).__name__, e)

def onStep(app): app.stop()
def redrawAll(app): pass
def onAppStart(app): drawRect(0, 0, 10, 10)
expect('T2a draw in controller', MVCError)
def onAppStart(app): pass
def redrawAll(app): app.score = 1
expect('T2b assign in view', MVCError)
def redrawAll(app): pass
def onAppStart(app): app.elapsedTime = 3
expect('T2c elapsedTime write', AttributeError)
def onAppStart(app): app.stepsPerSecond = -1
expect('T2d negative sps', ValueError)
def onAppStart(app): app.rotation = 45
expect('T2e bad rotation', ValueError)
def onAppStart(app): app.score = 0
def onStep(app): app.score += missingVariable
expect('T2f NameError preserved', NameError)
def onAppStart(app): pass
def onStep(app): app.stop()
def redrawAll(app): drawRect(0, 0, 10, 10, fill='chartreuse2')
expect('T2g bad color', ValueError)
def redrawAll(app): drawCircle(0, 0, 5, align='middle')
expect('T2h bad align', ValueError)
def redrawAll(app):
    for i in range(201):
        drawCircle(120, 120, 2)
expect('T2i too many shapes', RuntimeError)
try:
    runApp(width=400, height=400)
    print('T2j bad size FAIL: no error')
except ValueError as e:
    print('T2j bad size ok:', e)

# ------------------------------------------------------------------ T3
COLORS = ('red', 'green', 'blue', 'white')
results = []
N = 0
def onAppStart(app):
    app.stepsPerSecond = 1000
    app.frame = 0
    app.n = N
    app.start = supervisor.ticks_ms()
def onStep(app):
    app.frame += 1
    if app.frame == 100:
        ms = cmu_embedded_graphics._ticksDiff(supervisor.ticks_ms(), app.start)
        results.append((app.n, 100000 / ms))
        app.stop()
def redrawAll(app):
    # The background changes every frame, so the whole screen is resent.
    app_bg = COLORS[app.frame % 4]
    drawRect(0, 0, 240, 240, fill=app_bg)
    for i in range(app.n):
        drawCircle(30 + (i * 37 + app.frame) % 180, 30 + (i * 53) % 180, 8,
                   fill='black')
for N in (0, 20, 60):
    runApp()
for n, fps in results:
    print('T3 full-screen fps with %d shapes: %.1f' % (n, fps))

# ------------------------------------------------------------------ T4
mem = []
def onAppStart(app):
    app.stepsPerSecond = 1000
    app.frame = 0
def onStep(app):
    app.frame += 1
    if app.frame in (10, 500, 1000):
        gc.collect()
        mem.append(gc.mem_free())
    if app.frame == 1000:
        app.stop()
def redrawAll(app):
    x = app.frame % 200
    drawCircle(20 + x, 120, 10, fill='gold', border='white')
    drawRect(x, 40, 30, 20, fill='teal', rotateAngle=app.frame)
    drawLine(0, 0, x, 240, fill='red')
    drawLabel('frame %d' % app.frame, 120, 200, size=24)
runApp()
print('T4 free RAM at frames 10/500/1000:', mem, '(should be flat)')
print('done')
