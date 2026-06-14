import psutil
from datetime import datetime


SUSPICIOUS_PATHS = [
    "\\temp\\",
    "\\tmp\\",
    "\\appdata\\local\\temp\\",
    "\\downloads\\",
    "\\public\\",
]


def get_all_processes():
    """
    Returns a list of currently running processes as dicts.
    Each dict contains pid, name, exe path, username, and start time.
    """
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'username', 'create_time']):
        try:
            info = proc.info
            create_time = datetime.fromtimestamp(info['create_time']).strftime("%Y-%m-%d %H:%M:%S") if info['create_time'] else "N/A"
            processes.append({
                'pid': info['pid'],
                'name': info['name'] or "N/A",
                'exe': info['exe'] or "N/A",
                'username': info['username'] or "N/A",
                'create_time': create_time,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def is_suspicious(exe_path: str) -> bool:
    """
    Checks if a process executable path matches any known suspicious locations.
    Returns True if suspicious, False otherwise.
    """
    if not exe_path or exe_path == "N/A":
        return False
    path_lower = exe_path.lower()
    return any(sus in path_lower for sus in SUSPICIOUS_PATHS)


def detect_new_processes(previous_pids: set, current_processes: list) -> list:
    """
    Compares current process list against a previous snapshot.
    Returns a list of newly spawned process dicts.
    """
    new_procs = []
    current_pids = {p['pid'] for p in current_processes}
    new_pids = current_pids - previous_pids
    for proc in current_processes:
        if proc['pid'] in new_pids:
            new_procs.append(proc)
    return new_procs


def detect_terminated_processes(previous_snapshot: list, current_processes: list) -> list:
    """
    Detects processes that existed in the previous snapshot but no longer exist.
    Returns a list of terminated process dicts.
    """
    current_pids = {p['pid'] for p in current_processes}
    terminated = [p for p in previous_snapshot if p['pid'] not in current_pids]
    return terminated