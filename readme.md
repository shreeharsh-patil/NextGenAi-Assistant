# ULTRON AI Desktop Assistant

> **ULTRON** is a next-generation AI Desktop Assistant powered by Google Gemini. It features hands-free voice recognition, real-time voice synthesis, automated desktop control, browser automation, system monitoring, and a remote web dashboard.

---

## Features

- **Google Gemini Engine** -- Ultra-fast LLM with native audio and text models
- **Hands-Free Voice** -- Real-time speech recognition, neural TTS, and wake word ("Wake up Ultron")
- **Computer Control** -- Volume, brightness, media, app launcher, window management, keyboard shortcuts
- **Web Automation** -- Built-in Playwright engine for automated browsing, search, and page extraction
- **Hardware Monitor** -- Real-time CPU, RAM, GPU, battery, and network telemetry
- **Remote Dashboard** -- Web-based control panel accessible from any browser or phone
- **File Processing** -- Read, write, analyze files and generate presentations
- **Code Assistant** -- Write, debug, and explain code across languages

---

## Quick Start (Any Windows 10/11 PC)

### Prerequisites

- **Python 3.10+** installed with "Add python.exe to PATH" checked
  - Download from [python.org](https://python.org) if needed
- **Internet connection** for first-time setup (downloads dependencies)

### Option 1: Automatic Setup (Recommended)

```
1. Download or clone this repository
2. Double-click SETUP.bat
3. Done! ULTRON installs all dependencies and launches automatically.
```

### Option 2: Manual Setup

```bash
git clone https://github.com/shreeharsh-patil/NextGenAi-Assistant.git
cd NextGenAi-Assistant
python ULTRON_SETUP.py
```

### Option 3: Step-by-Step Manual

```bash
git clone https://github.com/shreeharsh-patil/NextGenAi-Assistant.git
cd NextGenAi-Assistant
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

---

## First Launch

On the very first launch, ULTRON will ask for your **Gemini API Key**.

1. Get a free key at [Google AI Studio](https://aistudio.google.com/apikey)
2. Paste it when prompted, or edit `config/api_keys.json` manually
3. optional if pyaudio error comes the go to requirements.txt and add ```pyaudio``` at the bottom

---

## Wake Word (Hands-Free Activation)

To keep ULTRON listening in the background:

- Double-click **`Start_ULTRON_Wake_Word.bat`**
- Say **"Wake up Ultron"** or **"Hey Ultron"** to activate

---

## Repository Structure

```
ULTRON/
|-- ULTRON_SETUP.py              # Portable first-time setup script
|-- SETUP.bat                    # 1-click setup launcher (runs ULTRON_SETUP.py)
|-- START_ULTRON.bat             # Main launcher (auto-runs setup on first use)
|-- Start_ULTRON_Wake_Word.bat   # Wake word background listener
|-- main.py                      # Main assistant entry point
|-- ui.py                        # PyQt6 WebEngine visual HUD
|-- wake_service.py              # Always-on voice wake word service
|-- requirements.txt             # Python package dependencies
|-- config/
|   |-- api_keys.json.example    # Template for API key configuration
|   |-- __init__.py              # Config loader module
|   +-- jarvis.ico               # Application icon
|-- core/                        # LLM client, TTS, STT engines
|-- actions/                     # Tool modules (browser, system, desktop, etc.)
|-- dashboard/                   # Remote web dashboard server & assets
+-- memory/                      # Local assistant memory & preferences
```

---

## How Sharing Works

This project is **fully portable** -- no hardcoded paths.

**To share ULTRON with someone:**

1. Push this repo to GitHub (or send as ZIP)
2. Recipient clones/extracts to ANY folder on their PC
3. They double-click `SETUP.bat` (or run `python ULTRON_SETUP.py`)
4. Everything installs automatically
5. ULTRON launches and works immediately

**The setup script automatically:**
- Verifies all project files are present
- Downloads missing files from GitHub if needed
- Installs all Python packages (PyQt6, sounddevice, google-genai, etc.)
- Installs Playwright Chromium browser engine
- Creates default configuration files
- Provides manual download links if auto-download fails

---

## Requirements

All dependencies are listed in `requirements.txt` and installed automatically by the setup script:

- PyQt6 + PyQt6-WebEngine
- sounddevice, PyAudio, SpeechRecognition
- google-genai, google-generativeai
- playwright, requests, beautifulsoup4
- numpy, opencv-python, pillow
- psutil, pyautogui, pyperclip
- fastapi, uvicorn, cryptography
- And more (see requirements.txt)

---

## License

Contributions, issues, and feature requests are welcome!
