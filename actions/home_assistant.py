"""
actions/home_assistant.py — smart-home control via the Home Assistant REST API.

One-time setup
--------------
1. Create a Long-Lived Access Token in Home Assistant:
   Profile → Security → Long-lived access tokens.
2. Add it to ``config/api_keys.json``::

       "home_assistant_url":   "http://192.168.1.50:8123",
       "home_assistant_token": "eyJhbGciOi..."

Tools exposed to Gemini: ``home_assistant``.  Action functions return a plain
string meant for the LLM to speak.  All network calls are isolated behind
``_get`` / ``_call_service`` so the pure helpers are unit-testable.
"""
from __future__ import annotations

from urllib.parse import urljoin

import requests

from utils.env import load_config
from utils.logger import get_logger

logger = get_logger("ultron.ha")

_HA_TIMEOUT = 8  # seconds
_SERVICE_ACTIONS = {
    "turn_on":       ("homeassistant", "turn_on"),
    "turn_off":      ("homeassistant", "turn_off"),
    "toggle":        ("homeassistant", "toggle"),
    "set_brightness": ("light", "turn_on"),
    "set_value":     ("homeassistant", "turn_on"),
    "media_play":    ("media_player", "media_play"),
    "media_pause":   ("media_player", "media_pause"),
    "media_next":    ("media_player", "media_next"),
    "media_previous":("media_player", "media_previous"),
    "media_volume":  ("media_player", "volume_set"),
    "climate_set":   ("climate", "set_temperature"),
    "climate_mode":  ("climate", "set_hvac_mode"),
}


# ── config / connectivity ─────────────────────────────────────────────────────

def _settings() -> tuple[str, str]:
    cfg  = load_config()
    url  = str(cfg.get("home_assistant_url") or "").strip().rstrip("/")
    token = str(cfg.get("home_assistant_token") or "").strip()
    return url, token


def _configured() -> bool:
    url, token = _settings()
    return bool(url and token)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _endpoint(base: str, path: str) -> str:
    return urljoin(base + "/", path.lstrip("/"))


def _get(path: str, timeout: int = _HA_TIMEOUT) -> dict | list:
    base, token = _settings()
    resp = requests.get(_endpoint(base, path), headers=_headers(token), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _call_service(domain: str, service: str, entity_id: str,
                  extra: dict | None = None, timeout: int = _HA_TIMEOUT) -> None:
    base, token = _settings()
    url  = _endpoint(base, f"api/services/{domain}/{service}")
    body = {"entity_id": entity_id}
    if extra:
        body.update(extra)
    resp = requests.post(url, json=body, headers=_headers(token), timeout=timeout)
    resp.raise_for_status()


# ── pure helpers (unit-testable) ──────────────────────────────────────────────

def _entity_name(state: dict) -> str:
    return str((state.get("attributes") or {}).get("friendly_name") or state.get("entity_id") or "")


def _state_summary(state: dict) -> str:
    entity = state.get("entity_id", "")
    name   = _entity_name(state)
    state_v = state.get("state", "")
    attrs  = state.get("attributes") or {}
    extra  = ""
    if "brightness" in attrs:
        try:
            extra = f", brightness {int(attrs['brightness']) * 100 // 255}%"
        except (TypeError, ValueError):
            pass
    if "temperature" in attrs:
        extra = f", {attrs['temperature']}°"
    return f"{name or entity} = {state_v}{extra}"


def format_states(states: list[dict]) -> str:
    if not states:
        return "No matching entities found in Home Assistant."
    return "\n".join(f"- {_state_summary(s)}" for s in states)


def match_entities(states: list[dict], query: str, limit: int = 5) -> list[dict]:
    """Fuzzy-match entities by entity_id / friendly_name tokens.

    Exact match wins; then entities whose name contains *all* query words;
    then those containing *any* word. Returns at most ``limit`` results.
    """
    q = (query or "").strip().lower()
    if not q:
        return states[:limit]
    tokens = [w for w in q.replace("_", " ").split() if w]

    def score(st: dict) -> tuple[int, int]:
        ent  = str(st.get("entity_id") or "").lower()
        name = _entity_name(st).lower().replace("_", " ")
        hay  = f"{name} {ent}"
        if ent == q or name == q:
            return (0, 0)
        if all(w in hay for w in tokens):
            return (1, len(hay))
        if any(w in hay for w in tokens):
            return (2, len(hay))
        return (9, 0)

    ranked = sorted(states, key=score)
    return [s for s in ranked[:limit] if score(s)[0] < 9]


def _brightness_percent(value) -> int | None:
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, v))


def _clamp_temp(value, lo: float = 5.0, hi: float = 35.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 22.0
    return max(lo, min(hi, v))


# ── tool action ───────────────────────────────────────────────────────────────

def home_assistant_action(params: dict) -> str:
    action = str(params.get("action") or "").strip().lower()
    target = str(params.get("entity") or "").strip()

    if not _configured():
        return ("Home Assistant is not configured. Add 'home_assistant_url' and "
                "'home_assistant_token' to config/api_keys.json.")

    try:
        if action in ("states", "list"):
            states = _get("api/states")
            if not isinstance(states, list):
                return "Home Assistant returned an unexpected response."
            q = str(params.get("filter") or "").strip()
            matched = match_entities(states, q) if q else states
            return format_states(matched[: int(params.get("limit") or 20)])

        if action == "state":
            states = _get("api/states")
            if not isinstance(states, list):
                return "Home Assistant returned an unexpected response."
            matched = match_entities(states, target)
            return format_states(matched[:3]) if matched else f"No entity found for '{target}'."

        if not target:
            return f"Action '{action}' needs an 'entity' (name or entity_id)."

        states = _get("api/states")
        if not isinstance(states, list):
            return "Home Assistant returned an unexpected response."
        matched = match_entities(states, target, limit=1)
        if not matched:
            return f"No entity found for '{target}'."
        entity_id = matched[0]["entity_id"]

        if action == "set_brightness":
            pct = _brightness_percent(params.get("value"))
            if pct is None:
                return "set_brightness needs a numeric 'value' (0-100)."
            _call_service("light", "turn_on", entity_id, {"brightness_pct": pct})
            return f"Brightness of {target} set to {pct}%."

        if action == "set_value":
            val = str(params.get("value") or "").strip()
            if not val:
                return "set_value needs a numeric 'value'."
            _call_service("homeassistant", "turn_on", entity_id, {"value": val})
            return f"Set {target} to {val}."

        if action in ("media_play", "media_pause", "media_next", "media_previous"):
            domain, service = _SERVICE_ACTIONS[action]
            _call_service(domain, service, entity_id)
            return f"{action.replace('media_', '').title()} on {target}."

        if action == "media_volume":
            pct = _brightness_percent(params.get("value"))
            if pct is None:
                return "media_volume needs a numeric 'value' (0-100)."
            _call_service("media_player", "volume_set", entity_id, {"volume_level": pct / 100.0})
            return f"Volume of {target} set to {pct}%."

        if action == "climate_set":
            temp = _clamp_temp(params.get("value"))
            _call_service("climate", "set_temperature", entity_id, {"temperature": temp})
            return f"Temperature on {target} set to {temp}°."

        if action == "climate_mode":
            mode = str(params.get("mode") or "heat").strip().lower()
            _call_service("climate", "set_hvac_mode", entity_id, {"hvac_mode": mode})
            return f"HVAC mode of {target} set to {mode}."

        domain, service = _SERVICE_ACTIONS.get(action, ("homeassistant", action))
        _call_service(domain, service, entity_id)
        return f"{action.replace('_', ' ').title()} on {target}."
    except Exception as e:
        logger.error("Home Assistant %s failed: %s", action, e)
        return f"Home Assistant {action} failed: {e}"
