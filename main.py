# WinGuard application entry point
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QStatusBar, QTabWidget, QVBoxLayout, QWidget

from ui.dashboard_tab import DashboardTab
from ui.file_tab import FileIntegrityTab
from ui.registry_tab import RegistryTab


class WinGuardMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WinGuard - Windows Registry & Integrity Monitor")
        self.setGeometry(200, 200, 1100, 600)
        self.setMinimumSize(900, 500)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("WinGuard ready.")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        title = QLabel("WinGuard Monitoring Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 8px 0;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.dashboard_tab = DashboardTab()
        self.tabs.addTab(self.dashboard_tab, "Main Dashboard")

        self.registry_tab = RegistryTab(self.update_status, self.dashboard_tab.handle_registry_event)
        self.tabs.addTab(self.registry_tab, "Registry Monitor")

        self.fim_tab = FileIntegrityTab(self.update_status, self.dashboard_tab.handle_fim_event)
        self.tabs.addTab(self.fim_tab, "File Integrity Monitor")

    def update_status(self, message: str):
        self.status_bar.showMessage(message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WinGuardMainWindow()
    window.show()
    sys.exit(app.exec())
