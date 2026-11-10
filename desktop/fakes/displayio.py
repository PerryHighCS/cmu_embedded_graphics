# Fake displayio: records what the library builds.


class Palette:
    def __init__(self, n):
        self.colors = [0] * n
        self.transparent = set()
        self.writes = 0

    def __setitem__(self, i, color):
        self.colors[i] = color
        self.writes += 1

    def __getitem__(self, i):
        return self.colors[i]

    def make_transparent(self, i):
        self.transparent.add(i)


class Group:
    def __init__(self, scale=1, x=0, y=0):
        self.items = []
        self.scale = scale
        self.x = x
        self.y = y
        self.hidden = False

    def append(self, item):
        self.items.append(item)

    def __setitem__(self, i, item):
        self.items[i] = item

    def __getitem__(self, i):
        return self.items[i]

    def __len__(self):
        return len(self.items)


class TileGrid:
    def __init__(self, bitmap, pixel_shader, width=1, height=1,
                 tile_width=None, tile_height=None, default_tile=0, x=0, y=0):
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader
        self.width = width
        self.height = height
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.tiles = [default_tile] * (width * height)
        self.x = x
        self.y = y
        self.hidden = False

    def __setitem__(self, i, v):
        self.tiles[i] = v

    def __getitem__(self, i):
        return self.tiles[i]


def release_displays():
    pass
