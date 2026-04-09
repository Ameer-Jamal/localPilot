from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from history_presenter import (
    format_history_preview,
    format_history_source,
    format_history_title,
    format_history_updated,
)
from history_store import SessionSummary
from ui.theme import ACCENT_BUTTON_STYLE, HISTORY_PANEL_STYLE, SUBTLE_BUTTON_STYLE
from ui_text import (
    HISTORY_PANEL_BODY,
    LABEL_DELETE,
    LABEL_HISTORY,
    LABEL_OPEN,
    LABEL_OPEN_SELECTED,
    LABEL_REOPEN,
    LABEL_SAVED_CHATS,
    TOOLTIP_HIDE_HISTORY_PANEL,
    history_count_text,
)


class HistoryRowWidget(QWidget):
    reopenRequested = Signal(int)

    def __init__(self, session: SessionSummary, parent=None):
        super().__init__(parent)
        self.session_id = session.session_id
        self.setObjectName("historyRow")
        self.setProperty("selected", False)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)

        title = QLabel(format_history_title(session.title, session.file_name), self)
        title.setProperty("role", "rowTitle")
        title.setWordWrap(False)
        top.addWidget(title, 1)

        top.addStretch(1)

        if session.is_open:
            badge = QLabel(LABEL_OPEN, self)
            badge.setProperty("role", "badgeOpen")
            badge.setAlignment(Qt.AlignCenter)
            badge.setMinimumWidth(46)
            top.addWidget(badge, 0, Qt.AlignTop)
        else:
            reopen_btn = QPushButton(LABEL_REOPEN, self)
            reopen_btn.setProperty("role", "rowAction")
            reopen_btn.setCursor(Qt.PointingHandCursor)
            reopen_btn.clicked.connect(lambda: self.reopenRequested.emit(self.session_id))
            top.addWidget(reopen_btn, 0, Qt.AlignTop)

        root.addLayout(top)

        preview = QLabel(format_history_preview(session.preview), self)
        preview.setProperty("role", "rowPreview")
        preview.setWordWrap(False)
        root.addWidget(preview)

        meta = QLabel(
            f"{format_history_source(session.file_path, session.file_name)}  •  {'Open' if session.is_open else 'Closed'}  •  {format_history_updated(session.updated_at)}",
            self,
        )
        meta.setProperty("role", "rowMeta")
        meta.setWordWrap(False)
        root.addWidget(meta)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)


class HistoryPanel(QWidget):
    openRequested = Signal(int)
    deleteRequested = Signal(int)
    toggleRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyPanel")
        self.setMinimumWidth(340)
        self.setMaximumWidth(430)
        self.setStyleSheet(HISTORY_PANEL_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        eyebrow = QLabel(LABEL_SAVED_CHATS, self)
        eyebrow.setProperty("role", "eyebrow")
        header_row.addWidget(eyebrow, 0, Qt.AlignLeft)
        header_row.addStretch(1)
        self.collapse_btn = QToolButton(self)
        self.collapse_btn.setProperty("role", "collapse")
        self.collapse_btn.setText("‹")
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
        self.collapse_btn.setToolTip(TOOLTIP_HIDE_HISTORY_PANEL)
        self.collapse_btn.setFixedSize(30, 30)
        self.collapse_btn.clicked.connect(self.toggleRequested.emit)
        header_row.addWidget(self.collapse_btn, 0, Qt.AlignRight)
        root.addLayout(header_row)

        title = QLabel(LABEL_HISTORY, self)
        title.setProperty("role", "title")
        body = QLabel(HISTORY_PANEL_BODY, self)
        body.setProperty("role", "body")
        body.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(body)

        self.list = QListWidget(self)
        self.list.setSpacing(10)
        self.list.itemDoubleClicked.connect(lambda *_: self._request_open())
        self.list.currentItemChanged.connect(lambda *_: self._sync_selection_state())
        root.addWidget(self.list, 1)

        footer = QVBoxLayout()
        footer.setSpacing(8)
        self.count_label = QLabel("0 saved chats", self)
        self.count_label.setProperty("role", "body")
        footer.addWidget(self.count_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_btn = QPushButton(LABEL_OPEN_SELECTED, self)
        self.open_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.open_btn.clicked.connect(self._request_open)
        self.delete_btn = QPushButton(LABEL_DELETE, self)
        self.delete_btn.setStyleSheet(SUBTLE_BUTTON_STYLE)
        self.delete_btn.clicked.connect(self._request_delete)
        actions.addWidget(self.open_btn, 1)
        actions.addWidget(self.delete_btn, 1)
        footer.addLayout(actions)
        root.addLayout(footer)

    def set_sessions(self, sessions: Sequence[SessionSummary]) -> None:
        self.list.clear()
        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, session.session_id)
            item.setToolTip(
                f"{session.title or session.file_name or 'Untitled Chat'}\n"
                f"{format_history_source(session.file_path, session.file_name)}\n"
                f"{format_history_preview(session.preview, max_len=160)}"
            )
            row_widget = HistoryRowWidget(session, self.list)
            row_widget.reopenRequested.connect(self.openRequested.emit)
            row_size = row_widget.sizeHint()
            item.setSizeHint(QSize(0, max(118, row_size.height() + 8)))
            self.list.addItem(item)
            self.list.setItemWidget(item, row_widget)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.count_label.setText(history_count_text(self.list.count()))
        self._sync_selection_state()

    def selected_session_id(self) -> int | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return int(item.data(Qt.UserRole))

    def _sync_selection_state(self) -> None:
        current = self.list.currentItem()
        for index in range(self.list.count()):
            item = self.list.item(index)
            widget = self.list.itemWidget(item)
            if isinstance(widget, HistoryRowWidget):
                widget.set_selected(item is current)

    def _request_open(self) -> None:
        session_id = self.selected_session_id()
        if session_id is not None:
            self.openRequested.emit(session_id)

    def _request_delete(self) -> None:
        session_id = self.selected_session_id()
        if session_id is not None:
            self.deleteRequested.emit(session_id)
