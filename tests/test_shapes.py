# test_shapes.py - visual check of every MVP shape. Deploy as code.py
# ("deploy shapes"). Type any key in the serial console to rotate the
# screen 90 degrees.
#
# Expect, inside the round screen on a dark gray background:
#   top row:    red square, green square with thick white border,
#               hollow blue square outline
#   middle row: gold circle, purple circle with white border,
#               hollow cyan ring
#   lines:      a thin white horizontal line, a thick orange diagonal,
#               a pink rectangle rotated 30 degrees
#   labels:     'size 12' small, 'size 24' twice as large, 'opacity 50'
#               in a dimmer white

from cmu_embedded_graphics import *


def onAppStart(app):
    app.background = rgb(40, 40, 40)
    app.stepsPerSecond = 0


def onKeyPress(app, key):
    app.rotation = (app.rotation + 90) % 360


def redrawAll(app):
    drawRect(50, 50, 30, 30, fill='red')
    drawRect(105, 50, 30, 30, fill='green', border='white', borderWidth=4)
    drawRect(160, 50, 30, 30, fill=None, border='blue', borderWidth=3)

    drawCircle(65, 115, 15, fill='gold')
    drawCircle(120, 115, 15, fill='purple', border='white', borderWidth=3)
    drawCircle(175, 115, 15, fill=None, border='cyan', borderWidth=3)

    drawLine(40, 145, 200, 145, fill='white', lineWidth=1)
    drawLine(50, 155, 110, 190, fill='orange', lineWidth=6)
    drawRect(165, 172, 50, 16, fill='hotPink', rotateAngle=30,
             align='center')

    drawLabel('size 12', 120, 200, fill='white')
    drawLabel('size 24', 120, 30, size=24, fill='white')
    drawLabel('opacity 50', 120, 218, fill='white', opacity=50)
    drawLabel('rotation %d' % app.rotation, 120, 10, fill='white')


runApp()
