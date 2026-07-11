#!/usr/bin/env python3
"""Build standalone Windows EXE and installer."""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Build EXE with PyInstaller."""
    print("🔨 Building EXE with PyInstaller...")
    
    # PyInstaller spec
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('soundiq_logo.ico', '.'),
        ('soundiq_logo.png', '.'),
    ] + collect_data_files('transformers') + collect_data_files('torch'),
    hiddenimports=[
        'PySide6',
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
    upx=True,
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
    
    cmd = [sys.executable, '-m', 'PyInstaller', '--onefile', 'SoundIQ.spec']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ PyInstaller failed:")
        print(result.stderr)
        return False
    
    print("✅ EXE built successfully!")
    return True

def build_installer():
    """Build NSIS installer."""
    print("📦 Building NSIS installer...")
    
    nsis_script = r'''!include "MUI2.nsh"

; Basic Installer Settings
Name "Sound IQ v2.0"
OutFile "SoundIQ-v2.0-Installer.exe"
InstallDir "$PROGRAMFILES\\SoundIQ"

; UI Settings
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; Installer Sections
Section "Install"
    SetOutPath "$INSTDIR"
    File "dist\\SoundIQ.exe"
    File "soundiq_logo.ico"
    File "soundiq_logo.png"
    
    ; Create Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\\SoundIQ"
    CreateShortcut "$SMPROGRAMS\\SoundIQ\\Sound IQ.lnk" "$INSTDIR\\SoundIQ.exe" "" "$INSTDIR\\soundiq_logo.ico"
    CreateShortcut "$SMPROGRAMS\\SoundIQ\\Uninstall.lnk" "$INSTDIR\\uninstall.exe"
    
    ; Desktop shortcut
    CreateShortcut "$DESKTOP\\Sound IQ.lnk" "$INSTDIR\\SoundIQ.exe" "" "$INSTDIR\\soundiq_logo.ico"
    
    ; Write uninstaller
    WriteUninstaller "$INSTDIR\\uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\SoundIQ.exe"
    Delete "$INSTDIR\\soundiq_logo.ico"
    Delete "$INSTDIR\\soundiq_logo.png"
    Delete "$INSTDIR\\uninstall.exe"
    RMDir "$INSTDIR"
    
    Delete "$SMPROGRAMS\\SoundIQ\\Sound IQ.lnk"
    Delete "$SMPROGRAMS\\SoundIQ\\Uninstall.lnk"
    RMDir "$SMPROGRAMS\\SoundIQ"
    
    Delete "$DESKTOP\\Sound IQ.lnk"
SectionEnd
'''
    
    with open('SoundIQ-Installer.nsi', 'w') as f:
        f.write(nsis_script)
    
    # Try to find and run makensis
    nsis_paths = [
        r'C:\\Program Files\\NSIS\\makensis.exe',
        r'C:\\Program Files (x86)\\NSIS\\makensis.exe',
    ]
    
    makensis = None
    for path in nsis_paths:
        if os.path.exists(path):
            makensis = path
            break
    
    if makensis is None:
        print("⚠️  NSIS not found. Install from https://nsis.sourceforge.io/")
        print("📁 Use dist/SoundIQ.exe directly or run: makensis SoundIQ-Installer.nsi")
        return False
    
    cmd = [makensis, 'SoundIQ-Installer.nsi']
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ NSIS build failed")
        return False
    
    print("✅ Installer built successfully!")
    return True

def main():
    """Main build process."""
    print("\n🚀 Sound IQ v2.0 Build System\n")
    
    # Check prerequisites
    try:
        import PyInstaller
    except ImportError:
        print("❌ PyInstaller not found. Install: pip install pyinstaller")
        return
    
    # Clean old builds
    for folder in ['build', 'dist', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"🗑️  Cleaned {folder}")
    
    # Build EXE
    if not build_exe():
        return
    
    # Build installer (optional)
    print("\nBuild options:")
    print("1. EXE only (portable)")
    print("2. EXE + NSIS Installer")
    
    choice = input("\nChoice (1-2) [1]: ").strip() or "1"
    
    if choice == "2":
        if not build_installer():
            print("💾 You can manually build the installer using: makensis SoundIQ-Installer.nsi")
    
    print("\n✅ Build complete!")
    print("📁 Find your files in: ./dist/")

if __name__ == '__main__':
    main()
