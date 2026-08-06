"""
Unit tests for utils/logger.py — rotating file logging.
"""
import logging

import pytest

from utils import logger as ul


@pytest.fixture(autouse=True)
def _clean():
    ul.reset_logging()
    yield
    ul.reset_logging()


def test_configure_creates_log_file(tmp_path):
    log_file = tmp_path / "ultron.log"
    assert ul.configure_logging(
        log_file=log_file, console=False, force=True) == log_file
    assert log_file.exists()


def test_log_records_land_in_file(tmp_path):
    log_file = tmp_path / "ultron.log"
    ul.configure_logging(log_file=log_file, console=False, force=True)
    ul.get_logger("ultron.test").error("boom %s", "detail")
    text = log_file.read_text(encoding="utf-8")
    assert "boom detail" in text
    assert "ultron.test" in text


def test_levels_are_severity_aware(tmp_path):
    log_file = tmp_path / "ultron.log"
    ul.configure_logging(log_file=log_file, console=False, force=True)
    logger = ul.get_logger("ultron.test")
    logger.debug("hidden")
    logger.warning("warned")
    text = log_file.read_text(encoding="utf-8")
    assert "hidden" not in text
    assert "warned" in text
    assert "WARNING" in text


def test_idempotent_no_duplicate_handlers(tmp_path):
    log_file = tmp_path / "ultron.log"
    ul.configure_logging(log_file=log_file, console=False, force=True)
    ul.configure_logging(log_file=log_file, console=False)   # not forced
    root = logging.getLogger()
    handlers = [h for h in root.handlers
                if isinstance(h, logging.Handler)]
    assert len(handlers) == 1


def test_rotation_respects_max_bytes(tmp_path):
    log_file = tmp_path / "ultron.log"
    ul.configure_logging(log_file=log_file, console=False,
                         max_bytes=200, backup_count=2, force=True)
    logger = ul.get_logger("ultron.rotate")
    for i in range(50):
        logger.info("rotating log entry number %d with padding text", i)
    assert log_file.exists()
    backups = list(tmp_path.glob("ultron.log.*"))
    assert backups, "expected at least one rotated backup file"
