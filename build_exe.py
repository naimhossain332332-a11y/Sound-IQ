#!/usr/bin/env python3
"""Build standalone Windows EXE with PyInstaller."""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Build EXE with PyInstaller - Option 1 (Portable)."""
    print("""
╔════════════════════════════════════════════════════════════════╗
║           🚀 Sound IQ v2.0 - Building EXE (Portable)           ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    # Check prerequisites
    try:
        import PyInstaller
        print("✅ PyInstaller found")
    except ImportError:
        print("❌ PyInstaller not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
    
    # Clean old builds
    print("\n🧹 Cleaning old builds...")
    for folder in ['build', 'dist', '__pycache__', '.pytest_cache']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"   ✅ Removed {folder}")
    
    # Create PyInstaller spec
    print("\n📝 Creating PyInstaller spec...")
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys
import os

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('soundiq_logo.ico', '.'),
        ('soundiq_logo.png', '.'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'soundfile',
        'sounddevice',
        'librosa',
        'transformers',
        'torch',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SoundIQ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='soundiq_logo.ico',
)
'''
    
    with open('SoundIQ.spec', 'w') as f:
        f.write(spec_content)
    print("   ✅ Created SoundIQ.spec")
    
    # Build EXE
    print("\n⚙️  Building EXE with PyInstaller (this may take 2-5 minutes)...")
    print("   This will download and bundle all dependencies...\n")
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name=SoundIQ',
        '--icon=soundiq_logo.ico',
        'app.py'
    ]
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("\n❌ PyInstaller build failed!")
        print("   Try running: pip install --upgrade pyinstaller")
        return False
    
    # Check if EXE was created
    exe_path = os.path.join('dist', 'SoundIQ.exe')
    if not os.path.exists(exe_path):
        print(f"\n❌ EXE not found at {exe_path}")
        return False
    
    # Get file size
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\n✅ EXE built successfully!")
    print(f"   📦 Size: {size_mb:.1f} MB")
    print(f"   📍 Location: {os.path.abspath(exe_path)}")
    
    return True

def create_launcher_script():
    """Create a helper batch file for quick launch."""
    script = r'''@echo off
REM Sound IQ v2.0 Launcher
echo 🎵 Sound IQ v2.0 Starting...
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%dist\SoundIQ.exe"

if not exist "%EXE_PATH%" (
    echo ❌ Error: SoundIQ.exe not found at %EXE_PATH%
    echo.
    echo Please run build_exe.py first to create the EXE
    pause
    exit /b 1
)

echo ✅ Launching Sound IQ from: %EXE_PATH%
echo.

start "Sound IQ v2.0" "%EXE_PATH%"
exit /b 0
'''
    
    with open('launch_soundiq.bat', 'w') as f:
        f.write(script)
    print("\n✅ Created launch_soundiq.bat")

def main():
    print("""
╔════════════════════════════════════════════════════════════════╗
║          🎵 Sound IQ v2.0 - EXE Builder (Portable)             ║
║                                                                ║
║  This will create a standalone EXE that works on any          ║
║  Windows PC without requiring Python to be installed.         ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("❌ Error: app.py not found in current directory")
        print("   Make sure you're in the Sound IQ project directory")
        return
    
    # Check if requirements are installed
    print("\n📋 Checking dependencies...")
    required_packages = {
        'PySide6': 'PySide6',
        'soundfile': 'soundfile',
        'sounddevice': 'sounddevice',
        'librosa': 'librosa',
        'transformers': 'transformers',
        'torch': 'torch',
        'numpy': 'numpy',
    }
    
    missing = []
    for pkg_import, pkg_name in required_packages.items():
        try:
            __import__(pkg_import)
            print(f"   ✅ {pkg_name}")
        except ImportError:
            print(f"   ⚠️  {pkg_name} (will be bundled in EXE)")
            missing.append(pkg_name)
    
    # Build EXE
    if build_exe():
        # Create launcher script
        create_launcher_script()
        
        print("""
╔════════════════════════════════════════════════════════════════╗
║                    ✅ BUILD COMPLETE!                          ║
╚════════════════════════════════════════════════════════════════╝

📍 Your EXE is ready at:
   dist/SoundIQ.exe

🚀 You can now:
   1. Run: .\\dist\\SoundIQ.exe
   2. OR use launcher: .\\launch_soundiq.bat
   3. OR copy dist/SoundIQ.exe to any Windows PC and run it

💡 Tips:
   • The first run will download AI models (~1.5 GB)
   • Subsequent runs will be fast
   • You can share the EXE with others
   • No Python installation needed on other PCs

📦 File Size: The EXE is large because it includes:
   • All Python dependencies
   • PySide6 GUI framework
   • Audio processing libraries
   • AI models for search

🎵 Enjoy Sound IQ!
        """)
        return True
    else:
        print("""
╔════════════════════════════════════════════════════════════════╗
║                    ❌ BUILD FAILED                             ║
╚════════════════════════════════════════════════════════════════╝

🔧 Troubleshooting:
   1. Make sure all dependencies are installed:
      pip install -r requirements.txt
   
   2. Update PyInstaller:
      pip install --upgrade pyinstaller
   
   3. Check Python version (3.8+ required):
      python --version
   
   4. Try building again:
      python build_exe.py

💬 If issues persist, check console output above for details.
        """)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
