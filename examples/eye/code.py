# Blinking eye: the EyePi demo (github.com/mrbdahlem/EyePi, based on
# sample code by Tod Kurt, todbot.com), rewritten for cmu_embedded_graphics.
#
# Put this file on CIRCUITPY as code.py and the images folder as
# CIRCUITPY/images ("deploy eye" does both).
# Type a space in the serial console to blink right away.

import random

from cmu_embedded_graphics import *

# Blink frames, from open to shut. The EyePi repo calls the in-between
# frames left.bmp and right.bmp.
FRAMES = ['images/open.bmp', 'images/left.bmp', 'images/right.bmp',
          'images/closed.bmp']
FRAME_TIME = 0.04       # seconds per in-between frame


def onAppStart(app):
    app.background = 'black'
    app.stepsPerSecond = 30
    app.frame = 0           # index into FRAMES
    app.closing = False
    app.opening = False
    app.nextChange = 0
    scheduleBlink(app)


def scheduleBlink(app):
    # Blink again in 2 to 10 seconds, like the original.
    app.nextChange = app.elapsedTime + 2 + random.random() * 8


def onKeyPress(app, key):
    if key == 'space' and not (app.closing or app.opening):
        app.nextChange = app.elapsedTime


def onStep(app):
    now = app.elapsedTime
    if now < app.nextChange:
        return
    last = len(FRAMES) - 1
    if app.opening:
        app.frame -= 1
        if app.frame == 0:
            app.opening = False
            scheduleBlink(app)
        else:
            app.nextChange = now + FRAME_TIME
    elif app.closing or app.frame == 0:
        app.closing = True
        app.frame += 1
        if app.frame == last:
            # Stay shut for a random fraction of a second.
            app.closing = False
            app.opening = True
            app.nextChange = now + random.random()
        else:
            app.nextChange = now + FRAME_TIME


def redrawAll(app):
    drawImage(FRAMES[app.frame], 0, 0)


runApp()
