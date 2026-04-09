import importlib
import sys
import types
import queue
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


def load_client(monkeypatch, post_impl):
    dummy = types.SimpleNamespace(post=post_impl)
    monkeypatch.setitem(sys.modules, 'requests', dummy)
    settings_mod = types.ModuleType('settings_store')

    class DummySettingsStore:
        def get_runtime_settings(self):
            return types.SimpleNamespace(
                ollama_chat_url='http://localhost:11434/api/chat',
                temperature=0.2,
                num_ctx=16384,
                keep_alive='10m',
            )

    settings_mod.SettingsStore = DummySettingsStore
    monkeypatch.setitem(sys.modules, 'settings_store', settings_mod)
    import ollama_client
    return importlib.reload(ollama_client)


class DummyResponse:
    def __init__(self, lines, payload=None):
        self.lines = lines
        self.payload = payload or {}
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass
    def iter_lines(self, decode_unicode=True):
        for l in self.lines:
            yield l
    def raise_for_status(self):
        pass
    def json(self):
        return self.payload


def test_stream_success(monkeypatch):
    seen = {}

    def fake_post(*a, **k):
        seen.update(k)
        return DummyResponse([
            '{"model":"m","message":{"role":"assistant","content":"hi"}}',
            '{"message":{"role":"assistant","content":" there"}}',
        ])
    client = load_client(monkeypatch, fake_post)
    q = queue.Queue()
    client.stream_ollama([{'role': 'user', 'content': 'prompt'}], q, model='m')
    assert seen["json"]["messages"] == [{'role': 'user', 'content': 'prompt'}]
    assert q.get() == 'hi'
    assert q.get() == ' there'
    assert q.get() is None


def test_stream_no_model(monkeypatch):
    client = load_client(monkeypatch, lambda *a, **k: DummyResponse([]))
    q = queue.Queue()
    client.stream_ollama([{'role': 'user', 'content': 'prompt'}], q, model='')
    assert q.get().startswith('\n[Error]')
    assert q.get() is None


def test_stream_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('fail')
    client = load_client(monkeypatch, boom)
    q = queue.Queue()
    client.stream_ollama([{'role': 'user', 'content': 'p'}], q, model='x')
    first = q.get()
    assert first.startswith('\n[Error]')
    assert q.get() is None


def test_build_title_messages_keeps_recent_non_system_context(monkeypatch):
    client = load_client(monkeypatch, lambda *a, **k: DummyResponse([]))
    messages = [
        {'role': 'system', 'content': 'sys'},
        {'role': 'user', 'content': 'first'},
        {'role': 'assistant', 'content': 'second'},
        {'role': 'user', 'content': 'third'},
    ]
    built = client.build_title_messages(messages, file_name='demo.py')
    assert built[0]['role'] == 'system'
    assert 'demo.py' in built[0]['content']
    assert '2 to 4 words' in built[0]['content']
    assert [msg['content'] for msg in built[1:]] == ['second', 'third']


def test_generate_chat_title_sends_non_streaming_request(monkeypatch):
    seen = {}

    def fake_post(*a, **k):
        seen.update(k)
        return DummyResponse([], payload={'message': {'content': '"Refactor Session Widget"' }})

    client = load_client(monkeypatch, fake_post)
    title = client.generate_chat_title(
        [{'role': 'user', 'content': 'Help me refactor the session widget render flow'}],
        model='m',
        file_name='session_widget.py',
    )
    assert title == 'Refactor Session Widget'
    assert seen['json']['stream'] is False
    assert seen['json']['messages'][0]['role'] == 'system'
    assert seen['json']['options']['num_ctx'] == 1024


def test_normalize_chat_title_limits_noise(monkeypatch):
    client = load_client(monkeypatch, lambda *a, **k: DummyResponse([]))
    assert client.normalize_chat_title('  "Investigate renderer jitter: detailed follow-up plan"  ') == 'Investigate renderer jitter'
