# main.py
# WinGuard - Main Entry Point
# Assembles the main window with tabbed UI.
# Registry monitoring is handled via QTimer polling.

import sys
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QStatusBar, QTabWidget, QHeaderView, QMessageBox,
    QGridLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from config import POLLING_INTERVAL_MS, SEVERITY_COLORS, MONITORED_REGISTRY_KEYS
from registry_monitor import (
    take_registry_snapshot,
    save_baseline,
    load_baseline,
    get_baseline_timestamp,
    compare_snapshots
)
from logger import write_log, write_info_log


# ==============================================================================
# REGISTRY TAB
# ==============================================================================

class RegistryTab(QWidget):
    def __init__(self, status_callback, dashboard_callback=None):
        super().__init__()

        # status_callback lets this tab update the main window's status bar
        self.status_callback = status_callback
        self.dashboard_callback = dashboard_callback
        self.baseline_snapshot = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Info bar (baseline timestamp) ---
        self.lbl_baseline_info = QLabel("Baseline: Not created yet.")
        self.lbl_baseline_info.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self.lbl_baseline_info)

        # --- Button row ---
        btn_layout = QHBoxLayout()

        self.btn_baseline = QPushButton("Create Baseline")
        self.btn_start = QPushButton("Start Monitoring")
        self.btn_stop = QPushButton("Stop Monitoring")
        self.btn_clear = QPushButton("Clear Log")

        self.btn_stop.setEnabled(False)

        btn_layout.addWidget(self.btn_baseline)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        # --- Change detection table ---
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Timestamp", "Severity", "Change Type", "Registry Key", "Value Name", "Details"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # --- Last scan label ---
        self.lbl_last_scan = QLabel("Last scan: -")
        self.lbl_last_scan.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.lbl_last_scan)

        # --- QTimer for polling ---
        self.timer = QTimer()
        self.timer.setInterval(POLLING_INTERVAL_MS)
        self.timer.timeout.connect(self.run_scan)

        # --- Button connections ---
        self.btn_baseline.clicked.connect(self.create_baseline)
        self.btn_start.clicked.connect(self.start_monitoring)
        self.btn_stop.clicked.connect(self.stop_monitoring)
        self.btn_clear.clicked.connect(self.clear_table)

        # --- Load existing baseline timestamp if available ---
        self._refresh_baseline_label()

    # --------------------------------------------------------------------------

    def create_baseline(self):
        self.status_callback("Creating registry baseline...")
        snapshot = take_registry_snapshot()
        msg = save_baseline(snapshot)
        self.baseline_snapshot = snapshot
        write_info_log("Registry baseline created.")
        self._refresh_baseline_label()
        self.status_callback("Registry baseline ready.")
        QMessageBox.information(self, "Baseline Created", msg)

    def start_monitoring(self):
        # Load baseline from file if not already in memory
        if self.baseline_snapshot is None:
            self.baseline_snapshot = load_baseline()

        if self.baseline_snapshot is None:
            QMessageBox.warning(
                self,
                "No Baseline",
                "No baseline found.\nPlease create a baseline before starting monitoring."
            )
            return

        self.timer.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_baseline.setEnabled(False)
        write_info_log("Registry monitoring started.")
        self.status_callback("Registry monitoring active...")
        self._update_dashboard("status", "Active")

    def stop_monitoring(self):
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_baseline.setEnabled(True)
        write_info_log("Registry monitoring stopped.")
        self.status_callback("Registry monitoring stopped.")
        self._update_dashboard("status", "Stopped")

    def run_scan(self):
        """Called by QTimer on every polling interval."""
        current_snapshot = take_registry_snapshot()
        changes = compare_snapshots(self.baseline_snapshot, current_snapshot)

        scan_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.lbl_last_scan.setText(f"Last scan: {scan_time}  |  Changes detected: {len(changes)}")
        self._update_dashboard("scan", scan_time, changes)

        if changes:
            for change in changes:
                self._add_change_row(change)
                write_log(change)
            self.status_callback(f"[ALERT] {len(changes)} change(s) detected in registry!")
        else:
            self.status_callback("Registry scan complete. No changes detected.")

    def clear_table(self):
        self.table.setRowCount(0)
        self.status_callback("Change log cleared.")

    # --------------------------------------------------------------------------

    def _add_change_row(self, change: dict):
        """Inserts one change entry into the table with severity color coding."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Build details string
        if change["change_type"] == "ADDED":
            details = f"New value: {change['new_data']}"
        elif change["change_type"] == "DELETED":
            details = f"Removed value: {change['old_data']}"
        else:
            details = f"{change['old_data']} -> {change['new_data']}"

        cells = [
            change["timestamp"],
            change["severity"],
            change["change_type"],
            change["key_path"],
            change["value_name"],
            details
        ]

        color_hex = SEVERITY_COLORS.get(change["severity"], "#FFFFFF")
        bg_color = QColor(color_hex)
        bg_color.setAlpha(60)  # Light tint so text stays readable

        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setBackground(bg_color)
            # Bold the severity and change type columns
            if col in (1, 2):
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.table.setItem(row, col, item)

        # Auto-scroll to latest entry
        self.table.scrollToBottom()

    def _refresh_baseline_label(self):
        ts = get_baseline_timestamp()
        if ts:
            self.lbl_baseline_info.setText(f"Baseline created: {ts}")
            self.lbl_baseline_info.setStyleSheet("color: green; font-size: 12px;")
        else:
            self.lbl_baseline_info.setText("Baseline: Not created yet.")
            self.lbl_baseline_info.setStyleSheet("color: gray; font-size: 12px;")

    def _update_dashboard(self, event_type: str, *args):
        if self.dashboard_callback:
            self.dashboard_callback(event_type, *args)


# ==============================================================================
# DASHBOARD TAB
# ==============================================================================

class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self.total_changes = 0
        self.change_type_counts = {"ADDED": 0, "MODIFIED": 0, "DELETED": 0}
        self.severity_counts = {}
        self.category_counts = self._build_initial_category_counts()

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Main Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 12px 0;")
        layout.addWidget(title)

        summary_grid = QGridLayout()
        layout.addLayout(summary_grid)

        self.lbl_registry_status = self._create_value_label("Stopped")
        self.lbl_fim_status = self._create_value_label("-- --")
        self.lbl_total_changes = self._create_value_label("0")
        self.lbl_last_scan = self._create_value_label("Not scanned yet")

        self._add_metric(summary_grid, 0, 0, "Registry Monitor", self.lbl_registry_status)
        self._add_metric(summary_grid, 0, 1, "File Integrity Monitor", self.lbl_fim_status)
        self._add_metric(summary_grid, 1, 0, "Total Registry Changes", self.lbl_total_changes)
        self._add_metric(summary_grid, 1, 1, "Last Registry Scan", self.lbl_last_scan)

        counts_grid = QGridLayout()
        layout.addLayout(counts_grid)

        self.lbl_added = self._create_value_label("0")
        self.lbl_modified = self._create_value_label("0")
        self.lbl_deleted = self._create_value_label("0")
        self.lbl_high = self._create_value_label("0")
        self.lbl_medium = self._create_value_label("0")
        self.lbl_low = self._create_value_label("0")
        self.lbl_other_severity = self._create_value_label("0")

        self._add_metric(counts_grid, 0, 0, "Added", self.lbl_added)
        self._add_metric(counts_grid, 0, 1, "Modified", self.lbl_modified)
        self._add_metric(counts_grid, 0, 2, "Deleted", self.lbl_deleted)
        self._add_metric(counts_grid, 1, 0, "High Severity", self.lbl_high)
        self._add_metric(counts_grid, 1, 1, "Medium Severity", self.lbl_medium)
        self._add_metric(counts_grid, 1, 2, "Low Severity", self.lbl_low)
        self._add_metric(counts_grid, 1, 3, "Other Severity", self.lbl_other_severity)

        self.category_table = QTableWidget()
        self.category_table.setColumnCount(2)
        self.category_table.setHorizontalHeaderLabels(["Registry Area", "Changes"])
        self.category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.category_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.category_table.setAlternatingRowColors(True)
        self.category_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.category_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.category_table)

        self.lbl_latest_alert = QLabel("Latest alert: None")
        self.lbl_latest_alert.setWordWrap(True)
        self.lbl_latest_alert.setStyleSheet("font-size: 12px; color: gray; padding: 8px 0;")
        layout.addWidget(self.lbl_latest_alert)

        layout.addStretch()
        self._refresh_category_table()

    def handle_registry_event(self, event_type: str, *args):
        if event_type == "status":
            self.lbl_registry_status.setText(args[0])
            return

        if event_type == "scan":
            scan_time, changes = args
            self.lbl_last_scan.setText(scan_time)
            self.record_registry_changes(changes)

    def record_registry_changes(self, changes: list[dict]):
        if not changes:
            return

        self.total_changes += len(changes)

        for change in changes:
            change_type = change.get("change_type", "UNKNOWN")
            severity = change.get("severity", "UNKNOWN")
            category = self._category_from_key(change.get("key_path", ""))

            self.change_type_counts[change_type] = self.change_type_counts.get(change_type, 0) + 1
            self.severity_counts[severity] = self.severity_counts.get(severity, 0) + 1
            self.category_counts[category] = self.category_counts.get(category, 0) + 1

        latest = changes[-1]
        self.lbl_latest_alert.setText(
            "Latest alert: "
            f"{latest.get('severity', 'UNKNOWN')} - "
            f"{latest.get('change_type', 'UNKNOWN')} in "
            f"{self._category_from_key(latest.get('key_path', ''))} "
            f"({latest.get('value_name', '')})"
        )

        self._refresh_summary_counts()
        self._refresh_category_table()

    def _add_metric(self, layout: QGridLayout, row: int, col: int, title: str, value_label: QLabel):
        box = QWidget()
        box_layout = QVBoxLayout()
        box.setLayout(box_layout)
        box.setStyleSheet(
            "QWidget { border: 1px solid #d0d0d0; border-radius: 6px; padding: 8px; }"
            "QLabel { border: none; padding: 0; }"
        )

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: gray;")
        box_layout.addWidget(title_label)
        box_layout.addWidget(value_label)

        layout.addWidget(box, row, col)

    def _create_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        return label

    def _refresh_summary_counts(self):
        self.lbl_total_changes.setText(str(self.total_changes))
        self.lbl_added.setText(str(self.change_type_counts.get("ADDED", 0)))
        self.lbl_modified.setText(str(self.change_type_counts.get("MODIFIED", 0)))
        self.lbl_deleted.setText(str(self.change_type_counts.get("DELETED", 0)))
        self.lbl_high.setText(str(self.severity_counts.get("HIGH", 0)))
        self.lbl_medium.setText(str(self.severity_counts.get("MEDIUM", 0)))
        self.lbl_low.setText(str(self.severity_counts.get("LOW", 0)))

        known_severity_total = (
            self.severity_counts.get("HIGH", 0)
            + self.severity_counts.get("MEDIUM", 0)
            + self.severity_counts.get("LOW", 0)
        )
        self.lbl_other_severity.setText(str(self.total_changes - known_severity_total))

    def _refresh_category_table(self):
        self.category_table.setRowCount(0)

        for category, count in sorted(self.category_counts.items()):
            row = self.category_table.rowCount()
            self.category_table.insertRow(row)
            self.category_table.setItem(row, 0, QTableWidgetItem(category))
            self.category_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def _build_initial_category_counts(self) -> dict:
        categories = {}
        for _, _, subkey, _ in MONITORED_REGISTRY_KEYS:
            category = self._category_from_key(subkey)
            categories[category] = 0
        return categories

    def _category_from_key(self, key_path: str) -> str:
        normalized = key_path.lower()

        if normalized.endswith(r"\run") or normalized == "run":
            return "Run"
        if normalized.endswith(r"\runonce") or normalized == "runonce":
            return "RunOnce"
        if r"policies\explorer" in normalized:
            return "Policies Explorer"
        if normalized.endswith(r"\services") or r"\services" in normalized:
            return "Services"
        if "winguardtest" in normalized:
            return "WinGuardTest"

        return key_path.split("\\")[-1] if key_path else "Unknown"


# ==============================================================================
# MAIN WINDOW
# ==============================================================================

class WinGuardMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("WinGuard - Windows Registry & Integrity Monitor")
        self.setGeometry(200, 200, 1100, 600)
        self.setMinimumSize(900, 500)

        # --- Status bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("WinGuard ready.")

        # --- Central widget + tab container ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout()
        central_widget.setLayout(root_layout)

        # Title
        title = QLabel("WinGuard Monitoring Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px 0;")
        root_layout.addWidget(title)

        # Tabs
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        # Tab 1: Dashboard
        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Main Dashboard")

        # Tab 2: Registry Monitor
        self.registry_tab = RegistryTab(
            status_callback=self.update_status,
            dashboard_callback=self.dashboard_tab.handle_registry_event
        )
        self.tabs.addTab(self.registry_tab, "Registry Monitor")

        # Tab 3: File Integrity Monitor (placeholder)
        fim_placeholder = QLabel("File Integrity Monitoring. Coming Soon")
        fim_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fim_placeholder.setStyleSheet("font-size: 14px; color: gray;")
        self.tabs.addTab(fim_placeholder, "File Integrity Monitor")

    def update_status(self, message: str):
        self.status_bar.showMessage(message)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WinGuardMainWindow()
    window.show()
    sys.exit(app.exec())
