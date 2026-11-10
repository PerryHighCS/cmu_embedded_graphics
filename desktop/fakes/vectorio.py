# Fake vectorio shapes: plain attribute holders that count writes.


class _Shape:
    def __init__(self, pixel_shader, x=0, y=0, **kw):
        object.__setattr__(self, 'writes', 0)
        self.pixel_shader = pixel_shader
        self.x = x
        self.y = y
        self.hidden = False
        for k, v in kw.items():
            setattr(self, k, v)
        object.__setattr__(self, 'writes', 0)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        object.__setattr__(self, 'writes', self.writes + 1)

    @property
    def color(self):
        return self.pixel_shader[0]


class Rectangle(_Shape):
    def __init__(self, pixel_shader, width, height, x=0, y=0):
        if width < 1 or height < 1:
            raise ValueError('width and height must be >= 1')
        super().__init__(pixel_shader, x, y, width=width, height=height)


class Circle(_Shape):
    def __init__(self, pixel_shader, radius, x=0, y=0):
        super().__init__(pixel_shader, x, y, radius=radius)


class Polygon(_Shape):
    def __init__(self, pixel_shader, points, x=0, y=0):
        super().__init__(pixel_shader, x, y, points=points)
