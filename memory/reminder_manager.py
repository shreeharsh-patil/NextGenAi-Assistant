from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
import threading

_lock = threading.Lock()
_cache = None

BASE_DIR = Path(__file__).resolve().parent.parent
REMINDERS_FILE = BASE_DIR / "memory" / "reminders.json"

def _ensure_file():
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REMINDERS_FILE.exists():
        REMINDERS_FILE.write_text("[]", encoding="utf-8")

def load_reminders() -> list[dict]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache.copy()
        _ensure_file()
        try:
            data = json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
            _cache = data if isinstance(data, list) else []
            return _cache.copy()
        except Exception:
            _cache = []
            return []

def save_reminders(reminders: list[dict]) -> None:
    global _cache
    with _lock:
        _ensure_file()
        REMINDERS_FILE.write_text(json.dumps(reminders, indent=2), encoding="utf-8")
        _cache = reminders.copy()

def add_reminder(text: str, due_datetime: str) -> dict:
    reminders = load_reminders()
    rec = {
        "id": str(uuid.uuid4())[:8],
        "text": text.strip(),
        "due": due_datetime.strip(),  # Format: "YYYY-MM-DD HH:MM"
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "triggered": False
    }
    reminders.append(rec)
    save_reminders(reminders)
    return rec

def delete_reminder(reminder_id: str) -> bool:
    reminders = load_reminders()
    initial_len = len(reminders)
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    if len(reminders) < initial_len:
        save_reminders(reminders)
        return True
    return False

def get_due_reminders() -> list[dict]:
    reminders = load_reminders()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    due_list = []
    updated = False
    for r in reminders:
        if not r.get("triggered", False):
            due = r.get("due", "")
            if due and due <= now_str:
                r["triggered"] = True
                due_list.append(r)
                updated = True
    if updated:
        save_reminders(reminders)
    return due_list
