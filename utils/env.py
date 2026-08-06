import os
import sys
import json
import platform
import threading
from pathlib import Path
from functools import lru_cache

_config_lock = threading.Lock()

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

@lru_cache(maxsize=1)
def get_os() -> str:
    return platform.system()

def is_windows() -> bool:
    return get_os() == "Windows"

def is_mac() -> bool:
    return get_os() == "Darwin"

def is_linux() -> bool:
    return get_os() == "Linux"

@lru_cache(maxsize=1)
def load_config() -> dict:
    config_path = get_base_dir() / "config" / "api_keys.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_api_key(service_name: str) -> str:
    config = load_config()
    return config.get(service_name, "")

def save_config_key(key: str, value) -> None:
    with _config_lock:
        config_path = get_base_dir() / "config" / "api_keys.json"
        config = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        config[key] = value
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        
        load_config.cache_clear()
