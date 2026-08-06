"""
Unit tests for memory/task_scheduler.py — cadence parsing, next-run math,
due/reschedule flow, and JSON persistence (no wall-clock dependence).
"""
import json
from datetime import datetime

import pytest

import memory.task_scheduler as ts


# ── parse_cadence ─────────────────────────────────────────────────────────────

def test_parse_interval():
    assert ts.parse_cadence("every 2 hours") == {"kind": "interval", "n": 2, "unit": "hour"}
    assert ts.parse_cadence("every 30 minutes")["unit"] == "minute"
    assert ts.parse_cadence("EVERY 1 DAY") == {"kind": "interval", "n": 1, "unit": "day"}


def test_parse_daily():
    assert ts.parse_cadence("daily at 09:30")["kind"] == "daily"
    assert ts.parse_cadence("daily at 09:30")["time"] == (9, 30)
    assert ts.parse_cadence("every day at 08:00")["time"] == (8, 0)


def test_parse_weekly():
    w = ts.parse_cadence("weekly at 10:00")
    assert w["kind"] == "weekly" and w["weekday"] == 0 and w["time"] == (10, 0)
    assert ts.parse_cadence("every Monday at 08:00")["weekday"] == 0
    assert ts.parse_cadence("every friday at 18:30")["weekday"] == 4
    assert ts.parse_cadence("every SUN at 07:15")["weekday"] == 6


def test_parse_monthly_and_startup():
    assert ts.parse_cadence("monthly on 15 at 12:00") == {
        "kind": "monthly", "day": 15, "time": (12, 0)}
    assert ts.parse_cadence("startup") == {"kind": "startup"}


def test_parse_invalid():
    assert ts.parse_cadence("") is None
    assert ts.parse_cadence("bogus") is None
    assert ts.parse_cadence("every 0 hours") is None


# ── compute_next_run ──────────────────────────────────────────────────────────

def test_next_interval():
    base = datetime(2026, 8, 6, 12, 0)
    assert ts.compute_next_run({"kind": "interval", "n": 3, "unit": "hour"}, base) == \
        datetime(2026, 8, 6, 15, 0)


def test_next_daily_rolls_to_tomorrow():
    late = datetime(2026, 8, 6, 10, 0)
    sched = {"kind": "daily", "time": (9, 0)}
    assert ts.compute_next_run(sched, late) == datetime(2026, 8, 7, 9, 0)
    early = datetime(2026, 8, 6, 8, 0)
    assert ts.compute_next_run(sched, early) == datetime(2026, 8, 6, 9, 0)


def test_next_weekly():
    # 2026-08-06 is a Thursday (weekday 3).
    base = datetime(2026, 8, 6, 15, 0)
    monday = ts.compute_next_run({"kind": "weekly", "weekday": 0, "time": (9, 0)}, base)
    assert monday == datetime(2026, 8, 10, 9, 0)
    thursday_same_day = ts.compute_next_run({"kind": "weekly", "weekday": 3, "time": (9, 0)},
                                            datetime(2026, 8, 6, 8, 0))
    assert thursday_same_day == datetime(2026, 8, 6, 9, 0)


def test_next_monthly_clamps():
    base = datetime(2026, 2, 1, 12, 0)
    feb = ts.compute_next_run({"kind": "monthly", "day": 31, "time": (10, 0)}, base)
    assert feb == datetime(2026, 2, 28, 10, 0)
    base2 = datetime(2026, 3, 15, 12, 0)
    mar = ts.compute_next_run({"kind": "monthly", "day": 10, "time": (10, 0)}, base2)
    assert mar == datetime(2026, 4, 10, 10, 0)


def test_next_startup_is_none():
    assert ts.compute_next_run({"kind": "startup"}, datetime(2026, 8, 6)) is None


# ── full lifecycle with temp store ────────────────────────────────────────────

@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(ts, "TASKS_FILE", tmp_path / "scheduled_tasks.json")
    ts.reset()
    yield
    ts.reset()


def test_add_list_remove(store):
    t = ts.add_task("daily at 09:00", "Drink water", name="Hydration")
    assert t["id"] and t["next_run"]
    assert ts.list_tasks()[0]["name"] == "Hydration"
    assert ts.remove_task(t["id"]) is True
    assert ts.remove_task(t["id"]) is False
    assert ts.list_tasks() == []


def test_add_bad_cadence_raises(store):
    with pytest.raises(ValueError):
        ts.add_task("whenever", "do something")


def test_get_due_respects_enabled(store):
    t = ts.add_task("daily at 09:00", "Stretch")
    tasks = ts.load_tasks()
    tasks[0]["next_run"] = "2020-01-01T00:00:00"
    tasks[0]["enabled"]  = False
    ts._save(tasks)
    assert ts.get_due() == []
    tasks[0]["enabled"] = True
    ts._save(tasks)
    assert [x["id"] for x in ts.get_due()] == [t["id"]]


def test_reschedule_updates_next_run(store):
    ts.add_task("every 1 minute", "Ping")
    task = ts.list_tasks()[0]
    ts.reschedule(task["id"], datetime(2026, 8, 6, 10, 0))
    updated = ts.load_tasks()[0]
    assert updated["last_run"]
    assert updated["next_run"] == datetime(2026, 8, 6, 10, 1).isoformat()


def test_startup_task_fires_once(store):
    t = ts.add_task("startup", "Welcome briefing")
    assert t["kind"] == "startup"
    assert ts.get_due()[0]["id"] == t["id"]
    ts.reschedule(t["id"], datetime(2026, 8, 6, 9, 0))
    assert ts.get_due() == []


def test_persistence_survives_cache_reset(store):
    ts.add_task("weekly at 08:00", "Weekly review")
    ts.reset()
    assert len(ts.list_tasks()) == 1
    assert ts.list_tasks()[0]["kind"] == "weekly"


def test_format_tasks_empty_and_populated(store):
    assert "No scheduled tasks" in ts.format_tasks([])
    ts.add_task("daily at 09:00", "Meditate")
    out = ts.format_tasks()
    assert "Meditate" in out and "next:" in out
