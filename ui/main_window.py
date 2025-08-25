import json

from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QToolButton, QLabel, QMessageBox
)

from ui.session_widget import SessionWidget

SOCKET_NAME = "AskAboutSelectionSocket"


class MainWindow(QMainWindow):
    """Holds tabs; manages IPC; persistent Always-On-Top toggle with visible status."""
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

        # Header with Pin control (top-left)
        container = QWidget(self)
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QWidget(container)
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 8, 10, 4)
        h.setSpacing(8)

        # Small circular toggle
        self._pin_btn = QToolButton(header)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setFixedSize(18, 18)
        self._pin_btn.setCursor(Qt.PointingHandCursor)
        self._pin_btn.setToolTip("Keep window on top")
        self._pin_btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #343a40;
                border-radius: 9px;
                background: #3a3f44;           /* off */
            }
            QToolButton:hover { background: #454b52; }
            QToolButton:checked {
                background: #2ecc71;           /* on (green) */
                border-color: #24a65b;
            }
            QToolButton:checked:hover { background: #29c168; }
        """)
        self._pin_btn.toggled.connect(self._toggle_pin)

        # Visible status text
        self._pin_label = QLabel(header)
        self._pin_label.setStyleSheet("color:#c3c7cf; font-size:12px;")
        self._pin_label.setTextInteractionFlags(Qt.NoTextInteraction)
        self._pin_label.setToolTip("Always-on-top status")

        h.addWidget(self._pin_btn, 0, Qt.AlignLeft)
        h.addWidget(self._pin_label, 0, Qt.AlignLeft)
        h.addStretch(1)

        v.addWidget(header, 0)
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(container)

        self._server: QLocalServer | None = None

        # Restore pin state and apply
        pinned = self._settings.value("ui/pin_on_top", False, type=bool)
        self._pin_btn.blockSignals(True)
        self._pin_btn.setChecked(pinned)
        self._pin_btn.blockSignals(False)
        self._apply_pin(pinned)

        # First tab
        self.new_tab(code, file_name, select=True)

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
        self._pin_label.setText("Pin: On" if checked else "Pin: Off")
        # subtle color change for clarity
        self._pin_label.setStyleSheet(
            "color:#a8e4c8; font-size:12px;" if checked else "color:#c3c7cf; font-size:12px;"
        )

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
        if w and hasattr(w, "input"):
            w.input.setFocus(Qt.ActiveWindowFocusReason)

    # Tabs
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
                if code.strip():
                    self.new_tab(code, file_name, select=True)
                    self.bring_to_front()
        finally:
            sock.disconnectFromServer()
