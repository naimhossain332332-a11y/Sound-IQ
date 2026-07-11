@echo off
REM ============================================================================
REM Sound IQ v2.0 - ONE-CLICK EXE BUILDER
REM ============================================================================
REM Just double-click this file and you get SoundIQ.exe!
REM No other steps needed!
REM ============================================================================

setlocal enabledelayedexpansion

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    cls
    echo.
    echo ============================================================================
    echo                             ERROR
    echo ============================================================================
    echo.
    echo Python not found! Please install Python 3.8 or later from:
    echo.
    echo     https://www.python.org/downloads/
    echo.
    echo Important: CHECK "Add Python to PATH" during installation!
    echo.
    echo After installing Python, run this file again.
    echo.
    echo ============================================================================
    echo.
    pause
    exit /b 1
)

REM Run the Python builder
python BUILD_SOUNDIQ.py

if errorlevel 1 (
    echo.
    echo Build failed! Check the error messages above.
    echo.
    pause
    exit /b 1
)

exit /b 0
