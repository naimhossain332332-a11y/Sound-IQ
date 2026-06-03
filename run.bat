@echo off
cd /d "%~dp0"

:: Use venv if available
if exist "_venv\Scripts\python.exe" (
    start "" "%~dp0_venv\Scripts\python.exe" app.py
    exit
)

:: Find real Python (skip WindowsApps stub)
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    "%%i" --version 2>&1 | findstr /R "Python\.[0-9]" >nul 2>&1
    if not errorlevel 1 (
        start "" "%%i" app.py
        exit
    )
)

:: Check common install paths
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%ProgramFiles%\Python\Python314\python.exe"
) do (
    if exist %%p (
        start "" %%p app.py
        exit
    )
)

echo Python not found. Run setup.bat first.
pause
