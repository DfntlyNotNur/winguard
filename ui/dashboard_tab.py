from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from config import MONITORED_REGISTRY_KEYS


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self.total_changes = 0
        self.change_type_counts = {"ADDED": 0, "MODIFIED": 0, "DELETED": 0}
        self.severity_counts = {}
        self.category_counts = self._build_initial_category_counts()

        layout = QVBoxLayout(self)
        title = QLabel("Main Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 12px 0;")
        layout.addWidget(title)

        metrics = QGridLayout()
        layout.addLayout(metrics)
        self.lbl_registry_status = self._value("Stopped")
        self.lbl_fim_status = self._value("Stopped")
        self.lbl_total_changes = self._value("0")
        self.lbl_last_scan = self._value("Not scanned yet")
        self._metric(metrics, 0, 0, "Registry Monitor", self.lbl_registry_status)
        self._metric(metrics, 0, 1, "File Integrity Monitor", self.lbl_fim_status)
        self._metric(metrics, 1, 0, "Total Changes", self.lbl_total_changes)
        self._metric(metrics, 1, 1, "Last Registry Scan", self.lbl_last_scan)

        counts = QGridLayout()
        layout.addLayout(counts)
        self.lbl_added = self._value("0")
        self.lbl_modified = self._value("0")
        self.lbl_deleted = self._value("0")
        self.lbl_high = self._value("0")
        self.lbl_medium = self._value("0")
        self.lbl_low = self._value("0")
        self.lbl_other = self._value("0")
        for index, (name, label) in enumerate((("Added", self.lbl_added), ("Modified", self.lbl_modified), ("Deleted", self.lbl_deleted), ("High Severity", self.lbl_high), ("Medium Severity", self.lbl_medium), ("Low Severity", self.lbl_low), ("Other Severity", self.lbl_other))):
            self._metric(counts, index // 4, index % 4, name, label)

        self.category_table = QTableWidget(0, 2)
        self.category_table.setHorizontalHeaderLabels(["Registry Area", "Changes"])
        self.category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.category_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.category_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.category_table)
        self.lbl_latest_alert = QLabel("Latest alert: None")
        self.lbl_latest_alert.setWordWrap(True)
        layout.addWidget(self.lbl_latest_alert)
        self._refresh_category_table()

    def handle_registry_event(self, event_type, *args):
        if event_type == "status":
            self.lbl_registry_status.setText(args[0])
        elif event_type == "scan":
            scan_time, changes = args
            self.lbl_last_scan.setText(scan_time)
            self.record_changes(changes, "registry")

    def handle_fim_event(self, event_type, *args):
        if event_type == "status":
            self.lbl_fim_status.setText(args[0])
        elif event_type == "scan":
            self.record_changes(args[1], "file")

    def record_changes(self, changes, source):
        if not changes:
            return
        self.total_changes += len(changes)
        for change in changes:
            change_type = change.get("change_type", "UNKNOWN")
            severity = change.get("severity", "UNKNOWN")
            self.change_type_counts[change_type] = self.change_type_counts.get(change_type, 0) + 1
            self.severity_counts[severity] = self.severity_counts.get(severity, 0) + 1
            if source == "registry":
                category = self._category(change.get("key_path", ""))
                self.category_counts[category] = self.category_counts.get(category, 0) + 1
        latest = changes[-1]
        location = latest.get("file_path") if source == "file" else latest.get("value_name")
        self.lbl_latest_alert.setText(f"Latest alert: {latest.get('severity', 'UNKNOWN')} - {latest.get('change_type', 'UNKNOWN')} ({location})")
        self._refresh_counts()
        self._refresh_category_table()

    def _refresh_counts(self):
        self.lbl_total_changes.setText(str(self.total_changes))
        self.lbl_added.setText(str(self.change_type_counts.get("ADDED", 0)))
        self.lbl_modified.setText(str(self.change_type_counts.get("MODIFIED", 0)))
        self.lbl_deleted.setText(str(self.change_type_counts.get("DELETED", 0)))
        self.lbl_high.setText(str(self.severity_counts.get("HIGH", 0)))
        self.lbl_medium.setText(str(self.severity_counts.get("MEDIUM", 0)))
        self.lbl_low.setText(str(self.severity_counts.get("LOW", 0)))
        known = sum(self.severity_counts.get(item, 0) for item in ("HIGH", "MEDIUM", "LOW"))
        self.lbl_other.setText(str(self.total_changes - known))

    def _refresh_category_table(self):
        self.category_table.setRowCount(0)
        for category, count in sorted(self.category_counts.items()):
            row = self.category_table.rowCount()
            self.category_table.insertRow(row)
            self.category_table.setItem(row, 0, QTableWidgetItem(category))
            self.category_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def _build_initial_category_counts(self):
        return {self._category(subkey): 0 for _, _, subkey, _ in MONITORED_REGISTRY_KEYS}

    def _category(self, key_path):
        normalized = key_path.lower()
        if normalized.endswith("\\run") or normalized == "run": return "Run"
        if normalized.endswith("\\runonce") or normalized == "runonce": return "RunOnce"
        if "policies\\explorer" in normalized: return "Policies Explorer"
        if "\\services" in normalized: return "Services"
        if "winguardtest" in normalized: return "WinGuardTest"
        return key_path.split("\\")[-1] if key_path else "Unknown"

    def _value(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-size: 18px; font-weight: bold;")
        return label

    def _metric(self, layout, row, column, title, value):
        box = QWidget()
        box.setStyleSheet("QWidget { border: 1px solid #d0d0d0; border-radius: 6px; padding: 8px; } QLabel { border: none; padding: 0; }")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(QLabel(title))
        box_layout.addWidget(value)
        layout.addWidget(box, row, column)
