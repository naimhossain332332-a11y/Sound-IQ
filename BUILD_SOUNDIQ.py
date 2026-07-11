#!/usr/bin/env python3
"""
Sound IQ v2.0 - Ultimate One-Click Builder

Just run this file and it creates SoundIQ.exe automatically!
No dependencies needed - downloads everything on the fly.
"""

import os
import sys
import subprocess
import shutil
import urllib.request
import zipfile
import json
from pathlib import Path

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header():
    print(f"""
{Colors.BOLD}{Colors.CYAN}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🎵 SOUND IQ v2.0 - ONE-CLICK EXE BUILDER 🚀          ║
║                                                              ║
║         No Python needed. Just click and get EXE!            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.ENDC}
    """)

def check_python():
    """Verify Python 3.8+ is available."""
    print(f"\n{Colors.BOLD}[STEP 1/5] Checking Python...{Colors.ENDC}")
    
    if sys.version_info < (3, 8):
        print(f"{Colors.RED}❌ Python 3.8+ required. You have: {sys.version}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Install Python from: https://www.python.org/downloads/{Colors.ENDC}")
        input("Press ENTER to close...")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✓ Python {sys.version.split()[0]} detected{Colors.ENDC}")

def upgrade_pip():
    """Upgrade pip to latest version."""
    print(f"\n{Colors.BOLD}[STEP 2/5] Upgrading pip...{Colors.ENDC}")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                      capture_output=True, timeout=60)
        print(f"{Colors.GREEN}✓ Pip upgraded{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠ Pip upgrade failed (continuing anyway): {e}{Colors.ENDC}")

def install_dependencies():
    """Install all required packages."""
    print(f"\n{Colors.BOLD}[STEP 3/5] Installing dependencies...{Colors.ENDC}")
    print(f"{Colors.CYAN}This will download and install all required packages.{Colors.ENDC}")
    print(f"{Colors.YELLOW}⏳ This may take 10-15 minutes. Do NOT close this window!{Colors.ENDC}\n")
    
    packages = [
        ('torch', 'PyTorch (AI/ML engine)'),
        ('PySide6', 'GUI Framework'),
        ('soundfile', 'Audio file reading'),
        ('sounddevice', 'Audio playback'),
        ('librosa', 'Audio processing'),
        ('transformers', 'AI models'),
        ('numpy', 'Numerical computing'),
        ('pyinstaller', 'EXE builder'),
    ]
    
    failed = []
    
    for package, description in packages:
        try:
            print(f"  📥 Installing {Colors.CYAN}{description}{Colors.ENDC}...", end=' ', flush=True)
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', package],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                print(f"{Colors.GREEN}✓{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}⚠ Warning{Colors.ENDC}")
                failed.append(package)
        except Exception as e:
            print(f"{Colors.YELLOW}⚠ Error{Colors.ENDC}")
            failed.append(package)
    
    if failed:
        print(f"\n{Colors.YELLOW}⚠ Some packages had issues: {', '.join(failed)}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Continuing anyway...{Colors.ENDC}")
    else:
        print(f"\n{Colors.GREEN}✓ All dependencies installed successfully!{Colors.ENDC}")

def check_source_files():
    """Verify required source files exist."""
    print(f"\n{Colors.BOLD}[STEP 4/5] Checking source files...{Colors.ENDC}")
    
    required_files = [
        'app.py',
        'audio_engine.py',
        'search_engine.py',
        'waveform_widget.py',
        'soundiq_logo.ico'
    ]
    
    missing = []
    for file in required_files:
        if os.path.exists(file):
            print(f"  {Colors.GREEN}✓{Colors.ENDC} {file}")
        else:
            print(f"  {Colors.RED}✗{Colors.ENDC} {file} (missing)")
            missing.append(file)
    
    if missing:
        print(f"\n{Colors.RED}❌ Error: Missing source files!{Colors.ENDC}")
        print(f"{Colors.YELLOW}Make sure you're in the Sound IQ project directory.{Colors.ENDC}")
        input("Press ENTER to close...")
        sys.exit(1)
    
    print(f"\n{Colors.GREEN}✓ All source files found!{Colors.ENDC}")

def build_exe():
    """Build standalone EXE with PyInstaller."""
    print(f"\n{Colors.BOLD}[STEP 5/5] Building SoundIQ.exe...{Colors.ENDC}")
    print(f"{Colors.YELLOW}⏳ This will take 3-5 minutes. Do NOT close this window!{Colors.ENDC}\n")
    
    # Clean old builds
    print(f"  🧹 Cleaning old builds...")
    for folder in ['build', 'dist', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    print(f"     {Colors.GREEN}✓ Cleaned{Colors.ENDC}")
    
    # Build command
    print(f"  🔨 Building with PyInstaller...")
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name=SoundIQ',
        '--icon=soundiq_logo.ico',
        '--collect-all=transformers',
        '--collect-all=torch',
        'app.py'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            print(f"{Colors.RED}\n❌ Build failed!{Colors.ENDC}")
            print(f"{Colors.YELLOW}Error output:{Colors.ENDC}")
            print(result.stderr)
            input("Press ENTER to close...")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}❌ Build timed out!{Colors.ENDC}")
        input("Press ENTER to close...")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}❌ Build error: {e}{Colors.ENDC}")
        input("Press ENTER to close...")
        sys.exit(1)
    
    # Verify EXE exists
    exe_path = os.path.join('dist', 'SoundIQ.exe')
    if not os.path.exists(exe_path):
        print(f"{Colors.RED}❌ SoundIQ.exe not created!{Colors.ENDC}")
        input("Press ENTER to close...")
        sys.exit(1)
    
    # Get file size
    size_bytes = os.path.getsize(exe_path)
    size_mb = size_bytes / (1024 * 1024)
    
    print(f"     {Colors.GREEN}✓ Built successfully!{Colors.ENDC}")
    print(f"     📦 Size: {size_mb:.1f} MB")
    print(f"     📁 Location: {os.path.abspath(exe_path)}")

def create_launchers():
    """Create launcher scripts."""
    print(f"\n  📝 Creating launcher scripts...")
    
    # Quick launcher
    with open('launch_soundiq.bat', 'w') as f:
        f.write('@echo off\n')
        f.write('title Sound IQ v2.0\n')
        f.write('start "Sound IQ v2.0" "dist\\SoundIQ.exe"\n')
        f.write('exit /b 0\n')
    
    # Uninstaller
    with open('uninstall.bat', 'w') as f:
        f.write('@echo off\n')
        f.write('rmdir /s /q dist build\n')
        f.write('del /q *.spec\n')
        f.write('echo Cleaned up.\n')
    
    print(f"     {Colors.GREEN}✓ Created{Colors.ENDC}")

def cleanup():
    """Clean up build artifacts."""
    print(f"\n  🧹 Cleaning up build files...")
    for folder in ['build', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    print(f"     {Colors.GREEN}✓ Cleaned{Colors.ENDC}")

def print_success():
    """Print success message."""
    print(f"""
{Colors.GREEN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║                   ✅ BUILD COMPLETE! 🎉                     ║
║                                                              ║
║              Your SoundIQ.exe is ready to use!               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.ENDC}

{Colors.BOLD}📍 Your Files:{Colors.ENDC}
  • {Colors.CYAN}dist/SoundIQ.exe{Colors.ENDC} ← Your standalone app!
  • {Colors.CYAN}launch_soundiq.bat{Colors.ENDC} ← Quick launcher
  • {Colors.CYAN}uninstall.bat{Colors.ENDC} ← Cleanup tool

{Colors.BOLD}🚀 To Launch Sound IQ:{Colors.ENDC}
  1. Double-click: {Colors.CYAN}launch_soundiq.bat{Colors.ENDC}
     OR
  2. Double-click: {Colors.CYAN}dist/SoundIQ.exe{Colors.ENDC}

{Colors.BOLD}📤 Share with Others:{Colors.ENDC}
  • Copy {Colors.CYAN}dist/SoundIQ.exe{Colors.ENDC} to any Windows PC
  • {Colors.GREEN}No Python needed{Colors.ENDC} on their computer!
  • Works {Colors.GREEN}100% offline{Colors.ENDC} after first run

{Colors.BOLD}💡 First Run Tips:{Colors.ENDC}
  • First launch downloads AI models (~1.5 GB)
  • Takes 2-3 minutes on first run
  • Subsequent launches are instant
  • Add folders with audio files to index
  • Use natural language to search

{Colors.BOLD}📊 System Requirements:{Colors.ENDC}
  • Windows 10/11
  • 4GB RAM minimum (8GB recommended)
  • 2GB free disk space
  • Audio device connected

{Colors.BOLD}❓ Troubleshooting:{Colors.ENDC}
  • If EXE won't start: Run as Administrator
  • If slow: Close other apps
  • If audio issues: Update audio drivers

{Colors.BOLD}🔗 Support:{Colors.ENDC}
  • GitHub: https://github.com/naimhossain332332-a11y/Sound-IQ

{Colors.GREEN}{Colors.BOLD}🎵 Enjoy Sound IQ!{Colors.ENDC}
    """)

def main():
    """Main build process."""
    try:
        print_header()
        check_python()
        upgrade_pip()
        install_dependencies()
        check_source_files()
        build_exe()
        create_launchers()
        cleanup()
        print_success()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}\n⚠ Build cancelled by user.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Unexpected error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print(f"\n{Colors.BOLD}Press ENTER to close...{Colors.ENDC}")
        input()

if __name__ == '__main__':
    main()
