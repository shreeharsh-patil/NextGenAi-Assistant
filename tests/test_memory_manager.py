"""
Unit tests for memory/memory_manager.py — structured long-term memory.
Uses a temp file so the developer's real long_term.json is never touched.
"""
import json

import pytest

import memory.memory_manager as mm


@pytest.fixture()
def mem_path(tmp_path, monkeypatch):
    p = tmp_path / "long_term.json"
    monkeypatch.setattr(mm, "MEMORY_PATH", p)
    return p


def test_empty_memory_loads_clean(mem_path):
    memory = mm.load_memory()
    for cat in ("identity", "preferences", "projects", "relationships",
                "wishes", "notes"):
        assert memory[cat] == {}


def test_update_and_load_roundtrip(mem_path):
    mm.update_memory({"identity": {"name": {"value": "Fatih"}}})
    memory = mm.load_memory()
    assert memory["identity"]["name"]["value"] == "Fatih"


def test_update_persists_to_disk(mem_path):
    mm.update_memory({"preferences": {"coffee": {"value": "black"}}})
    raw = json.loads(mem_path.read_text(encoding="utf-8"))
    assert raw["preferences"]["coffee"]["value"] == "black"


def test_update_skips_empty_values(mem_path):
    before = mm.load_memory()
    mm.update_memory({"identity": {"name": {"value": "   "}}})
    assert mm.load_memory() == before


def test_format_memory_for_prompt(mem_path):
    mm.update_memory({
        "identity":    {"name": {"value": "Fatih"}, "city": {"value": "Istanbul"}},
        "preferences": {"music": {"value": "jazz"}},
    })
    text = mm.format_memory_for_prompt(mm.load_memory())
    assert "Fatih" in text
    assert "Istanbul" in text
    assert "jazz" in text
    assert "WHAT YOU KNOW" in text


def test_format_empty_memory_returns_empty():
    assert mm.format_memory_for_prompt({}) == ""


def test_remember_and_forget(mem_path):
    assert "Remembered" in mm.remember("favorite_food", "pizza", "preferences")
    assert mm.load_memory()["preferences"]["favorite_food"]["value"] == "pizza"
    assert "Forgotten" in mm.forget("favorite_food", "preferences")
    assert "favorite_food" not in mm.load_memory()["preferences"]


def test_truncate_long_values(mem_path):
    long_value = "x" * 2000
    mm.update_memory({"notes": {"long": {"value": long_value}}})
    stored = mm.load_memory()["notes"]["long"]["value"]
    assert len(stored) <= mm.MAX_VALUE_LENGTH + 1
