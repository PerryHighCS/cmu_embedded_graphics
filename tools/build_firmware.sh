#!/usr/bin/env bash
# Build CircuitPython 10.3.1 for the EyePi board (boards/eyepi), freezing
# cmu_embedded_graphics.py into the firmware once it exists.
#
# Run in Linux (GitHub Actions does this; see .github/workflows) with
# CircuitPython's build dependencies installed.
# Usage: bash tools/build_firmware.sh /path/to/circuitpython-10.3.1
set -euo pipefail

CP_VERSION='10.3.1'
BOARD='eyepi'

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 1 ]]; then
    echo "Usage: bash tools/build_firmware.sh /path/to/circuitpython-$CP_VERSION" >&2
    exit 1
fi
cp_dir="$(cd "$1" && pwd)"
if [[ "$(git -C "$cp_dir" describe --tags --exact-match HEAD)" != "$CP_VERSION" ]]; then
    echo "Use a dedicated CircuitPython checkout at tag $CP_VERSION." >&2
    exit 1
fi
for tool in make gcc arm-none-eabi-gcc python3; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
arm-none-eabi-gcc --version

port_dir="$cp_dir/ports/raspberrypi"

# Install our board definition into the checkout.
rm -rf "$port_dir/boards/$BOARD"
cp -r "$project_dir/boards/$BOARD" "$port_dir/boards/$BOARD"

# Fetch only what this board needs (pico-sdk, tinyusb, ...), not every
# submodule in the repository.
make -C "$port_dir" BOARD="$BOARD" fetch-board-submodules
# Frozen-module manifests can need micropython-lib; fetch just that.
git -C "$cp_dir" submodule update --init --depth 1 -- lib/micropython-lib

# Frozen modules. FROZEN_MPY_DIRS must be set in the board's .mk file:
# py/circuitpy_mpconfig.mk decides whether to build frozen_content.o before
# user_post_mpconfigport.mk is read, so setting it there links without the
# frozen modules (undefined mp_frozen_names). Only the checkout's copy of
# the board file is changed, so boards/eyepi stays buildable without it.
if [[ -f "$project_dir/cmu_embedded_graphics.py" ]]; then
    rm -rf "$cp_dir/cmu_frozen"
    mkdir -p "$cp_dir/cmu_frozen"
    # Freeze the source with the firmware's own mpy-cross.
    cp "$project_dir/cmu_embedded_graphics.py" "$cp_dir/cmu_frozen/"
    printf '\n# Added by tools/build_firmware.sh\nFROZEN_MPY_DIRS += $(TOP)/cmu_frozen\n' \
        >> "$port_dir/boards/$BOARD/mpconfigboard.mk"
    echo 'Freezing cmu_embedded_graphics.py'
else
    echo 'cmu_embedded_graphics.py not found; building without frozen modules'
fi

make -C "$cp_dir/mpy-cross" -j"$(nproc)"
make -C "$port_dir" BOARD="$BOARD" -j"$(nproc)"

out="$project_dir/firmware/circuitpython-$BOARD-$CP_VERSION.uf2"
mkdir -p "$project_dir/firmware"
cp "$port_dir/build-$BOARD/firmware.uf2" "$out"
echo "Built $out"
