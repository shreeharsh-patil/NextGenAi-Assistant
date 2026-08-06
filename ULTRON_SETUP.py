"""
ULTRON SETUP SCRIPT

This is a portable first-time setup script for the ULTRON AI Desktop Assistant.
It verifies project integrity, downloads missing files from GitHub,
checks Python version, installs dependencies, configures API keys,
and prepares the environment for running the assistant.
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
import json
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_URL_GIT = "https://github.com/shreeharsh-patil/NextGenAi-Assistant.git"
REPO_URL_ZIP = "https://github.com/shreeharsh-patil/NextGenAi-Assistant/archive/refs/heads/main.zip"

MARKER_FILES = [
    "main.py",
    "ui.py",
    "requirements.txt",
    "core/tts.py",
    "actions/browser_control.py",
    "dashboard/server.py",
]

def print_separator():
    print("=" * 60)

def show_manual_download_error():
    print_separator()
    print(" AUTOMATIC DOWNLOAD FAILED")
    print_separator()
    print("")
    print(" Please download ULTRON manually:")
    print("")
    print(" Option 1 (Git):")
    print(f"   git clone {REPO_URL_GIT}")
    print("")
    print(" Option 2 (Direct ZIP):")
    print(f"   {REPO_URL_ZIP}")
    print("")
    print(" After downloading, extract all files into this folder:")
    print(f"   {SCRIPT_DIR}")
    print("")
    print(" Then run this setup script again:")
    print("   python ULTRON_SETUP.py")
    print_separator()

def check_marker_files():
    for marker in MARKER_FILES:
        if not (SCRIPT_DIR / marker).exists():
            return False
    
    config_json = SCRIPT_DIR / "config" / "api_keys.json"
    config_example = SCRIPT_DIR / "config" / "api_keys.json.example"
    
    if not (config_json.exists() or config_example.exists()):
        return False
        
    return True

def download_from_github():
    print("[INFO] Attempting to download ULTRON from GitHub...")
    # Try Git clone
    try:
        print("[INFO] Trying git clone...")
        result = subprocess.run(
            ["git", "clone", REPO_URL_GIT, "."],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("[INFO] Git clone successful.")
            return True
        else:
            print("[WARN] Git clone failed. Git might not be installed or directory is not empty.")
    except Exception as e:
        print(f"[WARN] Git clone error: {e}")

    # Try ZIP download
    try:
        print("[INFO] Trying direct ZIP download...")
        zip_path = SCRIPT_DIR / "ultron_temp.zip"
        urllib.request.urlretrieve(REPO_URL_ZIP, zip_path)
        
        print("[INFO] Extracting ZIP...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Need to extract contents of the inner folder, usually ULTRON-main
            temp_extract = SCRIPT_DIR / "temp_extract"
            zip_ref.extractall(temp_extract)
            
            # Find the root folder inside the zip
            inner_folders = [f for f in temp_extract.iterdir() if f.is_dir()]
            if inner_folders:
                inner_root = inner_folders[0]
                for item in inner_root.iterdir():
                    dest = SCRIPT_DIR / item.name
                    if not dest.exists():
                        shutil.move(str(item), str(dest))
                    
        # Cleanup
        shutil.rmtree(temp_extract, ignore_errors=True)
        if zip_path.exists():
            zip_path.unlink()
            
        print("[INFO] ZIP download and extraction successful.")
        return True
    except Exception as e:
        print(f"[WARN] ZIP download failed: {e}")
        
    return False

def check_python_version():
    print("[INFO] Checking Python version...")
    if sys.version_info < (3, 10):
        print(f"[ERROR] Python 3.10 or higher is required. Found Python {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(1)
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor} verified.")

def upgrade_pip():
    print("[INFO] Upgrading pip...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                       capture_output=True, check=True)
        print("[OK] Pip upgraded quietly.")
    except Exception as e:
        print(f"[WARN] Failed to upgrade pip: {e}")

def install_requirements():
    print("[INFO] Installing requirements.txt...")
    req_file = SCRIPT_DIR / "requirements.txt"
    if not req_file.exists():
        print(f"[ERROR] {req_file.name} not found!")
        sys.exit(1)
        
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], 
                       check=True)
        print("[OK] Requirements installed.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to install requirements: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error installing requirements: {e}")
        sys.exit(1)

def install_playwright_chromium():
    print("[INFO] Installing Playwright Chromium...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                       check=True)
        print("[OK] Playwright Chromium installed.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to install Playwright Chromium: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error installing Playwright Chromium: {e}")
        sys.exit(1)

def setup_api_keys():
    print("[INFO] Setting up config/api_keys.json...")
    config_dir = SCRIPT_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    api_keys_file = config_dir / "api_keys.json"
    api_keys_example = config_dir / "api_keys.json.example"
    
    if api_keys_file.exists():
        print("[OK] api_keys.json already exists.")
        return
        
    if api_keys_example.exists():
        try:
            shutil.copy(str(api_keys_example), str(api_keys_file))
            print("[OK] Copied api_keys.json.example to api_keys.json.")
        except Exception as e:
            print(f"[ERROR] Failed to copy example config: {e}")
            sys.exit(1)
    else:
        default_config = {
            "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
            "os_system": "windows",
            "morning_brief_enabled": True,
            "assistant_name": "ULTRON",
            "user_name": "",
            "ui_color": "#00ff66"
        }
        try:
            with open(api_keys_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            print("[OK] Created default api_keys.json.")
        except Exception as e:
            print(f"[ERROR] Failed to create api_keys.json: {e}")
            sys.exit(1)

def write_setup_marker():
    marker_file = SCRIPT_DIR / ".ultron_setup_complete"
    try:
        with open(marker_file, "w", encoding="utf-8") as f:
            f.write(f"Setup completed on: {datetime.now().isoformat()}")
        print("[OK] Wrote setup completion marker.")
    except Exception as e:
        print(f"[WARN] Failed to write setup marker: {e}")

def main():
    try:
        # STEP 1: Integrity Check
        if check_marker_files():
            print("[OK] ULTRON base project verified.")
        else:
            # STEP 2: Download from GitHub
            success = download_from_github()
            
            if not success:
                show_manual_download_error()
                sys.exit(1)
                
            if not check_marker_files():
                show_manual_download_error()
                sys.exit(1)
            else:
                print("[OK] ULTRON base project verified after download.")
                
        # STEP 3: Check Python Version
        check_python_version()
        
        # STEP 4: Upgrade pip
        upgrade_pip()
        
        # STEP 5: Install requirements.txt
        install_requirements()
        
        # STEP 6: Install Playwright Chromium
        install_playwright_chromium()
        
        # STEP 7: Setup config/api_keys.json
        setup_api_keys()
        
        # STEP 8: Write Setup Complete Marker
        write_setup_marker()
        
        # STEP 9: Print Success
        print_separator()
        print(" ULTRON SETUP COMPLETE!")
        print_separator()
        print("")
        print(" To launch ULTRON:")
        print("   python main.py")
        print("   OR double-click START_ULTRON.bat")
        print("")
        print(" IMPORTANT: Add your Gemini API key in config/api_keys.json")
        print(" Get a free key: https://aistudio.google.com/apikey")
        print_separator()
        
        choice = input("Do you want to launch ULTRON now? (Press Enter to launch, N to exit): ")
        if choice.strip().lower() != 'n':
            print("[INFO] Launching ULTRON...")
            subprocess.run([sys.executable, "main.py"], cwd=str(SCRIPT_DIR))
            
    except KeyboardInterrupt:
        print("\n[WARN] Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
