"""Application-wide light and dark theme definitions for WinGuard."""

from PyQt6.QtWidgets import QApplication


DARK_STYLESHEET = """
QWidget {
    background-color: #202326;
    color: #edf0f2;
}
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #202326;
}
QGroupBox {
    background-color: #303338;
    border: 1px solid #59616a;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #f2f4f5;
}
QPushButton {
    background-color: #3b4046;
    color: #f2f4f5;
    border: 1px solid #626b75;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover {
    background-color: #48545f;
}
QPushButton:disabled {
    color: #89939d;
    background-color: #303338;
}
QPushButton#primaryButton {
    background-color: #247bc5;
    border-color: #80b9e7;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background-color: #318ed8;
}
QPushButton#primaryButton:pressed {
    background-color: #16517f;
    border-color: #2c6b9d;
}
QPushButton#primaryButton:disabled {
    background-color: #16466e;
    border-color: #2b628c;
    color: #d7e7f3;
}
QPushButton#themeButton {
    font-size: 17px;
    padding: 2px;
    border-radius: 17px;
}
QLabel#secondaryLabel {
    color: #aeb5bc;
    font-size: 12px;
}
QLabel#baselineLabel {
    color: #7bd49c;
    font-size: 12px;
}
QLabel#warningLabel {
    color: #e2b45f;
    font-size: 12px;
}
QTableWidget {
    background-color: #303338;
    alternate-background-color: #35383d;
    color: #edf0f2;
    gridline-color: #4b5158;
    selection-background-color: #355d83;
    selection-color: #ffffff;
}
QTabWidget::pane {
    border: 1px solid #4b5c6b;
    top: -1px;
}
QTabBar::tab {
    background-color: #29323b;
    color: #b1c0cb;
    border: 1px solid #4b5c6b;
    border-bottom-color: #29323b;
    padding: 7px 14px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:hover {
    background-color: #35424e;
    color: #f2f7fa;
}
QTabBar::tab:selected {
    background-color: #303b46;
    color: #f7fafc;
    border-bottom-color: #303b46;
}
QHeaderView::section {
    background-color: #3d4147;
    color: #f2f4f5;
    border: 1px solid #4b5158;
    padding: 5px;
}
QStatusBar {
    background-color: #202326;
    color: #cbd1d6;
}
QWidget#metricBox {
    border: 1px solid #59616a;
    border-radius: 5px;
    padding: 5px;
}
QWidget#metricBox[summaryRole="total"] {
    background-color: #334b63;
}
QWidget#metricBox[summaryRole="registry"], QWidget#metricBox[summaryRole="file"] {
    background-color: #3a4046;
}
QWidget#metricBox[summaryRole="total"] QLabel#metricValue {
    color: #8fc5f2;
}
QWidget#metricBox[summaryRole="registry"] QLabel#metricValue,
QWidget#metricBox[summaryRole="file"] QLabel#metricValue {
    color: #d7e0e7;
}
QScrollBar:vertical {
    background-color: #292d31;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #727c86;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}
"""


LIGHT_STYLESHEET = """
QWidget {
    background-color: #f3f7fb;
    color: #253247;
}
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #f3f7fb;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #aebfd1;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #253247;
}
QPushButton {
    background-color: #eff3f7;
    color: #253247;
    border: 1px solid #8290a1;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover {
    background-color: #e0ebf5;
}
QPushButton:disabled {
    color: #8b98a6;
    background-color: #e8edf2;
}
QPushButton#primaryButton {
    background-color: #2d6cdf;
    border-color: #1f55b0;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background-color: #3c7bea;
}
QPushButton#primaryButton:pressed {
    background-color: #1e4fa9;
    border-color: #173d82;
}
QPushButton#primaryButton:disabled {
    background-color: #9bb7e8;
    border-color: #7798d2;
}
QPushButton#themeButton {
    font-size: 17px;
    padding: 2px;
    border-radius: 17px;
}
QLabel#secondaryLabel {
    color: #536174;
    font-size: 12px;
}
QLabel#baselineLabel {
    color: #16834b;
    font-size: 12px;
}
QLabel#warningLabel {
    color: #9b6a0b;
    font-size: 12px;
}
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f4f7fa;
    color: #253247;
    gridline-color: #d5dce5;
    selection-background-color: #cfe2f7;
    selection-color: #253247;
}
QTabWidget::pane {
    border: 1px solid #aebfd1;
    top: -1px;
}
QTabBar::tab {
    background-color: #e8edf3;
    color: #536174;
    border: 1px solid #b7c9dc;
    border-bottom-color: #aebfd1;
    padding: 7px 14px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:hover {
    background-color: #dfeaf5;
    color: #253247;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #253247;
    border-bottom-color: #ffffff;
}
QHeaderView::section {
    background-color: #eaf2fb;
    color: #536174;
    border: 1px solid #b7c9dc;
    padding: 5px;
}
QStatusBar {
    background-color: #eaf0f6;
    color: #536174;
}
QWidget#metricBox {
    border: 1px solid #c9d4df;
    border-radius: 5px;
    padding: 5px;
}
QWidget#metricBox[summaryRole="total"] {
    background-color: #e7f0fb;
}
QWidget#metricBox[summaryRole="registry"], QWidget#metricBox[summaryRole="file"] {
    background-color: #f1f4f7;
}
QWidget#metricBox[summaryRole="total"] QLabel#metricValue {
    color: #2868a8;
}
QWidget#metricBox[summaryRole="registry"] QLabel#metricValue,
QWidget#metricBox[summaryRole="file"] QLabel#metricValue {
    color: #52606d;
}
QScrollBar:vertical {
    background-color: #edf0f4;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #a7b1bf;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}
"""


def apply_theme(app: QApplication, dark: bool) -> None:
    """Apply the selected palette to the whole WinGuard application."""

    app.setProperty("darkTheme", dark)
    app.setStyleSheet(DARK_STYLESHEET if dark else LIGHT_STYLESHEET)
