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

    def __len__(self):
        return len(self.colors)


class ColorConverter:
    def __init__(self):
        self.transparent = set()

    def make_transparent(self, color):
        self.transparent.add(color)


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

    def pop(self, i=-1):
        return self.items.pop(i)


class Bitmap:
    # Raises MemoryError past `budget` bytes in total, to test fallbacks.
    budget = None
    allocated = 0

    def __init__(self, width, height, value_count):
        size = width * height
        if Bitmap.budget is not None and Bitmap.allocated + size > Bitmap.budget:
            raise MemoryError('fake out of memory')
        Bitmap.allocated += size
        import weakref
        weakref.finalize(self, Bitmap._free, size)
        self.width = width
        self.height = height
        self.value_count = value_count
        self.pixels = [0] * size

    @staticmethod
    def _free(size):
        Bitmap.allocated -= size

    def __getitem__(self, xy):
        x, y = xy
        return self.pixels[y * self.width + x]


class OnDiskBitmap:
    def __init__(self, path):
        import struct
        with open(path, 'rb') as f:
            header = f.read(54)
        self.path = path
        self.width, height = struct.unpack_from('<ii', header, 18)
        self.height = abs(height)
        self.pixel_shader = ColorConverter()


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
