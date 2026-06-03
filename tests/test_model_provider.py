import importlib
import queue
import sys
import types
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def load_model_provider(monkeypatch):
    sys.modules.pop("model_provider", None)
    bedrock_mod = types.ModuleType("bedrock_client")
    bedrock_mod.stream_bedrock = lambda *a, **k: None
    bedrock_mod.generate_bedrock_chat_title = lambda *a, **k: ""
    ollama_mod = types.ModuleType("ollama_client")
    ollama_mod.stream_ollama = lambda *a, **k: None
    ollama_mod.generate_chat_title = lambda *a, **k: ""
    ollama_mod.warm_up_model = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "bedrock_client", bedrock_mod)
    monkeypatch.setitem(sys.modules, "ollama_client", ollama_mod)
    import model_provider
    return importlib.reload(model_provider)


def test_bedrock_model_helpers(monkeypatch):
    provider = load_model_provider(monkeypatch)
    key = provider.bedrock_model_key("model-a")
    assert key == "bedrock:model-a"
    assert provider.is_bedrock_model(key)
    assert provider.provider_model_id(key) == "model-a"
    assert provider.display_model_name(key) == "Bedrock: model-a"
    assert provider.display_model_name("llama3") == "llama3"


def test_available_bedrock_models_requires_enabled(monkeypatch):
    provider = load_model_provider(monkeypatch)
    enabled = types.SimpleNamespace(bedrock_enabled=True, bedrock_model_ids=("a", "b"))
    disabled = types.SimpleNamespace(bedrock_enabled=False, bedrock_model_ids=("a",))
    assert provider.available_bedrock_models(enabled) == ["bedrock:a", "bedrock:b"]
    assert provider.available_bedrock_models(disabled) == []


def test_stream_model_routes_by_prefix(monkeypatch):
    provider = load_model_provider(monkeypatch)
    seen = {}

    def fake_bedrock(messages, out_q, model_id=None, stop_event=None):
        seen["bedrock"] = (messages, model_id, stop_event)
        out_q.put(None)

    def fake_ollama(messages, out_q, model=None, stop_event=None):
        seen["ollama"] = (messages, model, stop_event)
        out_q.put(None)

    monkeypatch.setattr(provider, "stream_bedrock", fake_bedrock)
    monkeypatch.setattr(provider, "stream_ollama", fake_ollama)
    q = queue.Queue()
    provider.stream_model([{"role": "user", "content": "u"}], q, model="bedrock:model-a")
    assert seen["bedrock"][1] == "model-a"
    assert q.get() is None

    provider.stream_model([], q, model="llama3")
    assert seen["ollama"][1] == "llama3"
    assert q.get() is None
