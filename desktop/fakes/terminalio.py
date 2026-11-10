# Fake terminalio.FONT: 6x12 glyphs for printable ASCII only.


class _Glyph:
    def __init__(self, tile_index):
        self.tile_index = tile_index


class _Font:
    bitmap = 'font-bitmap'

    def get_bounding_box(self):
        return (6, 12)

    def get_glyph(self, codepoint):
        if 32 <= codepoint < 127:
            return _Glyph(codepoint - 32)
        return None


FONT = _Font()
