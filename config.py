# WinGuard configuration
import os
from pathlib import Path

import winreg

APP_DIRECTORY = Path(__file__).resolve().parent
LOGO_FILE = APP_DIRECTORY / "wgdt.png"

MONITORED_REGISTRY_KEYS = [
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "HIGH"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "HIGH"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HIGH"),
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HIGH"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "MEDIUM"),
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "MEDIUM"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"SYSTEM\CurrentControlSet\Services", "HIGH"),
]

# Environment-based paths work for any Windows user account.
MONITORED_DIRECTORIES = [
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup",
    r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup",
]

POLLING_INTERVAL_MS = 5000
DATE_FORMAT = "%d/%m/%Y %H:%M:%S"
FIM_MONITORING_PAUSED_MESSAGE = (
    "Monitoring paused. Create a new FIM baseline before restarting."
)
FIM_FOLDER_ADDED_MESSAGE = "Folder added. Create a new FIM baseline before monitoring."
FIM_FOLDER_REMOVED_MESSAGE = "Folder removed. Create a new FIM baseline before monitoring."
BASELINE_READY = "READY"
BASELINE_MISSING = "MISSING"
BASELINE_OUTDATED = "OUTDATED"

# Runtime data belongs in the user's writable profile, not beside the executable.
DATA_DIRECTORY = Path(
    os.environ.get("LOCALAPPDATA")
    or Path.home() / "AppData" / "Local"
) / "WinGuard"


def ensure_data_directory() -> None:
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)


try:
    ensure_data_directory()
except OSError:
    # Individual save operations will report the actual access error.
    pass


BASELINE_FILE_REGISTRY = DATA_DIRECTORY / "winguard_registry_baseline.json"
BASELINE_FILE_FIM = DATA_DIRECTORY / "winguard_fim_baseline.json"
STATE_FILE_FIM = DATA_DIRECTORY / "winguard_fim_state.json"
FIM_DIRECTORIES_FILE = DATA_DIRECTORY / "winguard_fim_directories.json"
LOG_FILE = DATA_DIRECTORY / "winguard_log.txt"

# Existing files from the pre-portable version remain readable for migration.
LEGACY_BASELINE_FILE_REGISTRY = Path("winguard_registry_baseline.json")
LEGACY_BASELINE_FILE_FIM = Path("winguard_fim_baseline.json")
LEGACY_FIM_DIRECTORIES_FILE = Path("winguard_fim_directories.json")
LEGACY_LOG_FILE = Path("winguard_log.txt")

FIM_FULL_REHASH_INTERVAL_SCANS = 24  # Two minutes at the five-second poll rate.
MAX_VISIBLE_ROWS = 300
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3

SEVERITY_COLORS = {
    "HIGH": "#FF4C4C",
    "MEDIUM": "#FFA500",
    "LOW": "#4CAF50",
    "INFO": "#2196F3",
}
