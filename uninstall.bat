@echo off
REM ============================================================================
REM Sound IQ v2.0 - Uninstaller
REM ============================================================================
REM This script safely removes Sound IQ build files
REM ============================================================================

title Sound IQ Uninstaller
cls

echo.
echo ============================================================================
echo                    SOUND IQ UNINSTALLER
echo ============================================================================
echo.
echo This will remove Sound IQ build files:
echo   - build/ folder
echo   - __pycache__/ folder
echo   - SoundIQ.spec
echo.
echo Your SoundIQ.exe will NOT be deleted.
echo If you want to remove everything, delete the dist/ folder manually.
echo.
echo.

set /p CONFIRM="Are you sure? (Y/N): "

if /i "%CONFIRM%"=="Y" (
    echo.
    echo Removing build artifacts...
    echo.
    
    if exist "build" (
        echo Removing build folder...
        rmdir /s /q build
        echo [OK] Removed build
    )
    
    if exist "__pycache__" (
        echo Removing __pycache__ folder...
        rmdir /s /q __pycache__
        echo [OK] Removed __pycache__
    )
    
    if exist "SoundIQ.spec" (
        echo Removing SoundIQ.spec...
        del /q SoundIQ.spec
        echo [OK] Removed SoundIQ.spec
    )
    
    echo.
    echo Cleanup complete!
    echo.
    echo Your dist\SoundIQ.exe is still available.
    echo You can delete the entire project folder if you no longer need it.
    echo.
) else (
    echo.
    echo Cancelled. No files were removed.
    echo.
)

pause
exit /b 0
