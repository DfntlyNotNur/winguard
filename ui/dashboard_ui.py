from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import MONITORED_REGISTRY_KEYS


NO_BASELINES_TITLE = "No Baselines"
NO_BASELINES_MESSAGE = "Create baselines before starting monitoring."


def show_no_baselines_warning(parent: QWidget) -> None:
    """Show the standard warning used when monitoring has no usable baseline."""

    QMessageBox.warning(parent, NO_BASELINES_TITLE, NO_BASELINES_MESSAGE)


class DashboardTab(QWidget):
    """Combined overview for the Registry Monitor and FIM modules."""

    MAX_EVENTS = 300

    def __init__(self):
        super().__init__()
        self.registry_active = False
        self.fim_active = False
        self.registry_counts = self._empty_counts()
        self.fim_counts = self._empty_counts(include_renamed=True)
        self.registry_categories = {
            self._category(subkey): 0
            for _, _, subkey, _ in MONITORED_REGISTRY_KEYS
        }
        self.latest_events: list[dict] = []
        self._toggle_callback: Callable[[], None] | None = None
        self._baseline_callback: Callable[[], None] | None = None
        self._registry_view_callback: Callable[[], None] | None = None
        self._fim_view_callback: Callable[[], None] | None = None

        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)
        scroll.setWidget(content)

        title = QLabel("Main Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 4px;")
        content_layout.addWidget(title)

        content_layout.addWidget(self._build_status_group())
        content_layout.addWidget(self._build_session_group())

        overview_layout = QHBoxLayout()
        overview_layout.setSpacing(10)
        overview_layout.addWidget(self._build_registry_group(), 1)
        overview_layout.addWidget(self._build_fim_group(), 1)
        content_layout.addLayout(overview_layout)

        events_group = QGroupBox("Latest Security Events")
        events_layout = QVBoxLayout(events_group)
        self.events_table = self._make_table(
            ["Timestamp", "Source", "Change Type", "Location", "Details"]
        )
        self.events_table.setFixedHeight(190)
        self.events_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        event_header = self.events_table.horizontalHeader()
        for column, width in ((0, 155), (1, 85), (2, 105), (3, 430)):
            event_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.events_table.setColumnWidth(column, width)
        event_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        events_layout.addWidget(self.events_table)
        content_layout.addWidget(events_group)

    def _build_status_group(self):
        group = QGroupBox("Monitoring Status")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, 5, 10, 7)
        layout.setSpacing(6)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self.btn_baselines = QPushButton("Create Baselines")
        self.btn_baselines.setObjectName("secondaryButton")
        self.btn_baselines.setFixedSize(165, 34)
        self.btn_baselines.clicked.connect(self._create_baselines)
        controls_layout.addWidget(self.btn_baselines)

        self.btn_toggle = QPushButton("Start Monitoring")
        self.btn_toggle.setObjectName("primaryButton")
        self.btn_toggle.setFixedSize(165, 34)
        self.btn_toggle.clicked.connect(self._toggle_monitoring)
        controls_layout.addWidget(self.btn_toggle)
        layout.addWidget(controls, 0, Qt.AlignmentFlag.AlignVCenter)

        registry_block, self.lbl_registry_status, self.lbl_registry_baseline, self.lbl_registry_scan = self._status_block(
            "Registry Monitor"
        )
        fim_block, self.lbl_fim_status, self.lbl_fim_baseline, self.lbl_fim_scan = self._status_block(
            "File Integrity Monitoring"
        )
        layout.addWidget(registry_block, 1)
        layout.addWidget(fim_block, 1)
        return group

    def _status_block(self, name):
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(1)
        title = QLabel(f"{name}: Stopped")
        title.setStyleSheet("font-weight: 600;")
        baseline = QLabel("Baseline created: Not created yet.")
        scan = QLabel("Last Scan: Not scanned yet")
        baseline.setObjectName("secondaryLabel")
        scan.setObjectName("secondaryLabel")
        layout.addWidget(title)
        layout.addWidget(baseline)
        layout.addWidget(scan)
        return block, title, baseline, scan

    def _build_session_group(self):
        group = QGroupBox("Session Summary")
        layout = QHBoxLayout(group)
        self.lbl_total_changes = self._add_metric(layout, "Total Changes", "summary_total")
        self.lbl_registry_changes = self._add_metric(layout, "Registry Changes", "summary_registry")
        self.lbl_file_changes = self._add_metric(layout, "File Changes", "summary_file")
        return group

    def _build_registry_group(self):
        group = QGroupBox("Registry Monitor Overview")
        layout = QVBoxLayout(group)

        self.btn_view_registry = QPushButton("View Registry Monitor")
        self.btn_view_registry.clicked.connect(self._view_registry)
        layout.addWidget(self.btn_view_registry)

        metrics = QHBoxLayout()
        self.lbl_registry_added = self._add_metric(metrics, "Added")
        self.lbl_registry_modified = self._add_metric(metrics, "Modified")
        self.lbl_registry_deleted = self._add_metric(metrics, "Deleted")
        layout.addLayout(metrics)

        self.registry_table = self._make_table(["Registry Area", "Changes"])
        self.registry_table.setFixedHeight(170)
        self.registry_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.registry_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.registry_table.setColumnWidth(1, 80)
        layout.addWidget(self.registry_table)
        return group

    def _build_fim_group(self):
        group = QGroupBox("File Integrity Monitoring Overview")
        layout = QVBoxLayout(group)

        self.btn_view_fim = QPushButton("View FIM Monitor")
        self.btn_view_fim.clicked.connect(self._view_fim)
        layout.addWidget(self.btn_view_fim)

        metrics = QHBoxLayout()
        self.lbl_fim_added = self._add_metric(metrics, "Added")
        self.lbl_fim_modified = self._add_metric(metrics, "Modified")
        self.lbl_fim_deleted = self._add_metric(metrics, "Deleted")
        self.lbl_fim_renamed = self._add_metric(metrics, "Renamed")
        layout.addLayout(metrics)

        self.fim_table = self._make_table(["Directory Path", "Status"])
        self.fim_table.setFixedHeight(150)
        self.fim_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.fim_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.fim_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.fim_table.setColumnWidth(1, 100)
        layout.addWidget(self.fim_table)
        return group

    def _add_metric(self, layout, title, role=None):
        box = QWidget()
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        box.setObjectName("metricBox")
        if role:
            box.setProperty("summaryRole", role.removeprefix("summary_"))
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(6, 5, 6, 5)
        caption = QLabel(title)
        value = QLabel("0")
        value.setObjectName("metricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("font-size: 18px; font-weight: bold;")
        box_layout.addWidget(caption)
        box_layout.addWidget(value)
        layout.addWidget(box)
        return value

    @staticmethod
    def _make_table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        for column in range(table.columnCount()):
            table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.Stretch
            )
        return table

    def set_monitoring_toggle_callback(self, callback):
        self._toggle_callback = callback

    def set_baseline_callback(self, callback):
        self._baseline_callback = callback

    def set_view_callbacks(self, registry_callback, fim_callback):
        self._registry_view_callback = registry_callback
        self._fim_view_callback = fim_callback

    def set_monitoring_state(self, active):
        self.registry_active = bool(active)
        self.fim_active = bool(active)
        self._refresh_status_labels()

    def handle_registry_event(self, event_type, *args):
        if event_type == "status":
            self.registry_active = str(args[0]).lower() == "active"
            self._refresh_status_labels()
        elif event_type == "baseline":
            self._set_baseline_label(
                self.lbl_registry_baseline, args[0] if args else None
            )
        elif event_type == "scan":
            scan_time, changes = args
            self.lbl_registry_scan.setText(f"Last Scan: {scan_time}")
            self.record_changes(changes, "Registry")

    def handle_fim_event(self, event_type, *args):
        if event_type == "status":
            self.fim_active = str(args[0]).lower() == "active"
            self._refresh_status_labels()
        elif event_type == "baseline":
            self._set_baseline_label(self.lbl_fim_baseline, args[0] if args else None)
        elif event_type == "directories":
            self._refresh_fim_table(args[0] if args else [])
        elif event_type == "scan":
            scan_time, changes = args
            self.lbl_fim_scan.setText(f"Last Scan: {scan_time}")
            self.record_changes(changes, "FIM")

    def record_changes(self, changes, source):
        counts = self.registry_counts if source == "Registry" else self.fim_counts
        for change in changes:
            change_type = change.get("change_type", "UNKNOWN")
            counts[change_type] = counts.get(change_type, 0) + 1
            if source == "Registry":
                category = self._category(change.get("key_path", ""))
                self.registry_categories[category] = self.registry_categories.get(category, 0) + 1
            self._prepend_event(self._event_record(change, source))
        if changes:
            self._refresh_all()

    def update_fim_directories(self, directories):
        self._refresh_fim_table(directories)

    def _prepend_event(self, event):
        self.latest_events.insert(0, event)
        del self.latest_events[self.MAX_EVENTS:]

    def _event_record(self, change, source):
        if source == "Registry":
            location = change.get("key_path", "")
            value_name = change.get("value_name", "")
            if value_name:
                location = f"{location} / {value_name}"
            change_type = change.get("change_type", "UNKNOWN")
            if change_type == "ADDED":
                details = f"New value: {change.get('new_data', '')}"
            elif change_type == "DELETED":
                details = f"Removed value: {change.get('old_data', '')}"
            else:
                details = f"{change.get('old_data', '')} -> {change.get('new_data', '')}"
        else:
            location = change.get("file_path", "")
            change_type = change.get("change_type", "UNKNOWN")
            details = change.get("details", "")
            if change_type == "RENAMED":
                old_name = Path(change.get("old_path", "")).name
                new_name = Path(location).name
                details = f"File renamed from {old_name} to {new_name}"
        return {
            "timestamp": change.get("timestamp", "-"),
            "source": source,
            "change_type": change_type,
            "location": location,
            "details": details,
            "details_tooltip": change.get("details", details),
        }

    def _refresh_all(self):
        registry_total = sum(self.registry_counts.values())
        fim_total = sum(self.fim_counts.values())
        self.lbl_total_changes.setText(str(registry_total + fim_total))
        self.lbl_registry_changes.setText(str(registry_total))
        self.lbl_file_changes.setText(str(fim_total))
        self.lbl_registry_added.setText(str(self.registry_counts.get("ADDED", 0)))
        self.lbl_registry_modified.setText(str(self.registry_counts.get("MODIFIED", 0)))
        self.lbl_registry_deleted.setText(str(self.registry_counts.get("DELETED", 0)))
        self.lbl_fim_added.setText(str(self.fim_counts.get("ADDED", 0)))
        self.lbl_fim_modified.setText(str(self.fim_counts.get("MODIFIED", 0)))
        self.lbl_fim_deleted.setText(str(self.fim_counts.get("DELETED", 0)))
        self.lbl_fim_renamed.setText(str(self.fim_counts.get("RENAMED", 0)))
        self._refresh_registry_table()
        self._refresh_events_table()
        self._refresh_status_labels()

    def _refresh_status_labels(self):
        registry_state = "Active" if self.registry_active else "Stopped"
        fim_state = "Active" if self.fim_active else "Stopped"
        self.lbl_registry_status.setText(f"Registry Monitor: {registry_state}")
        self.lbl_fim_status.setText(f"File Integrity Monitoring: {fim_state}")
        self.btn_baselines.setEnabled(not (self.registry_active or self.fim_active))
        self.btn_toggle.setText(
            "Stop Monitoring" if self.registry_active or self.fim_active else "Start Monitoring"
        )

    def _refresh_registry_table(self):
        self.registry_table.setRowCount(0)
        for category, count in self.registry_categories.items():
            row = self.registry_table.rowCount()
            self.registry_table.insertRow(row)
            self._set_row(self.registry_table, row, [category, str(count)])

    def _refresh_fim_table(self, directories):
        self.fim_table.setRowCount(0)
        for directory in directories:
            row = self.fim_table.rowCount()
            self.fim_table.insertRow(row)
            full_path = directory.get("path", "")
            values = [
                full_path,
                directory.get("status", "Unavailable"),
            ]
            self._set_row(self.fim_table, row, values, [full_path, values[1]])

    def _refresh_events_table(self):
        self.events_table.setRowCount(0)
        for event in self.latest_events:
            row = self.events_table.rowCount()
            self.events_table.insertRow(row)
            self._set_row(
                self.events_table,
                row,
                [
                    event["timestamp"],
                    event["source"],
                    event["change_type"],
                    event["location"],
                    event["details"],
                ],
                [
                    event["timestamp"],
                    event["source"],
                    event["change_type"],
                    event["location"],
                    event["details_tooltip"],
                ],
            )

    @staticmethod
    def _set_row(table, row, values, tooltips=None):
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            font = item.font()
            font.setBold(False)
            item.setFont(font)
            tooltip = tooltips[column] if tooltips and column < len(tooltips) else value
            item.setToolTip(str(tooltip))
            table.setItem(row, column, item)

    @staticmethod
    def _set_baseline_label(label, timestamp):
        if timestamp:
            label.setText(f"Baseline created: {timestamp}")
            label.setObjectName("baselineLabel")
        else:
            label.setText("Baseline created: Not created yet.")
            label.setObjectName("secondaryLabel")

    def _toggle_monitoring(self):
        if self._toggle_callback:
            self._toggle_callback()

    def _create_baselines(self):
        if self._baseline_callback:
            self._baseline_callback()

    def _view_registry(self):
        if self._registry_view_callback:
            self._registry_view_callback()

    def _view_fim(self):
        if self._fim_view_callback:
            self._fim_view_callback()

    @staticmethod
    def _empty_counts(include_renamed=False):
        counts = {"ADDED": 0, "MODIFIED": 0, "DELETED": 0}
        if include_renamed:
            counts["RENAMED"] = 0
        return counts

    @staticmethod
    def _category(key_path):
        normalized = key_path.lower()
        if normalized.endswith("\\run") or normalized == "run":
            return "Run"
        if normalized.endswith("\\runonce") or normalized == "runonce":
            return "RunOnce"
        if "policies\\explorer" in normalized:
            return "Policies Explorer"
        if "\\services" in normalized:
            return "Services"
        if "winguardtest" in normalized:
            return "WinGuardTest"
        return key_path.split("\\")[-1] if key_path else "Unknown"
