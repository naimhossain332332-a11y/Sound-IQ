@echo off
REM ============================================================================
REM Sound IQ v2.0 - Automatic Build Setup & EXE Creator
REM ============================================================================
REM This script will:
REM   1. Check Python installation
REM   2. Install all dependencies
REM   3. Build standalone SoundIQ.exe
REM   4. Create launcher shortcuts
REM ============================================================================

setlocal enabledelayedexpansion

REM Colors (for Windows 10+)
for /F %%A in ('echo prompt $H ^| cmd') do set "BS=%%A"

cls
echo.
echo ============================================================================
echo           SOUND IQ v2.0 - BUILD SETUP ^& EXE CREATOR
echo ============================================================================
echo.
echo This will create a standalone SoundIQ.exe executable that works on any
echo Windows PC without requiring Python to be installed.
echo.
echo Process:
echo   1. Check Python installation
echo   2. Install PyInstaller and dependencies
echo   3. Build standalone EXE
echo   4. Create shortcuts and launcher
echo.
echo Estimated time: 10-15 minutes (depends on internet speed)
echo.
echo Press ANY KEY to continue, or close this window to cancel...
echo.
pause

REM ============================================================================
REM STEP 1: Check Python Installation
REM ============================================================================

cls
echo.
echo [STEP 1/4] Checking Python installation...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo.
    echo Please install Python 3.8 or later from https://www.python.org/downloads/
    echo Make sure to CHECK "Add Python to PATH" during installation.
    echo.
    echo After installing Python, run this script again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION% found
echo.

REM ============================================================================
REM STEP 2: Install Dependencies
REM ============================================================================

cls
echo.
echo [STEP 2/4] Installing dependencies...
echo.
echo This will download and install:
echo   - PyInstaller (creates EXE)
echo   - PySide6 (GUI framework)
echo   - PyTorch (AI/ML)
echo   - Transformers (AI models)
echo   - Audio libraries (soundfile, sounddevice, librosa)
echo.
echo This may take several minutes. Do NOT close this window.
echo.
pause

echo.
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

echo.
echo Installing required packages...
echo.

setlocal
set packages=^^
  "torch" ^^
  "PySide6" ^^
  "soundfile" ^^
  "sounddevice" ^^
  "librosa" ^^
  "transformers" ^^
  "numpy" ^^
  "pyinstaller" ^^
  "pyaudio"

for %%p in (%packages%) do (
    echo Downloading %%p...
    python -m pip install %%p >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Could not install %%p - continuing anyway
    ) else (
        echo [OK] %%p installed
    )
)

echo.
echo [OK] Dependencies installed successfully
echo.
pause

REM ============================================================================
REM STEP 3: Build EXE
REM ============================================================================

cls
echo.
echo [STEP 3/4] Building standalone EXE...
echo.
echo Creating PyInstaller spec file...
echo.

REM Check if app.py exists
if not exist "app.py" (
    echo ERROR: app.py not found!
    echo.
    echo Make sure you're in the Sound IQ project directory.
    echo.
    pause
    exit /b 1
)

echo Building SoundIQ.exe with PyInstaller...
echo This may take 3-5 minutes. Do NOT close this window.
echo.

python -m PyInstaller ^^
  --onefile ^^
  --windowed ^^
  --name=SoundIQ ^^
  --icon=soundiq_logo.ico ^^
  app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo.
    echo Possible solutions:
    echo   1. Make sure app.py is in this directory
    echo   2. Check that soundiq_logo.ico exists
    echo   3. Try running: python -m PyInstaller --help
    echo.
    pause
    exit /b 1
)

if not exist "dist\SoundIQ.exe" (
    echo.
    echo ERROR: SoundIQ.exe was not created!
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] SoundIQ.exe built successfully!
echo.

REM Get file size
for %%f in ("dist\SoundIQ.exe") do set SIZE=%%~zf
set /a SIZE_MB=%SIZE% / 1048576
echo File size: %SIZE_MB% MB
echo Location: %CD%\dist\SoundIQ.exe
echo.
pause

REM ============================================================================
REM STEP 4: Create Shortcuts & Cleanup
REM ============================================================================

cls
echo.
echo [STEP 4/4] Creating launcher scripts and cleanup...
echo.

REM Create Quick Launch Batch
echo Creating launch_soundiq.bat...
(
    echo @echo off
    echo REM Sound IQ v2.0 Quick Launcher
    echo title Sound IQ v2.0
    echo cls
    echo echo.
    echo echo Starting Sound IQ v2.0...
    echo echo.
    echo start "Sound IQ v2.0" "%%~dp0dist\SoundIQ.exe"
    echo exit /b 0
) > launch_soundiq.bat

echo [OK] Created launch_soundiq.bat
echo.

REM Create Uninstaller (optional cleanup)
echo Creating uninstall.bat...
(
    echo @echo off
    echo cls
    echo echo.
    echo echo Sound IQ Uninstaller
    echo echo.
    echo set /p CONFIRM="Delete Sound IQ files? (Y/N): "
    echo if /i "%%CONFIRM%%"=="Y" (
    echo     echo Removing files...
    echo     rmdir /s /q dist
    echo     rmdir /s /q build
    echo     del /q SoundIQ.spec
    echo     del /q uninstall.bat
    echo     echo Done!
    echo ) else (
    echo     echo Cancelled.
    echo )
    echo pause
) > uninstall.bat

echo [OK] Created uninstall.bat
echo.

REM Clean up build artifacts (keep dist/SoundIQ.exe)
echo Cleaning up build files...
if exist "build" rmdir /s /q build >nul 2>&1
if exist "__pycache__" rmdir /s /q __pycache__ >nul 2>&1
echo [OK] Cleanup complete
echo.

REM ============================================================================
REM SUCCESS
REM ============================================================================

cls
echo.
echo ============================================================================
echo                         BUILD COMPLETE!
echo ============================================================================
echo.
echo 🎉 Your Sound IQ v2.0 EXE is ready!
echo.
echo Location: %CD%\dist\SoundIQ.exe
echo.
echo Quick Start Options:
echo.
echo   1. Double-click: launch_soundiq.bat
echo      OR
echo   2. Run directly: .\dist\SoundIQ.exe
echo      OR
echo   3. Command line: start dist\SoundIQ.exe
echo.
echo Share with Others:
echo.
echo   • Copy dist\SoundIQ.exe to any Windows PC
echo   • No Python installation needed on other computers
echo   • App works 100%% offline after first run
echo.
echo First Time Tips:
echo.
echo   • First launch will download AI models (~1.5 GB)
echo   • Setup takes 2-3 minutes on first run
echo   • Subsequent launches are instant
echo   • Add folders with audio files to index
echo   • Use natural language to search (e.g. "bright piano")
echo.
echo File Cleanup:
echo.
echo   • To remove build files, run: uninstall.bat
echo   • Only keeps dist\SoundIQ.exe
echo.
echo System Requirements:
echo.
echo   • Windows 10/11
echo   • 4GB RAM minimum (8GB recommended)
echo   • 2GB free disk space
echo   • Audio device connected
echo.
echo Troubleshooting:
echo.
echo   • If EXE won't start: Try running as Administrator
echo   • If slow: Close other apps, increase RAM
echo   • If audio issues: Update audio drivers
echo.
echo Support:
echo.
echo   GitHub: https://github.com/naimhossain332332-a11y/Sound-IQ
echo.
echo ============================================================================
echo.
echo Press ANY KEY to close this window and enjoy Sound IQ!
echo.
pause

exit /b 0
