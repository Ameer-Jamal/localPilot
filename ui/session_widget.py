from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from PySide6.QtCore import Qt, QTimer, Signal, QSettings
from PySide6.QtGui import QColor, QFont, QPalette, QPen
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
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)
from markdown_it import MarkdownIt

from app_constants import NEW_CHAT_TITLE, NO_OLLAMA_MODELS_FOUND, SETTINGS_LABEL
from chat_logic import (
    has_meaningful_messages,
    pick_preferred_model,
    should_finalize_pending_assistant,
    should_handle_worker_signal,
    should_persist_initial_session,
)
from config import APP_NAME, APP_ORG, MODEL
from history_store import HistoryStore
from model_provider import available_bedrock_models, display_model_name, is_bedrock_model, provider_model_id, warm_up_selected_model
from ollama_client import remember_local_server_process, stop_local_ollama_server
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
from ui_text import (
    CONFIRM_CLEAR_HISTORY_INFO,
    CONFIRM_CLEAR_HISTORY_TEXT,
    CONFIRM_CLEAR_HISTORY_TITLE,
    LABEL_CANCEL,
    LABEL_CLEAR_HISTORY,
    LABEL_INSTALL_MODEL,
    LABEL_MODEL,
    LABEL_REFRESH,
    LABEL_SEND,
    LABEL_START_OLLAMA,
    LABEL_STOP,
    LABEL_STOP_OLLAMA,
    LABEL_UNTITLED_CHAT,
    STATUS_FAILED_TO_STOP_OLLAMA,
    STATUS_GENERATION_STOPPED,
    STATUS_NO_MODELS_AVAILABLE,
    STATUS_NO_OLLAMA_TO_STOP,
    STATUS_READY,
    STATUS_SERVER_NOT_RUNNING,
    STATUS_SERVER_STARTING,
    STATUS_STOPPED_OLLAMA,
    TOOLTIP_OPEN_SETTINGS,
    status_done,
    status_failed_to_install_model,
    status_failed_to_start_ollama,
    status_generating,
    status_installing_model,
    status_no_models_found,
    status_released_models,
)
from utils import lang_hint
from workers.chat_worker import ChatWorker
from workers.title_worker import TitleWorker
from transcript_render import block_has_role, render_code_context_block, render_message_block, render_thinking_block

md = MarkdownIt()
LEGACY_SETTINGS_ORG = "AskAboutSelection"
BEDROCK_ACCENT = QColor("#56b6a7")
DEFAULT_COMBO_COLOR = QColor("#eef2f6")
SECTION_TEXT_COLOR = QColor("#8ea0b5")
ITEM_KIND_ROLE = Qt.UserRole + 1
MODEL_VALUE_ROLE = Qt.UserRole + 2
ITEM_KIND_HEADER = "header"
ITEM_KIND_MODEL = "model"


class ModelComboDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:
        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)
        kind = index.data(ITEM_KIND_ROLE)
        if kind == ITEM_KIND_HEADER:
            view_option.font = QFont(view_option.font)
            view_option.font.setBold(True)
            view_option.palette.setColor(QPalette.Text, SECTION_TEXT_COLOR)
            view_option.palette.setColor(QPalette.WindowText, SECTION_TEXT_COLOR)
            view_option.state &= ~QStyle.State_Selected
            view_option.state &= ~QStyle.State_HasFocus
        elif is_bedrock_model(str(index.data(MODEL_VALUE_ROLE) or "")):
            view_option.palette.setColor(QPalette.Text, BEDROCK_ACCENT)
            view_option.palette.setColor(QPalette.WindowText, BEDROCK_ACCENT)
        super().paint(painter, view_option, index)
        if kind == ITEM_KIND_HEADER and index.row() > 0:
            painter.save()
            painter.setPen(QPen(QColor("#313b45")))
            painter.drawLine(
                view_option.rect.left() + 8,
                view_option.rect.top(),
                view_option.rect.right() - 8,
                view_option.rect.top(),
            )
            painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> object:
        size = super().sizeHint(option, index)
        kind = index.data(ITEM_KIND_ROLE)
        if kind == ITEM_KIND_HEADER:
            size.setHeight(max(size.height(), 34))
        else:
            size.setHeight(max(size.height(), 28))
        return size


class ModelComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_text_color = DEFAULT_COMBO_COLOR

    def set_current_text_color(self, color: QColor) -> None:
        self._current_text_color = color
        self.update()

    def paintEvent(self, event) -> None:
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.palette.setColor(QPalette.ButtonText, self._current_text_color)
        option.palette.setColor(QPalette.Text, self._current_text_color)
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        painter.drawControl(QStyle.CE_ComboBoxLabel, option)


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
        self.title = (session_title or file_name or NEW_CHAT_TITLE).strip() or LABEL_UNTITLED_CHAT
        self.history_store = history_store
        self.session_id = session_id
        self._session_model = (persisted_model or "").strip()
        self._preferred_model = self._session_model or MODEL
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
        self.status.showMessage(STATUS_READY)

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
        self.model_lbl.setText(LABEL_MODEL)

        self.model_combo = ModelComboBox()
        self.model_combo.setItemDelegate(ModelComboDelegate(self.model_combo))
        self.model_combo.currentIndexChanged.connect(lambda _index: self._on_model_changed(self._selected_model()))

        # Refresh button
        self.refresh_btn = self._mk_btn(LABEL_REFRESH, self._setup_model_selector, variant="subtle")
        self.refresh_btn.setVisible(False)

        # Run Ollama button
        self.run_ollama_btn = self._mk_btn(LABEL_START_OLLAMA, self._run_ollama_server, variant="subtle")
        self.run_ollama_btn.setVisible(False)
        self.stop_ollama_btn = self._mk_btn(LABEL_STOP_OLLAMA, self._stop_ollama_server, variant="subtle")
        self.stop_ollama_btn.setVisible(False)

        # Install default model button
        self.install_model_btn = self._mk_btn(LABEL_INSTALL_MODEL, self._install_default_model, variant="accent")
        self.install_model_btn.setVisible(False)

        self.settings_btn = self._mk_btn(SETTINGS_LABEL, self._open_settings_dialog, variant="subtle")
        self.settings_btn.setToolTip(TOOLTIP_OPEN_SETTINGS)

        top.addWidget(self.model_lbl)
        top.addWidget(self.model_combo)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.run_ollama_btn)
        top.addWidget(self.stop_ollama_btn)
        top.addWidget(self.install_model_btn)
        top.addWidget(self.settings_btn)

        self._rebuild_quick_prompt_buttons()
        self._setup_model_selector()
        self.warm_up()

        # Transcript view
        self.view = QWebEngineView()
        self._page_ready = False
        self._pending_html = None
        self.view.loadFinished.connect(self._on_page_ready)
        self.view.setHtml(HTML_TEMPLATE)

        # Input row
        bottom = QHBoxLayout()
        self.input = AutoResizingTextEdit(min_lines=2, max_lines=8)
        self.input.sendRequested.connect(self._send_message_same_tab)
        send_btn = self._mk_btn(LABEL_SEND, self._send_message_same_tab, variant="accent")
        stop_btn = self._mk_btn(LABEL_STOP, self._stop_generation, variant="subtle")
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
        Fetches available local Ollama models and appends enabled Bedrock models.
        """
        self._runtime_settings = self._settings_store.get_runtime_settings()
        return [
            *fetch_ollama_models(self._runtime_settings),
            *available_bedrock_models(self._runtime_settings),
        ]

    def _setup_model_selector(self):
        """
        Configures the model combobox and refresh button based on currently
        available Ollama models.
        """
        self._runtime_settings = self._settings_store.get_runtime_settings()
        ollama_model_list = fetch_ollama_models(self._runtime_settings)
        current_model_list = [
            *ollama_model_list,
            *available_bedrock_models(self._runtime_settings),
        ]
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        if current_model_list:
            if ollama_model_list:
                self._add_model_section("Ollama Models")
                for model in ollama_model_list:
                    self._add_model_item(model, label=model)
            bedrock_models = available_bedrock_models(self._runtime_settings)
            if bedrock_models:
                self._add_model_section("Bedrock Models")
                for model in bedrock_models:
                    self._add_model_item(model, label=provider_model_id(model))
            saved_model = get_saved_chat_model(self._settings)
            if not saved_model:
                saved_model = QSettings(LEGACY_SETTINGS_ORG, APP_NAME).value("chat/model", MODEL, type=str)
            preferred = pick_preferred_model(
                current_model_list,
                session_model=self._session_model,
                saved_model=saved_model,
                default_model=MODEL,
            )
            preferred_index = self.model_combo.findData(preferred)
            self.model_combo.setCurrentIndex(preferred_index if preferred_index >= 0 else 0)
            self.model_combo.setEnabled(True)
            self._on_model_changed(self._selected_model())
            server_up = is_ollama_running(self._runtime_settings) if not ollama_model_list else True
            self.status.showMessage(STATUS_READY)
            self.refresh_btn.setVisible(not ollama_model_list)
            self.run_ollama_btn.setVisible(not ollama_model_list and not server_up)
            self.stop_ollama_btn.setVisible(bool(ollama_model_list) or server_up)
            self.install_model_btn.setVisible(not ollama_model_list and server_up)
        else:
            server_up = is_ollama_running(self._runtime_settings)
            self.model_combo.addItem(NO_OLLAMA_MODELS_FOUND)
            self.model_combo.setCurrentIndex(0)
            self.model_combo.setEnabled(False)
            if server_up:
                self.status.showMessage(status_no_models_found(self._runtime_settings.default_pull_model))
            else:
                self.status.showMessage(STATUS_SERVER_NOT_RUNNING)
            self.refresh_btn.setVisible(True)
            self.run_ollama_btn.setVisible(not server_up)
            self.stop_ollama_btn.setVisible(server_up)
            self.install_model_btn.setVisible(server_up)
        self._sync_model_combo_accent()
        self.model_combo.blockSignals(False)

    def _run_ollama_server(self):
        """Attempt to start the Ollama server with predefined settings."""
        env = os.environ.copy()
        env.update(self._runtime_settings.serve_env)
        cmd = shutil.which("ollama") or "/opt/homebrew/opt/ollama/bin/ollama"
        try:
            process = subprocess.Popen(
                [cmd, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            remember_local_server_process(process)
            self.status.showMessage(STATUS_SERVER_STARTING)
            self.run_ollama_btn.setVisible(False)
            self.stop_ollama_btn.setVisible(True)
            self._begin_ollama_refresh()
        except Exception as exc:
            self.status.showMessage(status_failed_to_start_ollama(exc))

    def _stop_ollama_server(self):
        state, unloaded = stop_local_ollama_server()
        if state == "stopped":
            self.status.showMessage(STATUS_STOPPED_OLLAMA)
        elif state == "released":
            self.status.showMessage(status_released_models(len(unloaded)))
        elif state == "idle":
            self.status.showMessage(STATUS_NO_OLLAMA_TO_STOP)
        else:
            self.status.showMessage(STATUS_FAILED_TO_STOP_OLLAMA)
        self._setup_model_selector()

    def _install_default_model(self):
        cmd = shutil.which("ollama") or "/opt/homebrew/opt/ollama/bin/ollama"
        try:
            subprocess.Popen(
                [cmd, "pull", self._runtime_settings.default_pull_model],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.status.showMessage(status_installing_model(self._runtime_settings.default_pull_model))
            self.install_model_btn.setVisible(False)
            self._begin_ollama_refresh(attempts=60)
        except Exception as exc:
            self.status.showMessage(status_failed_to_install_model(exc))

    def _begin_ollama_refresh(self, *, attempts: int = 20, delay_ms: int = 1500):
        def _poll(remaining: int) -> None:
            self._setup_model_selector()
            if fetch_ollama_models(self._runtime_settings) or remaining <= 1:
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
            box.setWindowTitle(CONFIRM_CLEAR_HISTORY_TITLE)
            box.setText(CONFIRM_CLEAR_HISTORY_TEXT)
            box.setInformativeText(CONFIRM_CLEAR_HISTORY_INFO)
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            box.button(QMessageBox.Yes).setText(LABEL_CLEAR_HISTORY)
            box.button(QMessageBox.No).setText(LABEL_CANCEL)
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
            warm_up_selected_model(model)

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
        self._append_code_context_block(push_to_view=False)
        for msg in self.history:
            if msg.get("role") == "system":
                continue
            self._append_role_block(msg.get("role", "user"), msg.get("content", ""), push_to_view=False)
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
        data = self.model_combo.currentData(MODEL_VALUE_ROLE)
        model = str(data).strip() if data is not None else ""
        return "" if not model or model == NO_OLLAMA_MODELS_FOUND else model

    def display_title(self) -> str:
        return self.title or self.file_name or LABEL_UNTITLED_CHAT

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
            self.history.copy(),
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

    def _chat(self):
        model = self._selected_model()
        if not model:
            self.status.showMessage(STATUS_NO_MODELS_AVAILABLE)
            return

        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()

        self._assistant_md = ""
        self._render_buf = []
        self._assistant_persisted = False
        self._generation_stopped = False
        self.status.showMessage(status_generating(display_model_name(model)))
        self._start_ts = time.time()
        self._chars = 0
        self._append_thinking_block()

        self._active_model = model
        self._worker = ChatWorker(self.history, model=model)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.error.connect(self._on_error)
        self._worker.done.connect(self._on_done)
        self._worker.start()
        self._render_timer.start()

    def _on_chunk(self, s: str):
        if not should_handle_worker_signal(self._worker, self.sender()):
            return
        self._render_buf.append(s)
        self._assistant_md += s
        self._chars += len(s)

    def _on_model_changed(self, model: str):
        self._settings.setValue("chat/model", model)
        self._preferred_model = model
        self._session_model = model
        self._sync_model_combo_accent()
        if self.session_id is not None and model and model != NO_OLLAMA_MODELS_FOUND:
            self.history_store.update_session_model(self.session_id, model)

    def _sync_model_combo_accent(self) -> None:
        text_color = BEDROCK_ACCENT if is_bedrock_model(self._selected_model()) else DEFAULT_COMBO_COLOR
        self.model_combo.set_current_text_color(text_color)

    def _add_model_section(self, title: str) -> None:
        self.model_combo.addItem(title, "")
        item_index = self.model_combo.count() - 1
        self.model_combo.setItemData(item_index, ITEM_KIND_HEADER, ITEM_KIND_ROLE)
        self.model_combo.setItemData(item_index, "", MODEL_VALUE_ROLE)
        model = self.model_combo.model()
        if hasattr(model, "item"):
            item = model.item(item_index)
            if item is not None:
                item.setEnabled(False)

    def _add_model_item(self, model: str, *, label: str) -> None:
        self.model_combo.addItem(label, model)
        item_index = self.model_combo.count() - 1
        self.model_combo.setItemData(item_index, ITEM_KIND_MODEL, ITEM_KIND_ROLE)
        self.model_combo.setItemData(item_index, model, MODEL_VALUE_ROLE)

    def _on_error(self, msg: str):
        if not should_handle_worker_signal(self._worker, self.sender()):
            return
        rendered = f"\n\n**Error:** {msg}\n"
        self._render_buf.append(rendered)
        self._assistant_md += rendered

    def _on_done(self):
        if not should_handle_worker_signal(self._worker, self.sender()):
            return
        self._render_timer.stop()
        self._flush_render(True)
        if self._assistant_md:
            self._finalize_assistant_message()
        elif self._html and block_has_role(self._html[-1], "assistant"):
            self._html.pop()
            self._set_html("".join(self._html))
        self._worker = None
        elapsed = time.time() - self._start_ts
        cps = int(self._chars / elapsed) if elapsed > 0 else 0
        model = getattr(self, "_active_model", self._selected_model())
        self.status.showMessage(status_done(elapsed, self._chars, cps, display_model_name(model)))

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
    def _append_code_context_block(self, *, push_to_view: bool = False):
        if not self.code.strip():
            return
        block_html = render_code_context_block(self.code, self.lang or "plaintext")
        self._html.append(block_html)
        if push_to_view:
            self._set_html("".join(self._html))

    def _append_role_block(self, role: str, content_md: str, *, push_to_view: bool = True):
        block_html = render_message_block(role, md.render(content_md or ""))
        self._html.append(block_html)
        if push_to_view:
            self._set_html("".join(self._html))

    def _append_thinking_block(self, *, push_to_view: bool = True):
        block_html = render_thinking_block()
        self._html.append(block_html)
        if push_to_view:
            self._set_html("".join(self._html))

    def _flush_render(self, force=False):
        if self._render_buf or force:
            if self._html and block_has_role(self._html[-1], "assistant"):
                self._html[-1] = render_message_block("assistant", md.render(self._assistant_md))
                self._replace_last_block_in_view(self._html[-1])
            self._render_buf = []

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

    def _replace_last_block_in_view(self, block_html: str):
        if not hasattr(self, "_page_ready") or not self._page_ready:
            self._pending_html = "".join(self._html)
            return
        js = f"replaceLastBlock({json.dumps(block_html)});"
        self.view.page().runJavaScript(js)

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
        worker = self._worker
        if worker and worker.isRunning():
            self._generation_stopped = True
            try:
                worker.stop()
                worker.wait()
            except Exception:
                pass
            self._worker = None
            self._render_timer.stop()
            self._flush_render(True)
            if getattr(self, "_assistant_md", ""):
                self._finalize_assistant_message()
            elif self._html and block_has_role(self._html[-1], "assistant"):
                self._html.pop()
                self._set_html("".join(self._html))
            self.status.showMessage(STATUS_GENERATION_STOPPED)

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
