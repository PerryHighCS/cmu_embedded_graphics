@echo off
rem Compile cmu_embedded_graphics.py into cmu_embedded_graphics.mpy.
rem
rem   build             compile
rem   build deploy      compile, then run deploy.cmd
rem   build deploy test compile, then deploy tests\test_basic.py as code.py
rem
rem mpy-cross cannot run from a OneDrive folder, so it is kept in
rem %LOCALAPPDATA%\cmu_embedded_graphics and downloaded from Adafruit the
rem first time. Its version must match the board's CircuitPython
rem (boot_out.txt).

setlocal
cd /d "%~dp0"

set VERSION=10.3.1
set TOOLDIR=%LOCALAPPDATA%\cmu_embedded_graphics
set MPYCROSS=%TOOLDIR%\mpy-cross-%VERSION%.exe
set URL=https://adafruit-circuit-python.s3.amazonaws.com/bin/mpy-cross/windows/mpy-cross-windows-%VERSION%.static.exe

if not exist "%MPYCROSS%" (
    echo Downloading mpy-cross %VERSION%...
    if not exist "%TOOLDIR%" mkdir "%TOOLDIR%"
    curl.exe -sSfL -o "%MPYCROSS%.part" "%URL%" || (
        echo Download failed: %URL%
        exit /b 1
    )
    move /y "%MPYCROSS%.part" "%MPYCROSS%" >nul
)

"%MPYCROSS%" -o cmu_embedded_graphics.mpy cmu_embedded_graphics.py || (
    echo Build failed.
    exit /b 1
)
echo Built cmu_embedded_graphics.mpy with mpy-cross %VERSION%

if /i "%1"=="deploy" call deploy.cmd %2
