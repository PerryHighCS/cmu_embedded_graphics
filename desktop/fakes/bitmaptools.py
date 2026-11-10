# Fake bitmaptools.readinto for the BMP layouts the library uses: rows
# padded to 4 bytes, MSB-first pixels within bytes, bottom-up if
# reverse_rows.


def readinto(bitmap, file, bits_per_pixel, element_size=1,
             reverse_pixels_in_element=False, swap_bytes_in_element=False,
             reverse_rows=False):
    bpp = bits_per_pixel
    stride = ((bitmap.width * bpp + 31) // 32) * 4
    mask = (1 << bpp) - 1
    for row in range(bitmap.height):
        data = file.read(stride)
        y = bitmap.height - 1 - row if reverse_rows else row
        for x in range(bitmap.width):
            bit = x * bpp
            value = (data[bit // 8] >> (8 - bpp - bit % 8)) & mask
            bitmap.pixels[y * bitmap.width + x] = value
