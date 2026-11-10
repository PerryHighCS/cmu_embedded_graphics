# test_shapes.py - visual check of every shape. Deploy as code.py
# ("deploy shapes"). In the serial console: space switches pages,
# r rotates the screen 90 degrees. Uses screens, so it checks those too.
#
# Page 1, on a dark gray background:
#   top row:    red square, green square with thick white border,
#               hollow blue square outline
#   middle row: gold circle, purple circle with white border,
#               hollow cyan ring
#   lines:      a thin white horizontal line, a thick orange diagonal,
#               a pink rectangle rotated 30 degrees
#   labels:     'size 24' at the top, 'size 12', 'opacity 50' dimmer
#
# Page 2, on black:
#   orange oval with white border; cyan oval outline tilted 30 degrees
#   gold pie with a wedge cut out on the right (like Pac-Man)
#   green half-circle outline, flat side on the right
#   red 5-point star with white border in the middle
#   violet hexagon; yellow 4-sided outline; orange 8-point star outline
#   teal bar tilted 20 degrees at the top
#   white arrow pointing down-right; pink double-headed arrow
#
# Page 3 (dashes), on dark blue:
#   white dashed ring near the edge; teal box with yellow dashed border
#   (corners stay square); cyan dashed oval; red star with white dashed
#   border; gold dashed Pac-Man outline; green dotted 4-sided outline;
#   pink dashed line with a solid arrowhead; orange dashed line with a
#   solid arrowhead at its left end; violet dashed tilted box

from cmu_embedded_graphics import *


def onAppStart(app):
    app.stepsPerSecond = 0


def turn(app, key):
    if key == 'r':
        app.rotation = (app.rotation + 90) % 360


def basic_onKeyPress(app, key):
    turn(app, key)
    if key == 'space':
        setActiveScreen('more')


def basic_redrawAll(app):
    drawRect(0, 0, 240, 240, fill=rgb(40, 40, 40))
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


def more_onKeyPress(app, key):
    turn(app, key)
    if key == 'space':
        setActiveScreen('dashes')


def more_redrawAll(app):
    drawRect(0, 0, 240, 240, fill='black')
    drawCircle(120, 120, 118, fill='midnightBlue')
    drawOval(70, 60, 70, 36, fill='orange', border='white', borderWidth=3)
    drawOval(170, 60, 70, 36, fill=None, border='cyan', borderWidth=4,
             rotateAngle=30)
    drawArc(60, 125, 70, 70, 30, 300, fill='gold')
    drawArc(180, 125, 70, 50, 90, 180, fill=None, border='lime',
            borderWidth=3)
    drawStar(120, 120, 34, 5, fill='red', border='white', borderWidth=2)
    drawRegularPolygon(80, 185, 24, 6, fill='violet', rotateAngle=15)
    drawPolygon(140, 165, 190, 175, 170, 215, 135, 200, fill=None,
                border='yellow', borderWidth=3)
    drawRect(120, 30, 40, 14, fill='teal', rotateAngle=20, align='center')
    drawLine(30, 100, 95, 150, fill='white', lineWidth=3, arrowEnd=True)
    drawLine(150, 100, 210, 100, fill='pink', lineWidth=2, arrowStart=True,
             arrowEnd=True)
    drawStar(200, 190, 22, 8, fill=None, border='orange', borderWidth=2,
             roundness=60)


def dashes_onKeyPress(app, key):
    turn(app, key)
    if key == 'space':
        setActiveScreen('basic')


def dashes_redrawAll(app):
    drawRect(0, 0, 240, 240, fill='black')
    drawCircle(120, 120, 118, fill='midnightBlue')
    drawCircle(120, 120, 108, fill=None, border='white', dashes=True)
    drawRect(40, 40, 70, 45, fill='teal', border='yellow', borderWidth=4,
             dashes=[12, 6])
    drawOval(170, 62, 70, 40, fill=None, border='cyan', borderWidth=3,
             dashes=True, rotateAngle=20)
    drawStar(120, 130, 40, 5, fill='red', border='white', borderWidth=3,
             dashes=[8, 4])
    drawArc(60, 150, 60, 60, 30, 300, fill=None, border='gold',
            borderWidth=3, dashes=True)
    drawPolygon(160, 140, 210, 150, 190, 200, 150, 185, fill=None,
                border='lime', borderWidth=3, dashes=[4])
    drawLine(40, 205, 200, 205, fill='pink', lineWidth=3, dashes=[10, 5],
             arrowEnd=True)
    drawLine(150, 100, 215, 125, fill='orange', dashes=True,
             arrowStart=True)
    drawRect(95, 180, 50, 14, fill=None, border='violet', rotateAngle=-15,
             dashes=True)


runAppWithScreens('basic')
