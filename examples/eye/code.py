# Blinking eye: the EyePi demo (github.com/mrbdahlem/EyePi, based on
# sample code by Tod Kurt, todbot.com), rewritten for cmu_embedded_graphics.
#
# Put this file on CIRCUITPY as code.py and the images folder as
# CIRCUITPY/images ("deploy eye" does both).
# Type a space in the serial console to blink right away.
#
# The open eye fills the screen. To blink, a smaller picture of the closed
# lids is drawn over it. Its background is a bright green that
# transparentColor hides, so the open eye shows around the lids.
# (transparentColor is an EyePi extra; desktop CMU Graphics doesn't have it.)

from cmu_embedded_graphics import *     # also gives random(), as on desktop

GREEN_SCREEN = rgb(45, 255, 0)


def onAppStart(app):
    app.stepsPerSecond = 20
    app.closed = False
    app.nextChange = 0
    openLater(app)


def openLater(app):
    # Open eye for 2 to 10 seconds, like the original.
    app.closed = False
    app.nextChange = app.elapsedTime + 2 + random() * 8


def onKeyPress(app, key):
    if key == 'space':
        app.nextChange = app.elapsedTime


def onStep(app):
    if app.elapsedTime < app.nextChange:
        return
    if app.closed:
        openLater(app)
    else:
        # Shut for a random fraction of a second.
        app.closed = True
        app.nextChange = app.elapsedTime + random()


def redrawAll(app):
    drawImage('images/open.bmp', 0, 0)
    if app.closed:
        drawImage('images/closedsm.bmp', 120, 120, align='center',
                  transparentColor=GREEN_SCREEN)


runApp()
