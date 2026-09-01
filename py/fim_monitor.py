# WinGuard file integrity monitoring engine
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from config import (
    BASELINE_FILE_FIM,
    FIM_DIRECTORIES_FILE,
    LEGACY_BASELINE_FILE_FIM,
    LEGACY_FIM_DIRECTORIES_FILE,
    MONITORED_DIRECTORIES,
    STATE_FILE_FIM,
    ensure_data_directory,
)

DATE_FORMAT = "%d/%m/%Y %H:%M:%S"


def _timestamp() -> str:
    return datetime.now().strftime(DATE_FORMAT)


def normalize_directory(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expandvars(path))))


def display_directory(path: str) -> str:
    return os.path.normpath(os.path.abspath(os.path.expandvars(path)))


def load_fim_directories() -> list[str]:
    directories = list(MONITORED_DIRECTORIES)
    directory_file = FIM_DIRECTORIES_FILE if FIM_DIRECTORIES_FILE.exists() else LEGACY_FIM_DIRECTORIES_FILE
    try:
        with open(directory_file, "r", encoding="utf-8") as handle:
            saved = json.load(handle).get("directories", [])
        known_directories = {normalize_directory(item) for item in directories}
        for directory in saved:
            normalized = normalize_directory(directory)
            if normalized not in known_directories:
                directories.append(directory)
                known_directories.add(normalized)
    except (OSError, json.JSONDecodeError):
        pass
    return directories


def save_fim_directories(directories: list[str]) -> None:
    _write_json_atomic(FIM_DIRECTORIES_FILE, {"directories": directories})


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


def take_file_snapshot(
    directories: list[str] | None = None,
    previous_snapshot: dict | None = None,
    force_full_hash: bool = False,
) -> dict:
    directories = directories if directories is not None else load_fim_directories()
    previous_files = (previous_snapshot or {}).get("files", {})
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
                    previous_record = previous_files.get(absolute_path)
                    reuse_hash = (
                        not force_full_hash
                        and previous_record
                        and previous_record.get("size") == stat.st_size
                        and previous_record.get("modified") == stat.st_mtime_ns
                        and previous_record.get("sha256")
                    )
                    files[absolute_path] = {
                        "size": stat.st_size,
                        "modified": stat.st_mtime_ns,
                        "sha256": previous_record["sha256"] if reuse_hash else _hash_file(path),
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
    created_at = _timestamp()
    baseline = {
        "created_at": created_at,
        "directories": directories,
        "snapshot": snapshot,
    }
    runtime_state = {
        "updated_at": created_at,
        "directories": directories,
        "reference_snapshot": snapshot,
        "original_hashes": {
            file_path: record.get("sha256", "")
            for file_path, record in snapshot.get("files", {}).items()
        },
    }
    try:
        _write_json_atomic(BASELINE_FILE_FIM, baseline)
        _write_json_atomic(STATE_FILE_FIM, runtime_state)
        return f"Baseline saved at {created_at}"
    except OSError as error:
        return f"Failed to save FIM baseline: {error}"


def _load_json_file(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _load_baseline_data() -> dict | None:
    baseline_file = BASELINE_FILE_FIM if BASELINE_FILE_FIM.exists() else LEGACY_BASELINE_FILE_FIM
    data = _load_json_file(baseline_file)
    if not data:
        return None

    # Support the previous combined baseline/reference file format.
    snapshot = data.get("snapshot") or data.get("baseline_snapshot") or {}
    return {
        "created_at": data.get("created_at"),
        "directories": data.get("directories", load_fim_directories()),
        "snapshot": snapshot,
    }


def load_fim_state() -> dict | None:
    baseline = _load_baseline_data()
    runtime = _load_json_file(STATE_FILE_FIM)
    if runtime is None:
        legacy = _load_json_file(LEGACY_BASELINE_FILE_FIM)
        runtime = legacy if legacy and legacy.get("reference_snapshot") else None
    if baseline is None and runtime is None:
        return None

    baseline = baseline or {"created_at": None, "directories": load_fim_directories(), "snapshot": {}}
    runtime = runtime or {}
    return {
        "created_at": baseline.get("created_at"),
        "directories": runtime.get("directories", baseline.get("directories", load_fim_directories())),
        "baseline_snapshot": baseline.get("snapshot", {}),
        "reference_snapshot": runtime.get("reference_snapshot", baseline.get("snapshot", {})),
        "original_hashes": runtime.get("original_hashes", {}),
    }


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

    changes = _coalesce_renames(changes)

    if advance_reference:
        reference.clear()
        reference.update({**current, "files": effective_files})
    return changes


def _coalesce_renames(changes: list[dict]) -> list[dict]:
    """Pair same-hash additions and deletions as one rename event."""
    added_by_hash = {}
    deleted_by_hash = {}
    for index, change in enumerate(changes):
        if change["change_type"] == "ADDED" and change.get("new_hash"):
            added_by_hash.setdefault(change["new_hash"], []).append(index)
        elif change["change_type"] == "DELETED" and change.get("old_hash"):
            deleted_by_hash.setdefault(change["old_hash"], []).append(index)

    consumed = set()
    rename_events = []
    for file_hash, added_indexes in added_by_hash.items():
        deleted_indexes = deleted_by_hash.get(file_hash, [])
        for added_index, deleted_index in zip(added_indexes, deleted_indexes):
            added = changes[added_index]
            deleted = changes[deleted_index]
            consumed.update((added_index, deleted_index))
            rename_events.append({
                "timestamp": added["timestamp"],
                "severity": "HIGH",
                "change_type": "RENAMED",
                "file_path": added["file_path"],
                "old_path": deleted["file_path"],
                "old_hash": file_hash,
                "new_hash": file_hash,
                "details": f"File renamed from {deleted['file_path']} to {added['file_path']}",
            })

    remaining = [change for index, change in enumerate(changes) if index not in consumed]
    return sorted(remaining + rename_events, key=lambda change: change["file_path"])


def persist_reference(state: dict) -> None:
    runtime_state = {
        "updated_at": _timestamp(),
        "directories": state.get("directories", []),
        "reference_snapshot": state.get("reference_snapshot", {}),
        "original_hashes": state.get("original_hashes", {}),
    }
    _write_json_atomic(STATE_FILE_FIM, runtime_state)
