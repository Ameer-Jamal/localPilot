import importlib
import sys
import types
import threading
import time

import pytest


def load_worker(monkeypatch):
    sys.modules.pop('workers.chat_worker', None)
    pyside6 = types.ModuleType('PySide6')
    qtcore = types.ModuleType('PySide6.QtCore')

    class DummySignal:
        def __init__(self, *a, **k):
            pass
        def connect(self, *a, **k):
            pass
        def emit(self, *a, **k):
            pass
    qtcore.QThread = object
    qtcore.Signal = lambda *a, **k: DummySignal()

    monkeypatch.setitem(sys.modules, 'PySide6', pyside6)
    monkeypatch.setitem(sys.modules, 'PySide6.QtCore', qtcore)
    monkeypatch.setitem(sys.modules, 'requests', types.SimpleNamespace(post=lambda *a, **k: None))
    settings_mod = types.ModuleType('settings_store')
    settings_mod.SettingsStore = lambda: types.SimpleNamespace(
        get_runtime_settings=lambda: types.SimpleNamespace(
            ollama_chat_url='http://localhost:11434/api/chat',
            temperature=0.2,
            num_ctx=16384,
            keep_alive='10m',
        )
    )
    monkeypatch.setitem(sys.modules, 'settings_store', settings_mod)
    import workers.chat_worker as cw
    return importlib.reload(cw)


def load_worker_thread(monkeypatch, stream_impl):
    sys.modules.pop('workers.chat_worker', None)
    pyside6 = types.ModuleType('PySide6')
    qtcore = types.ModuleType('PySide6.QtCore')

    class DummySignal:
        def __init__(self):
            self._cbs = []
        def connect(self, cb):
            self._cbs.append(cb)
        def emit(self, *a, **k):
            for cb in list(self._cbs):
                cb(*a, **k)

    class DummyQThread(threading.Thread):
        def __init__(self, *a, **k):
            super().__init__()
        def isRunning(self):
            return self.is_alive()
        def wait(self, msecs=None):
            self.join(None if msecs is None else msecs / 1000)

    qtcore.QThread = DummyQThread
    qtcore.Signal = lambda *a, **k: DummySignal()

    monkeypatch.setitem(sys.modules, 'PySide6', pyside6)
    monkeypatch.setitem(sys.modules, 'PySide6.QtCore', qtcore)
    monkeypatch.setitem(sys.modules, 'requests', types.SimpleNamespace(post=lambda *a, **k: None))
    settings_mod = types.ModuleType('settings_store')
    settings_mod.SettingsStore = lambda: types.SimpleNamespace(
        get_runtime_settings=lambda: types.SimpleNamespace(
            ollama_chat_url='http://localhost:11434/api/chat',
            temperature=0.2,
            num_ctx=16384,
            keep_alive='10m',
        )
    )
    monkeypatch.setitem(sys.modules, 'settings_store', settings_mod)
    import workers.chat_worker as cw
    cw = importlib.reload(cw)
    monkeypatch.setattr(cw, 'stream_ollama', stream_impl)
    return cw


def test_worker_passes_structured_messages(monkeypatch):
    seen = {}

    def fake_stream(messages, out_q, model=None, stop_event=None):
        seen["messages"] = messages
        seen["model"] = model
        out_q.put(None)

    cw = load_worker_thread(monkeypatch, fake_stream)
    messages = [
        {'role': 'system', 'content': 'sys'},
        {'role': 'user', 'content': 'u'},
        {'role': 'assistant', 'content': 'a'},
    ]
    worker = cw.ChatWorker(messages, model='x')
    worker.start()
    worker.wait(500)
    assert seen["messages"] == messages
    assert seen["model"] == "x"


def test_worker_stop(monkeypatch):
    def fake_stream(prompt, out_q, model=None, stop_event=None):
        out_q.put('hi')
        while not (stop_event and stop_event.is_set()):
            time.sleep(0.01)
        out_q.put(None)

    cw = load_worker_thread(monkeypatch, fake_stream)
    worker = cw.ChatWorker([], model='x')
    chunks = []
    worker.chunk.connect(chunks.append)
    worker.start()
    time.sleep(0.05)
    worker.stop()
    worker.wait(500)
    assert chunks == ['hi']
