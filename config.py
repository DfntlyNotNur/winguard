# WinGuard configuration
import os
import winreg

MONITORED_REGISTRY_KEYS = [
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "HIGH"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "HIGH"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HIGH"),
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HIGH"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "MEDIUM"),
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "MEDIUM"),
    (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"SYSTEM\CurrentControlSet\Services", "HIGH"),
    (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\WinGuardTest", "TESTING"),
]

# Environment-based paths work for any Windows user account.
MONITORED_DIRECTORIES = [
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup",
    r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup",
]

POLLING_INTERVAL_MS = 5000
BASELINE_FILE_REGISTRY = "winguard_registry_baseline.json"
BASELINE_FILE_FIM = "winguard_fim_baseline.json"
FIM_DIRECTORIES_FILE = "winguard_fim_directories.json"
LOG_FILE = "winguard_log.txt"

SEVERITY_COLORS = {
    "HIGH": "#FF4C4C",
    "MEDIUM": "#FFA500",
    "LOW": "#4CAF50",
    "INFO": "#2196F3",
}
