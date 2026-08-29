# WinGuard application entry point
import sys

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from theme import apply_theme
from ui.dashboard_ui import DashboardTab, show_no_baselines_warning
from ui.fim_ui import FileIntegrityTab
from ui.registry_ui import RegistryTab


class WinGuardMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WinGuard - Windows Registry & Integrity Monitoring")
        self.setGeometry(200, 200, 1100, 600)
        self.setMinimumSize(900, 500)
        self.settings = QSettings("WinGuard", "WinGuard")
        self.dark_theme = self.settings.value("theme", "dark") == "dark"
        apply_theme(QApplication.instance(), self.dark_theme)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("WinGuard ready.")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        header_layout = QGridLayout()
        header_layout.setColumnStretch(0, 1)
        header_layout.setColumnStretch(1, 2)
        header_layout.setColumnStretch(2, 1)

        title = QLabel("WinGuard Monitoring Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px 0;")
        header_layout.addWidget(title, 0, 1)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setFixedSize(34, 34)
        self.theme_button.setAccessibleName("Theme toggle")
        self._update_theme_button()
        self.theme_button.clicked.connect(self.toggle_theme)
        header_layout.addWidget(
            self.theme_button,
            0,
            2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addLayout(header_layout)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Main Dashboard")

        self.registry_tab = RegistryTab(self.update_status, self.dashboard_tab.handle_registry_event)
        self.tabs.addTab(self.registry_tab, "Registry Monitor")

        self.fim_tab = FileIntegrityTab(self.update_status, self.dashboard_tab.handle_fim_event)
        self.tabs.addTab(self.fim_tab, "File Integrity Monitor")

        self.dashboard_tab.set_monitoring_toggle_callback(self.toggle_monitoring)
        self.dashboard_tab.set_baseline_callback(self.create_baselines)
        self.dashboard_tab.set_view_callbacks(
            lambda: self.tabs.setCurrentWidget(self.registry_tab),
            lambda: self.tabs.setCurrentWidget(self.fim_tab),
        )
        self.dashboard_tab.update_fim_directories(self.fim_tab.get_directory_overview())

    def toggle_monitoring(self):
        if self.registry_tab.timer.isActive() or self.fim_tab.timer.isActive():
            self.registry_tab.stop_monitoring()
            self.fim_tab.stop_monitoring()
            self.dashboard_tab.set_monitoring_state(False)
            return

        if not self.registry_tab.can_start_monitoring() or not self.fim_tab.can_start_monitoring():
            show_no_baselines_warning(self)
            return

        registry_started = self.registry_tab.start_monitoring(notify=False)
        fim_started = self.fim_tab.start_monitoring(notify=False)
        if registry_started and fim_started:
            self.dashboard_tab.set_monitoring_state(True)
        else:
            self.registry_tab.stop_monitoring()
            self.fim_tab.stop_monitoring()
            QMessageBox.warning(self, "Monitoring Not Started", "Both monitoring modules must be ready before monitoring can start.")

    def create_baselines(self):
        """Create both module baselines from the dashboard in one action."""

        self.update_status("Creating Registry Monitor and FIM baselines...")
        try:
            self.registry_tab.create_baseline(notify=False)
            self.fim_tab.create_baseline(notify=False)
        except OSError as error:
            QMessageBox.critical(self, "Baseline Creation Failed", str(error))
            self.update_status("Baseline creation failed.")
            return

        QMessageBox.information(
            self,
            "Baselines Created",
            "Registry Monitor and FIM baselines have been created successfully.",
        )
        self.update_status("Registry Monitor and FIM baselines ready.")

    def toggle_theme(self):
        self.dark_theme = not self.dark_theme
        self.settings.setValue("theme", "dark" if self.dark_theme else "light")
        apply_theme(QApplication.instance(), self.dark_theme)
        self._update_theme_button()

    def _update_theme_button(self):
        if self.dark_theme:
            self.theme_button.setText("☀")
            self.theme_button.setToolTip("Switch to light theme")
        else:
            self.theme_button.setText("☾")
            self.theme_button.setToolTip("Switch to dark theme")

    def update_status(self, message: str):
        self.status_bar.showMessage(message)

    def closeEvent(self, event: QCloseEvent):
        self.registry_tab.stop_monitoring()
        self.fim_tab.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WinGuardMainWindow()
    window.show()
    sys.exit(app.exec())
