import json
import time
from html import escape

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStatusBar, QInputDialog
from markdown_it import MarkdownIt

from config import MODEL
from resources.html_template import HTML_TEMPLATE
from ui.input_widget import AutoResizingTextEdit
from utils import ACTIONS, lang_hint
from workers.chat_worker import ChatWorker

md = MarkdownIt()


class SessionWidget(QWidget):
    """One chat session pinned to a specific code selection."""
    asked = Signal()  # emitted whenever a question is sent (used to bring window to front)

    def __init__(self, code: str, file_name: str):
        super().__init__()
        self.code = code
        self.lang = lang_hint(file_name)
        self.file_name = file_name

        # Conversation state
        self._build_system_message()

        # Top bar
        top = QHBoxLayout()
        top.addWidget(self._mk_btn("Explain", lambda: self.auto_run(ACTIONS["explain"])))
        top.addWidget(self._mk_btn("Refactor (diff)", lambda: self.auto_run(ACTIONS["refactor"])))
        top.addWidget(self._mk_btn("Tests", lambda: self.auto_run(ACTIONS["tests"])))
        top.addWidget(self._mk_btn("Custom…", self._do_custom))
        top.addStretch(1)
        self.model_lbl = QLabel(f"Model: {MODEL}")
        self.model_lbl.setStyleSheet("color:#9aa5b1;")
        top.addWidget(self.model_lbl)

        # Transcript view
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

        # Root layout
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.view, 1)
        root.addLayout(bottom)
        root.addWidget(self.status)

        # Streaming state
        self._render_buf: list[str] = []
        self._html: list[str] = []
        self._assistant_md = ""
        self._append_code_context_block()
        self._set_html("".join(self._html))

        self._render_timer = QTimer(self)
        self._render_timer.setInterval(80)
        self._render_timer.timeout.connect(self._flush_render)

        self._worker: ChatWorker | None = None
        self._start_ts = 0.0
        self._chars = 0

        self._flush_render(force=True)

    # public API
    def auto_run(self, instruction: str):
        if not instruction.strip() or self._busy():
            return
        self.asked.emit()
        self._user_say(instruction)
        self._chat()

    def focus_input(self):
        self.input.setFocus(Qt.TabFocusReason)

    # conversation plumbing
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
        self._flush_render(True)

    def _chat(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()

        self._assistant_md = ""
        self._render_buf = []
        self.status.showMessage("Generating…")
        self._start_ts = time.time()
        self._chars = 0
        self._append_role_block("assistant", "")
        self._flush_render(True)

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
        self._flush_render(True)
        self.history.append({"role": "assistant", "content": self._assistant_md})
        elapsed = time.time() - self._start_ts
        cps = int(self._chars / elapsed) if elapsed > 0 else 0
        self.status.showMessage(f"Done in {elapsed:.1f}s | {self._chars} chars @ {cps} cps")

    # rendering
    def _append_code_context_block(self):
        lang = self.lang or "plaintext"
        self._html.append('<div class="role">system</div>')
        self._html.append(
            f'<details open>'
            f'<summary style="cursor:pointer">Pinned code context ({lang})</summary>'
            f'<pre><code class="language-{lang}">{escape(self.code)}</code></pre>'
            f'</details><hr/>'
        )

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
        if not hasattr(self, "_page_ready") or not self._page_ready:
            self._pending_html = html
            return
        self._really_set_html(html)

    def _really_set_html(self, html: str):
        js = f"setHtml({json.dumps(html)});"
        self.view.page().runJavaScript(js)

    # actions
    def _do_custom(self):
        text, ok = QInputDialog.getText(self, "Custom Instruction", "Enter your request:")
        if ok and text.strip():
            self.auto_run(text.strip())

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
            self._render_timer.stop()
            self._flush_render(True)
            if getattr(self, "_assistant_md", ""):
                self.history.append({"role": "assistant", "content": self._assistant_md})
            self.status.showMessage("Generation stopped")

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
