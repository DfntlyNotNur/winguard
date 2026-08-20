# WinGuard file integrity monitoring engine
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from config import BASELINE_FILE_FIM, FIM_DIRECTORIES_FILE, MONITORED_DIRECTORIES

DATE_FORMAT = "%d/%m/%Y %H:%M:%S"


def _timestamp() -> str:
    return datetime.now().strftime(DATE_FORMAT)


def normalize_directory(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expandvars(path))))


def display_directory(path: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expandvars(path)))


def load_fim_directories() -> list[str]:
    directories = list(MONITORED_DIRECTORIES)
    try:
        with open(FIM_DIRECTORIES_FILE, "r", encoding="utf-8") as handle:
            saved = json.load(handle).get("directories", [])
        for directory in saved:
            if normalize_directory(directory) not in {normalize_directory(item) for item in directories}:
                directories.append(directory)
    except (OSError, json.JSONDecodeError):
        pass
    return directories


def save_fim_directories(directories: list[str]) -> None:
    with open(FIM_DIRECTORIES_FILE, "w", encoding="utf-8") as handle:
        json.dump({"directories": directories}, handle, indent=4)


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    # A second stat check avoids hashing a file while another process is writing it.
    for _ in range(3):
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                digest.update(chunk)
        after = path.stat()
        if before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns:
            return digest.hexdigest()
    raise OSError("File is still changing")


def take_file_snapshot(directories: list[str] | None = None) -> dict:
    directories = directories if directories is not None else load_fim_directories()
    files, warnings, directory_records = {}, [], []
    complete = True

    for directory in directories:
        root = Path(display_directory(directory))
        record = {"path": str(root), "exists": root.is_dir(), "file_count": 0}
        directory_records.append(record)
        if not root.is_dir():
            complete = False
            warnings.append({"path": str(root), "message": "Directory does not exist or is inaccessible."})
            continue
        try:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                absolute_path = str(path.resolve())
                try:
                    stat = path.stat()
                    files[absolute_path] = {
                        "size": stat.st_size,
                        "modified": stat.st_mtime_ns,
                        "sha256": _hash_file(path),
                    }
                    record["file_count"] += 1
                except (OSError, PermissionError) as error:
                    complete = False
                    warnings.append({"path": absolute_path, "message": str(error)})
        except (OSError, PermissionError) as error:
            complete = False
            warnings.append({"path": str(root), "message": str(error)})

    return {
        "scanned_at": _timestamp(),
        "files": files,
        "directories": directory_records,
        "warnings": warnings,
        "complete": complete,
    }


def save_fim_baseline(snapshot: dict, directories: list[str]) -> str:
    state = {
        "created_at": _timestamp(),
        "directories": directories,
        "baseline_snapshot": snapshot,
        "reference_snapshot": snapshot,
    }
    try:
        with open(BASELINE_FILE_FIM, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=4)
        return f"Baseline saved at {state['created_at']}"
    except OSError as error:
        return f"Failed to save FIM baseline: {error}"


def load_fim_state() -> dict | None:
    if not os.path.exists(BASELINE_FILE_FIM):
        return None
    try:
        with open(BASELINE_FILE_FIM, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        state.setdefault("reference_snapshot", state.get("snapshot", {}))
        state.setdefault("baseline_snapshot", state.get("snapshot", {}))
        state.setdefault("directories", load_fim_directories())
        return state
    except (OSError, json.JSONDecodeError):
        return None


def get_fim_baseline_timestamp() -> str | None:
    state = load_fim_state()
    return state.get("created_at") if state else None


def compare_file_snapshots(reference: dict, current: dict, advance_reference: bool = True) -> list[dict]:
    old_files = reference.get("files", {})
    new_files = current.get("files", {})
    changes = []
    timestamp = _timestamp()

    # If any part of a scan was inaccessible, retain missing old entries. This
    # prevents a temporary read failure from becoming a false DELETED alert.
    if not current.get("complete", True):
        effective_files = dict(old_files)
        effective_files.update(new_files)
    else:
        effective_files = new_files

    for path in sorted(set(old_files) | set(effective_files)):
        old_record = old_files.get(path)
        new_record = effective_files.get(path)
        if old_record is None:
            changes.append({"timestamp": timestamp, "severity": "HIGH", "change_type": "ADDED",
                            "file_path": path, "old_hash": "", "new_hash": new_record["sha256"],
                            "details": "New file detected"})
        elif new_record is None:
            changes.append({"timestamp": timestamp, "severity": "HIGH", "change_type": "DELETED",
                            "file_path": path, "old_hash": old_record["sha256"], "new_hash": "",
                            "details": "File no longer exists"})
        elif old_record.get("sha256") != new_record.get("sha256"):
            changes.append({"timestamp": timestamp, "severity": "MEDIUM", "change_type": "MODIFIED",
                            "file_path": path, "old_hash": old_record["sha256"],
                            "new_hash": new_record["sha256"], "details": "SHA-256 hash changed"})

    if advance_reference:
        reference.clear()
        reference.update({**current, "files": effective_files})
    return changes


def persist_reference(state: dict) -> None:
    with open(BASELINE_FILE_FIM, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=4)
