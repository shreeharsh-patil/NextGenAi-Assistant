from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
import threading

_lock = threading.Lock()
_cache = None

BASE_DIR = Path(__file__).resolve().parent.parent
CMR_FILE = BASE_DIR / "memory" / "cmr_records.json"

def _ensure_file():
    CMR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CMR_FILE.exists():
        initial_data = [
            {
                "id": "cmr-001",
                "name": "Tony Stark",
                "company": "Stark Industries",
                "email": "tony@starkindustries.com",
                "phone": "+1-212-555-0199",
                "status": "VIP Lead",
                "notes": "Arc reactor blueprints & HUNNY HUD updates.",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            },
            {
                "id": "cmr-002",
                "name": "Pepper Potts",
                "company": "Stark Industries CEO",
                "email": "pepper@starkindustries.com",
                "phone": "+1-212-555-0100",
                "status": "Active Client",
                "notes": "Quarterly operational briefings & budget approval.",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ]
        CMR_FILE.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

def load_cmr_records() -> list[dict]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache.copy()
        _ensure_file()
        try:
            data = json.loads(CMR_FILE.read_text(encoding="utf-8"))
            _cache = data if isinstance(data, list) else []
            return _cache.copy()
        except Exception:
            _cache = []
            return []

def save_cmr_records(records: list[dict]) -> None:
    global _cache
    with _lock:
        _ensure_file()
        CMR_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")
        _cache = records.copy()

def add_cmr_record(name: str, company: str, email: str, phone: str, status: str, notes: str) -> dict:
    records = load_cmr_records()
    rec = {
        "id": f"cmr-{str(uuid.uuid4())[:6]}",
        "name": name.strip() or "Unnamed Contact",
        "company": company.strip() or "N/A",
        "email": email.strip() or "N/A",
        "phone": phone.strip() or "N/A",
        "status": status.strip() or "New Lead",
        "notes": notes.strip(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    records.append(rec)
    save_cmr_records(records)
    return rec

def delete_cmr_record(record_id: str) -> bool:
    records = load_cmr_records()
    initial_len = len(records)
    records = [r for r in records if r.get("id") != record_id]
    if len(records) < initial_len:
        save_cmr_records(records)
        return True
    return False

def search_cmr_records(query: str) -> list[dict]:
    records = load_cmr_records()
    if not query:
        return records
    q = query.lower()
    results = []
    for r in records:
        text_block = f"{r.get('name','')} {r.get('company','')} {r.get('email','')} {r.get('phone','')} {r.get('status','')} {r.get('notes','')}".lower()
        if q in text_block:
            results.append(r)
    return results
