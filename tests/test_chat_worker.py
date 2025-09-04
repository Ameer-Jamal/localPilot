import importlib
import sys
import types

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
    monkeypatch.setitem(sys.modules, 'requests', types.SimpleNamespace(get=lambda *a, **k: None))
    import workers.chat_worker as cw
    return importlib.reload(cw)


def test_build_prompt(monkeypatch):
    cw = load_worker(monkeypatch)
    messages = [
        {'role': 'system', 'content': 'sys'},
        {'role': 'user', 'content': 'u'},
        {'role': 'assistant', 'content': 'a'},
    ]
    worker = cw.ChatWorker(messages, model='x')
    prompt = worker._build_prompt()
    assert 'sys' in prompt
    assert 'user: u' in prompt
    assert prompt.strip().endswith('assistant:')
