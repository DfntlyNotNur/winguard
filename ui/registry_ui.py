from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMenu, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from config import (
    BASELINE_MISSING,
    BASELINE_READY,
    MAX_VISIBLE_ROWS,
    POLLING_INTERVAL_MS,
    SEVERITY_COLORS,
)
from ui.dashboard_ui import (
    DeselectableTable,
    confirm_clear_log,
    refresh_widget_style,
    show_no_baselines_warning,
)
from logger import clear_log as clear_persisted_log, write_info_log, write_log
from registry_monitor import (
    compare_snapshots, get_baseline_timestamp, load_baseline,
    save_baseline, take_registry_snapshot,
)


class RegistryTab(QWidget):
    def __init__(self, status_callback, dashboard_callback=None):
        super().__init__()
        self.status_callback = status_callback
        self.dashboard_callback = dashboard_callback
        self.baseline_snapshot = None

        layout = QVBoxLayout(self)
        self.lbl_baseline_info = QLabel()
        layout.addWidget(self.lbl_baseline_info)

        buttons = QHBoxLayout()
        self.btn_baseline = QPushButton("Create Baseline")
        self.btn_baseline.setObjectName("secondaryButton")
        self.btn_start = QPushButton("Start Monitoring")
        self.btn_start.setObjectName("primaryButton")
        self.btn_stop = QPushButton("Stop Monitoring")
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
            self.btn_clear_alerts,
            self.btn_more,
        ):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.table = DeselectableTable(0, 6)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Severity", "Change Type", "Registry Key", "Value Name", "Details"])
        for column in (0, 1, 2, 4):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in (3, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.lbl_last_scan = QLabel("Last scan: -")
        layout.addWidget(self.lbl_last_scan)

        self.timer = QTimer(self)
        self.timer.setInterval(POLLING_INTERVAL_MS)
        self.timer.timeout.connect(self.run_scan)
        self.btn_baseline.clicked.connect(lambda: self.create_baseline())
        self.btn_start.clicked.connect(lambda: self.start_monitoring())
        self.btn_stop.clicked.connect(self.stop_monitoring)
        self.btn_clear_alerts.clicked.connect(self.clear_alerts)
        self._refresh_baseline_label()

    def create_baseline(self, notify=True):
        self.status_callback("Creating registry baseline...")
        self.baseline_snapshot = take_registry_snapshot()
        message = save_baseline(self.baseline_snapshot)
        self._refresh_baseline_label()
        write_info_log("Registry baseline created.")
        self.status_callback("Registry baseline ready.")
        if notify:
            QMessageBox.information(self, "Baseline Created", message)

    def can_start_monitoring(self):
        return self.get_monitoring_readiness() == BASELINE_READY

    def get_monitoring_readiness(self):
        self.baseline_snapshot = self.baseline_snapshot or load_baseline()
        return BASELINE_READY if self.baseline_snapshot is not None else BASELINE_MISSING

    def start_monitoring(self, notify=True):
        readiness = self.get_monitoring_readiness()
        if readiness == BASELINE_MISSING:
            if notify:
                show_no_baselines_warning(self)
            return False
        self.timer.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_baseline.setEnabled(False)
        write_info_log("Registry monitoring started.")
        self.status_callback("Registry monitoring active...")
        self._send_dashboard("status", "Active")
        return True

    def stop_monitoring(self):
        was_active = self.timer.isActive()
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_baseline.setEnabled(True)
        if was_active:
            write_info_log("Registry monitoring stopped.")
        self.status_callback("Registry monitoring stopped.")
        self._send_dashboard("status", "Stopped")

    def run_scan(self):
        current = take_registry_snapshot()
        changes = compare_snapshots(self.baseline_snapshot, current)
        scan_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.lbl_last_scan.setText(f"Last scan: {scan_time}  |  Changes detected: {len(changes)}")
        self._send_dashboard("scan", scan_time, changes)
        for change in changes:
            self._add_change_row(change)
            write_log(change)
        self.status_callback(f"[ALERT] {len(changes)} registry change(s) detected!" if changes else "Registry scan complete. No changes detected.")

    def clear_alerts(self):
        self.table.setRowCount(0)
        self.status_callback("Registry alerts cleared.")

    def clear_log(self):
        if not confirm_clear_log(self):
            return
        clear_persisted_log()
        self.status_callback("Saved WinGuard log cleared.")

    def _add_change_row(self, change):
        if self.table.rowCount() >= MAX_VISIBLE_ROWS:
            self.table.removeRow(0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        if change["change_type"] == "ADDED":
            details = f"New value: {change['new_data']}"
        elif change["change_type"] == "DELETED":
            details = f"Removed value: {change['old_data']}"
        else:
            details = f"{change['old_data']} -> {change['new_data']}"
        values = [change["timestamp"], change["severity"], change["change_type"], change["key_path"], change["value_name"], details]
        color = QColor(SEVERITY_COLORS.get(change["severity"], "#FFFFFF"))
        color.setAlpha(60)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setBackground(color)
            font = item.font()
            font.setBold(False)
            item.setFont(font)
            item.setToolTip(str(value))
            self.table.setItem(row, column, item)
        self.table.scrollToBottom()

    def _refresh_baseline_label(self):
        timestamp = get_baseline_timestamp()
        if timestamp:
            self.lbl_baseline_info.setText(f"Baseline created: {timestamp}")
            self.lbl_baseline_info.setObjectName("baselineLabel")
        else:
            self.lbl_baseline_info.setText("Baseline: Not created yet.")
            self.lbl_baseline_info.setObjectName("secondaryLabel")
        refresh_widget_style(self.lbl_baseline_info)
        self._send_dashboard("baseline", timestamp)

    def _send_dashboard(self, event_type, *args):
        if self.dashboard_callback:
            self.dashboard_callback(event_type, *args)
