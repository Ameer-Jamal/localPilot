import importlib
import sys
import types
import queue

import pytest


def load_client(monkeypatch, post_impl):
    dummy = types.SimpleNamespace(post=post_impl)
    monkeypatch.setitem(sys.modules, 'requests', dummy)
    import ollama_client
    return importlib.reload(ollama_client)


class DummyResponse:
    def __init__(self, lines):
        self.lines = lines
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass
    def iter_lines(self, decode_unicode=True):
        for l in self.lines:
            yield l
    def raise_for_status(self):
        pass


def test_stream_success(monkeypatch):
    def fake_post(*a, **k):
        return DummyResponse(['{"model":"m","response":"hi"}', '{"response":" there"}'])
    client = load_client(monkeypatch, fake_post)
    q = queue.Queue()
    client.stream_ollama('prompt', q, model='m')
    assert q.get() == 'hi'
    assert q.get() == ' there'
    assert q.get() is None


def test_stream_no_model(monkeypatch):
    client = load_client(monkeypatch, lambda *a, **k: DummyResponse([]))
    q = queue.Queue()
    client.stream_ollama('prompt', q, model='')
    assert q.get().startswith('\n[Error]')
    assert q.get() is None


def test_stream_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('fail')
    client = load_client(monkeypatch, boom)
    q = queue.Queue()
    client.stream_ollama('p', q, model='x')
    first = q.get()
    assert first.startswith('\n[Error]')
    assert q.get() is None
