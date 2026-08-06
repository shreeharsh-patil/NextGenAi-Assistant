"""
memory/task_scheduler.py — persistent recurring-task scheduler for ULTRON.

Stores recurring / one-off scheduled tasks in ``memory/scheduled_tasks.json``
and provides pure, unit-testable cadence parsing + next-run math so the main
loop can fire tasks without a cron daemon.

Supported cadences (case-insensitive)::

    "every N minutes" / "every N hours" / "every N days"   interval
    "daily at HH:MM" / "every day at HH:MM"                daily
    "weekly at HH:MM" / "every Monday at HH:MM"            weekly (default Monday)
    "monthly on DD at HH:MM"                               monthly (clamped to month end)
    "startup"                                              fires once per app launch

Persistence mirrors ``reminder_manager.py`` (JSON + in-process cache).
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("ultron.scheduler")

_lock          = threading.RLock()
_cache: list[dict] | None = None

BASE_DIR       = Path(__file__).resolve().parent.parent
TASKS_FILE     = BASE_DIR / "memory" / "scheduled_tasks.json"

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


# ── persistence ───────────────────────────────────────────────────────────────

def _ensure_file() -> None:
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("[]", encoding="utf-8")


def load_tasks() -> list[dict]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache.copy()
        _ensure_file()
        try:
            data = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            _cache = data if isinstance(data, list) else []
        except Exception:
            _cache = []
        return _cache.copy()


def _save(tasks: list[dict]) -> None:
    with _lock:
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = TASKS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(TASKS_FILE)
        global _cache
        _cache = tasks.copy()


def reset() -> None:
    """Drop the in-memory cache so the next call reloads from disk (tests)."""
    global _cache
    with _lock:
        _cache = None


# ── pure cadence math (unit-testable) ─────────────────────────────────────────

def parse_cadence(text: str) -> dict | None:
    """Parse a human cadence string into a normalized schedule dict.

    Returns ``None`` for unrecognized input. Normalized keys:
    ``kind`` (interval|daily|weekly|monthly|startup), plus the matching fields.
    """
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return None

    if t == "startup":
        return {"kind": "startup"}

    m = re.fullmatch(r"every\s+(\d+)\s+(minute|minutes|hour|hours|day|days)", t)
    if m:
        n    = int(m.group(1))
        unit = m.group(2)
        if n < 1:
            return None
        if unit.endswith("s"):
            unit = unit[:-1]
        return {"kind": "interval", "n": n, "unit": unit}

    m = re.fullmatch(r"(?:daily|every day)(?: at)?\s*(\d{1,2}):(\d{2})?", t)
    if m:
        return {"kind": "daily", "time": _hm(m.group(1), m.group(2))}

    m = re.fullmatch(
        r"(?:weekly|every week|every\s+(monday|mon|tuesday|tue|tues|wednesday|wed|"
        r"thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun))"
        r"(?:\s+at)?\s*(\d{1,2}):(\d{2})?",
        t,
    )
    if m:
        day = _WEEKDAYS[m.group(1) or "monday"]
        return {"kind": "weekly", "weekday": day, "time": _hm(m.group(2), m.group(3))}

    m = re.fullmatch(r"monthly on\s+(\d{1,2})(?:\s+at)?\s*(\d{1,2}):(\d{2})?", t)
    if m:
        return {"kind": "monthly", "day": int(m.group(1)), "time": _hm(m.group(2), m.group(3))}

    return None


def _hm(h: str | None, m: str | None) -> tuple[int, int]:
    hour = int(h or "0") if h is not None else 0
    if not (0 <= hour <= 23):
        hour = 0
    minute = int(m or "0") if m is not None else 0
    if not (0 <= minute <= 59):
        minute = 0
    return hour, minute


def compute_next_run(schedule: dict, from_dt: datetime) -> datetime | None:
    """Return the next occurrence strictly after ``from_dt`` for ``schedule``.

    ``startup`` tasks never schedule an automatic repeat (returns ``None``);
    they are considered due only until they have run once.
    """
    kind = schedule.get("kind")
    if kind == "interval":
        n, unit = int(schedule.get("n", 1)), schedule.get("unit", "hour")
        delta = {"minute": timedelta(minutes=n),
                 "hour":   timedelta(hours=n),
                 "day":    timedelta(days=n)}[unit]
        return from_dt + delta

    if kind == "daily":
        hour, minute = schedule["time"]
        candidate = from_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= from_dt:
            candidate += timedelta(days=1)
        return candidate

    if kind == "weekly":
        hour, minute = schedule["time"]
        target_wd = int(schedule["weekday"])
        days_ahead = (target_wd - from_dt.weekday()) % 7
        candidate = from_dt.replace(hour=hour, minute=minute, second=0, microsecond=0) \
                            + timedelta(days=days_ahead)
        if candidate <= from_dt:
            candidate += timedelta(days=7)
        return candidate

    if kind == "monthly":
        hour, minute = schedule["time"]
        day = int(schedule["day"])
        candidate = _month_dt(from_dt.year, from_dt.month, day, hour, minute)
        if candidate <= from_dt:
            if from_dt.month == 12:
                candidate = _month_dt(from_dt.year + 1, 1, day, hour, minute)
            else:
                candidate = _month_dt(from_dt.year, from_dt.month + 1, day, hour, minute)
        return candidate

    return None


def _month_dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, min(day, _days_in_month(year, month)),
                    hour, minute, 0, 0)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (datetime(year, month + 1, 1) - timedelta(days=1)).day


# ── public API ────────────────────────────────────────────────────────────────

def add_task(cadence: str, prompt: str, name: str | None = None, enabled: bool = True) -> dict:
    """Add a recurring task. Returns the stored record (raises on bad cadence)."""
    schedule = parse_cadence(cadence)
    if not schedule:
        raise ValueError(f"Unrecognized cadence: {cadence!r}")
    now = datetime.now()
    task = {
        "id":        str(uuid.uuid4())[:8],
        "name":      (name or prompt).strip()[:60],
        "cadence":   (cadence or "").strip(),
        "kind":      schedule["kind"],
        "schedule":  schedule,
        "prompt":    prompt.strip(),
        "enabled":   enabled,
        "created_at": now.strftime("%Y-%m-%d %H:%M"),
        "last_run":  None,
        "next_run":  compute_next_run(schedule, now).isoformat() if schedule["kind"] != "startup" else None,
    }
    tasks = load_tasks()
    tasks.append(task)
    _save(tasks)
    logger.info("Scheduler: added task '%s' (%s)", task["name"], cadence)
    return task


def remove_task(task_id: str) -> bool:
    tasks = load_tasks()
    kept  = [t for t in tasks if t.get("id") != task_id]
    if len(kept) < len(tasks):
        _save(kept)
        logger.info("Scheduler: removed task %s", task_id)
        return True
    return False


def set_enabled(task_id: str, enabled: bool) -> bool:
    tasks = load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            t["enabled"] = bool(enabled)
            _save(tasks)
            return True
    return False


def list_tasks() -> list[dict]:
    return load_tasks()


def get_due(now: datetime | None = None) -> list[dict]:
    """Return enabled tasks that are due at ``now`` (default: wall clock)."""
    now = now or datetime.now()
    due: list[dict] = []
    for t in load_tasks():
        if not t.get("enabled", True):
            continue
        if t.get("kind") == "startup":
            if t.get("last_run") is None:
                due.append(t)
            continue
        nxt = t.get("next_run")
        if nxt and _iso(nxt) <= now:
            due.append(t)
    return due


def reschedule(task_id: str, ran_at: datetime | None = None) -> None:
    """Mark a task as just run and compute its next occurrence."""
    ran_at = ran_at or datetime.now()
    tasks = load_tasks()
    for t in tasks:
        if t.get("id") != task_id:
            continue
        t["last_run"] = ran_at.strftime("%Y-%m-%d %H:%M:%S")
        schedule = t.get("schedule") or parse_cadence(t.get("cadence", "")) or {"kind": "startup"}
        if schedule.get("kind") == "startup":
            t["next_run"] = None
        else:
            nxt = compute_next_run(schedule, ran_at)
            t["next_run"] = nxt.isoformat() if nxt else None
        _save(tasks)
        return


def _iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.min


def format_tasks(tasks: list[dict] | None = None) -> str:
    tasks = tasks if tasks is not None else load_tasks()
    if not tasks:
        return "No scheduled tasks."
    lines = ["Scheduled tasks:"]
    for t in tasks:
        state = "paused" if not t.get("enabled", True) else "active"
        nxt   = t.get("next_run") or "startup (once)"
        lines.append(f"- [{t.get('id')}] {t.get('name')} | {t.get('cadence')} | "
                     f"next: {nxt} | {state}")
    return "\n".join(lines)
