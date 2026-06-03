@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "ROOT=%~dp0"
set "VENV=%ROOT%_venv"
title Sound IQ Setup

echo ============================================
echo         Sound IQ - Setup
echo ============================================
echo.

:: ---- Step 1: Find a working Python ----
set "PYEXE="

:: Check common install paths first
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\python.exe"
    "%ProgramFiles%\Python\Python314\python.exe"
    "%ProgramFiles%\Python\Python313\python.exe"
    "%ProgramFiles%\Python\Python312\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
) do (
    if exist %%p (
        set "PYEXE=%%~p"
        goto :pyfound
    )
)

:: Check PATH but skip WindowsApps stub (which shows "Microsoft Store" message)
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    "%%i" --version 2>&1 | findstr /R "Python\.[0-9]" >nul 2>&1
    if not errorlevel 1 (
        set "PYEXE=%%i"
        goto :pyfound
    )
)

:: ---- Step 2: No working Python - download and install ----
:download_python
echo.
echo Python not found or not working.
echo Downloading Python 3.14.5...
echo.

powershell -Command "& {curl.exe -L -o '%TEMP%\python-3.14.5-amd64.exe' 'https://www.python.org/ftp/python/3.14.5/python-3.14.5-amd64.exe'}"
if not exist "%TEMP%\python-3.14.5-amd64.exe" (
    echo Failed to download. Trying PowerShell fallback...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = 'tls12'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.14.5/python-3.14.5-amd64.exe' -OutFile '%TEMP%\python-3.14.5-amd64.exe'}"
)
if not exist "%TEMP%\python-3.14.5-amd64.exe" (
    echo.
    echo Download failed. Please install Python 3.10+ manually from:
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Installing Python (this may take a minute)...
start /wait "" "%TEMP%\python-3.14.5-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 TargetDir="%LOCALAPPDATA%\Programs\Python\Python314"

:: Find the fresh install
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto :pyfound
)

:: One more try with path search
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    "%%i" --version 2>&1 | findstr /R "Python\.[0-9]" >nul 2>&1
    if not errorlevel 1 (
        set "PYEXE=%%i"
        goto :pyfound
    )
)

echo Python installation may have failed. Please install manually.
pause
exit /b 1

:: ---- Step 3: Python found - proceed ----
:pyfound
echo Python: "%PYEXE%"
"%PYEXE%" --version
echo.

:: ---- Step 4: Create virtual environment ----
if not exist "%VENV%" (
    echo Creating virtual environment...
    "%PYEXE%" -m venv "%VENV%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: ---- Step 5: Install packages ----
echo Installing packages (this may take 10-15 minutes)...
echo.
call "%VENV%\Scripts\activate.bat"

echo [1/5] Upgrading pip...
python -m pip install --upgrade pip --no-cache-dir --quiet

echo [2/5] Installing PyTorch (CPU-only)...
pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
if errorlevel 1 (
    echo Retrying PyTorch without CPU index...
    pip install torch --no-cache-dir
)

echo [3/5] Installing audio libraries (soundfile, sounddevice)...
pip install soundfile sounddevice --no-cache-dir

echo [4/5] Installing AI libraries (librosa, transformers)...
pip install librosa transformers --no-cache-dir

echo [5/5] Installing GUI and utilities (PySide6, pywin32, numpy)...
pip install PySide6 pywin32 numpy --no-cache-dir

:: ---- Step 6: Create desktop shortcut ----
echo.
echo Creating desktop shortcut...
call "%VENV%\Scripts\python.exe" create_shortcut.py

echo.
echo ============================================
echo   Setup complete!
echo   Click on the shortcut on your desktop.
echo ============================================
pause
