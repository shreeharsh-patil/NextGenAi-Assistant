import json
import sys
from pathlib import Path
import threading

_lock = threading.RLock()
_cache = None

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def load_api_keys() -> dict:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache.copy()
        if not CONFIG_FILE.exists():
            _cache = {}
            return {}
        try:
            _cache = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return _cache.copy()
        except Exception as e:
            print(f"❌ Failed to load api_keys.json: {e}")
            _cache = {}
            return {}

def save_api_keys(gemini_api_key: str) -> None:
    global _cache
    with _lock:
        ensure_config_dir()
        data = load_api_keys()
        data["gemini_api_key"] = gemini_api_key.strip()
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _cache = data.copy()

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'ULTRON' if not set."""
    return load_api_keys().get("assistant_name", "ULTRON") or "ULTRON"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    global _cache
    with _lock:
        ensure_config_dir()
        data = load_api_keys()
        data["assistant_name"] = assistant_name.strip() or "ULTRON"
        data["user_name"] = user_name.strip()
        CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        _cache = data.copy()


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    global _cache
    with _lock:
        ensure_config_dir()
        data = load_api_keys()
        data["morning_brief_enabled"] = enabled
        CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        _cache = data.copy()