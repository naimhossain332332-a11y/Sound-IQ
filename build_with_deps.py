#!/usr/bin/env python3
"""One-click EXE builder with auto-dependency installer."""

import os
import sys
import subprocess

def install_dependencies():
    """Install all required dependencies."""
    print("""
╔════════════════════════════════════════════════════════════════╗
║         📦 Installing Sound IQ v2.0 Dependencies               ║
║                                                                ║
║  This will download and install all required packages.        ║
║  This may take 5-10 minutes depending on internet speed.      ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    requirements = [
        'torch>=2.0.0',
        'PySide6>=6.5.0',
        'soundfile>=0.12.1',
        'sounddevice>=0.4.6',
        'librosa>=0.10.0',
        'transformers>=4.30.0',
        'PyAudio>=0.2.13',
        'numpy>=1.24.0',
        'pyinstaller>=6.0.0',
    ]
    
    print("\n⬇️  Installing packages...\n")
    
    for package in requirements:
        print(f"  📥 Installing {package}...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"     ✅ Success")
        else:
            print(f"     ⚠️  Warning: Installation may have issues")
            print(f"     {result.stderr[:100]}...")
    
    print("\n✅ Dependencies installation complete!\n")

def main():
    print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║        🎵 Sound IQ v2.0 - One-Click EXE Builder 🚀             ║
║                                                                ║
║  This script will create a standalone EXE that:               ║
║  ✅ Works on any Windows PC (no Python needed)                ║
║  ✅ Includes all dependencies                                 ║
║  ✅ Can be shared with others                                 ║
║  ✅ Runs instantly after build                                ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required. You have: {sys.version}")
        return False
    
    print(f"✅ Python {sys.version.split()[0]} detected\n")
    
    # Install dependencies
    print("Step 1: Installing dependencies...\n")
    input("Press ENTER to start installation (or Ctrl+C to cancel)...\n")
    install_dependencies()
    
    # Build EXE
    print("\nStep 2: Building EXE...\n")
    print("Running build_exe.py...\n")
    
    result = subprocess.run([sys.executable, 'build_exe.py'])
    
    if result.returncode == 0:
        print("""
╔════════════════════════════════════════════════════════════════╗
║                  ✅ ALL DONE! READY TO USE!                   ║
╚════════════════════════════════════════════════════════════════╝

🎵 Your EXE is ready:
   ✨ dist/SoundIQ.exe

🚀 Next steps:
   1. Double-click dist/SoundIQ.exe to launch
   2. OR run: .\\launch_soundiq.bat

💾 Share with others:
   • Copy dist/SoundIQ.exe to any Windows PC
   • No Python installation needed!
   • App works offline after first run

🎊 Enjoy Sound IQ!
        """)
        return True
    else:
        print("\n❌ Build failed. Check output above.")
        return False

if __name__ == '__main__':
    success = main()
    if success:
        print("\n✨ Press ENTER to close...")
        input()
    sys.exit(0 if success else 1)
