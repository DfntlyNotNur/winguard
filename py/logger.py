# logger.py
# WinGuard - Logging Module
# Handles writing detected changes and events to a rotating log file.

import logging
import os
import shutil
from datetime import datetime
from logging.handlers import RotatingFileHandler

from config import (
    DATE_FORMAT,
    LEGACY_LOG_FILE,
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_MAX_BYTES,
    ensure_data_directory,
)

LOGGER_NAME = "winguard"
_logger = logging.getLogger(LOGGER_NAME)
_logger.setLevel(logging.INFO)
_logger.propagate = False
_handler = None


def _get_logger() -> logging.Logger | None:
    global _handler
    if _handler is not None:
        return _logger

    try:
        ensure_data_directory()
        if not LOG_FILE.exists() and LEGACY_LOG_FILE.exists():
            shutil.copy2(LEGACY_LOG_FILE, LOG_FILE)
        _handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
            delay=True,
        )
        _handler.setFormatter(logging.Formatter("%(message)s"))
        _logger.addHandler(_handler)
        return _logger
    except OSError:
        return None


def write_log(entry: dict) -> None:
    """
    Appends a single change entry dict to the WinGuard log file.
    Entry format expected (from compare_snapshots):
        {
            "timestamp":   str,
            "key_path":    str,
            "value_name":  str,
            "change_type": str,
            "old_data":    str,
            "new_data":    str,
            "severity":    str
        }
    """
    logger = _get_logger()
    if logger is None:
        return
    line = (
        f"[{entry['timestamp']}] "
        f"[{entry['severity']}] "
        f"[{entry['change_type']}] "
        f"Key: {entry['key_path']} | "
        f"Value: {entry['value_name']} | "
        f"Old: {entry['old_data']} | "
        f"New: {entry['new_data']}"
    )
    logger.info(line)


def write_fim_log(entry: dict) -> None:
    """Write a file-integrity event using the shared rotating log."""
    logger = _get_logger()
    if logger is None:
        return
    line = (
        f"[{entry['timestamp']}] "
        f"[{entry.get('severity', 'INFO')}] "
        f"[{entry['change_type']}] "
        f"File: {entry['file_path']} | {entry['details']} | "
        f"Old SHA-256: {entry.get('old_hash', '')} | "
        f"New SHA-256: {entry.get('new_hash', '')}"
    )
    logger.info(line)


def write_info_log(message: str) -> None:
    """
    Writes a general informational message to the log file.
    Used for system events like baseline creation, monitoring start/stop.
    """
    logger = _get_logger()
    if logger is not None:
        timestamp = datetime.now().strftime(DATE_FORMAT)
        logger.info(f"[{timestamp}] [INFO] {message}")


def log_exists() -> bool:
    """Returns True if the log file exists."""
    return os.path.exists(LOG_FILE)


def clear_log() -> None:
    """Clears the log file."""
    global _handler
    if _handler is not None:
        _logger.removeHandler(_handler)
        _handler.close()
        _handler = None
    try:
        ensure_data_directory()
        LOG_FILE.write_text("", encoding="utf-8")
    except OSError:
        pass
