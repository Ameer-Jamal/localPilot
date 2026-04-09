from __future__ import annotations

import json

from chat_logic import should_open_new_chat
from PySide6.QtCore import Qt, QTimer, QSettings, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QToolButton, QLabel, QMessageBox, QTabBar, QSplitter, QPushButton, QDialog
)

from config import APP_AUTHORLINE, APP_NAME, APP_ORG, APP_WINDOW_TITLE
from history_store import HistoryStore
from ollama_client import unload_tracked_models
from settings_store import SettingsStore
from ui.history_panel import HistoryPanel
from ui.settings_dialog import SettingsDialog
from ui.session_widget import SessionWidget
from ui.theme import (
    ACCENT_BUTTON_STYLE,
    APP_WINDOW_STYLE,
    EMPTY_STATE_STYLE,
    HISTORY_REVEAL_BUTTON_STYLE,
    PIN_BUTTON_STYLE,
    PRIMARY_BUTTON_STYLE,
    SUBTLE_BUTTON_STYLE,
)

SOCKET_NAME = "LocalPilot"


class BrowserTabBar(QTabBar):
    middleClicked = Signal(int)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.pos())
            if index >= 0:
                self.middleClicked.emit(index)
                event.accept()
                return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    """Holds tabs; manages IPC; persistent Always-On-Top toggle with visible status."""
    def __init__(
            self,
            code: str,
            file_name: str,
            file_path: str = "",
            *,
            history_store: HistoryStore | None = None,
    ):
        super().__init__()
        self.setWindowTitle(APP_AUTHORLINE)
        self.resize(1100, 820)
        self.history_store = history_store or HistoryStore()
        self.setStyleSheet(APP_WINDOW_STYLE)

        # Settings
        self._settings = QSettings(APP_ORG, APP_NAME)
        self._settings_store = SettingsStore(self._settings)
        self._apply_history_retention()

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabBar(BrowserTabBar(self.tabs))
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        self.tabs.tabBarClicked.connect(self._on_tab_clicked)
        self.tabs.tabBar().middleClicked.connect(self._on_tab_close)
        self._plus_tab = self._build_plus_placeholder()
        self._history_panel = HistoryPanel(self)
        self._history_panel.openRequested.connect(self._reopen_history_session)
        self._history_panel.deleteRequested.connect(self._delete_session_with_prompt)
        self._history_panel.toggleRequested.connect(self._hide_history_panel)
        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._history_panel)
        self._splitter.addWidget(self.tabs)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        # Header with Pin control (top-left)
        container = QWidget(self)
        container.setObjectName("appShell")
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QWidget(container)
        header.setObjectName("windowHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(10)

        # Small circular toggle
        self._pin_btn = QToolButton(header)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setFixedSize(20, 20)
        self._pin_btn.setCursor(Qt.PointingHandCursor)
        self._pin_btn.setToolTip("Keep window on top")
        self._pin_btn.setStyleSheet(PIN_BUTTON_STYLE)
        self._pin_btn.toggled.connect(self._toggle_pin)

        # Visible status text
        self._pin_label = QLabel(header)
        self._pin_label.setProperty("role", "muted")
        self._pin_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self._pin_label.setToolTip("Always-on-top status")

        self._brand_label = QLabel(APP_WINDOW_TITLE, header)
        self._brand_label.setProperty("role", "headerTitle")
        self._brand_label.setTextInteractionFlags(Qt.NoTextInteraction)

        self._history_btn = QToolButton(header)
        self._history_btn.setText("History")
        self._history_btn.setCheckable(True)
        self._history_btn.setCursor(Qt.PointingHandCursor)
        self._history_btn.setToolTip("Show saved chats")
        self._history_btn.setStyleSheet(SUBTLE_BUTTON_STYLE.replace("QPushButton", "QToolButton"))
        self._history_btn.toggled.connect(self._toggle_history_panel)

        self._settings_btn = QToolButton(header)
        self._settings_btn.setText("Settings")
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setToolTip("Open LocalPilot settings")
        self._settings_btn.setStyleSheet(SUBTLE_BUTTON_STYLE.replace("QPushButton", "QToolButton"))
        self._settings_btn.clicked.connect(self._open_settings_dialog)

        h.addWidget(self._pin_btn, 0, Qt.AlignLeft)
        h.addWidget(self._pin_label, 0, Qt.AlignLeft)
        h.addSpacing(10)
        h.addWidget(self._brand_label, 0, Qt.AlignLeft)
        h.addStretch(1)
        h.addWidget(self._settings_btn, 0, Qt.AlignRight)
        h.addWidget(self._history_btn, 0, Qt.AlignRight)

        v.addWidget(header, 0)
        v.addWidget(self._splitter, 1)
        self.setCentralWidget(container)

        self._history_reveal_btn = QToolButton(container)
        self._history_reveal_btn.setText("›")
        self._history_reveal_btn.setCursor(Qt.PointingHandCursor)
        self._history_reveal_btn.setToolTip("Show history panel")
        self._history_reveal_btn.setFixedSize(30, 46)
        self._history_reveal_btn.setStyleSheet(HISTORY_REVEAL_BUTTON_STYLE)
        self._history_reveal_btn.clicked.connect(lambda: self._history_btn.setChecked(True))
        self._history_reveal_btn.hide()
        self._history_reveal_btn.raise_()

        self._server: QLocalServer | None = None

        # Restore pin state and apply
        pinned = self._settings.value("ui/pin_on_top", False, type=bool)
        self._pin_btn.blockSignals(True)
        self._pin_btn.setChecked(pinned)
        self._pin_btn.blockSignals(False)
        self._apply_pin(pinned)

        restored = self._restore_open_sessions()
        if code or not restored:
            self.new_tab(code, file_name, file_path=file_path, select=True)
        elif restored:
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self._ensure_plus_tab()
        self._refresh_history_panel()
        show_history = self._settings.value("ui/show_history_panel", False, type=bool)
        self._history_btn.blockSignals(True)
        self._history_btn.setChecked(show_history)
        self._history_btn.blockSignals(False)
        self._toggle_history_panel(show_history)
        self._position_history_reveal()

    def _restore_open_sessions(self) -> bool:
        restored_any = False
        for session in self.history_store.load_open_sessions():
            self.new_tab(
                session.code,
                session.file_name,
                file_path=session.file_path,
                session_id=session.session_id,
                persisted_model=session.model,
                session_title=session.title,
                select=False,
            )
            restored_any = True
        return restored_any

    def _apply_history_retention(self):
        deleted_blank = self.history_store.delete_blank_sessions()
        history_settings = self._settings_store.get_history_settings()
        deleted = 0
        trimmed = 0
        if not history_settings.keep_forever:
            deleted = self.history_store.delete_closed_sessions_older_than(history_settings.delete_closed_after_days)
            trimmed = self.history_store.cap_total_sessions(history_settings.max_sessions)
        if deleted_blank or deleted or trimmed:
            self.history_store.vacuum()

    # Pin logic
    def _apply_pin(self, checked: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        if self.isVisible():  # re-apply flags on macOS
            self.hide()
            self.show()
        self._update_pin_label(checked)
        self.bring_to_front()

    def _toggle_pin(self, checked: bool):
        self._apply_pin(checked)
        self._settings.setValue("ui/pin_on_top", checked)

    def _update_pin_label(self, checked: bool):
        self._pin_label.setText("Always on Top" if checked else "Standard Window")
        self._pin_label.setProperty("role", "muted")
        self._pin_label.style().unpolish(self._pin_label)
        self._pin_label.style().polish(self._pin_label)

    # Focus
    def bring_to_front(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()
        try:
            wh = self.windowHandle()
            if wh is not None:
                wh.requestActivate()
        except Exception:
            pass
        QTimer.singleShot(0, self._focus_current)

    def _focus_current(self):
        w = self.tabs.currentWidget()
        if w and hasattr(w, "focus_input"):
            w.focus_input()
        elif w and hasattr(w, "input"):
            w.input.setFocus(Qt.ActiveWindowFocusReason)

    # Tabs
    def new_tab(
            self,
            code: str,
            file_name: str,
            *,
            file_path: str = "",
            session_id: int | None = None,
            persisted_model: str = "",
            session_title: str = "",
            select: bool = True,
    ):
        w = SessionWidget(
            code,
            file_name,
            file_path=file_path,
            history_store=self.history_store,
            session_id=session_id,
            persisted_model=persisted_model,
            session_title=session_title,
        )
        w.asked.connect(self.bring_to_front)
        w.settingsChanged.connect(self._reload_session_settings)
        w.historyCleared.connect(self._on_history_cleared)
        w.historyUpdated.connect(self._refresh_history_panel)
        w.titleChanged.connect(self._on_session_title_changed)
        insert_at = self._real_tab_insert_index()
        idx = self.tabs.insertTab(insert_at, w, w.display_title())
        self.tabs.setTabToolTip(idx, file_path or file_name or w.display_title())
        self._ensure_plus_tab()
        self._refresh_history_panel()
        if select:
            self.tabs.setCurrentIndex(idx)
        QTimer.singleShot(0, w.focus_input)

    def _open_empty_tab(self):
        self.new_tab("", "New Chat", session_title="New Chat", select=True)
        self.bring_to_front()

    def _build_plus_placeholder(self) -> QWidget:
        wrap = QWidget(self)
        wrap.setObjectName("emptyState")
        wrap.setStyleSheet(EMPTY_STATE_STYLE)
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(0)

        card = QWidget(wrap)
        card.setProperty("role", "emptyCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 34, 34, 34)
        card_layout.setSpacing(14)

        eyebrow = QLabel(APP_AUTHORLINE, card)
        eyebrow.setProperty("role", "emptyEyebrow")
        eyebrow.setAlignment(Qt.AlignCenter)

        title = QLabel("Start a new chat", card)
        title.setProperty("role", "emptyTitle")
        title.setAlignment(Qt.AlignCenter)

        body = QLabel(
            "Open a blank chat, review saved conversations, or adjust LocalPilot settings before you begin.",
            card,
        )
        body.setProperty("role", "emptyBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        body.setFixedWidth(460)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.setContentsMargins(0, 8, 0, 0)

        new_chat_btn = QPushButton("New Chat", card)
        new_chat_btn.setStyleSheet(ACCENT_BUTTON_STYLE)
        new_chat_btn.clicked.connect(self._open_empty_tab)

        settings_btn = QPushButton("Settings", card)
        settings_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        settings_btn.clicked.connect(self._open_settings_dialog)

        history_btn = QPushButton("Show History", card)
        history_btn.setStyleSheet(SUBTLE_BUTTON_STYLE)
        history_btn.clicked.connect(lambda: self._history_btn.setChecked(True))

        actions.addWidget(new_chat_btn)
        actions.addWidget(settings_btn)
        actions.addWidget(history_btn)

        layout.addStretch(1)
        card_layout.addWidget(eyebrow, 0, Qt.AlignCenter)
        card_layout.addWidget(title, 0, Qt.AlignCenter)
        card_layout.addWidget(body, 0, Qt.AlignCenter)
        card_layout.addLayout(actions)
        layout.addWidget(card, 0, Qt.AlignCenter)
        layout.addStretch(1)
        return wrap

    def _plus_tab_index(self) -> int:
        return self.tabs.indexOf(self._plus_tab)

    def _real_tab_insert_index(self) -> int:
        plus_index = self._plus_tab_index()
        return self.tabs.count() if plus_index == -1 else plus_index

    def _ensure_plus_tab(self):
        plus_index = self._plus_tab_index()
        if plus_index == -1:
            self.tabs.addTab(self._plus_tab, "+")
        elif plus_index != self.tabs.count() - 1:
            self.tabs.removeTab(plus_index)
            self.tabs.addTab(self._plus_tab, "+")
        plus_index = self._plus_tab_index()
        self.tabs.setTabToolTip(plus_index, "New chat")
        self.tabs.tabBar().setTabButton(plus_index, QTabBar.RightSide, None)
        self.tabs.tabBar().setTabButton(plus_index, QTabBar.LeftSide, None)

    def _on_tab_clicked(self, index: int):
        if should_open_new_chat(index, self._plus_tab_index()):
            self._open_empty_tab()

    def _reload_session_settings(self):
        self._reload_all_session_settings(origin=self.sender())

    def _reload_all_session_settings(self, origin=None):
        self._settings_store = SettingsStore(self._settings)
        self._apply_history_retention()
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if widget is origin:
                continue
            if hasattr(widget, "reload_settings"):
                widget.reload_settings()
        self._refresh_history_panel()

    def _on_history_cleared(self):
        origin = self.sender()
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if widget is self._plus_tab:
                continue
            if hasattr(widget, "reset_persistence"):
                widget.reset_persistence()
            if widget is not origin and hasattr(widget, "reload_settings"):
                widget.reload_settings()
        self._refresh_history_panel()

    def _open_settings_dialog(self):
        dialog = SettingsDialog(
            runtime=self._settings_store.get_runtime_settings(),
            quick_prompts=self._settings_store.get_quick_prompts(),
            confirm_close_tabs=self._settings_store.get_confirm_before_closing_tabs(),
            history=self._settings_store.get_history_settings(),
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        self._settings_store.save_runtime_settings(dialog.get_runtime_settings())
        self._settings_store.save_quick_prompts(dialog.get_quick_prompts())
        self._settings_store.set_confirm_before_closing_tabs(dialog.get_confirm_close_tabs())
        self._settings_store.save_history_settings(dialog.get_history_settings())
        if dialog.should_clear_history():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Clear Saved History")
            box.setText("Clear all saved chat history?")
            box.setInformativeText("This permanently deletes every saved chat. Open tabs will remain visible until "
                                   "you close them.")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            box.button(QMessageBox.Yes).setText("Clear History")
            box.button(QMessageBox.No).setText("Cancel")
            if box.exec() == QMessageBox.Yes:
                self.history_store.clear_all_history()
                self._on_history_cleared()
        self._reload_all_session_settings()

    def _find_open_tab_by_session_id(self, session_id: int) -> int:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if getattr(widget, "session_id", None) == session_id:
                return index
        return -1

    def _toggle_history_panel(self, visible: bool):
        self._history_panel.setVisible(visible)
        self._settings.setValue("ui/show_history_panel", visible)
        if visible:
            self._refresh_history_panel()
            self._splitter.setSizes([360, max(660, self.width() - 360)])
        else:
            self._splitter.setSizes([0, 1])
        self._history_reveal_btn.setVisible(not visible)
        self._position_history_reveal()

    def _hide_history_panel(self):
        self._history_btn.setChecked(False)

    def _position_history_reveal(self):
        if not hasattr(self, "_history_reveal_btn"):
            return
        header = self.centralWidget().findChild(QWidget, "windowHeader")
        header_height = header.height() if header is not None else 56
        content_height = max(0, self.height() - header_height)
        y = header_height + max(24, (content_height - self._history_reveal_btn.height()) // 2)
        self._history_reveal_btn.move(10, y)
        self._history_reveal_btn.raise_()

    def _refresh_history_panel(self):
        self._history_panel.set_sessions(self.history_store.load_recent_sessions(limit=250))

    def _on_session_title_changed(self, session_id: int, title: str):
        index = self._find_open_tab_by_session_id(session_id)
        if index >= 0:
            self.tabs.setTabText(index, title)
            widget = self.tabs.widget(index)
            tooltip = getattr(widget, "file_path", "") or getattr(widget, "file_name", "") or title
            self.tabs.setTabToolTip(index, tooltip)
        self._refresh_history_panel()

    def _reopen_history_session(self, session_id: int):
        existing_index = self._find_open_tab_by_session_id(session_id)
        if existing_index >= 0:
            self.tabs.setCurrentIndex(existing_index)
            self.bring_to_front()
            return
        session = self.history_store.get_session(session_id)
        if session is None:
            return
        self.history_store.reopen_session(session_id)
        self.new_tab(
            session.code,
            session.file_name,
            file_path=session.file_path,
            session_id=session.session_id,
            persisted_model=session.model,
            session_title=session.title,
            select=True,
        )
        self._refresh_history_panel()
        self.bring_to_front()

    def _delete_session_with_prompt(self, session_id: int):
        session = self.history_store.get_session(session_id)
        if session is None:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Delete Chat History")
        box.setText(f'Delete "{session.title or session.file_name or "Untitled Chat"}" from history?')
        box.setInformativeText("This permanently removes the saved chat transcript from LocalPilot.")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.button(QMessageBox.Yes).setText("Delete")
        box.button(QMessageBox.No).setText("Cancel")
        if box.exec() != QMessageBox.Yes:
            return
        open_index = self._find_open_tab_by_session_id(session_id)
        if open_index >= 0:
            widget = self.tabs.widget(open_index)
            if hasattr(widget, "session_id"):
                widget.session_id = None
            self.tabs.removeTab(open_index)
            self._ensure_plus_tab()
        self.history_store.delete_session(session_id)
        self._refresh_history_panel()

    def _on_tab_close(self, index: int):
        if index == self._plus_tab_index():
            return
        w = self.tabs.widget(index)
        title = self.tabs.tabText(index) or "Untitled"
        busy_note = "\nA response is still generating." if getattr(w, "_busy", None) and w._busy() else ""
        if self._settings_store.get_confirm_before_closing_tabs():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Close Chat")
            box.setText(f'Close "{title}"?')
            info = "You can open a new blank chat from the + tab."
            if busy_note:
                info += " A response is still generating and will be stopped."
            box.setInformativeText(info)
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            box.button(QMessageBox.Yes).setText("Close Tab")
            box.button(QMessageBox.No).setText("Keep Open")
            if box.exec() != QMessageBox.Yes:
                return
        try:
            if getattr(w, "_worker", None) and w._worker.isRunning():
                w._worker.stop()
                w._worker.wait()
        except Exception:
            pass
        if hasattr(w, "close_session"):
            w.close_session()
        self.tabs.removeTab(index)
        self._ensure_plus_tab()
        self._refresh_history_panel()

    # IPC (single window)
    def listen_ipc(self):
        try:
            QLocalServer.removeServer(SOCKET_NAME)
        except Exception:
            pass
        self._server = QLocalServer(self)
        if not self._server.listen(SOCKET_NAME):
            return
        self._server.newConnection.connect(self._on_new_ipc_connection)

    def _on_new_ipc_connection(self):
        sock = self._server.nextPendingConnection()
        sock.readyRead.connect(lambda s=sock: self._on_ipc_ready(s))

    def _on_ipc_ready(self, sock: QLocalSocket):
        try:
            raw = bytes(sock.readAll()).decode("utf-8", errors="replace")
            msg = json.loads(raw or "{}")
            if msg.get("cmd") == "open_session":
                code = msg.get("code", "")
                file_name = msg.get("file", "selection")
                file_path = msg.get("filepath", "")
                self.new_tab(code, file_name, file_path=file_path, select=True)
                self.bring_to_front()
        finally:
            sock.disconnectFromServer()

    def closeEvent(self, event):
        try:
            unload_tracked_models()
        except Exception:
            pass
        try:
            self.history_store.close()
        finally:
            super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_history_reveal()
