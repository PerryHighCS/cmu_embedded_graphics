# Demo: a bouncing ball on the round screen.
# Type in the serial console: arrow keys nudge the ball, space pauses,
# r rotates the screen, c changes color.

from cmu_embedded_graphics import *

COLORS = ['crimson', 'gold', 'limeGreen', 'deepSkyBlue', 'violet']


def onAppStart(app):
    app.background = 'midnightBlue'
    app.stepsPerSecond = 30
    app.x = 120
    app.y = 80
    app.dx = 3
    app.dy = 2
    app.r = 14
    app.color = 0
    app.bounces = 0


def onStep(app):
    app.x += app.dx
    app.y += app.dy
    # Stay inside the round screen: bounce off a circle of radius 110.
    cx = app.x - 120
    cy = app.y - 120
    if cx * cx + cy * cy > (110 - app.r) ** 2:
        app.dx = -app.dx
        app.dy = -app.dy
        app.x += app.dx
        app.y += app.dy
        app.bounces += 1


def onKeyPress(app, key):
    if key == 'space':
        app.paused = not app.paused
    elif key == 'r':
        app.rotation = (app.rotation + 90) % 360
    elif key == 'c':
        app.color = (app.color + 1) % len(COLORS)
    elif key == 'left':
        app.dx -= 1
    elif key == 'right':
        app.dx += 1
    elif key == 'up':
        app.dy -= 1
    elif key == 'down':
        app.dy += 1


def redrawAll(app):
    drawCircle(120, 120, 110, fill=None, border='white', borderWidth=2)
    drawLine(60, 120, 180, 120, fill='slateGray', lineWidth=1)
    drawRect(120, 40, 60, 16, fill='darkSlateBlue', align='center')
    drawLabel('Bounces: ' + str(app.bounces), 120, 40, fill='white')
    drawCircle(app.x, app.y, app.r, fill=COLORS[app.color],
               border='white', borderWidth=2)
    if app.paused:
        drawLabel('PAUSED', 120, 190, fill='gold', size=24)


runApp()
