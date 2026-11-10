// This file is part of the CircuitPython project: https://circuitpython.org
//
// SPDX-FileCopyrightText: Copyright (c) 2021 Scott Shawcroft for Adafruit Industries
//
// SPDX-License-Identifier: MIT
//
// EyePi: RP2040 + GC9A01 240x240 round display. Based on raspberry_pi_pico
// (CircuitPython 10.3.1), which the original EyePi firmware also used.

#pragma once

#define MICROPY_HW_BOARD_NAME "EyePi"
#define MICROPY_HW_MCU_NAME "rp2040"

#define MICROPY_HW_LED_STATUS (&pin_GPIO25)

// board.I2C() uses the A0/A1 expansion connector (RP2040 I2C1).
#define CIRCUITPY_BOARD_I2C         (1)
#define CIRCUITPY_BOARD_I2C_PIN     {{.scl = &pin_GPIO27, .sda = &pin_GPIO26}}
