from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from html import escape

from PySide6.QtCore import Qt, QTimer, Signal, QSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStatusBar,
    QComboBox,
    QDialog,
    QMessageBox,
)
from markdown_it import MarkdownIt

from chat_logic import (
    has_meaningful_messages,
    should_finalize_pending_assistant,
    should_persist_initial_session,
)
from config import APP_NAME, APP_ORG, MODEL
from history_store import HistoryStore
from ollama_client import warm_up_model
from resources.html_template import HTML_TEMPLATE
from settings_store import (
    SettingsStore,
    fetch_ollama_models,
    get_saved_chat_model,
    is_ollama_running,
)
from ui.input_widget import AutoResizingTextEdit
from ui.settings_dialog import SettingsDialog
from ui.theme import ACCENT_BUTTON_STYLE, PRIMARY_BUTTON_STYLE, SUBTLE_BUTTON_STYLE
from utils import lang_hint
from workers.chat_worker import ChatWorker
from workers.title_worker import TitleWorker

md = MarkdownIt()
LEGACY_SETTINGS_ORG = "AskAboutSelection"


class SessionWidget(QWidget):
    """One chat session pinned to a specific code selection."""
    asked = Signal()  # emitted whenever a question is sent (used to bring window to front)
    settingsChanged = Signal()
    historyCleared = Signal()
    historyUpdated = Signal()
    titleChanged = Signal(int, str)

    def __init__(
            self,
            code: str,
            file_name: str,
            *,
            file_path: str = "",
            history_store: HistoryStore,
            session_id: int | None = None,
            persisted_model: str = "",
            session_title: str = "",
    ):
        super().__init__()
        self.code = code
        self.lang = lang_hint(file_name)
        self.file_name = file_name
        self.file_path = file_path
        self.title = (session_title or file_name or "New Chat").strip() or "Untitled Chat"
        self.history_store = history_store
        self.session_id = session_id
        self._preferred_model = persisted_model or MODEL
        self._assistant_persisted = False
        self._generation_stopped = False
        self._allow_auto_title = session_id is None
        self._settings_store = SettingsStore()
        self._runtime_settings = self._settings_store.get_runtime_settings()
        self._quick_prompts = self._settings_store.get_quick_prompts()
        self._title_worker: TitleWorker | None = None

        # Conversation state
        if session_id is not None:
            self.history = self.history_store.load_messages(session_id)
            if not self.history:
                self._build_system_message()
        else:
            self._build_system_message()

        # Settings for persisting model selection
        self._settings = QSettings(APP_ORG, APP_NAME)

        # Initialize Status bar FIRST (as moved in previous fix)
        self.status = QStatusBar()
        self.status.showMessage("Ready")

        # Top bar
        toolbar = QWidget(self)
        toolbar.setObjectName("windowHeader")
        top = QHBoxLayout(toolbar)
        top.setContentsMargins(14, 12, 14, 12)
        top.setSpacing(10)
        self._quick_prompt_layout = QHBoxLayout()
        self._quick_prompt_layout.setSpacing(6)
        top.addLayout(self._quick_prompt_layout)
        top.addStretch(1)

        # Model selector and label
        self.model_lbl = QLabel()
        self.model_lbl.setProperty("role", "muted")
        self.model_lbl.setText("Model")

        self.model_combo = QComboBox()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

        # Refresh button
        self.refresh_btn = self._mk_btn("Refresh", self._setup_model_selector, variant="subtle")
        self.refresh_btn.setVisible(False)

        # Run Ollama button
        self.run_ollama_btn = self._mk_btn("Start Ollama", self._run_ollama_server, variant="subtle")
        self.run_ollama_btn.setVisible(False)

        # Install default model button
        self.install_model_btn = self._mk_btn("Install Model", self._install_default_model, variant="accent")
        self.install_model_btn.setVisible(False)

        self.settings_btn = self._mk_btn("Settings", self._open_settings_dialog, variant="subtle")

        top.addWidget(self.model_lbl)
        top.addWidget(self.model_combo)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.run_ollama_btn)
        top.addWidget(self.install_model_btn)
        top.addWidget(self.settings_btn)

        self._rebuild_quick_prompt_buttons()
        self._setup_model_selector()
        self.warm_up()

        # Transcript view
        self.view = QWebEngineView()
        self.view.setHtml(HTML_TEMPLATE)
        self._page_ready = False
        self._pending_html = None
        self.view.loadFinished.connect(self._on_page_ready)

        # Input row
        bottom = QHBoxLayout()
        self.input = AutoResizingTextEdit(min_lines=2, max_lines=8)
        self.input.sendRequested.connect(self._send_message_same_tab)
        send_btn = self._mk_btn("Send", self._send_message_same_tab, variant="accent")
        stop_btn = self._mk_btn("Stop", self._stop_generation, variant="subtle")
        bottom.addWidget(self.input, 1)
        bottom.addWidget(stop_btn)
        bottom.addWidget(send_btn)

        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(toolbar)
        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self.view, 1)
        bottom_wrap = QWidget(content)
        bottom_wrap.setObjectName("windowHeader")
        bottom_layout = QHBoxLayout(bottom_wrap)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(10)
        bottom_layout.addLayout(bottom, 1)
        content_layout.addWidget(bottom_wrap)
        root.addWidget(content, 1)
        root.addWidget(self.status)

        # Streaming state
        self._render_buf: list[str] = []
        self._html: list[str] = []
        self._assistant_md = ""
        self._restore_transcript()

        self._render_timer = QTimer(self)
        self._render_timer.setInterval(80)
        self._render_timer.timeout.connect(self._flush_render)

        self._worker: ChatWorker | None = None
        self._start_ts = 0.0
        self._chars = 0

        if should_persist_initial_session(self.code, self.history):
            self._ensure_session()
        self._flush_render(force=True)

    def _get_current_available_models(self) -> list[str]:
        """
        Fetches the current list of Ollama models by calling the function
        from config.py.
        """
        self._runtime_settings = self._settings_store.get_runtime_settings()
        return fetch_ollama_models(self._runtime_settings)

    def _setup_model_selector(self):
        """
        Configures the model combobox and refresh button based on currently
        available Ollama models.
        """
        current_model_list = self._get_current_available_models()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        if current_model_list:
            self.model_combo.addItems(current_model_list)
            saved_model = get_saved_chat_model(self._settings)
            if not saved_model:
                saved_model = QSettings(LEGACY_SETTINGS_ORG, APP_NAME).value("chat/model", MODEL, type=str)
            preferred = next(
                (model for model in (self._preferred_model, saved_model, MODEL) if model in current_model_list),
                current_model_list[0],
            )
            self.model_combo.setCurrentText(preferred)
            self.model_combo.setEnabled(True)
            self._on_model_changed(self.model_combo.currentText())
            self.status.showMessage("Ready")
            self.refresh_btn.setVisible(False)
            self.run_ollama_btn.setVisible(False)
            self.install_model_btn.setVisible(False)
        else:
            server_up = is_ollama_running(self._runtime_settings)
            self.model_combo.addItem("No Ollama Models Found")
            self.model_combo.setCurrentIndex(0)
            self.model_combo.setEnabled(False)
            if server_up:
                self.status.showMessage(
                    f"No Ollama models found. Install one with `ollama pull {self._runtime_settings.default_pull_model}` or click Install Model."
                )
            else:
                self.status.showMessage("Ollama server not running. Click Run Ollama to start it.")
            self.refresh_btn.setVisible(True)
            self.run_ollama_btn.setVisible(not server_up)
            self.install_model_btn.setVisible(server_up)
        self.model_combo.blockSignals(False)

    def _run_ollama_server(self):
        """Attempt to start the Ollama server with predefined settings."""
        env = os.environ.copy()
        env.update(self._runtime_settings.serve_env)
        cmd = shutil.which("ollama") or "/opt/homebrew/opt/ollama/bin/ollama"
        try:
            subprocess.Popen(
                [cmd, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.status.showMessage("Ollama server starting…")
            self.run_ollama_btn.setVisible(False)
            self._begin_ollama_refresh()
        except Exception as exc:
            self.status.showMessage(f"Failed to start Ollama: {exc}")

    def _install_default_model(self):
        cmd = shutil.which("ollama") or "/opt/homebrew/opt/ollama/bin/ollama"
        try:
            subprocess.Popen(
                [cmd, "pull", self._runtime_settings.default_pull_model],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.status.showMessage(f"Installing {self._runtime_settings.default_pull_model}…")
            self.install_model_btn.setVisible(False)
            self._begin_ollama_refresh(attempts=60)
        except Exception as exc:
            self.status.showMessage(f"Failed to install model: {exc}")

    def _begin_ollama_refresh(self, *, attempts: int = 20, delay_ms: int = 1500):
        def _poll(remaining: int) -> None:
            self._setup_model_selector()
            if self._get_current_available_models() or remaining <= 1:
                return
            QTimer.singleShot(delay_ms, lambda: _poll(remaining - 1))

        QTimer.singleShot(delay_ms, lambda: _poll(attempts))

    def _rebuild_quick_prompt_buttons(self):
        while self._quick_prompt_layout.count():
            item = self._quick_prompt_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for label, prompt in self._quick_prompts.items():
            button = self._mk_btn(label, lambda checked=False, p=prompt: self.auto_run(p), variant="subtle")
            self._quick_prompt_layout.addWidget(button)

    def _open_settings_dialog(self):
        dialog = SettingsDialog(
            runtime=self._runtime_settings,
            quick_prompts=self._quick_prompts,
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
            box.setInformativeText("This permanently deletes every saved chat. Open tabs will remain visible until you close them.")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            box.button(QMessageBox.Yes).setText("Clear History")
            box.button(QMessageBox.No).setText("Cancel")
            if box.exec() == QMessageBox.Yes:
                self.history_store.clear_all_history()
                self.historyCleared.emit()
        self.reload_settings()
        self.settingsChanged.emit()

    def reload_settings(self):
        self._runtime_settings = self._settings_store.get_runtime_settings()
        self._quick_prompts = self._settings_store.get_quick_prompts()
        self._rebuild_quick_prompt_buttons()
        self._setup_model_selector()

    # public API
    def auto_run(self, instruction: str):
        if not instruction.strip() or self._busy():
            return
        self.asked.emit()
        self._user_say(instruction)
        self._chat()

    def focus_input(self):
        self.warm_up()
        self.input.setFocus(Qt.TabFocusReason)

    def warm_up(self):
        model = self._selected_model()
        if model:
            warm_up_model(model)

    # conversation plumbing
    def _build_system_message(self):
        base = "You are a senior software engineer. Be concise and precise."
        location = self.file_path or self.file_name
        if self.code.strip():
            content = (
                base + f" Source file: {location}.\nPinned code context follows.\n\n" +
                f"```{self.lang}\n{self.code}\n```"
            )
        else:
            content = base
        self.history = [{"role": "system", "content": content}]

    def _restore_transcript(self):
        self._append_code_context_block()
        for msg in self.history:
            if msg.get("role") == "system":
                continue
            self._append_role_block(msg.get("role", "user"), msg.get("content", ""))
        self._set_html("".join(self._html))

    def _ensure_session(self):
        if self.session_id is not None:
            return
        self.session_id = self.history_store.create_session(
            title=self.title,
            file_name=self.file_name,
            file_path=self.file_path,
            code=self.code,
            model=self._selected_model(),
            messages=self.history,
            is_open=True,
        )

    def _selected_model(self) -> str:
        model = self.model_combo.currentText().strip()
        return "" if not model or model == "No Ollama Models Found" else model

    def display_title(self) -> str:
        return self.title or self.file_name or "Untitled Chat"

    def _set_title(self, title: str) -> None:
        cleaned = title.strip()
        if not cleaned or cleaned == self.title:
            return
        self.title = cleaned
        if self.session_id is not None:
            self.history_store.update_session_title(self.session_id, cleaned)
            self.historyUpdated.emit()
            self.titleChanged.emit(self.session_id, cleaned)

    def _maybe_generate_title(self) -> None:
        if not self._allow_auto_title:
            return
        if self._title_worker is not None and self._title_worker.isRunning():
            return
        model = self._selected_model()
        if not model:
            return
        self._title_worker = TitleWorker(
            list(self.history),
            model=model,
            file_name=self.file_name,
            file_path=self.file_path,
        )
        self._title_worker.done.connect(self._on_title_ready)
        self._title_worker.start()

    def _on_title_ready(self, title: str) -> None:
        worker = self._title_worker
        self._title_worker = None
        if worker is not None:
            worker.deleteLater()
        cleaned = title.strip()
        if cleaned:
            self._set_title(cleaned)
            self._allow_auto_title = False

    def _user_say(self, text: str):
        self.history.append({"role": "user", "content": text})
        already_persisted = self.session_id is not None
        self._ensure_session()
        if already_persisted and self.session_id is not None:
            self.history_store.append_message(self.session_id, "user", text)
            self.historyUpdated.emit()
        elif self.session_id is not None:
            self.historyUpdated.emit()
        self._append_role_block("user", text)
        self._flush_render(True)

    def _chat(self):
        model = self._selected_model()
        if not model:
            self.status.showMessage("No Ollama models available to chat with.")
            return

        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()

        self._assistant_md = ""
        self._render_buf = []
        self._assistant_persisted = False
        self._generation_stopped = False
        self.status.showMessage(f"Generating with {model}…")
        self._start_ts = time.time()
        self._chars = 0
        self._append_role_block("assistant", "")
        self._flush_render(True)

        self._active_model = model
        self._worker = ChatWorker(self.history, model=model)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.error.connect(self._on_error)
        self._worker.done.connect(self._on_done)
        self._worker.start()
        self._render_timer.start()

    def _on_chunk(self, s: str):
        self._render_buf.append(s)
        self._assistant_md += s
        self._chars += len(s)

    def _on_model_changed(self, model: str):
        self._settings.setValue("chat/model", model)
        self._preferred_model = model
        if self.session_id is not None and model and model != "No Ollama Models Found":
            self.history_store.update_session_model(self.session_id, model)

    def _on_error(self, msg: str):
        rendered = f"\n\n**Error:** {msg}\n"
        self._render_buf.append(rendered)
        self._assistant_md += rendered

    def _on_done(self):
        self._render_timer.stop()
        self._flush_render(True)
        if self._assistant_md:
            self._finalize_assistant_message()
        elapsed = time.time() - self._start_ts
        cps = int(self._chars / elapsed) if elapsed > 0 else 0
        model = getattr(self, "_active_model", self.model_combo.currentText())
        self.status.showMessage(
            f"Done in {elapsed:.1f}s | {self._chars} chars @ {cps} cps | {model}"
        )

    def _finalize_assistant_message(self):
        if self._assistant_persisted:
            return
        self._assistant_persisted = True
        self.history.append({"role": "assistant", "content": self._assistant_md})
        already_persisted = self.session_id is not None
        self._ensure_session()
        if already_persisted and self.session_id is not None:
            self.history_store.append_message(self.session_id, "assistant", self._assistant_md)
            self.historyUpdated.emit()
        elif self.session_id is not None:
            self.historyUpdated.emit()
        self._maybe_generate_title()

    # rendering
    def _append_code_context_block(self):
        if not self.code.strip():
            return
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
            self._generation_stopped = True
            try:
                self._worker.stop()
                self._worker.wait()
            except Exception:
                pass
            self._worker = None
            self._render_timer.stop()
            self._flush_render(True)
            if getattr(self, "_assistant_md", ""):
                self._finalize_assistant_message()
            self.status.showMessage("Generation stopped")

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def close_session(self):
        if should_finalize_pending_assistant(self._assistant_md, self._assistant_persisted):
            self._render_timer.stop()
            self._flush_render(True)
            self._finalize_assistant_message()
        if self.session_id is not None:
            if has_meaningful_messages(self.history):
                self.history_store.mark_session_closed(self.session_id)
            else:
                self.history_store.delete_session(self.session_id)
                self.session_id = None
            self.historyUpdated.emit()

    def reset_persistence(self):
        self.session_id = None
        self._allow_auto_title = False
        if should_persist_initial_session(self.code, self.history):
            self._ensure_session()
            self.historyUpdated.emit()

    def matches_context(self, code: str, file_name: str, file_path: str) -> bool:
        return self.code == code and self.file_name == file_name and self.file_path == file_path

    @staticmethod
    def _mk_btn(text, handler, *, variant="primary"):
        b = QPushButton(text)
        b.clicked.connect(handler)
        b.setMinimumHeight(36)
        style = PRIMARY_BUTTON_STYLE
        if variant == "accent":
            style = ACCENT_BUTTON_STYLE
        elif variant == "subtle":
            style = SUBTLE_BUTTON_STYLE
        b.setStyleSheet(style)
        return b
