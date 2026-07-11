#!/bin/bash
# Sound IQ v2.0 - Build Setup for Linux/Mac

echo ""
echo "============================================================================"
echo "          SOUND IQ v2.0 - BUILD SETUP & EXE CREATOR (Linux/Mac)"
echo "============================================================================"
echo ""
echo "This will:"
echo "  1. Check Python installation"
echo "  2. Install all dependencies"
echo "  3. Build standalone package"
echo "  4. Create launcher scripts"
echo ""
echo "Estimated time: 10-15 minutes"
echo ""
read -p "Press ENTER to continue, or Ctrl+C to cancel..."

# Check Python
echo ""
echo "[STEP 1/4] Checking Python..."
echo ""

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo ""
    echo "Install Python 3.8+ from https://www.python.org/downloads/"
    echo ""
    exit 1
fi

python3 --version
echo "[OK] Python found"
echo ""

# Install dependencies
echo "[STEP 2/4] Installing dependencies..."
echo ""
echo "This may take several minutes. Do NOT close this window."
echo ""

python3 -m pip install --upgrade pip
python3 -m pip install torch PySide6 soundfile sounddevice librosa transformers numpy pyinstaller

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Dependency installation failed!"
    exit 1
fi

echo ""
echo "[OK] Dependencies installed"
echo ""

# Build
echo "[STEP 3/4] Building executable..."
echo ""
echo "This may take 3-5 minutes..."
echo ""

if [ ! -f "app.py" ]; then
    echo "ERROR: app.py not found!"
    exit 1
fi

python3 -m PyInstaller --onefile --name=SoundIQ app.py

if [ ! -f "dist/SoundIQ" ]; then
    echo "ERROR: Build failed!"
    exit 1
fi

echo ""
echo "[OK] SoundIQ built successfully!"
echo ""

# Create launcher
echo "[STEP 4/4] Creating launcher..."
echo ""

cat > launch_soundiq.sh << 'EOF'
#!/bin/bash
# Sound IQ v2.0 Quick Launcher
echo ""
echo "Starting Sound IQ v2.0..."
echo ""
./dist/SoundIQ &
exit 0
EOF

chmod +x launch_soundiq.sh
echo "[OK] Created launch_soundiq.sh"
echo ""

# Cleanup
echo "Cleaning up build files..."
rm -rf build __pycache__
echo "[OK] Cleanup complete"
echo ""

# Success
echo "============================================================================"
echo "                         BUILD COMPLETE!"
echo "============================================================================"
echo ""
echo "Your Sound IQ executable is ready!"
echo ""
echo "Location: $(pwd)/dist/SoundIQ"
echo ""
echo "To launch:"
echo "  ./launch_soundiq.sh"
echo "  or"
echo "  ./dist/SoundIQ"
echo ""
echo "============================================================================"
echo ""
read -p "Press ENTER to close..."
