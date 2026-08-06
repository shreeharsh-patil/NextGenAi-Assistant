"""
utils/logger.py — ULTRON rotating file + console logging.

Call ``configure_logging()`` once at every process entry point
(``main.py``, ``wake_service.py``, ``ULTRON_SETUP.py``).  Log records are
written to ``logs/ultron.log`` with automatic rotation (5 MB per file,
5 backups) and mirrored to the console.

Usage::

    from utils.logger import configure_logging, get_logger
    configure_logging()
    logger = get_logger("ultron.main")
    logger.info("ULTRON online")
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


DEFAULT_LOG_DIR  = get_base_dir() / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "ultron.log"

_FORMAT   = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(
    level: int = logging.INFO,
    log_file: str | Path | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
    force: bool = False,
) -> Path:
    """Set up the root logger. Idempotent unless ``force=True``.

    Returns the log file path that was used.
    """
    global _configured
    if _configured and not force:
        return Path(log_file) if log_file else DEFAULT_LOG_FILE

    path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Drop any handlers added by a previous configuration so rotation
    # settings / file paths never accumulate.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    fmt = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    file_handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        root.addHandler(console_handler)

    _configured = True
    return path


def get_logger(name: str = "ultron") -> logging.Logger:
    """Return a named child logger (hierarchy root: ``ultron``)."""
    return logging.getLogger(name)


def reset_logging() -> None:
    """Remove all handlers from the root logger (used by tests)."""
    global _configured
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    _configured = False
