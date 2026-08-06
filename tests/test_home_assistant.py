"""
Unit tests for actions/home_assistant.py — pure helpers + action guards
(no network, no live HA instance).
"""
import actions.home_assistant as ha


LIGHT = {"entity_id": "light.living_room",
         "state": "on",
         "attributes": {"friendly_name": "Living Room Light",
                        "brightness": 128}}
CLIMATE = {"entity_id": "climate.office",
           "state": "heat",
           "attributes": {"friendly_name": "Office Climate",
                          "temperature": 21.5}}
STANDBY = {"entity_id": "switch.office",
           "state": "off",
           "attributes": {"friendly_name": "Office Switch"}}
ALL = [LIGHT, CLIMATE, STANDBY]


# ── pure helpers ──────────────────────────────────────────────────────────────

def test_state_summary_basic():
    out = ha._state_summary(STANDBY)
    assert "Office Switch" in out and "off" in out


def test_state_summary_brightness():
    assert "brightness 50%" in ha._state_summary(LIGHT)


def test_state_summary_temperature():
    assert "21.5" in ha._state_summary(CLIMATE)


def test_format_states_empty():
    assert "No matching" in ha.format_states([])


def test_format_states_populated():
    out = ha.format_states([LIGHT, STANDBY])
    assert "Living Room Light" in out and "Office Switch" in out


def test_match_entities_exact_name():
    got = ha.match_entities(ALL, "living room light")
    assert got[0]["entity_id"] == "light.living_room"


def test_match_entities_partial_tokens():
    got = ha.match_entities(ALL, "office")
    assert [s["entity_id"] for s in got] == ["switch.office", "climate.office"]


def test_match_entities_none():
    assert ha.match_entities(ALL, "garage door") == []


def test_brightness_clamps():
    assert ha._brightness_percent("150") == 100
    assert ha._brightness_percent("-5") == 0
    assert ha._brightness_percent("42.7") == 42
    assert ha._brightness_percent("abc") is None


def test_temp_clamps():
    assert ha._clamp_temp("99") == 35.0
    assert ha._clamp_temp("-3") == 5.0
    assert ha._clamp_temp("22") == 22.0


# ── action guards ─────────────────────────────────────────────────────────────

def test_action_not_configured(monkeypatch):
    monkeypatch.setattr(ha, "_configured", lambda: False)
    out = ha.home_assistant_action({"action": "states"})
    assert "not configured" in out.lower()


def test_action_requires_entity(monkeypatch):
    monkeypatch.setattr(ha, "_configured", lambda: True)
    out = ha.home_assistant_action({"action": "turn_on"})
    assert "entity" in out.lower()


def test_turn_on_unknown_entity(monkeypatch):
    monkeypatch.setattr(ha, "_configured", lambda: True)
    monkeypatch.setattr(ha, "_get", lambda path: ALL)
    out = ha.home_assistant_action({"action": "turn_on", "entity": "garage door"})
    assert "no entity found" in out.lower()


def test_turn_on_dispatch(monkeypatch):
    calls = {}
    monkeypatch.setattr(ha, "_configured", lambda: True)
    monkeypatch.setattr(ha, "_get", lambda path: ALL)
    monkeypatch.setattr(ha, "_call_service",
                        lambda domain, service, entity, extra=None: calls.update(
                            domain=domain, service=service, entity=entity, extra=extra))
    out = ha.home_assistant_action({"action": "turn_off", "entity": "living room light"})
    assert "off" in out.lower()
    assert calls["domain"] == "homeassistant"
    assert calls["service"] == "turn_off"
    assert calls["entity"] == "light.living_room"


def test_set_brightness_dispatch(monkeypatch):
    calls = {}
    monkeypatch.setattr(ha, "_configured", lambda: True)
    monkeypatch.setattr(ha, "_get", lambda path: ALL)
    monkeypatch.setattr(ha, "_call_service",
                        lambda domain, service, entity, extra=None: calls.update(
                            extra=extra or {}))
    out = ha.home_assistant_action(
        {"action": "set_brightness", "entity": "living room light", "value": "60"})
    assert "60%" in out
    assert calls["extra"]["brightness_pct"] == 60
