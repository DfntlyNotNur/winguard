# logger.py
# WinGuard - Logging Module
# Handles writing detected changes and events to a log file.

import os
from datetime import datetime
from config import LOG_FILE


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
    try:
        with open(LOG_FILE, "a") as f:
            line = (
                f"[{entry['timestamp']}] "
                f"[{entry['severity']}] "
                f"[{entry['change_type']}] "
                f"Key: {entry['key_path']} | "
                f"Value: {entry['value_name']} | "
                f"Old: {entry['old_data']} | "
                f"New: {entry['new_data']}\n"
            )
            f.write(line)
    except OSError:
        pass  # Silently fail — UI status bar handles user feedback


def write_info_log(message: str) -> None:
    """
    Writes a general informational message to the log file.
    Used for system events like baseline creation, monitoring start/stop.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] [INFO] {message}\n")
    except OSError:
        pass


def log_exists() -> bool:
    """Returns True if the log file exists."""
    return os.path.exists(LOG_FILE)


def clear_log() -> None:
    """Clears the log file."""
    try:
        with open(LOG_FILE, "w") as f:
            f.write("")
    except OSError:
        pass