# registry_monitor.py
# WinGuard - Windows Registry Monitor Module
# Handles snapshot, baseline save/load, and change detection (diff).

import json
import os
from datetime import datetime
from pathlib import Path

import winreg

from config import (
    BASELINE_FILE_REGISTRY,
    DATE_FORMAT,
    LEGACY_BASELINE_FILE_REGISTRY,
    MONITORED_REGISTRY_KEYS,
    ensure_data_directory,
)

NO_MORE_VALUES_ERROR = 259
SEVERITY_LOOKUP = {
    f"{hive_name}\\{subkey}": severity
    for _, hive_name, subkey, severity in MONITORED_REGISTRY_KEYS
}


# ==============================================================================
# SNAPSHOT
# Reads all values under every monitored registry key.
# Returns a dict keyed by "HIVE\SubKey" -> {value_name: (data, type_int)}
# ==============================================================================

def take_registry_snapshot() -> dict:
    """
    Reads all values from every monitored registry key defined in config.py.
    Returns a nested dict:
        {
            "HKCU\\Software\\...\\Run": {
                "value_name": {"data": "...", "type": 1}
            },
            ...
        }
    """
    snapshot = {}

    for hive_const, hive_name, subkey, severity in MONITORED_REGISTRY_KEYS:
        full_key_path = f"{hive_name}\\{subkey}"
        snapshot[full_key_path] = {}

        try:
            with winreg.OpenKey(hive_const, subkey, 0, winreg.KEY_READ) as reg_key:
                index = 0
                while True:
                    try:
                        value_name, value_data, value_type = winreg.EnumValue(reg_key, index)
                        snapshot[full_key_path][value_name] = {
                            "data": str(value_data),
                            "type": value_type,
                        }
                        index += 1
                    except OSError as error:
                        if getattr(error, "winerror", None) == NO_MORE_VALUES_ERROR:
                            break
                        snapshot[full_key_path]["__error__"] = {
                            "data": f"OS Error: {error}",
                            "type": -1,
                        }
                        break

        except PermissionError:
            # Access denied (common for HKLM keys without admin rights)
            snapshot[full_key_path]["__error__"] = {
                "data": "ACCESS DENIED - Run as Administrator for full access.",
                "type": -1
            }
        except FileNotFoundError:
            # Key does not exist on this system — not an error, just empty
            pass
        except OSError as e:
            snapshot[full_key_path]["__error__"] = {
                "data": f"OS Error: {str(e)}",
                "type": -1
            }

    return snapshot


# ==============================================================================
# BASELINE — SAVE & LOAD
# ==============================================================================

def save_baseline(snapshot: dict) -> str:
    """
    Saves the given snapshot dict to a JSON baseline file.
    Returns a status message string.
    """
    baseline_data = {
        "created_at": datetime.now().strftime(DATE_FORMAT),
        "snapshot": snapshot
    }

    try:
        _write_json_atomic(BASELINE_FILE_REGISTRY, baseline_data)
        return f"Baseline saved at {baseline_data['created_at']}"
    except OSError as e:
        return f"Failed to save baseline: {str(e)}"


def load_baseline() -> dict | None:
    """
    Loads the saved baseline JSON file.
    Returns the snapshot dict, or None if no baseline file exists.
    """
    baseline_file = _baseline_file()
    if not baseline_file.exists():
        return None

    try:
        with baseline_file.open("r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        return baseline_data.get("snapshot", {})
    except (json.JSONDecodeError, OSError):
        return None


def get_baseline_timestamp() -> str | None:
    """
    Returns the timestamp string from the saved baseline file,
    or None if no baseline exists.
    """
    baseline_file = _baseline_file()
    if not baseline_file.exists():
        return None
    try:
        with baseline_file.open("r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        return baseline_data.get("created_at", None)
    except (json.JSONDecodeError, OSError):
        return None


# ==============================================================================
# DIFF — CHANGE DETECTION
# Compares current snapshot against saved baseline.
# ==============================================================================

def compare_snapshots(baseline: dict, current: dict, advance_reference: bool = True) -> list[dict]:
    """
    Compares current registry snapshot against the baseline.
    Returns a list of detected change dicts:
        {
            "timestamp":   "2025-01-01 12:00:00",
            "key_path":    "HKCU\\Software\\...\\Run",
            "value_name":  "MyValue",
            "change_type": "ADDED" | "DELETED" | "MODIFIED",
            "old_data":    "...",
            "new_data":    "...",
            "severity":    "HIGH" | "MEDIUM" | "LOW"
        }

    If advance_reference is True, the baseline dictionary is updated in memory
    after comparison. This prevents the same change from being reported again on
    every polling interval while still allowing later changes to be detected.
    """
    changes = []
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    all_keys = set(baseline.keys()) | set(current.keys())

    for key_path in sorted(all_keys):
        severity = SEVERITY_LOOKUP.get(key_path, "MEDIUM")

        baseline_values = baseline.get(key_path, {})
        current_values  = current.get(key_path, {})

        all_value_names = sorted(set(baseline_values.keys()) | set(current_values.keys()))

        for value_name in all_value_names:
            # Skip internal error markers
            if value_name == "__error__":
                continue

            in_baseline = value_name in baseline_values
            in_current  = value_name in current_values

            if in_baseline and not in_current:
                # Value was deleted
                changes.append({
                    "timestamp":   timestamp,
                    "key_path":    key_path,
                    "value_name":  value_name,
                    "change_type": "DELETED",
                    "old_data":    baseline_values[value_name]["data"],
                    "new_data":    "",
                    "severity":    severity
                })

            elif in_current and not in_baseline:
                # Value was added
                changes.append({
                    "timestamp":   timestamp,
                    "key_path":    key_path,
                    "value_name":  value_name,
                    "change_type": "ADDED",
                    "old_data":    "",
                    "new_data":    current_values[value_name]["data"],
                    "severity":    severity
                })

            else:
                # Value exists in both — check if data changed
                if baseline_values[value_name]["data"] != current_values[value_name]["data"]:
                    changes.append({
                        "timestamp":   timestamp,
                        "key_path":    key_path,
                        "value_name":  value_name,
                        "change_type": "MODIFIED",
                        "old_data":    baseline_values[value_name]["data"],
                        "new_data":    current_values[value_name]["data"],
                        "severity":    severity
                    })

    if advance_reference:
        baseline.clear()
        baseline.update(current)

    return changes


def _baseline_file() -> Path:
    return BASELINE_FILE_REGISTRY if BASELINE_FILE_REGISTRY.exists() else LEGACY_BASELINE_FILE_REGISTRY


def _write_json_atomic(path: Path, payload: dict) -> None:
    ensure_data_directory()
    temporary_path = path.with_name(f".{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
