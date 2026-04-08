from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from settings_store import DEFAULT_QUICK_PROMPTS, RuntimeSettings


class SettingsDialog(QDialog):
    def __init__(
            self,
            runtime: RuntimeSettings,
            quick_prompts: OrderedDict[str, str],
            parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(860, 620)

        root = QVBoxLayout(self)
        tabs = QTabWidget(self)
        tabs.addTab(self._build_runtime_tab(runtime), "Runtime")
        tabs.addTab(self._build_quick_prompts_tab(quick_prompts), "Quick Prompts")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_runtime_tab(self, runtime: RuntimeSettings) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.base_url_edit = QLineEdit(runtime.ollama_base_url, tab)
        self.base_url_edit.setPlaceholderText("http://localhost:11434/api")
        form.addRow("Ollama API base", self.base_url_edit)

        self.temperature_spin = QDoubleSpinBox(tab)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setRange(0.0, 4.0)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setValue(runtime.temperature)
        form.addRow("Temperature", self.temperature_spin)

        self.num_ctx_spin = QSpinBox(tab)
        self.num_ctx_spin.setRange(1024, 1_000_000)
        self.num_ctx_spin.setSingleStep(1024)
        self.num_ctx_spin.setValue(runtime.num_ctx)
        form.addRow("Context window", self.num_ctx_spin)

        self.keep_alive_edit = QLineEdit(runtime.keep_alive, tab)
        form.addRow("Keep alive", self.keep_alive_edit)

        self.pull_model_edit = QLineEdit(runtime.default_pull_model, tab)
        form.addRow("Default pull model", self.pull_model_edit)

        self.num_parallel_spin = QSpinBox(tab)
        self.num_parallel_spin.setRange(1, 64)
        self.num_parallel_spin.setValue(runtime.serve_num_parallel)
        form.addRow("Serve num parallel", self.num_parallel_spin)

        self.max_loaded_spin = QSpinBox(tab)
        self.max_loaded_spin.setRange(1, 64)
        self.max_loaded_spin.setValue(runtime.serve_max_loaded_models)
        form.addRow("Serve max loaded", self.max_loaded_spin)

        self.flash_attention_check = QCheckBox(tab)
        self.flash_attention_check.setChecked(runtime.serve_flash_attention)
        form.addRow("Flash attention", self.flash_attention_check)

        self.kv_cache_edit = QLineEdit(runtime.serve_kv_cache_type, tab)
        form.addRow("KV cache type", self.kv_cache_edit)

        layout.addLayout(form)
        layout.addWidget(
            QLabel(
                "Changes apply to future Ollama requests immediately. Running requests are not restarted.",
                tab,
            )
        )
        layout.addStretch(1)
        return tab

    def _build_quick_prompts_tab(self, quick_prompts: OrderedDict[str, str]) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        self.quick_prompts_table = QTableWidget(0, 2, tab)
        self.quick_prompts_table.setHorizontalHeaderLabels(["Button", "Prompt"])
        self.quick_prompts_table.horizontalHeader().setStretchLastSection(True)
        self.quick_prompts_table.verticalHeader().setVisible(False)
        self.quick_prompts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.quick_prompts_table.setSelectionMode(QTableWidget.SingleSelection)
        for name, prompt in quick_prompts.items():
            self._append_prompt_row(name, prompt)
        layout.addWidget(self.quick_prompts_table)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add", tab)
        add_btn.clicked.connect(lambda: self._append_prompt_row("", ""))
        remove_btn = QPushButton("Remove", tab)
        remove_btn.clicked.connect(self._remove_selected_prompt)
        defaults_btn = QPushButton("Restore Defaults", tab)
        defaults_btn.clicked.connect(self._restore_default_prompts)
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addWidget(defaults_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Prompt rows with an empty button label or prompt are ignored.", tab))
        return tab

    def _append_prompt_row(self, name: str, prompt: str) -> None:
        row = self.quick_prompts_table.rowCount()
        self.quick_prompts_table.insertRow(row)
        self.quick_prompts_table.setItem(row, 0, QTableWidgetItem(name))
        self.quick_prompts_table.setItem(row, 1, QTableWidgetItem(prompt))
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
