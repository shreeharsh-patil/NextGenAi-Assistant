"""
Unit tests for actions/screen_ocr.py — region parsing, result formatting,
and action guards (no screen capture / no OCR engine run).
"""
import pytest

import actions.screen_ocr as so


# ── parse_region ──────────────────────────────────────────────────────────────

def test_full_screen_is_none():
    assert so.parse_region(None) is None
    assert so.parse_region("screen") is None
    assert so.parse_region("") is None


def test_parse_bbox():
    assert so.parse_region("0,0,500,300") == (0, 0, 500, 300)
    assert so.parse_region("100, 50, 400, 200") == (100, 50, 500, 250)


def test_parse_bbox_clamps_to_screen():
    assert so.parse_region("0,0,99999,99999", 1920, 1080) == (0, 0, 1920, 1080)
    assert so.parse_region("-10,-10,500,300") == (0, 0, 490, 290)


def test_parse_center():
    assert so.parse_region("center,800x600", 1920, 1080) == (560, 240, 1360, 840)
    assert so.parse_region("center,1920x1080", 1920, 1080) == (0, 0, 1920, 1080)


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        so.parse_region("a,b,c")
    with pytest.raises(ValueError):
        so.parse_region("0,0,-5,10")


# ── format_ocr_result ─────────────────────────────────────────────────────────

def test_format_ocr_result():
    result = [([0, 0, 10, 10], "Hello", 0.99),
              ([0, 20, 10, 30], "world", 0.98)]
    assert so.format_ocr_result(result) == "Hello\nworld"


def test_format_ocr_result_empty_and_garbage():
    assert so.format_ocr_result([]) == ""
    assert so.format_ocr_result([[1, 2, 3, 4]]) == ""


# ── action guards ─────────────────────────────────────────────────────────────

def test_missing_file():
    out = so.screen_ocr_action({"file_path": r"C:\does_not_exist_ultron.png"})
    assert "not found" in out


def test_engine_missing_guard(monkeypatch):
    monkeypatch.setattr(so, "_engine_available", lambda: False)
    out = so.screen_ocr_action({"region": "screen"})
    assert "rapidocr" in out.lower()
