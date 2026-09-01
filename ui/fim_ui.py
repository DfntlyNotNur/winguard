from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config import (
    BASELINE_MISSING,
    BASELINE_OUTDATED,
    BASELINE_READY,
    FIM_FULL_REHASH_INTERVAL_SCANS,
    FIM_FOLDER_ADDED_MESSAGE,
    FIM_FOLDER_REMOVED_MESSAGE,
    FIM_MONITORING_PAUSED_MESSAGE,
    MAX_VISIBLE_ROWS,
    POLLING_INTERVAL_MS,
)
from ui.dashboard_ui import (
    DeselectableTable,
    confirm_clear_log,
    refresh_widget_style,
    show_no_baselines_warning,
)
from fim_monitor import (
    compare_file_snapshots, display_directory, get_fim_baseline_timestamp,
    load_fim_directories, load_fim_state, normalize_directory, persist_reference,
    save_fim_baseline, save_fim_directories, take_file_snapshot,
)
from logger import clear_log as clear_persisted_log, write_fim_log, write_info_log


class FimScanWorker(QObject):
    """Run filesystem scans away from the PyQt event loop."""

    finished = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    @pyqtSlot(object, object, bool, int)
    def scan(self, directories, previous_snapshot, force_full_hash, generation):
        try:
            snapshot = take_file_snapshot(directories, previous_snapshot, force_full_hash)
            self.finished.emit(generation, snapshot)
        except Exception as error:  # Surface scan failures without killing the worker.
            self.failed.emit(generation, str(error))


class FileIntegrityTab(QWidget):
    CONFIRMATION_SCANS = 2
    DETAILS_HASH_COLUMN_WIDTH = 220
    scan_requested = pyqtSignal(object, object, bool, int)

    def __init__(self, status_callback, dashboard_callback=None):
        super().__init__()
        self.status_callback = status_callback
        self.dashboard_callback = dashboard_callback
        self.directories = load_fim_directories()
        self.state = load_fim_state()
        saved_directories = {normalize_directory(item) for item in (self.state or {}).get("directories", [])}
        current_directories = {normalize_directory(item) for item in self.directories}
        self.baseline_invalid = bool(self.state and saved_directories != current_directories)
        self.original_hashes = dict((self.state or {}).get("original_hashes", {}))
        for file_path, record in ((self.state or {}).get("baseline_snapshot", {}).get("files", {})).items():
            self.original_hashes.setdefault(file_path, record.get("sha256", ""))
        self.pending_changes = {}
        self.total_changes = {"ADDED": 0, "MODIFIED": 0, "DELETED": 0, "RENAMED": 0}
        self._scan_count = 0
        self._scan_generation = 0
        self._scan_busy = False
        self._shutdown_started = False
        self._last_directory_overview = None

        self._scan_thread = QThread(self)
        self._scan_worker = FimScanWorker()
        self._scan_worker.moveToThread(self._scan_thread)
        self.scan_requested.connect(self._scan_worker.scan)
        self._scan_worker.finished.connect(self._handle_scan_result)
        self._scan_worker.failed.connect(self._handle_scan_error)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.start()

        layout = QVBoxLayout(self)
        self.lbl_baseline = QLabel()
        layout.addWidget(self.lbl_baseline)

        controls = QHBoxLayout()
        self.btn_baseline = QPushButton("Create Baseline")
        self.btn_baseline.setObjectName("secondaryButton")
        self.btn_start = QPushButton("Start Monitoring")
        self.btn_start.setObjectName("primaryButton")
        self.btn_stop = QPushButton("Stop Monitoring")
        self.btn_add = QPushButton("Add Folder")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_clear_alerts = QPushButton("Clear Alerts")
        self.btn_more = QToolButton()
        self.btn_more.setObjectName("overflowButton")
        self.btn_more.setText("...")
        self.btn_more.setToolTip("More actions")
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        clear_log_action = menu.addAction("Clear Log")
        clear_log_action.triggered.connect(self.clear_log)
        self.btn_more.setMenu(menu)
        self.btn_stop.setEnabled(False)
        for button in (
            self.btn_baseline,
            self.btn_start,
            self.btn_stop,
            self.btn_add,
            self.btn_remove,
            self.btn_clear_alerts,
            self.btn_more,
        ):
            controls.addWidget(button)
        layout.addLayout(controls)

        layout.addWidget(QLabel("Monitored Directories"))
        self.directory_table = DeselectableTable(0, 4)
        self.directory_table.setHorizontalHeaderLabels(["Directory Path", "Status", "Baseline Files", "Current Files"])
        self.directory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.directory_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.directory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.directory_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.directory_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.directory_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.directory_table)

        layout.addWidget(QLabel("Detected File Changes"))
        self.change_table = DeselectableTable(0, 5)
        self.change_table.setHorizontalHeaderLabels(["Timestamp", "Change Type", "File Path", "Details", "SHA-256"])
        for column in (0, 1):
            self.change_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.change_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.change_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.change_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._set_equal_details_hash_width()
        self.change_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.change_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.change_table.cellClicked.connect(self._show_hash_details)
        layout.addWidget(self.change_table)

        self.lbl_last_scan = QLabel("Last file scan: -")
        layout.addWidget(self.lbl_last_scan)
        self.timer = QTimer(self)
        self.timer.setInterval(POLLING_INTERVAL_MS)
        self.timer.timeout.connect(self.run_scan)
        self.btn_baseline.clicked.connect(lambda: self.create_baseline())
        self.btn_start.clicked.connect(lambda: self.start_monitoring())
        self.btn_stop.clicked.connect(self.stop_monitoring)
        self.btn_add.clicked.connect(self.add_folder)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear_alerts.clicked.connect(self.clear_alerts)
        self.baseline_effect = QGraphicsOpacityEffect(self.btn_baseline)
        self.baseline_effect.setOpacity(1.0)
        self.btn_baseline.setGraphicsEffect(self.baseline_effect)
        self.baseline_pulse = QPropertyAnimation(self.baseline_effect, b"opacity", self)
        self.baseline_pulse.setDuration(1100)
        self.baseline_pulse.setStartValue(0.55)
        self.baseline_pulse.setKeyValueAt(0.5, 1.0)
        self.baseline_pulse.setEndValue(0.55)
        self.baseline_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.baseline_pulse.setLoopCount(-1)
        if self.baseline_invalid:
            self._start_baseline_alert()
        self._refresh_baseline_label()
        self._refresh_directory_table()

    def create_baseline(self, notify=True):
        snapshot = take_file_snapshot(self.directories)
        message = save_fim_baseline(snapshot, self.directories)
        self.state = load_fim_state()
        if self.state is None:
            raise OSError(message)
        self.baseline_invalid = False
        self.pending_changes.clear()
        self.original_hashes = {
            file_path: record.get("sha256", "")
            for file_path, record in snapshot.get("files", {}).items()
        }
        self.state["original_hashes"] = self.original_hashes
        persist_reference(self.state)
        self._stop_baseline_alert()
        self._refresh_baseline_label()
        self._refresh_directory_table(snapshot)
        write_info_log("FIM baseline created.")
        self.status_callback("FIM baseline ready.")
        if notify:
            QMessageBox.information(self, "FIM Baseline Created", message)

    def can_start_monitoring(self):
        return self.get_monitoring_readiness() == BASELINE_READY

    def get_monitoring_readiness(self):
        self.state = self.state or load_fim_state()
        if not self.state:
            return BASELINE_MISSING
        saved = {normalize_directory(item) for item in self.state.get("directories", [])}
        current = {normalize_directory(item) for item in self.directories}
        if self.baseline_invalid or saved != current:
            return BASELINE_OUTDATED
        return BASELINE_READY

    def start_monitoring(self, notify=True):
        readiness = self.get_monitoring_readiness()
        if readiness == BASELINE_MISSING:
            if notify:
                show_no_baselines_warning(self)
            return False
        if readiness == BASELINE_OUTDATED:
            if notify:
                QMessageBox.warning(self, "Baseline Outdated", "Create a new FIM baseline before starting monitoring.")
            return False
        self.pending_changes.clear()
        self._scan_count = 0
        self._scan_generation += 1
        self.timer.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_baseline.setEnabled(False)
        write_info_log("FIM monitoring started.")
        self.status_callback("FIM monitoring active...")
        self._send_dashboard("status", "Active")
        return True

    def stop_monitoring(self):
        was_active = self.timer.isActive() or self._scan_busy
        self.timer.stop()
        self._scan_generation += 1
        self._stop_baseline_alert()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_baseline.setEnabled(True)
        self.pending_changes.clear()
        save_error = None
        if self.state is not None:
            try:
                persist_reference(self.state)
            except OSError as error:
                save_error = f"FIM state save failed: {error}"
        if was_active:
            write_info_log("FIM monitoring stopped.")
        self.status_callback(save_error or "FIM monitoring stopped.")
        self._send_dashboard("status", "Stopped")

    def run_scan(self):
        if not self.state or self._scan_busy:
            return
        self._scan_busy = True
        self._scan_count += 1
        force_full_hash = self._scan_count % FIM_FULL_REHASH_INTERVAL_SCANS == 1
        self.scan_requested.emit(
            list(self.directories),
            self.state["reference_snapshot"],
            force_full_hash,
            self._scan_generation,
        )

    def _handle_scan_result(self, generation, current):
        if generation != self._scan_generation:
            self._scan_busy = False
            return

        try:
            reference = self.state["reference_snapshot"]
            raw_changes = compare_file_snapshots(reference, current, advance_reference=False)
            confirmed = self._confirm_stable_changes(raw_changes)
            self._advance_reference(reference, current, confirmed)
            scan_time = current.get("scanned_at", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            self.lbl_last_scan.setText(f"Last file scan: {scan_time}  |  Changes detected: {len(confirmed)}")
            for change in confirmed:
                self._add_change_row(change)
                write_fim_log(change)
                self.total_changes[change["change_type"]] += 1
            if confirmed:
                persist_reference(self.state)
            self._refresh_directory_table(current)
            self._send_dashboard("scan", scan_time, confirmed)
            self.status_callback(
                f"[ALERT] {len(confirmed)} file change(s) detected!"
                if confirmed else "FIM scan complete. No changes detected."
            )
        except OSError as error:
            self.status_callback(f"FIM state update failed: {error}")
        finally:
            self._scan_busy = False

    def _handle_scan_error(self, generation, message):
        if generation == self._scan_generation:
            self.status_callback(f"FIM scan failed: {message}")
        self._scan_busy = False

    def shutdown(self):
        """Stop the worker thread before the main window is destroyed."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self.stop_monitoring()
        self._scan_thread.quit()
        self._scan_thread.wait()

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
            pending_change = self.pending_changes[path]["change"]
            if pending_change["change_type"] == "RENAMED":
                old_path = pending_change.get("old_path")
                if old_path in old_files:
                    next_files[old_path] = old_files[old_path]
                next_files.pop(path, None)
                continue
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
            was_active = self.timer.isActive() or self._scan_busy
            if was_active:
                self.stop_monitoring()
            self.directories.append(folder)
            save_fim_directories(self.directories)
            self.baseline_invalid = True
            self._start_baseline_alert()
            self._refresh_baseline_label()
            self._refresh_directory_table()
            self.status_callback(
                FIM_MONITORING_PAUSED_MESSAGE
                if was_active
                else FIM_FOLDER_ADDED_MESSAGE
            )

    def remove_selected(self):
        row = self.directory_table.currentRow()
        if 0 <= row < len(self.directories):
            was_active = self.timer.isActive() or self._scan_busy
            if was_active:
                self.stop_monitoring()
            self.directories.pop(row)
            save_fim_directories(self.directories)
            self.baseline_invalid = True
            self._start_baseline_alert()
            self._refresh_baseline_label()
            self._refresh_directory_table()
            self.status_callback(
                FIM_MONITORING_PAUSED_MESSAGE
                if was_active
                else FIM_FOLDER_REMOVED_MESSAGE
            )

    def clear_alerts(self):
        self.change_table.setRowCount(0)
        self.status_callback("FIM alerts cleared.")

    def clear_log(self):
        if not confirm_clear_log(self):
            return
        clear_persisted_log()
        self.status_callback("Saved WinGuard log cleared.")

    def _add_change_row(self, change):
        self._remember_original_hash(change)
        if self.change_table.rowCount() >= MAX_VISIBLE_ROWS:
            self.change_table.removeRow(0)
        row = self.change_table.rowCount()
        self.change_table.insertRow(row)
        hash_value = change.get("new_hash") or change.get("old_hash")
        values = [
            change["timestamp"],
            change["change_type"],
            change["file_path"],
            self._display_details(change),
            self._short_hash(hash_value),
        ]
        colors = {
            "ADDED": "#FFFFFF",    # event color.
            "MODIFIED": "#2196F3",
            "DELETED": "#BA68C8",
            "RENAMED": "#FFFFFF",
        }
        color = QColor(colors.get(change["change_type"], "#FFFFFF"))
        color.setAlpha(60)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setBackground(color)
            font = item.font()
            font.setBold(False)
            item.setFont(font)
            self.change_table.setItem(row, column, item)
        self.change_table.item(row, 2).setToolTip(change["file_path"])
        self.change_table.item(row, 3).setToolTip(change["details"])
        self.change_table.item(row, 4).setToolTip(self._hash_tooltip(change))
        self.change_table.scrollToBottom()

    @staticmethod
    def _display_details(change):
        if change["change_type"] == "RENAMED":
            old_name = Path(change.get("old_path", "")).name
            new_name = Path(change["file_path"]).name
            return f"File renamed from {old_name} to {new_name}"
        return change["details"]

    @staticmethod
    def _short_hash(hash_value, visible_characters=16):
        if not hash_value:
            return "(none)"
        return f"{hash_value[:visible_characters]}..."

    def _set_equal_details_hash_width(self):
        header = self.change_table.horizontalHeader()
        width = self.DETAILS_HASH_COLUMN_WIDTH
        header.resizeSection(3, width)
        header.resizeSection(4, width)

    def _hash_tooltip(self, change):
        """Build hash details appropriate for the file's complete change history."""
        file_path = change["file_path"]
        file_name = Path(file_path).name
        change_type = change["change_type"]

        if change_type == "ADDED":
            return f"File Name: {file_name}\nSHA-256: {change.get('new_hash') or '(none)'}"

        if change_type == "RENAMED":
            return (
                f"File Name: {file_name}\n"
                f"Renamed From: {Path(change.get('old_path', '')).name}\n"
                f"SHA-256: {change.get('new_hash') or change.get('old_hash') or '(none)'}"
            )

        if change_type == "MODIFIED":
            return (
                f"File Name: {file_name}\n"
                f"Original SHA-256: {change.get('old_hash') or '(none)'}\n"
                f"New SHA-256: {change.get('new_hash') or '(none)'}"
            )

        # A deletion normally contains the latest known hash. Compare it with
        # the original baseline to detect whether the file was modified first.
        original_hash = self.original_hashes.get(file_path)
        deleted_hash = change.get("old_hash") or "(none)"
        if original_hash and original_hash != deleted_hash:
            return (
                f"File Name: {file_name}\n"
                f"Original SHA-256: {original_hash}\n"
                f"New SHA-256: {deleted_hash}"
            )
        return f"File Name: {file_name}\nSHA-256: {deleted_hash}"

    def _remember_original_hash(self, change):
        file_path = change["file_path"]
        if change["change_type"] == "ADDED":
            self.original_hashes.setdefault(file_path, change.get("new_hash", ""))
        elif change["change_type"] == "RENAMED":
            old_path = change.get("old_path")
            original_hash = self.original_hashes.pop(old_path, "") if old_path else ""
            self.original_hashes.setdefault(file_path, original_hash or change.get("new_hash", ""))
        elif change["change_type"] == "MODIFIED":
            self.original_hashes.setdefault(file_path, change.get("old_hash", ""))
        self.state["original_hashes"] = self.original_hashes

    def _refresh_baseline_label(self):
        timestamp = get_fim_baseline_timestamp()
        if timestamp and not self.baseline_invalid:
            self.lbl_baseline.setText(f"Baseline created: {timestamp}")
            self.lbl_baseline.setObjectName("baselineLabel")
        elif timestamp:
            self.lbl_baseline.setText(f"Baseline created: {timestamp} (outdated)")
            self.lbl_baseline.setObjectName("warningLabel")
        else:
            self.lbl_baseline.setText("Baseline: Not created yet.")
            self.lbl_baseline.setObjectName("secondaryLabel")
        refresh_widget_style(self.lbl_baseline)
        self._send_dashboard("baseline", timestamp)

    def _refresh_directory_table(self, snapshot=None):
        selected_path = None
        selected_row = self.directory_table.currentRow()
        if selected_row >= 0 and self.directory_table.item(selected_row, 0):
            selected_path = self.directory_table.item(selected_row, 0).text()

        overview = self.get_directory_overview(snapshot)
        if overview == self._last_directory_overview:
            return
        self._last_directory_overview = overview
        self.directory_table.setRowCount(0)
        for directory in overview:
            row = self.directory_table.rowCount()
            self.directory_table.insertRow(row)
            values = [
                directory["path"],
                directory["status"],
                str(directory["baseline"]),
                str(directory["current"]),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                font = item.font()
                font.setBold(False)
                item.setFont(font)
                if column == 0:
                    item.setToolTip(directory["path"])
                elif column == 1 and directory["status"] == "Active":
                    theme_color = "#4ade80" if QApplication.instance().property("darkTheme") else "#16834b"
                    item.setForeground(QColor(theme_color))
                self.directory_table.setItem(row, column, item)
            if selected_path == values[0]:
                self.directory_table.selectRow(row)
        self._send_dashboard("directories", overview)

    def get_directory_overview(self, snapshot=None):
        baseline_records = {
            normalize_directory(item["path"]): item
            for item in ((self.state or {}).get("baseline_snapshot", {}).get("directories", []))
        }
        if snapshot is None and self.state:
            snapshot = self.state.get("reference_snapshot", {})
        current_records = {
            normalize_directory(item["path"]): item
            for item in (snapshot or {}).get("directories", [])
        }
        overview = []
        for directory in self.directories:
            path = display_directory(directory)
            key = normalize_directory(directory)
            overview.append({
                "path": path,
                "status": "Active" if Path(path).is_dir() else "Unavailable",
                "baseline": baseline_records.get(key, {}).get("file_count", "-"),
                "current": current_records.get(key, {}).get("file_count", "-"),
            })
        return overview

    def _show_hash_details(self, row, column):
        if column == 4:
            item = self.change_table.item(row, column)
            if item and item.toolTip():
                QMessageBox.information(self, "SHA-256 Details", item.toolTip())

    def _start_baseline_alert(self):
        self.btn_baseline.setStyleSheet(
            "QPushButton { background-color: #F8FAFC; border: 1px solid #2563EB; "
            "color: #1D4ED8; font-weight: 600; }"
        )
        self.baseline_pulse.start()

    def _stop_baseline_alert(self):
        self.baseline_pulse.stop()
        self.baseline_effect.setOpacity(1.0)
        self.btn_baseline.setStyleSheet("")

    def _send_dashboard(self, event_type, *args):
        if self.dashboard_callback:
            self.dashboard_callback(event_type, *args)
