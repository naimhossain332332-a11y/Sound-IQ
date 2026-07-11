@echo off
REM ============================================================================
REM Sound IQ v2.0 - Quick Launcher
REM ============================================================================
REM Double-click this file to launch Sound IQ
REM ============================================================================

title Sound IQ v2.0
cls

echo.
echo Launching Sound IQ v2.0...
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%dist\SoundIQ.exe"

REM Check if EXE exists
if not exist "%EXE_PATH%" (
    echo ERROR: SoundIQ.exe not found!
    echo.
    echo Please run BuildSetup.bat first to build the EXE.
    echo.
    pause
    exit /b 1
)

echo Found: %EXE_PATH%
echo.
echo Starting application...
echo.

REM Launch the application
start "Sound IQ v2.0" "%EXE_PATH%"

echo Application launched!
echo You can close this window.
echo.
pause
exit /b 0
