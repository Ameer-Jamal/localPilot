import json
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QMessageBox

from ui.session_widget import SessionWidget

SOCKET_NAME = "AskAboutSelectionSocket"

class MainWindow(QMainWindow):
    """Holds tabs; manages IPC; supports a persistent Always-On-Top 'Pin' toggle."""
    def __init__(self, code: str, file_name: str):
        super().__init__()
        self.setWindowTitle("Ask about selection")
        self.resize(1100, 820)

        # Settings
        self._settings = QSettings("AskAboutSelection", "Assistant")

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)

        # Header with Pin toggle (top-left)
        container = QWidget(self)
        v = QVBoxLayout(container); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        header = QWidget(container)
        h = QHBoxLayout(header); h.setContentsMargins(8, 8, 8, 4); h.setSpacing(8)

        self._pin_btn = QPushButton("Pin: Off", header)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setMinimumHeight(32)
        self._pin_btn.setStyleSheet("""
            QPushButton {
                background:#22262b; color:#e6e6e6; border:1px solid #343a40;
                border-radius:8px; padding:6px 14px; font-weight:600;
            }
            QPushButton:hover { background:#2b3137; }
            QPushButton:checked { background:#205b3b; border-color:#2a7a50; color:#eafff4; }
        """)
        self._pin_btn.toggled.connect(self._toggle_pin)

        h.addWidget(self._pin_btn, 0, Qt.AlignLeft)
        h.addStretch(1)
        v.addWidget(header, 0)
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(container)

        self._server: QLocalServer | None = None

        # restore pin state
        pinned = self._settings.value("ui/pin_on_top", False, type=bool)
        self._pin_btn.blockSignals(True)
        self._pin_btn.setChecked(pinned)
        self._pin_btn.blockSignals(False)
        self._apply_pin(pinned)

        # first tab
        self.new_tab(code, file_name, select=True)

    # pin
    def _apply_pin(self, checked: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        if self.isVisible():  # macOS needs hide/show to apply new flags
            self.hide(); self.show()
        self._pin_btn.setText("Pin: On" if checked else "Pin: Off")
        self.bring_to_front()

    def _toggle_pin(self, checked: bool):
        self._apply_pin(checked)
        self._settings.setValue("ui/pin_on_top", checked)

    # focus
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
        if w and hasattr(w, "input"):
            w.input.setFocus(Qt.ActiveWindowFocusReason)

    # tabs
    def new_tab(self, code: str, file_name: str, select: bool = True):
        w = SessionWidget(code, file_name)
        w.asked.connect(self.bring_to_front)
        idx = self.tabs.addTab(w, file_name or "selection")
        if select:
            self.tabs.setCurrentIndex(idx)
        QTimer.singleShot(0, w.focus_input)

    def _on_tab_close(self, index: int):
        w = self.tabs.widget(index)
        title = self.tabs.tabText(index) or "Untitled"
        busy_note = "\nA response is still generating." if getattr(w, "_busy", None) and w._busy() else ""
        if QMessageBox.question(
            self, "Close tab", f'Close tab “{title}”?{busy_note}',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            if getattr(w, "_worker", None) and w._worker.isRunning():
                w._worker.terminate()
        except Exception:
            pass
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.close()

    # IPC (single window; other invocations can send JSON to open a new tab)
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
                if code.strip():
                    self.new_tab(code, file_name, select=True)
                    self.bring_to_front()
        finally:
            sock.disconnectFromServer()