"""
Unit tests for actions/email_calendar.py — pure helpers + action guards
(no network, no OAuth).
"""
from datetime import datetime

import email
from email import policy

import pytest

import actions.email_calendar as ec


def test_build_mime_headers():
    raw = ec._build_mime("a@b.com", "Hello", "Body text")
    msg = email.message_from_bytes(raw, policy=policy.SMTP)
    assert msg["To"] == "a@b.com"
    assert msg["Subject"] == "Hello"
    assert msg.get_body().get_content() == "Body text"


def test_parse_start_end_tz_aware():
    start, end = ec._parse_start_end("2026-08-07", "14:30", 90)
    assert start.year == 2026 and start.month == 8 and start.day == 7
    assert start.hour == 14 and start.minute == 30
    assert end.hour == 16 and end.minute == 0
    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert (end - start).total_seconds() == 90 * 60


def test_parse_start_end_default_duration():
    start, end = ec._parse_start_end("2026-08-07", "09:00")
    assert (end - start).total_seconds() == 60 * 60


def test_format_message_summary():
    msg = {"payload": {"headers": [
        {"name": "From", "value": "boss@corp.io"},
        {"name": "Subject", "value": "Quarterly review"},
        {"name": "Date", "value": "Mon, 03 Aug 2026 10:00:00 +0000"},
    ]}}
    out = ec._format_message_summary(msg)
    assert "boss@corp.io" in out and "Quarterly review" in out


def test_format_inbox_empty():
    assert "empty" in ec._format_inbox([])


def test_format_events():
    events = [{"start": {"dateTime": "2026-08-07T10:00:00+03:00"},
               "summary": "Team sync"}]
    out = ec._format_events(events)
    assert "Team sync" in out


def test_format_events_empty():
    assert "No upcoming" in ec._format_events([])


def test_email_send_requires_recipient():
    assert "recipient" in ec.email_send_action({"subject": "x", "body": "y"})


def test_email_send_not_configured(monkeypatch):
    monkeypatch.setattr(ec, "_credentials_ready", lambda: False)
    out = ec.email_send_action({"to": "a@b.com", "subject": "Hi", "body": "yo"})
    assert "not configured" in out.lower()


def test_calendar_add_requires_fields():
    out = ec.calendar_add_action({"title": "Meeting"})
    assert "required" in out.lower()


def test_calendar_add_not_configured(monkeypatch):
    monkeypatch.setattr(ec, "_credentials_ready", lambda: False)
    out = ec.calendar_add_action({"title": "M", "date": "2026-08-07", "time": "10:00"})
    assert "not configured" in out.lower()
