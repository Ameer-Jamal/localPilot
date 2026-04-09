from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import APP_DISPLAY_NAME
from history_store import SessionSummary


class HistoryDialog(QDialog):
    def __init__(self, sessions: Sequence[SessionSummary], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat History")
        self.resize(980, 640)
        self.setMinimumSize(840, 520)
        self.setObjectName("historyDialog")
        self._accepted_session_id: int | None = None
        self._delete_session_id: int | None = None

        self.setStyleSheet(
            """
            QDialog#historyDialog {
                background: #1a1e23;
                color: #eef2f6;
            }
            QLabel[role="eyebrow"] {
                color: #8ea0b5;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QLabel[role="title"] {
                color: #f6f9fc;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel[role="body"] {
                color: #aeb9c6;
                font-size: 13px;
            }
            QTableWidget {
                background: #14181d;
                color: #eef2f6;
                border: 1px solid #313b45;
                border-radius: 12px;
                gridline-color: #2a3138;
                selection-background-color: #2f8f81;
                selection-color: #f8fffd;
            }
            QHeaderView::section {
                background: #242b33;
                color: #c9d3de;
                border: none;
                padding: 10px 8px;
                font-weight: 600;
            }
            QPushButton {
                background: #242b33;
                color: #eef2f6;
                border: 1px solid #313b45;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2c3440; }
            QPushButton[variant="primary"] {
                background: #2f8f81;
                border-color: #2f8f81;
                color: #f8fffd;
            }
            QPushButton[variant="danger"] {
                background: #4c2b31;
                border-color: #7a3b46;
                color: #ffdfe3;
            }
            QPushButton[variant="danger"]:hover {
                background: #60343b;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(16)

        root.addWidget(self._build_header())
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Chat", "File", "Status", "Updated", "Preview"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.cellDoubleClicked.connect(lambda *_: self._accept_open())
        self._populate(sessions)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.count_label = QLabel("", self)
        self.count_label.setProperty("role", "body")
        self._update_count_label()
        actions.addWidget(self.count_label)
        actions.addStretch(1)

        self.delete_btn = QPushButton("Delete Selected", self)
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.clicked.connect(self._request_delete)
        self.open_btn = QPushButton("Open Chat", self)
        self.open_btn.setProperty("variant", "primary")
        self.open_btn.clicked.connect(self._accept_open)
        self.close_btn = QPushButton("Close", self)
        self.close_btn.clicked.connect(self.reject)
        for button in (self.delete_btn, self.open_btn, self.close_btn):
            button.style().unpolish(button)
            button.style().polish(button)
        actions.addWidget(self.delete_btn)
        actions.addWidget(self.open_btn)
        actions.addWidget(self.close_btn)
        root.addLayout(actions)

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        eyebrow = QLabel(APP_DISPLAY_NAME, header)
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("History", header)
        title.setProperty("role", "title")
        body = QLabel(
            "Reopen previous chats, review recent work, or delete history you no longer want to keep.",
            header,
        )
        body.setWordWrap(True)
        body.setProperty("role", "body")
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)
        return header

    def _populate(self, sessions: Sequence[SessionSummary]) -> None:
        self.table.setRowCount(0)
        for session in sessions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            chat_name = session.file_name or "Untitled Chat"
            file_name = session.file_path or "General chat"
            status = "Open" if session.is_open else "Closed"
            updated = session.updated_at.replace("T", " ").replace("+00:00", " UTC")
            preview = session.preview or "No messages yet"
            values = [chat_name, file_name, status, updated, preview]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, session.session_id)
                if column == 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 34)
        if self.table.rowCount():
            self.table.selectRow(0)

    def _update_count_label(self) -> None:
        self.count_label.setText(f"{self.table.rowCount()} saved chats")

    def selected_session_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _accept_open(self) -> None:
        session_id = self.selected_session_id()
        if session_id is None:
            return
        self._accepted_session_id = int(session_id)
        self.accept()

    def _request_delete(self) -> None:
        session_id = self.selected_session_id()
        if session_id is None:
            return
        self._delete_session_id = int(session_id)
        self.done(2)

    def get_open_session_id(self) -> int | None:
        return self._accepted_session_id

    def get_delete_session_id(self) -> int | None:
        return self._delete_session_id
