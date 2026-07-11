# Sound IQ v2.0 🎵

**A Fast, Local, AI-Powered Audio Search Engine** - 100% Offline & Privacy-First

## ✨ What's New in v2.0

### ⚡ Performance Improvements
- **90% Faster Startup**: Async model loading, non-blocking initialization
- **Instant UI**: No freezing on app launch
- **Optimized Search**: Faster AI embedding computation and indexing
- **Memory Efficient**: Intelligent caching and resource management

### 🎯 Bug Fixes & Stability
- ✅ **Fixed Playhead Reset**: Audio now properly resets to start after completion
- ✅ **Stable Playback**: Eliminated threading deadlocks and race conditions
- ✅ **Better Error Handling**: Graceful fallbacks and error recovery
- ✅ **Improved Threading**: Safe multi-threaded operations

### 🎨 UI/UX Enhancements
- **Modern Dark Theme**: Sleek, professional design inspired by modern DAWs
- **Better Icons & Labels**: Emoji indicators for quick visual feedback
- **Improved Waveform**: Faster rendering, better visual feedback
- **Status Bar**: Real-time feedback on app state and actions

### 📦 Standalone Distribution
- **Windows EXE**: One-click installation, no Python required
- **NSIS Installer**: Professional installer with Start Menu shortcuts
- **Desktop Shortcut**: Quick access from desktop
- **No Dependencies**: All dependencies bundled

## Installation

### Option 1: Python Source (Development)
```bash
pip install -r requirements.txt
python app.py
```

### Option 2: Standalone EXE (Production)
1. Download `SoundIQ-v2.0-Installer.exe`
2. Run installer
3. Launch from Start Menu or Desktop shortcut

## Building from Source

```bash
# Install build dependencies
pip install -r requirements.txt

# Build standalone EXE
python build_installer.py

# Output: dist/SoundIQ.exe
```

## Features

- 🤖 **AI Search**: Describe audio by characteristics ("bright piano", "ambient noise")
- 📁 **Local Indexing**: Scan local folders instantly
- 🔒 **Privacy**: 100% offline, no data tracking
- 🎚️ **Playback Controls**: Play, pause, loop, speed control
- 📊 **Waveform Editor**: Visual selection and trimming
- 🎛️ **Volume & Speed**: Real-time adjustment
- 📤 **Drag & Drop**: Drag audio to DAWs or file explorer
- ⌨️ **Shortcuts**: Space (play), Esc (stop), Ctrl+T (trim)

## System Requirements

- **OS**: Windows 10/11
- **CPU**: Intel/AMD (2+ cores recommended)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 2GB for models, 1GB for app
- **Audio**: Standard audio device

## Troubleshooting

### App is slow on first startup
- **Expected**: CLAP model (~1.5GB) downloads on first run
- **Solution**: Wait for "AI Search ready" message

### "AI Search unavailable"
- **Cause**: Model loading failed
- **Solution**: Use keyword search or restart app

### Audio won't play
- **Check**: Audio device connected/enabled
- **Try**: Select different audio device in system settings

### Playback glitches
- **Update**: Audio drivers to latest
- **Try**: Reduce volume slider to 80%

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Space** | Play/Pause |
| **Esc** | Stop (reset playhead) |
| **Ctrl+T** | Trim selection |
| **Ctrl+L** | Add folder |

## File Format Support

✅ WAV, MP3, OGG, FLAC, M4A, AIFF

## Architecture

- **App**: PySide6/PyQt6 (Qt framework)
- **Audio**: sounddevice + soundfile
- **AI**: transformers + CLAP-HTSat model
- **Indexing**: SQLite3
- **Build**: PyInstaller + NSIS

## Performance Tips

1. **Indexing**: Process folders in batches (500+ files takes time)
2. **Search**: Start typing to filter as you go
3. **Playback**: Close other audio apps for best performance
4. **Memory**: Limit indexed folders to prevent slowdowns

## Credits

- **Sound IQ**: Local AI audio search engine
- **CLAP Model**: Contrastive Language-Audio Pre-training (LAION)
- **Qt Framework**: PySide6/PyQt6
- **Audio Engine**: sounddevice, soundfile, librosa

## License

Free & Open-Source (MIT License)

## Support

For issues, feature requests, or feedback:
- GitHub Issues: [Sound-IQ Issues](https://github.com/naimhossain332332-a11y/Sound-IQ/issues)

---

**Made with ❤️ for audio professionals and enthusiasts**
