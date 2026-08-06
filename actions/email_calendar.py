"""
actions/email_calendar.py — Gmail + Google Calendar via Google APIs (OAuth 2.0).

One-time setup
--------------
1. Create an OAuth Desktop client at https://console.cloud.google.com/apis/credentials
   and enable the Gmail API + Google Calendar API for your project.
2. Download ``client_secret.json`` and save it as ``config/client_secret.json``.
3. Optionally override the path / set raw credentials in ``config/api_keys.json``::

       "google_client_secrets_file": "config/client_secret.json"

   First use opens the browser for consent; the token is cached in
   ``config/token.json`` (gitignored).

Tools exposed to Gemini: ``email_send``, ``email_read``, ``calendar_list``,
``calendar_add``.  Every action function returns a plain string meant for the
LLM to speak.
"""
from __future__ import annotations

import base64
import json
import sys
import threading
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from utils.logger import get_logger
from utils.env import load_config

logger = get_logger("ultron.google")

_SCOPES = {
    "gmail":    ["https://www.googleapis.com/auth/gmail.send",
                 "https://www.googleapis.com/auth/gmail.readonly"],
    "calendar": ["https://www.googleapis.com/auth/calendar"],
}

AUTH_PORT      = 8085
TOKEN_FILE     = "token.json"
CLIENT_FILE    = "client_secret.json"
_creds_lock    = threading.RLock()
_service_cache: dict[str, object] = {}


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


CONFIG_DIR = get_base_dir() / "config"


def _secrets_file() -> Path:
    cfg = load_config()
    custom = cfg.get("google_client_secrets_file")
    if custom:
        p = Path(custom)
        if not p.is_absolute():
            p = get_base_dir() / p
        return p
    return CONFIG_DIR / CLIENT_FILE


def _credentials_ready() -> bool:
    if (CONFIG_DIR / TOKEN_FILE).exists():
        return True
    return (_secrets_file().exists()
            or (load_config().get("google_client_id")
                and load_config().get("google_client_secret")))


def _get_credentials(api: str):
    """Load (or run the one-time OAuth flow for) Google credentials."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = CONFIG_DIR / TOKEN_FILE
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES[api])
        if creds and creds.valid:
            return creds
        if creds and creds.refresh_token:
            try:
                import google.auth.transport.requests as _req
                creds.refresh(_req.Request())
                return creds
            except Exception as e:
                logger.warning("GSuite: token refresh failed (%s) — re-running consent", e)

    cfg = load_config()
    cid, csec = cfg.get("google_client_id"), cfg.get("google_client_secret")
    if cid and csec:
        flow = InstalledAppFlow.from_client_config(
            {"installed": {"client_id": cid, "client_secret": csec,
                           "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                           "token_uri": "https://oauth2.googleapis.com/token"}},
            _SCOPES[api],
        )
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(_secrets_file()), _SCOPES[api])
    creds = flow.run_local_server(port=AUTH_PORT, open_browser=True)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    logger.info("GSuite: token saved to %s", token_path.name)
    return creds


def _service(api: str, version: str):
    """Lazily build a cached googleapiclient service."""
    if api in _service_cache:
        return _service_cache[api]
    with _creds_lock:
        if api in _service_cache:
            return _service_cache[api]
        from googleapiclient.discovery import build
        creds = _get_credentials(api)
        svc = build(api, version, credentials=creds, cache_discovery=False)
        _service_cache[api] = svc
        return svc


# ── pure helpers (unit-testable, no network) ─────────────────────────────────

def _build_mime(to: str, subject: str, body: str) -> bytes:
    msg = MIMEMultipart("alternative")
    msg["To"]      = to
    msg["Subject"] = subject or "(no subject)"
    msg.attach(MIMEText(body or "", "plain", "utf-8"))
    return msg.as_bytes()


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return str(h.get("value", ""))
    return ""


def _format_message_summary(msg: dict) -> str:
    headers = msg.get("payload", {}).get("headers", [])
    return (f"- {_header(headers, 'From')} | {_header(headers, 'Subject')} "
            f"| {_header(headers, 'Date')}")


def _format_inbox(messages: list[dict]) -> str:
    if not messages:
        return "Your inbox is empty."
    return "Recent emails:\n" + "\n".join(_format_message_summary(m) for m in messages)


def _parse_start_end(date: str, time: str, duration_min: int = 60):
    """Parse 'YYYY-MM-DD' + 'HH:MM' into local (start, end) datetimes."""
    start = datetime.strptime(f"{date}T{time}", "%Y-%m-%dT%H:%M")
    start = start.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return start, start + timedelta(minutes=int(duration_min))


def _format_events(events: list[dict]) -> str:
    if not events:
        return "No upcoming calendar events."
    lines = ["Upcoming events:"]
    for ev in events:
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        lines.append(f"- {start}  {ev.get('summary', '(untitled)')}")
    return "\n".join(lines)


# ── tool action functions ─────────────────────────────────────────────────────

def email_send_action(params: dict) -> str:
    to      = str(params.get("to") or "").strip()
    subject = str(params.get("subject") or "").strip()
    body    = str(params.get("body") or "").strip()
    if not to or "@" not in to:
        return "Email send failed: a valid recipient 'to' address is required."
    try:
        if not _credentials_ready():
            return ("Email is not configured. Add config/client_secret.json "
                    "(or google_client_id/secret) to config/api_keys.json.")
        raw = base64.urlsafe_b64encode(_build_mime(to, subject, body)).decode("ascii")
        svc = _service("gmail", "v1")
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info("Email sent to %s", to)
        return f"Email sent to {to}."
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return f"Email send failed: {e}"


def email_read_action(params: dict) -> str:
    max_results = int(params.get("max_results") or 5)
    query       = str(params.get("query") or "").strip()
    try:
        if not _credentials_ready():
            return ("Email is not configured. Add config/client_secret.json "
                    "(or google_client_id/secret) to config/api_keys.json.")
        svc = _service("gmail", "v1")
        result = svc.users().messages().list(
            userId="me", maxResults=max_results, q=query).execute()
        ids = (result.get("messages") or [])[:max_results]
        messages = []
        for m in ids:
            full = svc.users().messages().get(
                userId="me", id=m["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            messages.append(full)
        return _format_inbox(messages)
    except Exception as e:
        logger.error("Email read failed: %s", e)
        return f"Email read failed: {e}"


def calendar_list_action(params: dict) -> str:
    days = int(params.get("days") or 1)
    try:
        if not _credentials_ready():
            return ("Calendar is not configured. Add config/client_secret.json "
                    "(or google_client_id/secret) to config/api_keys.json.")
        svc = _service("calendar", "v3")
        now = datetime.now().astimezone().isoformat()
        end = (datetime.now().astimezone() + timedelta(days=days)).isoformat()
        result = svc.events().list(
            calendarId="primary", timeMin=now, timeMax=end,
            singleEvents=True, orderBy="startTime",
            maxResults=30,
        ).execute()
        return _format_events(result.get("items", []))
    except Exception as e:
        logger.error("Calendar list failed: %s", e)
        return f"Calendar list failed: {e}"


def calendar_add_action(params: dict) -> str:
    title   = str(params.get("title") or "").strip()
    date    = str(params.get("date") or "").strip()
    time    = str(params.get("time") or "").strip()
    minutes = int(params.get("duration_min") or 60)
    desc    = str(params.get("description") or "").strip()
    if not title or not date or not time:
        return ("Calendar add failed: 'title', 'date' (YYYY-MM-DD) and "
                "'time' (HH:MM) are required.")
    try:
        if not _credentials_ready():
            return ("Calendar is not configured. Add config/client_secret.json "
                    "(or google_client_id/secret) to config/api_keys.json.")
        start, end = _parse_start_end(date, time, minutes)
        svc = _service("calendar", "v3")
        event = {
            "summary": title,
            "start":   {"dateTime": start.isoformat()},
            "end":     {"dateTime": end.isoformat()},
        }
        if desc:
            event["description"] = desc
        svc.events().insert(calendarId="primary", body=event).execute()
        logger.info("Calendar event created: %s @ %s %s", title, date, time)
        return f"Calendar event '{title}' added for {date} at {time}."
    except Exception as e:
        logger.error("Calendar add failed: %s", e)
        return f"Calendar add failed: {e}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gmail / Calendar helper (CLI test)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    send = sub.add_parser("send")
    send.add_argument("--to", required=True)
    send.add_argument("--subject", default="")
    send.add_argument("--body", default="")
    lst = sub.add_parser("list")
    lst.add_argument("--days", type=int, default=1)
    add = sub.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--date", required=True)
    add.add_argument("--time", required=True)
    add.add_argument("--minutes", type=int, default=60)
    read = sub.add_parser("read")
    read.add_argument("--query", default="")
    read.add_argument("--max", type=int, default=5)
    args = parser.parse_args()

    if args.cmd == "send":
        print(email_send_action({"to": args.to, "subject": args.subject, "body": args.body}))
    elif args.cmd == "list":
        print(calendar_list_action({"days": args.days}))
    elif args.cmd == "add":
        print(calendar_add_action({"title": args.title, "date": args.date,
                                   "time": args.time, "duration_min": args.minutes}))
    else:
        print(email_read_action({"query": args.query, "max_results": args.max}))
