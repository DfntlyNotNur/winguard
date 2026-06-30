# config.py
# WinGuard - Configuration File
# Defines all monitored registry keys, paths, and application settings.

import winreg

# ==============================================================================
# MONITORED REGISTRY KEYS
# Each entry is a tuple: (hive_constant, hive_name_string, subkey_path, severity)
# Severity: "HIGH", "MEDIUM", "LOW"
# ==============================================================================

MONITORED_REGISTRY_KEYS = [
    (
        winreg.HKEY_CURRENT_USER,
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        "HIGH"
    ),
    (
        winreg.HKEY_LOCAL_MACHINE,
        "HKLM",
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        "HIGH"
    ),
    (
        winreg.HKEY_LOCAL_MACHINE,
        "HKLM",
        r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
        "HIGH"
    ),
    (
        winreg.HKEY_CURRENT_USER,
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
        "HIGH"
    ),
    (
        winreg.HKEY_LOCAL_MACHINE,
        "HKLM",
        r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        "MEDIUM"
    ),
    (
        winreg.HKEY_CURRENT_USER,
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        "MEDIUM"
    ),
    (
        winreg.HKEY_LOCAL_MACHINE,
        "HKLM",
        r"SYSTEM\CurrentControlSet\Services",
        "HIGH"
    ),
    (
        winreg.HKEY_CURRENT_USER,
        "HKCU",
        r"Software\WinGuardTest",
        "TESTING"
    ),
]

# ==============================================================================
# MONITORED FILE SYSTEM PATHS (for future FIM module)
# ==============================================================================

MONITORED_DIRECTORIES = [
    r"C:\Users\Default\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup",
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup",
]

# ==============================================================================
# APPLICATION SETTINGS
# ==============================================================================

# Polling interval in milliseconds (30 seconds default)
POLLING_INTERVAL_MS = 5000

# Baseline file path (stored as JSON)
BASELINE_FILE_REGISTRY = "winguard_registry_baseline.json"
BASELINE_FILE_FIM      = "winguard_fim_baseline.json"

# Log file path
LOG_FILE = "winguard_log.txt"

# Severity color mapping (used in UI)
SEVERITY_COLORS = {
    "HIGH":   "#FF4C4C",   # Red
    "MEDIUM": "#FFA500",   # Orange
    "LOW":    "#4CAF50",   # Green
    "INFO":   "#2196F3",   # Blue
}