# Fake board: pin names only, no DISPLAY.
for _n in range(29):
    globals()['GP%d' % _n] = 'GP%d' % _n
A0, A1 = GP26, GP27
