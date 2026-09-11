# 🔊 Sound IQ - Local AI Sound Searcher

**Sound IQ** is a free, lightweight, 100% offline Audio Search Tool. It runs entirely on your local machine using Python and local AI, allowing you to search, index, and find any sound effect from your personal audio library simply by describing what you need.

---

## ✨ Features

- 🤖 **Local AI Search:** No API keys, no internet required. Describe the sound, and the AI finds it.
- 📁 **Instant Library Indexing:** Scan thousands of local audio files in seconds.
- 🔒 **100% Privacy-Focused:** Zero data tracking. Your audio files and search queries never leave your PC.
- 🔊 **Professional Waveform Player:** Zoom, scrub, select, trim, drag-and-drop into any DAW.
- 🖥️ **System Tray:** Minimize to tray, quick restore, background operation.
- ⚙️ **Persistent Settings:** Your preferences are saved between sessions.
- ⌨️ **Full Keyboard Workflow:** Space = play/pause, Ctrl+T = trim, Ctrl+F = search, Ctrl+O = add folder.
- 📊 **AI Search Scores:** See how well each match ranks against your query.

---

## 📥 Installation

### Method 1: Windows Installer (Recommended)

1. Go to the [Releases](https://github.com/naimhossain332332-a11y/Sound-IQ/releases) section.
2. Download `SoundIQ-Setup-<version>.exe`.
3. Run the installer — it handles shortcuts, file associations, and uninstalling.

### Method 2: Portable EXE

1. Download `SoundIQ.exe` from Releases.
2. Run it directly — no installation needed.

### Method 3: Python Source

1. Clone this repository.
2. Run `setup.bat` to install dependencies automatically.
3. Launch with `run.bat`.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Space` | Play / Pause |
| `Esc` | Stop playback |
| `Ctrl+T` | Trim & save selection |
| `Ctrl+F` | Focus search box |
| `Ctrl+O` | Add local folder |
| `Ctrl+1` | Zoom waveform to fit |
| `Ctrl+=` / `Ctrl+-` | Zoom in / out |
| `↑` / `↓` | Navigate results |
| Mouse Wheel | Zoom waveform |

---

## 🛠️ Building From Source

### Build Windows EXE with PyInstaller

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean SoundIQ.spec
# Output: dist/SoundIQ.exe
```

### Build Professional Installer

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. Build the exe first (above)
3. Compile the installer:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
# Output: installer_output/SoundIQ-Setup-<version>.exe
```

### GitHub Actions Auto-Build

Push a version tag to trigger the automated build pipeline:

```bash
git tag v2.0.0
git push origin v2.0.0
```

The workflow builds the exe + installer and creates a GitHub Release automatically.

---

## 📁 Data Locations

| Data | Location |
|---|---|
| Settings | `%APPDATA%\SoundIQ\settings.json` |
| Search index | `%APPDATA%\SoundIQ\data\metadata.db` |
| Logs | `%APPDATA%\SoundIQ\logs\soundiq.log` |

---

## 🗺️ Roadmap

- [ ] Batch export multiple selections
- [ ] Cloud sync for search index (optional, opt-in)
- [ ] Tag / genre auto-detection
- [ ] Audio fingerprint matching with local hashing
- [ ] Plugin bridge for DAWs (VST / REAPER ReaScript)
- [ ] Windows Explorer context menu integration
- [ ] Code signing certificate purchase

---

## 💼 Support & Premium Audio Assets

Sound IQ software is completely free and open-source. If you want to level up your video editing with cinematic and viral sound effects, you can purchase our **Ultimate Audio Assets Bundle**.

📱 For business inquiries or to buy the premium audio pack, click the WhatsApp button on our official website.

---

⚠️ **Windows Defender Note:** Since this is a freshly compiled local app, Windows SmartScreen might show a warning. Click *More Info* -> *Run Anyway*. It is 100% safe and open-source.

License: MIT