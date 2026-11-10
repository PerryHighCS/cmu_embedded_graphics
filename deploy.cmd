@echo off
rem Copy the library and an app to the EyePi.
rem
rem   deploy            copy cmu_embedded_graphics.mpy and code.py to D:
rem   deploy test       ... but install tests\test_basic.py as code.py
rem   deploy shapes     ... but install tests\test_shapes.py as code.py
rem
rem Set CIRCUITPY to use a drive other than D:, e.g.  set CIRCUITPY=E:
rem
rem This copies the existing cmu_embedded_graphics.mpy. After editing
rem cmu_embedded_graphics.py, run build.cmd first (or "build deploy").

setlocal
cd /d "%~dp0"
if "%CIRCUITPY%"=="" set CIRCUITPY=D:

if not exist "%CIRCUITPY%\boot_out.txt" (
    echo No CIRCUITPY drive found at %CIRCUITPY%
    exit /b 1
)

if exist "%CIRCUITPY%\cmu_embedded_graphics.py" (
    echo WARNING: %CIRCUITPY%\cmu_embedded_graphics.py exists and will be
    echo imported instead of cmu_embedded_graphics.mpy. Delete it from the board.
)

set APP=code.py
if /i "%1"=="test" set APP=tests\test_basic.py
if /i "%1"=="shapes" set APP=tests\test_shapes.py

copy /y cmu_embedded_graphics.mpy "%CIRCUITPY%\cmu_embedded_graphics.mpy" >nul || exit /b 1
copy /y "%APP%" "%CIRCUITPY%\code.py" >nul || exit /b 1
echo Deployed cmu_embedded_graphics.mpy and %APP% to %CIRCUITPY%
