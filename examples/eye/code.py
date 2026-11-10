# Blinking eye: the EyePi demo (github.com/mrbdahlem/EyePi, based on
# sample code by Tod Kurt, todbot.com), rewritten for cmu_embedded_graphics.
#
# Put this file on CIRCUITPY as code.py and the images folder as
# CIRCUITPY/images ("deploy eye" does both).
# Keys in the serial console: space blinks, left/right arrows look.
#
# The open eye fills the screen. To blink or look aside, a smaller picture
# of the eyelids is drawn over it. Its background is a bright green that
# transparentColor hides, so the open eye shows around the lids.
# (transparentColor is an EyePi extra; desktop CMU Graphics doesn't have it.)

import gc
import random

from cmu_embedded_graphics import *

# Overlay picture and its green-screen color for each eye pose.
OVERLAYS = {
    'closed': ('images/closedsm.bmp', rgb(45, 255, 0)),
    'left': ('images/leftsm.bmp', rgb(0, 255, 0)),
    'right': ('images/rightsm.bmp', rgb(0, 255, 0)),
}
SHOW_MEMORY = True      # print free memory each time the pose changes


def onAppStart(app):
    app.stepsPerSecond = 20
    app.pose = 'open'
    app.nextChange = 0
    openLater(app)


def setPose(app, pose, seconds):
    app.pose = pose
    app.nextChange = app.elapsedTime + seconds
    if SHOW_MEMORY and hasattr(gc, 'mem_free'):   # not on desktop
        gc.collect()
        print(pose, 'free memory:', gc.mem_free())


def openLater(app):
    # Open eye for 2 to 10 seconds, like the original.
    setPose(app, 'open', 2 + random.random() * 8)


def onKeyPress(app, key):
    if key == 'space':
        setPose(app, 'closed', random.random())
    elif key == 'left' or key == 'right':
        setPose(app, key, 1 + random.random() * 2)


def onStep(app):
    if app.elapsedTime < app.nextChange:
        return
    if app.pose != 'open':
        openLater(app)
    else:
        # Mostly blink; sometimes glance left or right for 1 to 3 seconds.
        choice = random.random()
        if choice < 0.6:
            setPose(app, 'closed', random.random())
        elif choice < 0.8:
            setPose(app, 'left', 1 + random.random() * 2)
        else:
            setPose(app, 'right', 1 + random.random() * 2)


def redrawAll(app):
    drawImage('images/open.bmp', 0, 0)
    if app.pose != 'open':
        path, green = OVERLAYS[app.pose]
        drawImage(path, 120, 120, align='center', transparentColor=green)


runApp()
