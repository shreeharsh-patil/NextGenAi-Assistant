"""
actions/screen_ocr.py — offline OCR of the screen (or an image) + text return.

Captures a screen region (or reads an image file) and extracts visible text
using ``rapidocr_onnxruntime`` (ONNX, no PyTorch, runs fully offline).  The
returned text lets the assistant read on-screen content directly; translation
is done by the assistant's LLM in the spoken reply.

Region formats::

    "screen"                       → full primary display
    "left,top,width,height"       → pixel bounding box (e.g. "0,0,500,300")
    "center,WxH"                  → centered box e.g. "center,800x400"

Engine is cached module-wide and initialized lazily on first OCR call.
"""
from __future__ import annotations

import threading
from pathlib import Path

from utils.env import is_windows
from utils.logger import get_logger

logger = get_logger("ultron.ocr")

_engine_lock = threading.RLock()
_engine      = None


# ── pure helpers (unit-testable) ──────────────────────────────────────────────

def parse_region(region: str | None, screen_w: int = 1920, screen_h: int = 1080):
    """Translate a region spec into a PIL ``bbox`` tuple.

    Returns ``None`` for the full screen. Raises ``ValueError`` on bad input.
    """
    text = (region or "").strip().lower()
    if not text or text == "screen":
        return None
    if text.startswith("center"):
        base = text.split(",", 1)[1]
        parts = base.split("x") if "x" in base else [base, base]
        try:
            W, H = int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            raise ValueError(f"Bad centered region: {region!r}")
        if W <= 0 or H <= 0:
            raise ValueError("Region width/height must be positive.")
        left = max(0, (screen_w - W) // 2)
        top  = max(0, (screen_h - H) // 2)
        return (left, top, min(screen_w, left + W), min(screen_h, top + H))
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Region must be 'screen' or 'left,top,width,height', got {region!r}")
    try:
        left, top, w, h = (int(p) for p in parts)
    except ValueError:
        raise ValueError(f"Region coordinates must be integers, got {region!r}")
    if w <= 0 or h <= 0:
        raise ValueError("Region width/height must be positive.")
    return (max(0, left), max(0, top),
            max(0, min(screen_w, left + w)), max(0, min(screen_h, top + h)))


def format_ocr_result(result) -> str:
    """RapidOCR result → readable text. Input: list of [box, text, score]."""
    if not result:
        return ""
    lines = []
    for item in result:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            txt = str(item[1])
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            txt = str(item[0])
        else:
            continue
        if txt:
            lines.append(txt)
    return "\n".join(lines).strip() if lines else ""


# ── capture / engine ──────────────────────────────────────────────────────────

def _capture(bbox):
    if is_windows():
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=bbox)
    import mss
    with mss.mss() as sct:
        monitor = {"left": bbox[0], "top": bbox[1],
                   "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
        return sct.grab(monitor)


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
        logger.info("OCR: rapidocr engine ready")
        return _engine


def _engine_available() -> bool:
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        return True
    except Exception:
        return False


def screen_ocr_action(params: dict, player=None) -> str:
    import numpy as np

    region = str(params.get("region") or "screen").strip()
    file_path = str(params.get("file_path") or "").strip()

    try:
        if file_path:
            from PIL import Image
            p = Path(file_path)
            if not p.exists():
                return f"OCR: file not found: {file_path}"
            img = Image.open(p).convert("RGB")
        else:
            bbox = parse_region(region)
            img  = _capture(bbox)
    except ValueError as e:
        return f"OCR: {e}"
    except Exception as e:
        logger.error("OCR: capture failed: %s", e)
        return f"OCR: could not capture the region: {e}"

    if not _engine_available():
        return ("OCR engine not installed. Run: pip install rapidocr_onnxruntime. "
                "Until then, use screen_process (vision) to read on-screen text.")

    try:
        result, _ = _get_engine()(np.array(img))
        text = format_ocr_result(result)
        if not text:
            return "[SCREEN TEXT] No readable text found."
        logger.info("OCR: extracted %d chars from %s", len(text), region or file_path)
        return "[SCREEN TEXT]\n" + text
    except Exception as e:
        logger.error("OCR: engine failed: %s", e)
        return f"OCR failed: {e}"