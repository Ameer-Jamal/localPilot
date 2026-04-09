from __future__ import annotations

APP_WINDOW_STYLE = """
QWidget {
    color: #eef2f6;
    font-size: 13px;
}
QMainWindow {
    background: #1a1e23;
}
QWidget#appShell {
    background: #1a1e23;
}
QWidget#windowHeader {
    background: #20262d;
    border-bottom: 1px solid #2e3741;
}
QLabel[role="muted"] {
    color: #8ea0b5;
    font-size: 12px;
}
QLabel[role="headerTitle"] {
    color: #eef2f6;
    font-size: 12px;
    font-weight: 600;
}
QTabWidget::pane {
    border: none;
    background: #1a1e23;
}
QTabBar::tab {
    background: #232a31;
    color: #aeb9c6;
    border: 1px solid #313b45;
    padding: 8px 14px;
    margin-right: 8px;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #2d3640;
    color: #f6f9fc;
}
QTabBar::tab:hover:!selected {
    background: #29313a;
}
QStatusBar {
    background: #20262d;
    color: #96a3b3;
    border-top: 1px solid #2e3741;
    padding: 4px 10px;
}
QComboBox {
    background: #14181d;
    color: #eef2f6;
    border: 1px solid #313b45;
    border-radius: 9px;
    padding: 7px 30px 7px 12px;
    min-width: 180px;
}
QComboBox:hover {
    border-color: #3c4956;
}
QComboBox:focus {
    border-color: #56b6a7;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: #1f252c;
    color: #eef2f6;
    border: 1px solid #313b45;
    selection-background-color: #2f8f81;
    selection-color: #f8fffd;
}
QMessageBox {
    background: #1a1e23;
}
QMessageBox QLabel {
    color: #eef2f6;
}
QMessageBox QPushButton {
    min-width: 88px;
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    background: #242b33;
    color: #eef2f6;
    border: 1px solid #313b45;
    border-radius: 10px;
    padding: 8px 14px;
    min-height: 18px;
    font-weight: 600;
}
QPushButton:hover { background: #2c3440; }
QPushButton:pressed { background: #20262d; }
QPushButton:disabled {
    background: #1d2228;
    color: #6f7d8b;
    border-color: #2a3138;
}
"""

ACCENT_BUTTON_STYLE = """
QPushButton {
    background: #2f8f81;
    color: #f8fffd;
    border: 1px solid #2f8f81;
    border-radius: 10px;
    padding: 8px 14px;
    min-height: 18px;
    font-weight: 600;
}
QPushButton:hover { background: #38a192; border-color: #38a192; }
QPushButton:pressed { background: #27776b; border-color: #27776b; }
QPushButton:disabled {
    background: #275f58;
    color: #b8d7d2;
    border-color: #275f58;
}
"""

SUBTLE_BUTTON_STYLE = """
QPushButton {
    background: transparent;
    color: #aeb9c6;
    border: 1px solid #313b45;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 18px;
    font-weight: 600;
}
QPushButton:hover { background: #232a31; color: #eef2f6; }
QPushButton:pressed { background: #1f252c; }
"""

INPUT_STYLE = """
QTextEdit {
    background: #14181d;
    color: #eef2f6;
    border: 1px solid #313b45;
    border-radius: 12px;
    padding: 10px 12px;
    selection-background-color: #2f8f81;
}
QTextEdit:focus {
    border-color: #56b6a7;
}
"""

PIN_BUTTON_STYLE = """
QToolButton {
    border: 1px solid #3a4651;
    border-radius: 10px;
    background: #1a2026;
}
QToolButton:hover {
    background: #232a31;
}
QToolButton:checked {
    background: #2f8f81;
    border-color: #2f8f81;
}
QToolButton:checked:hover {
    background: #38a192;
}
"""

HISTORY_REVEAL_BUTTON_STYLE = """
QToolButton {
    background: rgba(32, 38, 45, 0.92);
    color: #c5d2de;
    border: 1px solid #313b45;
    border-radius: 12px;
    padding: 0;
    font-size: 18px;
    font-weight: 700;
}
QToolButton:hover {
    background: rgba(40, 48, 57, 0.98);
    color: #eef2f6;
    border-color: #425161;
}
QToolButton:pressed {
    background: rgba(29, 35, 41, 0.98);
}
"""

EMPTY_STATE_STYLE = """
QWidget#emptyState QWidget[role="emptyCard"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #20262d, stop:1 #1b2128);
    border: 1px solid #2f3944;
    border-radius: 22px;
}
QWidget#emptyState QLabel[role="emptyEyebrow"] {
    color: #8ca1b5;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QWidget#emptyState QLabel[role="emptyTitle"] {
    color: #eef2f6;
    font-size: 32px;
    font-weight: 700;
}
QWidget#emptyState QLabel[role="emptyBody"] {
    color: #8ea0b5;
    font-size: 15px;
    qproperty-alignment: AlignCenter;
}
QWidget#emptyState QLabel[role="emptyMeta"] {
    color: #9fb0c2;
    font-size: 13px;
    qproperty-alignment: AlignCenter;
}
"""

HISTORY_PANEL_STYLE = """
QWidget#historyPanel {
    background: #151a1f;
    border-right: 1px solid #2a333d;
}
QLabel[role="eyebrow"] {
    color: #8ca1b5;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QLabel[role="title"] {
    color: #f3f6f9;
    font-size: 24px;
    font-weight: 700;
}
QLabel[role="body"] {
    color: #99aaba;
    font-size: 13px;
}
QToolButton[role="collapse"] {
    background: transparent;
    color: #cbd7e3;
    border: 1px solid #2f3944;
    border-radius: 10px;
    padding: 0;
    font-size: 18px;
    font-weight: 700;
}
QToolButton[role="collapse"]:hover {
    background: #202a33;
    border-color: #425161;
}
QListWidget {
    background: transparent;
    color: #eef2f6;
    border: none;
    outline: none;
    padding: 0;
}
QListWidget::item {
    border: none;
    margin: 0 0 8px 0;
}
QWidget#historyRow {
    background: #1b222a;
    border: 1px solid #2a333d;
    border-radius: 14px;
}
QWidget#historyRow[selected="true"] {
    background: #213746;
    border-color: #2f8f81;
}
QWidget#historyRow QLabel[role="rowTitle"] {
    color: #eef2f6;
    font-size: 14px;
    font-weight: 700;
}
QWidget#historyRow QLabel[role="rowPreview"] {
    color: #dce5ee;
    font-size: 13px;
}
QWidget#historyRow QLabel[role="rowMeta"] {
    color: #90a3b7;
    font-size: 12px;
}
QWidget#historyRow QLabel[role="badgeOpen"] {
    background: #1e4c45;
    color: #c7f2eb;
    border: 1px solid #2f8f81;
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}
QWidget#historyRow QLabel[role="badgeClosed"] {
    background: #222931;
    color: #a8b7c8;
    border: 1px solid #33404c;
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton[role="rowAction"] {
    background: transparent;
    color: #b8c8d8;
    border: 1px solid #3a4652;
    border-radius: 9px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton[role="rowAction"]:hover {
    background: #222c35;
    color: #eef2f6;
    border-color: #4b5d6e;
}
QPushButton[role="rowAction"]:pressed {
    background: #202a33;
}
"""
