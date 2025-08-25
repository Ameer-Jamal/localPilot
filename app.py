import json, time
from markdown_it import MarkdownIt
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStatusBar,
    QApplication, QInputDialog, QLineEdit
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from utils import ACTIONS, build_prompt, lang_hint
from ollama_client import MODEL, TEMP, OLLAMA_URL

import requests

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

class ChatWorker(QThread):
    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, messages):
        super().__init__()
        self._assistant_md = ""  # cumulative assistant markdown for the current turn
        self.messages = messages  # list[{"role": "...", "content": "..."}]

    def run(self):
        try:
            with requests.post(
                OLLAMA_URL.replace("/generate", "/chat"),
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "model": MODEL,
                    "messages": self.messages,
                    "options": {"temperature": TEMP},
                    "stream": True
                }),
                stream=True, timeout=300
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        msg = obj.get("message", {})  # {role, content}
                        txt = msg.get("content", "") if msg else obj.get("response", "")
                    except json.JSONDecodeError:
                        txt = line
                    if txt:
                        self.chunk.emit(txt)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.done.emit()

class App(QWidget):
    def __init__(self, code: str, file_name: str):
        super().__init__()
        self.setWindowTitle("Ask about selection")
        self.resize(1000, 760)

        self.code = code
        self.lang = lang_hint(file_name)

        # Conversation state (system prompt pins code context)
        self.history = [
            {
                "role": "system",
                "content": (
                    "You are a senior software engineer. Be concise and precise. "
                    "When returning edits, prefer minimal code blocks. "
                    "Pinned code context follows; refer to it as 'the provided code'.\n\n"
                    f"```{self.lang}\n{self.code}\n```"
                ),
            }
        ]

        # Top bar (actions)
        top = QHBoxLayout()
        top.addWidget(self._mk_btn("Explain", lambda: self._run_instruction(ACTIONS["explain"])))
        top.addWidget(self._mk_btn("Refactor (diff)", lambda: self._run_instruction(ACTIONS["refactor"])))
        top.addWidget(self._mk_btn("Tests", lambda: self._run_instruction(ACTIONS["tests"])))
        top.addWidget(self._mk_btn("Custom…", self._do_custom))
        top.addStretch(1)
        self.model_lbl = QLabel(f"Model: {MODEL}")
        self.model_lbl.setStyleSheet("color:#9aa5b1;")
        top.addWidget(self.model_lbl)

        # Web view transcript
        self.view = QWebEngineView()
        self.view.setHtml(HTML_TEMPLATE)

        # Chat input row
        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask a follow-up…  (Enter to send)")
        self.input.returnPressed.connect(self._send_message)
        send_btn = self._mk_btn("Send", self._send_message)
        reset_btn = self._mk_btn("Reset", self._reset_chat)
        bottom.addWidget(self.input, 1)
        bottom.addWidget(send_btn)
        bottom.addWidget(reset_btn)

        # Status bar
        self.status = QStatusBar()
        self.status.showMessage("Ready")

        # Root layout
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.view, 1)
        root.addLayout(bottom)
        root.addWidget(self.status)

        # Streaming buffer and timers
        self._render_buf = []     # current assistant chunk buffer
        self._html = []           # full HTML transcript sections
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(80)
        self._render_timer.timeout.connect(self._flush_render)

        self._worker = None
        self._start_ts = 0.0
        self._chars = 0

        # Seed transcript
        self._append_role_block("system", "Pinned code context loaded.")
        self._flush_render(force=True)

    # UI helpers
    def _mk_btn(self, text, handler):
        b = QPushButton(text)
        b.setFixedHeight(36)
        b.clicked.connect(handler)
        b.setStyleSheet("""
            QPushButton { background:#22262b; color:#e6e6e6; border:none; padding:6px 14px; border-radius:8px; }
            QPushButton:hover { background:#2b3137; }
            QPushButton:pressed { background:#1e2328; }
        """)
        return b

    # Actions
    def _run_instruction(self, instruction: str):
        if not instruction.strip() or self._busy(): return
        self._user_say(instruction)
        self._chat()

    def _do_custom(self):
        text, ok = QInputDialog.getText(self, "Custom Instruction", "Enter your request:")
        if ok and text.strip():
            self._run_instruction(text.strip())

    def _send_message(self):
        text = self.input.text().strip()
        if not text or self._busy(): return
        self.input.clear()
        self._user_say(text)
        self._chat()

    def _reset_chat(self):
        if self._busy(): return
        self.history = [
            {
                "role": "system",
                "content": (
                    "You are a senior software engineer. Be concise and precise. "
                    "Pinned code context follows.\n\n"
                    f"```{self.lang}\n{self.code}\n```"
                ),
            }
        ]
        self._html = []
        self._append_role_block("system", "Conversation reset. Code context pinned.")
        self._flush_render(force=True)
        self.status.showMessage("Reset")

    # Conversation plumbing
    def _user_say(self, text: str):
        self.history.append({"role": "user", "content": text})
        self._append_role_block("user", text)
        self._flush_render(force=True)

    def _chat(self):
        self._assistant_md = ""
        self._render_buf = []
        self.status.showMessage("Generating…")
        self._start_ts = time.time()
        self._chars = 0
        self._render_buf = []
        self._append_role_block("assistant", "")  # start a new assistant block
        self._flush_render(force=True)

        self._worker = ChatWorker(self.history)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.error.connect(self._on_error)
        self._worker.done.connect(self._on_done)
        self._worker.start()
        self._render_timer.start()

    def _on_chunk(self, s: str):
        self._render_buf.append(s)  # small buffer to throttle UI refreshes
        self._assistant_md += s  # full cumulative assistant message
        self._chars += len(s)

    def _on_error(self, msg: str):
        self._render_buf.append(f"\n\n**Error:** {msg}\n")

    def _on_done(self):
        self._render_timer.stop()
        self._flush_render(force=True)
        # Save the full accumulated assistant text into chat history
        self.history.append({"role": "assistant", "content": self._assistant_md})
        elapsed = time.time() - self._start_ts
        cps = int(self._chars / elapsed) if elapsed > 0 else 0
        self.status.showMessage(f"Done in {elapsed:.1f}s | {self._chars} chars @ {cps} cps")

    # Rendering
    def _append_role_block(self, role: str, content_md: str):
        label = {"system": "system", "user": "you", "assistant": "assistant"}.get(role, role)
        self._html.append(f'<div class="role">{label}</div>')
        self._html.append(md.render(content_md or ""))

    def _extract_last_assistant_markdown(self):
        # last blocks are: <div class="role">assistant</div>, <rendered md ...>
        if len(self._html) >= 2 and "assistant" in self._html[-2]:
            return [self._html[-1].replace("</p>", "").replace("<p>", "")]
        return [""]

    def _flush_render(self, force=False):
        if self._render_buf or force:
            if len(self._html) >= 2 and "assistant" in self._html[-2]:
                # Render the full accumulated assistant markdown
                self._html[-1] = md.render(self._assistant_md)
            self._render_buf = []
            html = "".join(self._html)
            self._set_html(html)

    def _set_html(self, html: str):
        js = f"setHtml({json.dumps(html)});"
        self.view.page().runJavaScript(js)

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()
