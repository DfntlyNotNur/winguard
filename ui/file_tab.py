from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from config import LOG_FILE, POLLING_INTERVAL_MS, SEVERITY_COLORS
from fim_monitor import (
    compare_file_snapshots, display_directory, get_fim_baseline_timestamp,
    load_fim_directories, load_fim_state, normalize_directory, persist_reference,
    save_fim_baseline, save_fim_directories, take_file_snapshot,
)
from logger import write_info_log


class FileIntegrityTab(QWidget):
    CONFIRMATION_SCANS = 2

    def __init__(self, status_callback, dashboard_callback=None):
        super().__init__()
        self.status_callback = status_callback
        self.dashboard_callback = dashboard_callback
        self.directories = load_fim_directories()
        self.state = None
        self.pending_changes = {}
        self.total_changes = {"ADDED": 0, "MODIFIED": 0, "DELETED": 0}

        layout = QVBoxLayout(self)
        self.lbl_baseline = QLabel()
        layout.addWidget(self.lbl_baseline)

        controls = QHBoxLayout()
        self.btn_baseline = QPushButton("Create Baseline")
        self.btn_start = QPushButton("Start Monitoring")
        self.btn_stop = QPushButton("Stop Monitoring")
        self.btn_add = QPushButton("Add Folder")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_clear = QPushButton("Clear Log")
        self.btn_stop.setEnabled(False)
        for button in (self.btn_baseline, self.btn_start, self.btn_stop, self.btn_add, self.btn_remove, self.btn_clear):
            controls.addWidget(button)
        layout.addLayout(controls)

        self.lbl_summary = QLabel("Total Changes: 0 | Added: 0 | Modified: 0 | Deleted: 0")
        layout.addWidget(self.lbl_summary)
        layout.addWidget(QLabel("Monitored Directories"))
        self.directory_table = QTableWidget(0, 3)
        self.directory_table.setHorizontalHeaderLabels(["Directory Path", "Status", "Baseline Files"])
        self.directory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.directory_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.directory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.directory_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.directory_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.directory_table)

        layout.addWidget(QLabel("Detected File Changes"))
        self.change_table = QTableWidget(0, 6)
        self.change_table.setHorizontalHeaderLabels(["Timestamp", "Severity", "Change Type", "File Path", "Details", "SHA-256"])
        for column in (0, 1, 2, 5):
            self.change_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.change_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.change_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.change_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.change_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.change_table)

        self.lbl_last_scan = QLabel("Last file scan: -")
        layout.addWidget(self.lbl_last_scan)
        self.timer = QTimer(self)
        self.timer.setInterval(POLLING_INTERVAL_MS)
        self.timer.timeout.connect(self.run_scan)
        self.btn_baseline.clicked.connect(self.create_baseline)
        self.btn_start.clicked.connect(self.start_monitoring)
        self.btn_stop.clicked.connect(self.stop_monitoring)
        self.btn_add.clicked.connect(self.add_folder)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_log)
        self._refresh_baseline_label()
        self._refresh_directory_table()

    def create_baseline(self):
        snapshot = take_file_snapshot(self.directories)
        message = save_fim_baseline(snapshot, self.directories)
        self.state = load_fim_state()
        self.pending_changes.clear()
        self._refresh_baseline_label()
        self._refresh_directory_table(snapshot)
        write_info_log("FIM baseline created.")
        self.status_callback("FIM baseline ready.")
        QMessageBox.information(self, "FIM Baseline Created", message)

    def start_monitoring(self):
        self.state = self.state or load_fim_state()
        if not self.state:
            QMessageBox.warning(self, "No Baseline", "Create a FIM baseline before starting monitoring.")
            return
        saved = {normalize_directory(item) for item in self.state.get("directories", [])}
        current = {normalize_directory(item) for item in self.directories}
        if saved != current:
            QMessageBox.warning(self, "Baseline Outdated", "The monitored folders changed. Create a new baseline before monitoring.")
            return
        self.pending_changes.clear()
        self.timer.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_baseline.setEnabled(False)
        write_info_log("FIM monitoring started.")
        self.status_callback("FIM monitoring active...")
        self._send_dashboard("status", "Active")

    def stop_monitoring(self):
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_baseline.setEnabled(True)
        self.pending_changes.clear()
        write_info_log("FIM monitoring stopped.")
        self.status_callback("FIM monitoring stopped.")
        self._send_dashboard("status", "Stopped")

    def run_scan(self):
        if not self.state:
            return
        current = take_file_snapshot(self.directories)
        reference = self.state["reference_snapshot"]
        raw_changes = compare_file_snapshots(reference, current, advance_reference=False)
        confirmed = self._confirm_stable_changes(raw_changes)
        self._advance_reference(reference, current, confirmed)
        persist_reference(self.state)
        scan_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.lbl_last_scan.setText(f"Last file scan: {scan_time}  |  Changes detected: {len(confirmed)}")
        for change in confirmed:
            self._add_change_row(change)
            self._write_file_log(change)
            self.total_changes[change["change_type"]] += 1
        self._refresh_summary()
        self._refresh_directory_table(current)
        self._send_dashboard("scan", scan_time, confirmed)
        self.status_callback(f"[ALERT] {len(confirmed)} file change(s) detected!" if confirmed else "FIM scan complete. No changes detected.")

    def _confirm_stable_changes(self, changes):
        current = {}
        confirmed = []
        for change in changes:
            path = change["file_path"]
            signature = (change["change_type"], change.get("old_hash", ""), change.get("new_hash", ""))
            previous = self.pending_changes.get(path)
            count = previous["count"] + 1 if previous and previous["signature"] == signature else 1
            current[path] = {"signature": signature, "count": count, "change": change}
            if count >= self.CONFIRMATION_SCANS:
                confirmed.append(change)
        self.pending_changes = {path: item for path, item in current.items() if item["count"] < self.CONFIRMATION_SCANS}
        return confirmed

    def _advance_reference(self, reference, current, confirmed):
        """Advance stable paths while keeping unconfirmed paths pending."""
        old_files = reference.get("files", {})
        next_files = dict(current.get("files", {}))
        confirmed_paths = {change["file_path"] for change in confirmed}
        pending_paths = set(self.pending_changes)

        for path in pending_paths:
            if path in old_files:
                next_files[path] = old_files[path]
            elif path not in confirmed_paths:
                next_files.pop(path, None)

        if not current.get("complete", True):
            for path, record in old_files.items():
                next_files.setdefault(path, record)

        reference.clear()
        reference.update({**current, "files": next_files})

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Monitor")
        if folder and normalize_directory(folder) not in {normalize_directory(item) for item in self.directories}:
            self.directories.append(folder)
            save_fim_directories(self.directories)
            self.state = None
            self._refresh_directory_table()
            self.status_callback("Folder added. Create a new FIM baseline before monitoring.")

    def remove_selected(self):
        row = self.directory_table.currentRow()
        if 0 <= row < len(self.directories):
            self.directories.pop(row)
            save_fim_directories(self.directories)
            self.state = None
            self._refresh_directory_table()
            self.status_callback("Folder removed. Create a new FIM baseline before monitoring.")

    def clear_log(self):
        self.change_table.setRowCount(0)
        self.status_callback("FIM change log cleared.")

    def _add_change_row(self, change):
        row = self.change_table.rowCount()
        self.change_table.insertRow(row)
        hash_value = change.get("new_hash") or change.get("old_hash")
        values = [change["timestamp"], change["severity"], change["change_type"], change["file_path"], change["details"], hash_value]
        color = QColor(SEVERITY_COLORS.get(change["severity"], "#FFFFFF"))
        color.setAlpha(60)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setBackground(color)
            self.change_table.setItem(row, column, item)
        self.change_table.scrollToBottom()

    def _write_file_log(self, change):
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as handle:
                handle.write(f"[{change['timestamp']}] [{change['severity']}] [{change['change_type']}] File: {change['file_path']} | {change['details']} | Old SHA-256: {change['old_hash']} | New SHA-256: {change['new_hash']}\n")
        except OSError:
            pass

    def _refresh_baseline_label(self):
        timestamp = get_fim_baseline_timestamp()
        if timestamp:
            self.lbl_baseline.setText(f"Baseline created: {timestamp}")
            self.lbl_baseline.setStyleSheet("color: green; font-size: 12px;")
        else:
            self.lbl_baseline.setText("Baseline: Not created yet.")
            self.lbl_baseline.setStyleSheet("color: gray; font-size: 12px;")

    def _refresh_directory_table(self, snapshot=None):
        records = {normalize_directory(item["path"]): item for item in (snapshot or {}).get("directories", [])}
        self.directory_table.setRowCount(0)
        for directory in self.directories:
            record = records.get(normalize_directory(directory), {})
            row = self.directory_table.rowCount()
            self.directory_table.insertRow(row)
            values = [display_directory(directory), "Active" if record.get("exists", True) else "Unavailable", str(record.get("file_count", "-"))]
            for column, value in enumerate(values):
                self.directory_table.setItem(row, column, QTableWidgetItem(value))

    def _refresh_summary(self):
        total = sum(self.total_changes.values())
        self.lbl_summary.setText(f"Total Changes: {total} | Added: {self.total_changes['ADDED']} | Modified: {self.total_changes['MODIFIED']} | Deleted: {self.total_changes['DELETED']}")

    def _send_dashboard(self, event_type, *args):
        if self.dashboard_callback:
            self.dashboard_callback(event_type, *args)
