# Fake supervisor with a controllable clock. Each ticks_ms() call advances
# the clock by `autoAdvance` ms so a run loop always makes progress.
now = 0
autoAdvance = 1


def ticks_ms():
    global now
    now = (now + autoAdvance) & 0x3FFFFFFF
    return now


class _Runtime:
    serial_bytes_available = 0


runtime = _Runtime()
