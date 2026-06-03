import importlib
import sys
import types
from collections import OrderedDict
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


class FakeSettings:
    def __init__(self, *args, **kwargs):
        self.data = {}

    def value(self, key, default=None, type=None):
        value = self.data.get(key, default)
        if type is not None and value is not None:
            try:
                return type(value)
            except Exception:
                return value
        return value

    def set_value(self, key, value):
        self.data[key] = value

    def remove(self, key):
        self.data.pop(key, None)

    def __getattr__(self, name):
        if name == "setValue":
            return self.set_value
        raise AttributeError(name)


def load_settings_store(monkeypatch):
    sys.modules.pop("settings_store", None)
    pyside6 = types.ModuleType("PySide6")
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QSettings = FakeSettings
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    import settings_store
    return importlib.reload(settings_store)


def test_normalize_ollama_base_url_adds_api(monkeypatch):
    store = load_settings_store(monkeypatch)
    assert store.normalize_ollama_base_url("http://localhost:11434") == "http://localhost:11434/api"
    assert store.normalize_ollama_base_url("http://localhost:11434/api/") == "http://localhost:11434/api"


def test_normalize_quick_prompts_dedupes_and_drops_invalid(monkeypatch):
    store = load_settings_store(monkeypatch)
    normalized = store.normalize_quick_prompts([
        {"name": "Explain", "prompt": "One"},
        {"name": "Explain", "prompt": "Two"},
        {"name": "", "prompt": "skip"},
        {"name": "Valid", "prompt": ""},
    ])
    assert normalized == [
        {"name": "Explain", "prompt": "One"},
        {"name": "Explain (2)", "prompt": "Two"},
    ]


def test_settings_store_round_trips_runtime_and_prompts(monkeypatch):
    module = load_settings_store(monkeypatch)
    fake = FakeSettings()
    store = module.SettingsStore(fake)
    runtime = module.RuntimeSettings(
        ollama_base_url="http://host:11434",
        temperature=0.5,
        num_ctx=32000,
        keep_alive="20m",
        default_pull_model="llama3.1",
        serve_num_parallel=4,
        serve_max_loaded_models=3,
        serve_flash_attention=False,
        serve_kv_cache_type="f16",
        bedrock_enabled=True,
        bedrock_aws_profile="dev",
        bedrock_aws_region="us-west-2",
        bedrock_model_ids=("model-a", "model-b"),
        bedrock_max_tokens=8192,
    )
    store.save_runtime_settings(runtime)
    store.save_quick_prompts([
        {"name": "Explain", "prompt": "Explain it"},
        {"name": "Fix", "prompt": "Fix it"},
    ])

    loaded_runtime = store.get_runtime_settings()
    assert loaded_runtime.ollama_base_url == "http://host:11434/api"
    assert loaded_runtime.temperature == pytest.approx(0.5)
    assert loaded_runtime.num_ctx == 32000
    assert loaded_runtime.keep_alive == "20m"
    assert loaded_runtime.default_pull_model == "llama3.1"
    assert loaded_runtime.serve_env["OLLAMA_FLASH_ATTENTION"] == "0"
    assert loaded_runtime.bedrock_enabled is True
    assert loaded_runtime.bedrock_aws_profile == "dev"
    assert loaded_runtime.bedrock_aws_region == "us-west-2"
    assert loaded_runtime.bedrock_model_ids == ("model-a", "model-b")
    assert loaded_runtime.bedrock_max_tokens == 8192
    assert store.get_quick_prompts() == OrderedDict([
        ("Explain", "Explain it"),
        ("Fix", "Fix it"),
    ])


def test_settings_store_defaults_when_empty(monkeypatch):
    module = load_settings_store(monkeypatch)
    store = module.SettingsStore(FakeSettings())
    prompts = store.get_quick_prompts()
    assert prompts == module.DEFAULT_QUICK_PROMPTS
    assert store.get_confirm_before_closing_tabs() is True
    defaults = module.default_runtime_settings()
    runtime = store.get_runtime_settings()
    assert runtime == defaults
    assert runtime.bedrock_enabled is False
    assert runtime.bedrock_model_ids == tuple(module.DEFAULT_BEDROCK_MODEL_IDS)
    assert runtime.bedrock_model_ids[0] == "global.anthropic.claude-sonnet-4-6"


def test_normalize_bedrock_model_ids_dedupes_commas_and_lines(monkeypatch):
    module = load_settings_store(monkeypatch)
    assert module.normalize_bedrock_model_ids("a, b\na\n\nc") == ("a", "b", "c")


def test_fetch_ollama_models_prefers_env(monkeypatch):
    module = load_settings_store(monkeypatch)
    monkeypatch.setenv("MODEL_LIST", "a, b")
    assert module.fetch_ollama_models() == ["a", "b"]


def test_settings_store_round_trips_close_confirmation(monkeypatch):
    module = load_settings_store(monkeypatch)
    fake = FakeSettings()
    store = module.SettingsStore(fake)
    store.set_confirm_before_closing_tabs(False)
    assert store.get_confirm_before_closing_tabs() is False


def test_settings_store_round_trips_history_settings(monkeypatch):
    module = load_settings_store(monkeypatch)
    fake = FakeSettings()
    store = module.SettingsStore(fake)
    history = module.HistorySettings(
        keep_forever=False,
        delete_closed_after_days=14,
        max_sessions=123,
    )
    store.save_history_settings(history)
    loaded = store.get_history_settings()
    assert loaded.keep_forever is False
    assert loaded.delete_closed_after_days == 14
    assert loaded.max_sessions == 123
