import json, time
from markdown_it import MarkdownIt
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStatusBar, QApplication, QInputDialog
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

md = MarkdownIt()  # CommonMark; good enough for LLM output


class OllamaWorker(QThread):
    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            with requests.post(
                    OLLAMA_URL,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps({
                        "model": MODEL,
                        "prompt": self.prompt,
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
                        txt = obj.get("response", "")
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
        self.resize(1000, 700)

        self.code = code
        self.lang = lang_hint(file_name)

        # Top bar
        top = QHBoxLayout()
        btn = lambda label, fn: self._mk_btn(label, fn)
        top.addWidget(btn("Explain", self.do_explain))
        top.addWidget(btn("Refactor (diff)", self.do_refactor))
        top.addWidget(btn("Tests", self.do_tests))
        top.addWidget(btn("Custom…", self.do_custom))
        top.addStretch(1)
        self.model_lbl = QLabel(f"Model: {MODEL}")
        self.model_lbl.setStyleSheet("color:#9aa5b1;")
        top.addWidget(self.model_lbl)

        # Web view
        self.view = QWebEngineView()
        self.view.setHtml(HTML_TEMPLATE)

        # Status bar
        self.status = QStatusBar()
        self.status.showMessage("Ready")

        # Layout
        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.view, 1)
        root.addWidget(self.status)

        # Streaming state
        self._buf = []
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(80)  # ~12 fps; smooth and light
        self._render_timer.timeout.connect(self._render_flush)

        self._start_ts = 0.0
        self._chars = 0
        self._worker = None

        # Initial content
        self._set_html(md.render("Ready. Choose an action above.\n"))

    # Buttons
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
    def do_explain(self):
        self._run_task(ACTIONS["explain"])

    def do_refactor(self):
        self._run_task(ACTIONS["refactor"])

    def do_tests(self):
        self._run_task(ACTIONS["tests"])

    # Core
    def _run_task(self, task_text: str):
        if self._worker and self._worker.isRunning():
            return
        self._buf = [f"# Task\n{task_text}\n\n---\n"]
        self._chars = 0
        self._start_ts = time.time()
        self.status.showMessage("Generating…")
        prompt = build_prompt(task_text, self.code, self.lang)

        self._worker = OllamaWorker(prompt)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.error.connect(self._on_error)
        self._worker.done.connect(self._on_done)
        self._worker.start()
        self._render_timer.start()

    def _on_chunk(self, s: str):
        self._buf.append(s)
        self._chars += len(s)

    def _on_error(self, msg: str):
        self._buf.append(f"\n\n**Error:** {msg}\n")

    def _on_done(self):
        self._render_timer.stop()
        self._render_flush()
        elapsed = time.time() - self._start_ts
        cps = int(self._chars / elapsed) if elapsed > 0 else 0
        self.status.showMessage(f"Done in {elapsed:.1f}s | {self._chars} chars @ {cps} cps")

    def _render_flush(self):
        html = md.render("".join(self._buf))
        self._set_html(html)

    def _set_html(self, html: str):
        # Send HTML into the page and re-highlight
        js = f"setHtml({json.dumps(html)});"
        self.view.page().runJavaScript(js)

    def do_custom(self):
        text, ok = QInputDialog.getText(self, "Custom Instruction", "Enter your request:")
        if ok and text.strip():
            self._run_task(text.strip())