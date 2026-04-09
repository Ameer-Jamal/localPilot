from __future__ import annotations

import json
import os
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import requests
from PySide6.QtCore import QSettings

from config import (
    APP_NAME,
    APP_ORG,
    DEFAULT_PULL_MODEL,
    KEEP_ALIVE,
    MODEL,
    NUM_CTX,
    OLLAMA_BASE_URL,
    TEMP,
)

DEFAULT_SERVE_NUM_PARALLEL = 2
DEFAULT_SERVE_MAX_LOADED_MODELS = 2
DEFAULT_SERVE_FLASH_ATTENTION = True
DEFAULT_SERVE_KV_CACHE_TYPE = "q8_0"

DEFAULT_QUICK_PROMPTS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("Explain", "Explain what this code does, list concrete risks, and break down the flow."),
        ("Refactor", "Refactor for readability. Follow professional best practices like SRP (Single Responsibility Principle) and preserve behavior."),
        ("Tests", "Generate focused unit tests with Arrange-Act-Assert structure and cover edge cases."),
        ("Performance", "Rewrite for maximum performance gain without changing functionality."),
        ("Simplify", "Simplify the code to make it more readable and easier to understand while preserving its original functionality."),
        ("DocString", "Add concise, easy to understand, proper docstrings for this depending on the language of the file."),
    ]
)


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    ollama_base_url: str
    temperature: float
    num_ctx: int
    keep_alive: str
    default_pull_model: str
    serve_num_parallel: int
    serve_max_loaded_models: int
    serve_flash_attention: bool
    serve_kv_cache_type: str

    @property
    def ollama_chat_url(self) -> str:
        return f"{self.ollama_base_url}/chat"

    @property
    def ollama_tags_url(self) -> str:
        return f"{self.ollama_base_url}/tags"

    @property
    def serve_env(self) -> dict[str, str]:
        return {
            "OLLAMA_NUM_PARALLEL": str(self.serve_num_parallel),
            "OLLAMA_MAX_LOADED_MODELS": str(self.serve_max_loaded_models),
            "OLLAMA_FLASH_ATTENTION": "1" if self.serve_flash_attention else "0",
            "OLLAMA_KV_CACHE_TYPE": self.serve_kv_cache_type,
        }


@dataclass(frozen=True, slots=True)
class HistorySettings:
    keep_forever: bool
    delete_closed_after_days: int
    max_sessions: int


def default_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        ollama_base_url=OLLAMA_BASE_URL,
        temperature=TEMP,
        num_ctx=NUM_CTX,
        keep_alive=KEEP_ALIVE,
        default_pull_model=DEFAULT_PULL_MODEL,
        serve_num_parallel=DEFAULT_SERVE_NUM_PARALLEL,
        serve_max_loaded_models=DEFAULT_SERVE_MAX_LOADED_MODELS,
        serve_flash_attention=DEFAULT_SERVE_FLASH_ATTENTION,
        serve_kv_cache_type=DEFAULT_SERVE_KV_CACHE_TYPE,
    )


def get_qsettings() -> QSettings:
    return QSettings(APP_ORG, APP_NAME)


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def normalize_ollama_base_url(raw: str) -> str:
    value = (raw or OLLAMA_BASE_URL).strip().rstrip("/")
    if not value:
        value = OLLAMA_BASE_URL.rstrip("/")
    if not value.endswith("/api"):
        value = f"{value}/api"
    return value


def normalize_quick_prompts(prompts: list[dict[str, str]] | list[tuple[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: dict[str, int] = {}
    for item in prompts:
        if isinstance(item, tuple):
            name, prompt = item
        else:
            name = item.get("name", "")
            prompt = item.get("prompt", "")
        base_name = str(name).strip()
        prompt_text = str(prompt).strip()
        if not base_name or not prompt_text:
            continue
        count = seen.get(base_name, 0)
        seen[base_name] = count + 1
        final_name = base_name if count == 0 else f"{base_name} ({count + 1})"
        normalized.append({"name": final_name, "prompt": prompt_text})
    return normalized


class SettingsStore:
    def __init__(self, settings: QSettings | Any | None = None):
        self.settings = settings or get_qsettings()

    def get_runtime_settings(self) -> RuntimeSettings:
        defaults = default_runtime_settings()
        return RuntimeSettings(
            ollama_base_url=normalize_ollama_base_url(
                self.settings.value("runtime/ollama_base_url", defaults.ollama_base_url, type=str)
            ),
            temperature=_coerce_float(self.settings.value("runtime/temperature", defaults.temperature), defaults.temperature),
            num_ctx=max(
                1024,
                _coerce_int(self.settings.value("runtime/num_ctx", defaults.num_ctx), defaults.num_ctx),
            ),
            keep_alive=(
                self.settings.value("runtime/keep_alive", defaults.keep_alive, type=str) or defaults.keep_alive
            ).strip(),
            default_pull_model=(
                self.settings.value("runtime/default_pull_model", defaults.default_pull_model, type=str)
                or defaults.default_pull_model
            ).strip(),
            serve_num_parallel=max(
                1,
                _coerce_int(
                    self.settings.value("runtime/serve_num_parallel", defaults.serve_num_parallel),
                    defaults.serve_num_parallel,
                ),
            ),
            serve_max_loaded_models=max(
                1,
                _coerce_int(
                    self.settings.value("runtime/serve_max_loaded_models", defaults.serve_max_loaded_models),
                    defaults.serve_max_loaded_models,
                ),
            ),
            serve_flash_attention=_coerce_bool(
                self.settings.value("runtime/serve_flash_attention", defaults.serve_flash_attention),
                defaults.serve_flash_attention,
            ),
            serve_kv_cache_type=(
                self.settings.value("runtime/serve_kv_cache_type", defaults.serve_kv_cache_type, type=str)
                or defaults.serve_kv_cache_type
            ).strip(),
        )

    def save_runtime_settings(self, runtime: RuntimeSettings) -> None:
        self.settings.setValue("runtime/ollama_base_url", normalize_ollama_base_url(runtime.ollama_base_url))
        self.settings.setValue("runtime/temperature", runtime.temperature)
        self.settings.setValue("runtime/num_ctx", runtime.num_ctx)
        self.settings.setValue("runtime/keep_alive", runtime.keep_alive)
        self.settings.setValue("runtime/default_pull_model", runtime.default_pull_model)
        self.settings.setValue("runtime/serve_num_parallel", runtime.serve_num_parallel)
        self.settings.setValue("runtime/serve_max_loaded_models", runtime.serve_max_loaded_models)
        self.settings.setValue("runtime/serve_flash_attention", runtime.serve_flash_attention)
        self.settings.setValue("runtime/serve_kv_cache_type", runtime.serve_kv_cache_type)

    def get_quick_prompts(self) -> OrderedDict[str, str]:
        raw = self.settings.value("quick_prompts/items", "", type=str)
        parsed: list[dict[str, str]]
        if raw:
            try:
                parsed = normalize_quick_prompts(json.loads(raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = []
        else:
            parsed = []
        if not parsed:
            parsed = [{"name": name, "prompt": prompt} for name, prompt in DEFAULT_QUICK_PROMPTS.items()]
        return OrderedDict((item["name"], item["prompt"]) for item in parsed)

    def save_quick_prompts(self, prompts: list[dict[str, str]] | list[tuple[str, str]]) -> None:
        normalized = normalize_quick_prompts(prompts)
        self.settings.setValue("quick_prompts/items", json.dumps(normalized))

    def reset_quick_prompts(self) -> None:
        self.settings.remove("quick_prompts/items")

    def get_confirm_before_closing_tabs(self) -> bool:
        return _coerce_bool(self.settings.value("ui/confirm_close_tabs", True), True)

    def set_confirm_before_closing_tabs(self, enabled: bool) -> None:
        self.settings.setValue("ui/confirm_close_tabs", bool(enabled))

    def get_history_settings(self) -> HistorySettings:
        return HistorySettings(
            keep_forever=_coerce_bool(self.settings.value("history/keep_forever", True), True),
            delete_closed_after_days=max(
                1,
                _coerce_int(self.settings.value("history/delete_closed_after_days", 30), 30),
            ),
            max_sessions=max(1, _coerce_int(self.settings.value("history/max_sessions", 500), 500)),
        )

    def save_history_settings(self, history: HistorySettings) -> None:
        self.settings.setValue("history/keep_forever", bool(history.keep_forever))
        self.settings.setValue("history/delete_closed_after_days", int(history.delete_closed_after_days))
        self.settings.setValue("history/max_sessions", int(history.max_sessions))


def fetch_ollama_models(runtime: RuntimeSettings | None = None) -> list[str]:
    runtime = runtime or SettingsStore().get_runtime_settings()
    env = os.environ.get("MODEL_LIST")
    if env:
        models = [model.strip() for model in env.split(",") if model.strip()]
        if models:
            return models
    try:
        response = requests.get(runtime.ollama_tags_url, timeout=1)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    models = []
    for model in data.get("models", []):
        name = model.get("name") or model.get("model")
        if name:
            models.append(name)
    return models


def is_ollama_running(runtime: RuntimeSettings | None = None) -> bool:
    runtime = runtime or SettingsStore().get_runtime_settings()
    try:
        response = requests.get(runtime.ollama_tags_url, timeout=1)
        response.raise_for_status()
        return True
    except Exception:
        return False


def get_saved_chat_model(settings: QSettings | Any | None = None) -> str:
    store = settings or get_qsettings()
    value = store.value("chat/model", MODEL, type=str)
    return value or MODEL
