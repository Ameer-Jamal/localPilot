from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import APP_AUTHOR_NAME, APP_DISPLAY_NAME
from settings_store import DEFAULT_QUICK_PROMPTS, HistorySettings, RuntimeSettings


class SettingsDialog(QDialog):
    def __init__(
            self,
            runtime: RuntimeSettings,
            quick_prompts: OrderedDict[str, str],
            confirm_close_tabs: bool,
            history: HistorySettings,
            parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")
        self.resize(940, 720)
        self.setMinimumSize(860, 640)
        self._clear_history_requested = False
        self.setStyleSheet(
            """
            QDialog#settingsDialog {
                background: #1a1e23;
                color: #eef2f6;
            }
            QLabel[role="eyebrow"] {
                color: #8ea0b5;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QLabel[role="title"] {
                color: #f6f9fc;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel[role="body"] {
                color: #aeb9c6;
                font-size: 13px;
                line-height: 1.45em;
            }
            QLabel[role="section_title"] {
                color: #f6f9fc;
                font-size: 15px;
                font-weight: 650;
            }
            QLabel[role="section_body"] {
                color: #96a3b3;
                font-size: 12px;
                line-height: 1.4em;
            }
            QFrame[card="true"] {
                background: #20262d;
                border: 1px solid #2e3741;
                border-radius: 14px;
            }
            QTabWidget::pane {
                border: none;
                top: -1px;
            }
            QTabBar::tab {
                background: #242b33;
                color: #c9d3de;
                padding: 10px 16px;
                margin-right: 8px;
                border: 1px solid #313b45;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #2d3640;
                color: #ffffff;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QTableWidget {
                background: #14181d;
                color: #eef2f6;
                border: 1px solid #313b45;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus {
                border-color: #56b6a7;
            }
            QCheckBox {
                spacing: 8px;
                color: #eef2f6;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #42505d;
                border-radius: 5px;
                background: #14181d;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #2d9386;
                border-radius: 5px;
                background: #35a192;
            }
            QPushButton {
                background: #242b33;
                color: #eef2f6;
                border: 1px solid #313b45;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2c3440;
            }
            QPushButton[variant="primary"] {
                background: #2f8f81;
                border-color: #2f8f81;
                color: #f8fffd;
            }
            QPushButton[variant="primary"]:hover {
                background: #38a192;
                border-color: #38a192;
            }
            QPushButton[variant="danger"] {
                background: #4c2b31;
                border-color: #7a3b46;
                color: #ffdfe3;
            }
            QPushButton[variant="danger"]:hover {
                background: #60343b;
                border-color: #8d4653;
            }
            QHeaderView::section {
                background: #242b33;
                color: #c9d3de;
                border: none;
                padding: 10px 8px;
                font-weight: 600;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(18)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_runtime_tab(runtime, confirm_close_tabs), "Runtime")
        self.tabs.addTab(self._build_quick_prompts_tab(quick_prompts), "Quick Prompts")
        self.tabs.addTab(self._build_history_tab(history), "History")
        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_btn = QPushButton("Close", self)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save Changes", self)
        self.save_btn.setProperty("variant", "primary")
        self.save_btn.style().unpolish(self.save_btn)
        self.save_btn.style().polish(self.save_btn)
        self.save_btn.clicked.connect(self.accept)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.save_btn)
        root.addLayout(actions)

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        eyebrow = QLabel(APP_DISPLAY_NAME, header)
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("Settings", header)
        title.setProperty("role", "title")
        body = QLabel(
            f"Tune how {APP_DISPLAY_NAME} talks to Ollama and manage the quick actions that appear above every chat.",
            header,
        )
        body.setWordWrap(True)
        body.setProperty("role", "body")
        author = QLabel(f"by {APP_AUTHOR_NAME}", header)
        author.setProperty("role", "section_body")

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(author)
        return header

    def _build_scroll_tab(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _build_runtime_tab(self, runtime: RuntimeSettings, confirm_close_tabs: bool) -> QWidget:
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        intro = QLabel(
            "These defaults apply to new requests immediately. They do not interrupt a response that is already streaming.",
            content,
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "body")
        layout.addWidget(intro)

        layout.addWidget(
            self._build_form_card(
                "Connection",
                "Choose where LocalPilot reaches Ollama and which model it should suggest when no models are installed yet.",
                runtime,
                rows_builder=self._build_connection_rows,
            )
        )
        layout.addWidget(
            self._build_form_card(
                "Response Defaults",
                "Set the default creativity, context size, and how long Ollama should keep models warm between requests.",
                runtime,
                rows_builder=self._build_generation_rows,
            )
        )
        layout.addWidget(
            self._build_form_card(
                "Local Ollama Launch",
                "These values are used when you click “Run Ollama” from the chat window.",
                runtime,
                rows_builder=self._build_server_rows,
            )
        )
        layout.addWidget(self._build_window_behavior_card(confirm_close_tabs))
        layout.addStretch(1)
        return self._build_scroll_tab(content)

    def _build_form_card(self, title: str, description: str, runtime: RuntimeSettings, *, rows_builder) -> QWidget:
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        heading = QLabel(title, card)
        heading.setProperty("role", "section_title")
        body = QLabel(description, card)
        body.setWordWrap(True)
        body.setProperty("role", "section_body")
        rows = QVBoxLayout()
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(14)

        layout.addWidget(heading)
        layout.addWidget(body)
        rows_builder(rows, runtime, card)
        layout.addLayout(rows)
        return card

    def _make_form_label(self, title: str, description: str, parent: QWidget) -> QWidget:
        wrap = QWidget(parent)
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title_label = QLabel(title, wrap)
        title_label.setProperty("role", "section_title")
        detail_label = QLabel(description, wrap)
        detail_label.setWordWrap(True)
        detail_label.setProperty("role", "section_body")
        layout.addWidget(title_label)
        layout.addWidget(detail_label)
        return wrap

    def _add_setting_row(self, rows, label_widget: QWidget, control: QWidget, parent: QWidget) -> None:
        row = QWidget(parent)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(label_widget)
        layout.addWidget(control)
        rows.addWidget(row)

    def _build_connection_rows(self, rows, runtime: RuntimeSettings, parent: QWidget) -> None:
        self.base_url_edit = QLineEdit(runtime.ollama_base_url, parent)
        self.base_url_edit.setPlaceholderText("http://localhost:11434/api")
        self._add_setting_row(
            rows,
            self._make_form_label("Ollama API base URL", "Example: http://localhost:11434/api", parent),
            self.base_url_edit,
            parent,
        )

        self.pull_model_edit = QLineEdit(runtime.default_pull_model, parent)
        self.pull_model_edit.setPlaceholderText("qwen2.5-coder:7b")
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Default model to install",
                "Used by the “Install Model” button when Ollama is running but no model is available.",
                parent,
            ),
            self.pull_model_edit,
            parent,
        )

    def _build_generation_rows(self, rows, runtime: RuntimeSettings, parent: QWidget) -> None:
        self.temperature_spin = QDoubleSpinBox(parent)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setRange(0.0, 4.0)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setValue(runtime.temperature)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Creativity",
                "Lower values are steadier and more deterministic. Higher values are more exploratory.",
                parent,
            ),
            self.temperature_spin,
            parent,
        )

        self.num_ctx_spin = QSpinBox(parent)
        self.num_ctx_spin.setRange(1024, 1_000_000)
        self.num_ctx_spin.setSingleStep(1024)
        self.num_ctx_spin.setValue(runtime.num_ctx)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Context window",
                "How much code and conversation history LocalPilot asks Ollama to keep in view.",
                parent,
            ),
            self.num_ctx_spin,
            parent,
        )

        self.keep_alive_edit = QLineEdit(runtime.keep_alive, parent)
        self.keep_alive_edit.setPlaceholderText("10m")
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Keep models warm for",
                "Examples: 10m, 1h, 30s. Longer values reduce cold starts at the cost of memory use.",
                parent,
            ),
            self.keep_alive_edit,
            parent,
        )

    def _build_server_rows(self, rows, runtime: RuntimeSettings, parent: QWidget) -> None:
        self.num_parallel_spin = QSpinBox(parent)
        self.num_parallel_spin.setRange(1, 64)
        self.num_parallel_spin.setValue(runtime.serve_num_parallel)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Parallel requests",
                "How many requests the local Ollama server should try to serve at once when LocalPilot starts it.",
                parent,
            ),
            self.num_parallel_spin,
            parent,
        )

        self.max_loaded_spin = QSpinBox(parent)
        self.max_loaded_spin.setRange(1, 64)
        self.max_loaded_spin.setValue(runtime.serve_max_loaded_models)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Models kept loaded",
                "Caps how many models Ollama should keep resident in memory when LocalPilot starts it.",
                parent,
            ),
            self.max_loaded_spin,
            parent,
        )

        self.flash_attention_check = QCheckBox("Enable Flash Attention when supported", parent)
        self.flash_attention_check.setChecked(runtime.serve_flash_attention)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "GPU optimization",
                "Useful on supported hardware. Leave enabled unless you know it causes issues on your machine.",
                parent,
            ),
            self.flash_attention_check,
            parent,
        )

        self.kv_cache_edit = QLineEdit(runtime.serve_kv_cache_type, parent)
        self.kv_cache_edit.setPlaceholderText("q8_0")
        self._add_setting_row(
            rows,
            self._make_form_label(
                "KV cache format",
                "Controls the cache representation used when LocalPilot launches Ollama locally.",
                parent,
            ),
            self.kv_cache_edit,
            parent,
        )

    def _build_quick_prompts_tab(self, quick_prompts: OrderedDict[str, str]) -> QWidget:
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        intro = QLabel(
            "These actions appear above the chat box in every session. Keep labels short and make prompts specific enough to produce reliable results.",
            content,
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "body")
        layout.addWidget(intro)

        table_card = self._make_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(14)

        title = QLabel("Quick Prompt Buttons", table_card)
        title.setProperty("role", "section_title")
        body = QLabel(
            "Each row becomes one button. The label is what users see in the toolbar, and the prompt is what LocalPilot sends when that button is clicked.",
            table_card,
        )
        body.setWordWrap(True)
        body.setProperty("role", "section_body")
        table_layout.addWidget(title)
        table_layout.addWidget(body)

        self.quick_prompts_table = QTableWidget(0, 2, table_card)
        self.quick_prompts_table.setHorizontalHeaderLabels(["Button Label", "Prompt Sent to LocalPilot"])
        self.quick_prompts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.quick_prompts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.quick_prompts_table.verticalHeader().setVisible(False)
        self.quick_prompts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.quick_prompts_table.setSelectionMode(QTableWidget.SingleSelection)
        self.quick_prompts_table.setAlternatingRowColors(True)
        self.quick_prompts_table.setWordWrap(True)
        self.quick_prompts_table.setMinimumHeight(360)
        for name, prompt in quick_prompts.items():
            self._append_prompt_row(name, prompt)
        table_layout.addWidget(self.quick_prompts_table)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Prompt", table_card)
        add_btn.clicked.connect(lambda: self._append_prompt_row("", ""))
        remove_btn = QPushButton("Remove Selected", table_card)
        remove_btn.clicked.connect(self._remove_selected_prompt)
        defaults_btn = QPushButton("Restore Starter Set", table_card)
        defaults_btn.clicked.connect(self._restore_default_prompts)
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addWidget(defaults_btn)
        buttons.addStretch(1)
        table_layout.addLayout(buttons)

        note = QLabel(
            "Rows with an empty label or empty prompt are ignored when you save.",
            table_card,
        )
        note.setWordWrap(True)
        note.setProperty("role", "section_body")
        table_layout.addWidget(note)

        layout.addWidget(table_card)
        layout.addStretch(1)
        return self._build_scroll_tab(content)

    def _build_window_behavior_card(self, confirm_close_tabs: bool) -> QWidget:
        card = self._make_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Window Behavior", card)
        title.setProperty("role", "section_title")
        body = QLabel(
            "Choose how cautious LocalPilot should be when you close a chat tab.",
            card,
        )
        body.setWordWrap(True)
        body.setProperty("role", "section_body")

        self.confirm_close_tabs_check = QCheckBox("Ask before closing a chat tab", card)
        self.confirm_close_tabs_check.setChecked(confirm_close_tabs)

        detail = QLabel(
            "Turn this off if you prefer browser-style instant closes. Leave it on if you want a safety check before a tab disappears.",
            card,
        )
        detail.setWordWrap(True)
        detail.setProperty("role", "section_body")

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(self.confirm_close_tabs_check)
        layout.addWidget(detail)
        return card

    def _build_history_tab(self, history: HistorySettings) -> QWidget:
        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        intro = QLabel(
            "History keeps your previous chats available to reopen later. You can keep everything forever or let LocalPilot trim old closed chats automatically.",
            content,
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "body")
        layout.addWidget(intro)

        retention = self._make_card()
        retention_layout = QVBoxLayout(retention)
        retention_layout.setContentsMargins(18, 18, 18, 18)
        retention_layout.setSpacing(14)

        title = QLabel("Retention", retention)
        title.setProperty("role", "section_title")
        body = QLabel(
            "Open chats are preserved. Automatic cleanup only targets closed chats.",
            retention,
        )
        body.setWordWrap(True)
        body.setProperty("role", "section_body")
        retention_layout.addWidget(title)
        retention_layout.addWidget(body)

        self.keep_history_forever_check = QCheckBox("Keep history forever", retention)
        self.keep_history_forever_check.setChecked(history.keep_forever)
        self.keep_history_forever_check.toggled.connect(self._toggle_history_retention_controls)
        retention_layout.addWidget(self.keep_history_forever_check)

        rows = QVBoxLayout()
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(14)

        self.delete_closed_days_spin = QSpinBox(retention)
        self.delete_closed_days_spin.setRange(1, 3650)
        self.delete_closed_days_spin.setValue(history.delete_closed_after_days)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Delete closed chats after",
                "Older closed sessions beyond this age are removed during startup and after settings changes.",
                retention,
            ),
            self.delete_closed_days_spin,
            retention,
        )

        self.max_sessions_spin = QSpinBox(retention)
        self.max_sessions_spin.setRange(1, 100000)
        self.max_sessions_spin.setValue(history.max_sessions)
        self._add_setting_row(
            rows,
            self._make_form_label(
                "Maximum saved chats",
                "If history grows beyond this cap, LocalPilot trims the oldest closed chats first.",
                retention,
            ),
            self.max_sessions_spin,
            retention,
        )
        retention_layout.addLayout(rows)
        layout.addWidget(retention)

        actions = self._make_card()
        actions_layout = QVBoxLayout(actions)
        actions_layout.setContentsMargins(18, 18, 18, 18)
        actions_layout.setSpacing(14)
        actions_title = QLabel("Manual Cleanup", actions)
        actions_title.setProperty("role", "section_title")
        actions_body = QLabel(
            "Use this when you want to wipe every saved chat and start fresh.",
            actions,
        )
        actions_body.setWordWrap(True)
        actions_body.setProperty("role", "section_body")
        clear_button = QPushButton("Clear All Saved History", actions)
        clear_button.setProperty("variant", "danger")
        clear_button.clicked.connect(self._request_clear_history)
        clear_button.style().unpolish(clear_button)
        clear_button.style().polish(clear_button)
        self.clear_history_status = QLabel("No destructive actions selected.", actions)
        self.clear_history_status.setProperty("role", "section_body")

        actions_layout.addWidget(actions_title)
        actions_layout.addWidget(actions_body)
        actions_layout.addWidget(clear_button, 0, Qt.AlignLeft)
        actions_layout.addWidget(self.clear_history_status)
        layout.addWidget(actions)
        layout.addStretch(1)
        self._toggle_history_retention_controls(history.keep_forever)
        return self._build_scroll_tab(content)

    def _toggle_history_retention_controls(self, checked: bool) -> None:
        enabled = not checked
        self.delete_closed_days_spin.setEnabled(enabled)
        self.max_sessions_spin.setEnabled(enabled)

    def _request_clear_history(self) -> None:
        self._clear_history_requested = True
        self.clear_history_status.setText("Clear-all requested. Save changes to apply it.")

    def _make_card(self) -> QFrame:
        card = QFrame(self)
        card.setProperty("card", "true")
        card.setFrameShape(QFrame.StyledPanel)
        return card

    def _append_prompt_row(self, name: str, prompt: str) -> None:
        row = self.quick_prompts_table.rowCount()
        self.quick_prompts_table.insertRow(row)
        self.quick_prompts_table.setItem(row, 0, QTableWidgetItem(name))
        self.quick_prompts_table.setItem(row, 1, QTableWidgetItem(prompt))
        self.quick_prompts_table.setRowHeight(row, 54)
        self.quick_prompts_table.setCurrentCell(row, 0)

    def _remove_selected_prompt(self) -> None:
        row = self.quick_prompts_table.currentRow()
        if row >= 0:
            self.quick_prompts_table.removeRow(row)

    def _restore_default_prompts(self) -> None:
        self.quick_prompts_table.setRowCount(0)
        for name, prompt in DEFAULT_QUICK_PROMPTS.items():
            self._append_prompt_row(name, prompt)

    def get_runtime_settings(self) -> RuntimeSettings:
        return RuntimeSettings(
            ollama_base_url=self.base_url_edit.text(),
            temperature=self.temperature_spin.value(),
            num_ctx=self.num_ctx_spin.value(),
            keep_alive=self.keep_alive_edit.text().strip(),
            default_pull_model=self.pull_model_edit.text().strip(),
            serve_num_parallel=self.num_parallel_spin.value(),
            serve_max_loaded_models=self.max_loaded_spin.value(),
            serve_flash_attention=self.flash_attention_check.isChecked(),
            serve_kv_cache_type=self.kv_cache_edit.text().strip(),
        )

    def get_quick_prompts(self) -> list[dict[str, str]]:
        prompts = []
        for row in range(self.quick_prompts_table.rowCount()):
            name_item = self.quick_prompts_table.item(row, 0)
            prompt_item = self.quick_prompts_table.item(row, 1)
            prompts.append(
                {
                    "name": name_item.text() if name_item else "",
                    "prompt": prompt_item.text() if prompt_item else "",
                }
            )
        return prompts

    def get_confirm_close_tabs(self) -> bool:
        return self.confirm_close_tabs_check.isChecked()

    def get_history_settings(self) -> HistorySettings:
        return HistorySettings(
            keep_forever=self.keep_history_forever_check.isChecked(),
            delete_closed_after_days=self.delete_closed_days_spin.value(),
            max_sessions=self.max_sessions_spin.value(),
        )

    def should_clear_history(self) -> bool:
        return self._clear_history_requested
