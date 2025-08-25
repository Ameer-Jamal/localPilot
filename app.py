import json
import time
from html import escape

import requests
from PySide6.QtGui import QTextOption, QFontMetricsF
from markdown_it import MarkdownIt
from PySide6.QtCore import QThread, Signal, QTimer, Qt, QSettings
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStatusBar,
    QInputDialog, QMainWindow, QTabWidget, QMessageBox, QSizePolicy, QTextEdit, QToolButton
)

from ollama_client import MODEL, TEMP, OLLAMA_URL
from utils import ACTIONS, lang_hint

HTML_TEMPLATE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/styles/github-dark.min.css">
<script src="https://cdn.jsdelivr.net/npm/@highlightjs/cdn-assets@11.9.0/highlight.min.js"></script>
<style>
  :root { --bg:#0f1115; --panel:#12161a; --text:#e6e6e6; --muted:#9aa5b1; --accent:#4ec9b0; }
  html, body { background: var(--bg); color: var(--text); margin:0; padding:0; }
  body { font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "JetBrains Mono", monospace; }
  #wrap { padding: 16px 18px; }
  h1,h2,h3{ color: var(--accent); margin: 14px 0 8px; }
  pre { background: #23272e; padding: 12px; border-radius: 8px; overflow:auto; }
  code { background: #23272e; padding: 2px 4px; border-radius: 4px; }
  .role { color: var(--muted); font-size: 12px; margin: 10px 0 4px; }
  hr { border:0; height:1px; background:#2b3137; margin:16px 0; }
</style>
<script>
  function setHtml(html) {
    const c = document.getElementById('wrap');
    c.innerHTML = html;
    try { hljs.highlightAll(); } catch(e) {}
    window.scrollTo(0, document.body.scrollHeight);
  }
</script>
</head><body><div id="wrap"></div></body></html>
"""

md = MarkdownIt()


class AutoResizingTextEdit(QTextEdit):
    """Multi-line input that grows/shrinks between min/max lines.
       Enter → newline, Cmd/Ctrl+Enter → send."""
    sendRequested = Signal()

    def __init__(self, parent=None, min_lines=1, max_lines=8):
        super().__init__(parent)
        self._min_lines = int(min_lines)
        self._max_lines = int(max_lines)
        self._pad = 15

        # plain text, dark theme friendly
        self.setAcceptRichText(False)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QTextEdit.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setPlaceholderText("Ask a follow-up…  (Cmd/Ctrl+Enter to send; Enter for newline)")
        self.setStyleSheet("QTextEdit { background:#1b1e22; color:#e6e6e6; border-radius:6px; padding:6px; }")

        # make wrapping height depend on viewport width
        self.document().setDocumentMargin(2)
        self.document().setTextWidth(self.viewport().width())

        # react to edits and layout changes
        self.textChanged.connect(self._schedule_adjust)
        self.document().documentLayout().documentSizeChanged.connect(lambda *_: self._schedule_adjust())

        self._adjust_height()

    # --- shortcuts ---
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and (e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            e.accept()
            self.sendRequested.emit()
            return
        super().keyPressEvent(e)

    # --- sizing ---
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.document().setTextWidth(self.viewport().width())
        self._schedule_adjust()

    def _schedule_adjust(self):
        QTimer.singleShot(0, self._adjust_height)

    def _line_h(self) -> float:
        # Ensure font metrics calculation is done correctly
        fm = QFontMetricsF(self.font())
        return fm.lineSpacing() if fm else 16.0

    def _adjust_height(self):
        doc_h = float(self.document().size().height())  # respects textWidth
        min_h = self._min_lines * self._line_h() + self._pad
        max_h = self._max_lines * self._line_h() + self._pad
        new_h = int(max(min_h, min(max_h, doc_h + self._pad)))
        self.setFixedHeight(new_h)
        self.updateGeometry()

    def reset_to_min(self):
        self.setFixedHeight(int(self._min_lines * self._line_h() + self._pad))
        self.updateGeometry()

class ChatWorker(QThread):
    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):
        try:
            with requests.post(
                    OLLAMA_URL.replace("/generate", "/chat"),
                    json={
                        "model": MODEL,
                        "messages": self.messages,
                        "options": {
                            "temperature": float(TEMP),
                            "num_ctx": 8192,  # allow larger prompts
                        },
                        "keep_alive": "10m",  # avoid -1; some builds reject it
                        "stream": True
                    },
                    stream=True,
                    timeout=(10, 600)
            ) as r:
                try:
                    r.raise_for_status()
                except requests.HTTPError as e:
                    try:
                        body: r.text
                    except Exception:
                        body = ""
                        self.error.emit(f"HTTP {r.status_code} : {body}")
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        msg = obj.get("message", {})
                        txt = msg.get("content", "") if msg else obj.get("response", "")
                    except json.JSONDecodeError:
                        txt = line
                    if txt:
                        self.chunk.emit(txt)
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {str(e)}")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.done.emit()


class SessionWidget(QWidget):
    asked = Signal()  # emitted whenever a question is sent
    """Single chat session pinned to a code selection."""

    def __init__(self, code: str, file_name: str):
        super().__init__()
        self.code = code
        self.lang = lang_hint(file_name)
        self.file_name = file_name
        self._worker = None

        # Conversation state
        self._build_system_message()

        # Top bar
        top = QHBoxLayout()
        # CHANGED: run in current tab
        top.addWidget(self._mk_btn("Explain", lambda: self.auto_run(ACTIONS["explain"])))
        top.addWidget(self._mk_btn("Refactor (diff)", lambda: self.auto_run(ACTIONS["refactor"])))
        top.addWidget(self._mk_btn("Tests", lambda: self.auto_run(ACTIONS["tests"])))
        top.addWidget(self._mk_btn("Custom…", self._do_custom))
        top.addStretch(1)
        self.model_lbl = QLabel(f"Model: {MODEL}")
        self.model_lbl.setStyleSheet("color:#9aa5b1;")
        top.addWidget(self.model_lbl)

        # Web view
        self.view = QWebEngineView()
        self.view.setHtml(HTML_TEMPLATE)
        self._page_ready = False
        self._pending_html = None
        self.view.loadFinished.connect(self._on_page_ready)

        # Input row
        bottom = QHBoxLayout()
        self.input = AutoResizingTextEdit(min_lines=1, max_lines=8)
        self.input.sendRequested.connect(self._send_message_same_tab)
        send_btn = self._mk_btn("Send", self._send_message_same_tab)
        stop_btn = self._mk_btn("Stop", self._stop_generation)
        bottom.addWidget(self.input, 1)
        bottom.addWidget(stop_btn)
        bottom.addWidget(send_btn)

        # Status bar
        self.status = QStatusBar()
        self.status.showMessage("Ready")

        # Layout
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.view, 1)
        root.addLayout(bottom)
        root.addWidget(self.status)

        # Streaming state
        self._render_buf = []
        self._html = []
        self._assistant_md = ""

        self._append_code_context_block()
        self._set_html("".join(self._html))

        self._render_timer = QTimer(self)  # create once here
        self._render_timer.setInterval(80)
        self._render_timer.timeout.connect(self._flush_render)

        self._start_ts = 0.0
        self._chars = 0
        self._flush_render(force=True)

    # ---------- public API ----------
    def auto_run(self, instruction: str):
        """Run a question directly in THIS tab (used when a new tab is created by MainWindow)."""
        if not instruction.strip() or self._busy():
            return
        self.asked.emit()  # <-- bring-to-front request
        self._user_say(instruction)
        self._chat()

    def focus_input(self):
        self.input.setFocus(Qt.TabFocusReason)

    # ---------- internal: new-tab requests ----------
    def _do_custom(self):
        text, ok = QInputDialog.getText(self, "Custom Instruction", "Enter your request:")
        if ok and text.strip():
            self.auto_run(text.strip())

    # ---------- conversation (auto-run path) ----------
    def _build_system_message(self):
        self.history = [{
            "role": "system",
            "content": (
                "You are a senior software engineer. Be concise and precise. "
                "Pinned code context follows.\n\n"
                f"```{self.lang}\n{self.code}\n```"
            ),
        }]

    def _user_say(self, text: str):
        self.history.append({"role": "user", "content": text})
        self._append_role_block("user", text)
        self._flush_render(force=True)

    def _chat(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()

        self._assistant_md = ""
        self._render_buf = []
        self.status.showMessage("Generating…")
        self._start_ts = time.time()
        self._chars = 0
        self._append_role_block("assistant", "")
        self._flush_render(force=True)

        self._worker = ChatWorker(self.history)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.error.connect(self._on_error)
        self._worker.done.connect(self._on_done)
        self._worker.start()
        self._render_timer.start()

    def _on_chunk(self, s: str):
        self._render_buf.append(s)
        self._assistant_md += s
        self._chars += len(s)

    def _on_error(self, msg: str):
        self._render_buf.append(f"\n\n**Error:** {msg}\n")

    def _on_done(self):
        self._render_timer.stop()
        self._flush_render(force=True)
        self.history.append({"role": "assistant", "content": self._assistant_md})
        self._html[0] = self._html[0].replace('<details open>', '<details>')
        elapsed = time.time() - self._start_ts
        cps = int(self._chars / elapsed) if elapsed > 0 else 0
        self.status.showMessage(f"Done in {elapsed:.1f}s | {self._chars} chars @ {cps} cps")

    # ------- rendering - ---------

    def _append_code_context_block(self):
        lang = self.lang or "plaintext"
        code_html = (
            f'<div class="role">system</div>'
            f'<details open>'
            f'<summary style="cursor:pointer">Pinned code context ({lang})</summary>'
            f'<pre><code class="language-{lang}">{escape(self.code)}</code></pre>'
            f'</details>'
            f'<hr/>'
        )
        self._html.append(code_html)

    def _append_role_block(self, role: str, content_md: str):
        label = {"system": "system", "user": "you", "assistant": "assistant"}.get(role, role)
        self._html.append(f'<div class="role">{label}</div>')
        self._html.append(md.render(content_md or ""))

    def _flush_render(self, force=False):
        if self._render_buf or force:
            if len(self._html) >= 2 and "assistant" in self._html[-2]:
                self._html[-1] = md.render(self._assistant_md)
            self._render_buf = []
            self._set_html("".join(self._html))

    def _on_page_ready(self, ok: bool):
        self._page_ready = bool(ok)
        if self._page_ready and self._pending_html is not None:
            self._really_set_html(self._pending_html)
            self._pending_html = None

    def _set_html(self, html: str):
        if not self._page_ready:
            self._pending_html = html
            return
        self._really_set_html(html)

    def _really_set_html(self, html: str):
        js = f"setHtml({json.dumps(html)});"
        self.view.page().runJavaScript(js)

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @staticmethod
    def _mk_btn(text, handler):
        b = QPushButton(text)
        b.setFixedHeight(36)
        b.clicked.connect(handler)
        b.setStyleSheet("""
            QPushButton { background:#22262b; color:#e6e6e6; border:none; padding:6px 14px; border-radius:8px; }
            QPushButton:hover { background:#2b3137; }
            QPushButton:pressed { background:#1e2328; }
        """)
        return b

    def _send_message_same_tab(self):
        text = self.input.toPlainText().strip()
        if not text or self._busy():
            return
        self.input.clear()
        self.input.reset_to_min()
        self.input.setFocus(Qt.TabFocusReason)
        self.asked.emit()
        self._user_say(text)
        self._chat()

    def _stop_generation(self):
        if self._worker and self._worker.isRunning():
            try:
                self._worker.terminate()
            except Exception:
                pass
            self._worker = None
            # finalize current partial text
            self._render_timer.stop()
            self._flush_render(force=True)
            if getattr(self, "_assistant_md", ""):
                self.history.append({"role": "assistant", "content": self._assistant_md})
            self.status.showMessage("Generation stopped")


class MainWindow(QMainWindow):
    """Holds tabs; each question opens a new SessionWidget tab."""

    def __init__(self, code: str, file_name: str):
        super().__init__()
        self._settings = QSettings("AskAboutSelection", "Assistant")
        self.setWindowTitle("Ask about selection - Ameer J.")
        self.resize(1100, 820)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)  # use handler below
        # ---- header bar (top-left pin) + tabs ----
        container = QWidget(self)
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QWidget(container)
        h = QHBoxLayout(header)
        h.setContentsMargins(8, 8, 8, 4)
        h.setSpacing(8)

        self._pin_btn = QPushButton("Pin: Off", header)
        # Load persisted state (default False)
        pinned = self._settings.value("ui/pin_on_top", False, type=bool)

        # Apply without emitting toggled
        self._pin_btn.blockSignals(True)
        self._pin_btn.setChecked(pinned)
        self._pin_btn.blockSignals(False)
        self._apply_pin(pinned)  # helper defined below

        self._pin_btn.setCheckable(True)
        self._pin_btn.setMinimumHeight(32)
        self._pin_btn.setStyleSheet("""
            QPushButton {
                background: #22262b; color: #e6e6e6; border: 1px solid #343a40;
                border-radius: 8px; padding: 6px 14px; font-weight: 600;
            }
            QPushButton:hover { background: #2b3137; }
            QPushButton:checked {
                background: #205b3b; border-color: #2a7a50; color: #eafff4;
            }
        """)
        self._pin_btn.toggled.connect(self._toggle_pin)

        h.addWidget(self._pin_btn, 0, Qt.AlignLeft)
        h.addStretch(1)

        v.addWidget(header, 0)  # top bar
        v.addWidget(self.tabs, 1)  # tabs below
        self.setCentralWidget(container)

        # status bar with a "Pin" toggle
        sb = self.statusBar()  # QMainWindow's own status bar
        sb.setSizeGripEnabled(False)

        sb.addPermanentWidget(self._pin_btn)

        self._server = None  # IPC server

        self.new_tab(code, file_name, select=True)

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

        # also focus the current tab's input after activation
        def _focus_current():
            w = self.tabs.currentWidget()
            if w and hasattr(w, "input"):
                w.input.setFocus(Qt.ActiveWindowFocusReason)

        QTimer.singleShot(0, _focus_current)

    # ---- tab ops ----
    def new_tab(self, code: str, file_name: str, select: bool = True):
        w = SessionWidget(code, file_name)
        w.asked.connect(self.bring_to_front)
        idx = self.tabs.addTab(w, file_name)
        if select:
            self.tabs.setCurrentIndex(idx)
        QTimer.singleShot(0, w.focus_input)

    # ---- IPC single-window ----
    def listen_ipc(self, socket_name: str):
        try:
            QLocalServer.removeServer(socket_name)
        except Exception:
            pass
        self._server = QLocalServer(self)
        if not self._server.listen(socket_name):
            return
        self._server.newConnection.connect(self._on_new_ipc_connection)

    def _apply_pin(self, checked: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
            self.show()
        self._pin_btn.setText("Pin: On" if checked else "Pin: Off")
        self.bring_to_front()

    def _toggle_pin(self, checked: bool):
        self._apply_pin(checked)
        self._settings.setValue("ui/pin_on_top", checked)

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
                    self.bring_to_front()  # <-- focus on external ask
        finally:
            sock.disconnectFromServer()

    def _on_tab_close(self, index: int):
        w = self.tabs.widget(index)
        title = self.tabs.tabText(index) or "Untitled"

        # Optional: warn if a generation is in progress for this tab
        busy_note = ""
        if hasattr(w, "_busy") and callable(w._busy) and w._busy():
            busy_note = "\nA response is still generating."

        reply = QMessageBox.question(
            self,
            "Close tab",
            f'Close tab “{title}”?{busy_note}',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # If you want to cancel an in-flight worker explicitly:
        try:
            if hasattr(w, "_worker") and w._worker and w._worker.isRunning():
                w._worker.terminate()
        except Exception:
            pass

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.close()
