# main.py
# WinGuard - Main Entry Point
# Assembles the main window with tabbed UI.
# Registry monitoring is handled via QTimer polling.

import sys
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QStatusBar, QTabWidget, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from config import POLLING_INTERVAL_MS, SEVERITY_COLORS
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
    def __init__(self, status_callback):
        super().__init__()

        # status_callback lets this tab update the main window's status bar
        self.status_callback = status_callback
        self.baseline_snapshot = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Info bar (baseline timestamp) ---
        self.lbl_baseline_info = QLabel("Baseline: Not created yet.")
        self.lbl_baseline_info.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self.lbl_baseline_info)

        # --- Button row ---
        btn_layout = QHBoxLayout()

        self.btn_baseline   = QPushButton("Create Baseline")
        self.btn_start      = QPushButton("Start Monitoring")
        self.btn_stop       = QPushButton("Stop Monitoring")
        self.btn_clear      = QPushButton("Clear Log")

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
        self.lbl_last_scan = QLabel("Last scan: —")
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
        self.status_callback(f"Registry baseline ready.")
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

    def stop_monitoring(self):
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_baseline.setEnabled(True)
        write_info_log("Registry monitoring stopped.")
        self.status_callback("Registry monitoring stopped.")

    def run_scan(self):
        """Called by QTimer on every polling interval."""
        current_snapshot = take_registry_snapshot()
        changes = compare_snapshots(self.baseline_snapshot, current_snapshot)

        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_last_scan.setText(f"Last scan: {scan_time}  |  Changes detected: {len(changes)}")

        if changes:
            for change in changes:
                self._add_change_row(change)
                write_log(change)
            self.status_callback(f"[ALERT] {len(changes)} change(s) detected in registry!")
        else:
            self.status_callback(f"Registry scan complete — No changes detected.")

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
            details = f"{change['old_data']}  →  {change['new_data']}"

        cells = [
            change["timestamp"],
            change["severity"],
            change["change_type"],
            change["key_path"],
            change["value_name"],
            details
        ]

        color_hex = SEVERITY_COLORS.get(change["severity"], "#FFFFFF")
        bg_color  = QColor(color_hex)
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


# ==============================================================================
# DASHBOARD TAB (placeholder for summary/overview)
# ==============================================================================

class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        self.setLayout(layout)

        lbl = QLabel("WinGuard — Windows Registry & Integrity Guard")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 20px; font-weight: bold; margin-top: 40px;")
        layout.addWidget(lbl)

        sub = QLabel(
            "Navigate to the Registry Monitor or File Integrity Monitor tabs\n"
            "to begin monitoring your system."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 13px; color: gray; margin-top: 10px;")
        layout.addWidget(sub)

        layout.addStretch()


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
        self.tabs.addTab(self.dashboard_tab, "Dashboard")

        # Tab 2: Registry Monitor
        self.registry_tab = RegistryTab(status_callback=self.update_status)
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